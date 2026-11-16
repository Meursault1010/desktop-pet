"""Lock the side-saddle leg swing in place and drop its optical-flow in-betweens.

The twelve reviewed cells were placed by their own bounding box, so the long
hair that pools to viewer left pushed every seated torso about sixteen pixels
right of the standing one: she appears to slide sideways as she sits down. The
shift is baked into the pixels here, together with the small residual slide the
cells carry between themselves, measured by masked normalised correlation
against the base seated pose.
"""
from pathlib import Path
import json

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'action-work/sit-swing-lock/source'
OUT = ROOT / 'action-work/sit-swing-lock'
COLUMNS = 4
ANCHOR_X = 128.5
FLOOR_Y = 250

# Published frame -> authored keyframe (1-based) of the twelve-cell sheet.
def keyframe(index):
    if index <= 3:
        return index
    if index <= 27:
        return 4 + (index - 4) % 6
    return index - 18


# Horizontal correction per keyframe: the seated group is pulled back over the
# spot she stood on, then each cell is registered onto the base seated pose.
GROUP_SHIFT = -16
REGISTER = {1: 0, 2: 0, 3: 5, 4: 0, 5: 0, 6: 0, 7: 1, 8: -4, 9: -3,
            10: 0, 11: 0, 12: 0}


def shift(frame, dx):
    canvas = Image.new('RGBA', (256, 256))
    canvas.paste(frame, (dx, 0))
    return canvas


def measure(image):
    alpha = image.getchannel('A').point(lambda value: 255 if value >= 32 else 0)
    box = alpha.getbbox()
    grid = np.asarray(alpha) > 32
    ys, xs = np.nonzero(grid)
    height = box[3] - box[1] + 1
    head = ys < box[1] + int(height * .22)
    shoulder = (ys >= box[1] + int(height * .22)) & (ys < box[1] + int(height * .35))
    return {'box': box, 'bottom': box[3],
            'head_x': round(float(xs[head].mean()), 1),
            'shoulder_x': round(float(xs[shoulder].mean()), 1)}


def build():
    frames, shifts = [], {}
    for index in range(1, 31):
        key = keyframe(index)
        dx = GROUP_SHIFT + REGISTER[key] if key in range(3, 10) else 0
        frame = Image.open(SOURCE / f'{index:02d}.png').convert('RGBA')
        frames.append(shift(frame, dx))
        shifts[index] = dx
    return frames, shifts


def main():
    frames, shifts = build()
    target = OUT / 'frames'
    target.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames, start=1):
        frame.save(target / f'{index:02d}.png')

    rows = (len(frames) + COLUMNS - 1) // COLUMNS
    atlas = Image.new('RGBA', (COLUMNS * 256, rows * 256))
    for index, frame in enumerate(frames):
        atlas.paste(frame, ((index % COLUMNS) * 256, (index // COLUMNS) * 256))
    atlas.save(OUT / 'atlas.png')

    report = {'frames': len(frames), 'anchor_x': ANCHOR_X, 'floor_y': FLOOR_Y,
              'shifts': shifts,
              'metrics': [measure(frame) for frame in frames]}
    durations = json.loads((ROOT / 'assets/actions/catalog.json')
                           .read_text(encoding='utf-8'))
    durations = next(entry['durations'] for entry in durations
                     if entry['id'] == 'sit-swing')
    report['durations'] = durations
    report['duration_ms'] = sum(durations)
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                     encoding='utf-8')

    previews = []
    for frame in frames:
        background = Image.new('RGB', (256, 256), '#24334a')
        background.paste(frame, mask=frame.getchannel('A'))
        previews.append(background)
    previews[0].save(OUT / 'preview.gif', save_all=True, append_images=previews[1:],
                     duration=durations, loop=0)

    picks = (1, 2, 3, 4, 5, 6, 7, 8, 9, 27, 28, 29)
    sheet = Image.new('RGB', (4 * (256 + 4), ((len(picks) + 3) // 4) * (256 + 4)), '#101010')
    for position, index in enumerate(picks):
        card = previews[index - 1].copy()
        draw = ImageDraw.Draw(card)
        draw.line([(ANCHOR_X, 0), (ANCHOR_X, 255)], fill=(255, 120, 120))
        draw.text((6, 6), f'{index:02d}', fill=(240, 240, 240))
        sheet.paste(card, ((position % 4) * (256 + 4), (position // 4) * (256 + 4)))
    sheet.save(OUT / 'contact.jpg', quality=90)
    print(f'built {len(frames)} frames, {report["duration_ms"]} ms')
    for index, entry in enumerate(report['metrics'], start=1):
        print(f'{index:02d} box={entry["box"]} bottom={entry["bottom"]} '
              f'head_x={entry["head_x"]} shoulder_x={entry["shoulder_x"]}')


if __name__ == '__main__':
    main()
