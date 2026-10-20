"""Measure per-frame canvas drift and publish smooth runtime alignment offsets."""
import argparse
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT/'assets/actions'
OUTPUT = ASSETS/'frame-alignment.json'
EXCLUDED = {'leap', 'dragged'}
PRESERVE_VERTICAL = {'celebrate'}
THRESHOLD = 32


def frame_bounds(path):
    with Image.open(path) as image:
        return image_bounds(image)


def image_bounds(image):
    alpha = image.convert('RGBA').getchannel('A')
    return alpha.point(lambda value: 255 if value >= THRESHOLD else 0).getbbox()


def build():
    entries = json.loads((ASSETS/'catalog.json').read_text(encoding='utf-8'))
    actions = {}
    for entry in entries:
        if (entry.get('origin') != 'generated' or entry['frames'] < 2
                or entry.get('ground_idle') or entry.get('lazy_roll')
                or entry.get('physics_only') or entry['id'] in EXCLUDED):
            continue
        key = entry['id']
        boxes = [frame_bounds(ASSETS/key/f'{index+1:02d}.png')
                 for index in range(entry['frames'])]
        if any(box is None for box in boxes):
            raise ValueError(f'Empty frame in {key}')
        centers = sorted((box[0]+box[2])/2 for box in boxes)
        anchor_x = (centers[(len(centers)-1)//2]+centers[len(centers)//2])/2
        floor_y = max(box[3] for box in boxes)
        offsets = [[round(anchor_x-(box[0]+box[2])/2, 3),
                    0. if key in PRESERVE_VERTICAL else round(floor_y-box[3], 3)]
                   for box in boxes]
        actions[key] = dict(anchor_x=round(anchor_x, 3), floor_y=floor_y,
                            preserve_vertical=key in PRESERVE_VERTICAL, offsets=offsets)
    # Flow warps can follow a non-linear path even when their endpoints are
    # registered. Measure each shipped subframe as well; interpolating only
    # endpoint offsets leaves a residual jump around its ownership switch.
    transitions = {}
    motion = ROOT/'assets/action-motion'
    manifest = motion/'manifest.json'
    pairs = json.loads(manifest.read_text(encoding='utf-8'))['pairs'] if manifest.exists() else {}
    for pair, entry in pairs.items():
        before, after = (ref.rsplit(':', 1) for ref in pair.split('>'))
        if before[0] not in actions or after[0] not in actions:
            continue
        start, end = actions[before[0]], actions[after[0]]
        offsets = []
        with Image.open(motion/entry['file']) as strip:
            for index in range(entry['frames']):
                x, y = index % entry['columns']*256, index//entry['columns']*256
                box = image_bounds(strip.crop((x, y, x+256, y+256)))
                if box is None:
                    raise ValueError(f'Empty subframe in {pair}:{index}')
                t = index/(entry['frames']-1)
                anchor_x = start['anchor_x']+(end['anchor_x']-start['anchor_x'])*t
                floor_y = start['floor_y']+(end['floor_y']-start['floor_y'])*t
                preserve_y = start['preserve_vertical'] or end['preserve_vertical']
                offsets.append([round(anchor_x-(box[0]+box[2])/2, 3),
                                0. if preserve_y else round(floor_y-box[3], 3)])
        transitions[pair] = offsets
    return dict(version=2, method='visible-bounds-center-and-ground-line',
                threshold=THRESHOLD, actions=actions, transitions=transitions)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    payload = build()
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)+'\n'
    if args.write:
        OUTPUT.write_text(encoded, encoding='utf-8')
    print(json.dumps({key:dict(frames=len(value['offsets']),
                               max_offset=max(max(abs(dx),abs(dy)) for dx,dy in value['offsets']))
                      for key,value in payload['actions'].items()},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
