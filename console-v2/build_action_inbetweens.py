"""Deterministic local interpolation, with rejection diagnostics and originals intact.

No external service, image generation or runtime flow calculation. Each output
pixel comes from ONE warped endpoint; silhouettes are never double-exposed.
Run again whenever original action atlases change (hashes are recorded).
"""
import argparse
import hashlib
import json
from pathlib import Path
import random

import cv2
import numpy as np
from PIL import Image

from action_player import catalog, ground_idle_timeline, lazy_roll_timeline, pose_ref

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT/'assets/action-motion'
# Preserve the density of the reviewed preview in the shipping assets.
# At most 340ms per transition: 25 samples comfortably cover 60Hz drawing.
FRAMES, COLUMNS = 25, 5


def graph():
    pairs = set()
    for key, action in catalog().items():
        if action.get('physics_only') or action['frames'] < 2 or key == 'dragged':
            continue
        orders = [list(range(action['frames']))]
        if action.get('ground_idle'):
            orders = [ground_idle_timeline(action, random.Random(seed))[0] for seed in range(40)]
        if action.get('lazy_roll'):
            orders = [lazy_roll_timeline(action, random.Random(0))[0]]
        for order in orders:
            for left, right in zip(order, order[1:]):
                a, b = pose_ref(key, left), pose_ref(key, right)
                if a != b:
                    pairs.add((a, b))
        if action.get('lazy_roll'):
            pairs.add(((key, 11), ('prone-rest', 3)))
        elif not action.get('ground_idle'):
            pairs.add(((key, action['frames']-1), (key, action.get('loop_start', 0))))
    return sorted(pairs)


def premultiply(image):
    image = image.astype(np.float32)
    image[:, :, :3] *= image[:, :, 3:4]/255
    return image


def unpremultiply(image):
    image = image.copy()
    image[:, :, :3] = np.divide(image[:, :, :3]*255, image[:, :, 3:4],
                               out=np.zeros_like(image[:, :, :3]), where=image[:, :, 3:4] > 0)
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def gray(image):
    a = image[:, :, 3:4]/255
    return cv2.cvtColor((image[:, :, :3]*a+240*(1-a)).astype(np.uint8), cv2.COLOR_RGB2GRAY)


def difference(a, b):
    mask = np.maximum(a[:, :, 3], b[:, :, 3]) > 16
    return float(np.abs(a-b)[mask].mean()) if mask.any() else 0.


def interpolate(a, b):
    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow.setFinestScale(0)
    flow.setGradientDescentIterations(64)
    flow.setVariationalRefinementIterations(30)
    forward = flow.calc(gray(a), gray(b), None)
    backward = flow.calc(gray(b), gray(a), None)
    yy, xx = np.mgrid[:256, :256].astype(np.float32)
    pa, pb = premultiply(a), premultiply(b)
    baseline = difference(pa, pb)
    # Pull each endpoint towards the other. Choose the least discontinuous
    # ownership switch near the middle; never mix two different bodies.
    def warp(source, field, weight):
        return cv2.remap(source, xx+weight*field[:, :, 0], yy+weight*field[:, :, 1],
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    candidates = [(difference(warp(pa, backward, t), warp(pb, forward, 1-t)), t)
                  for t in (.375, .417, .458, .5, .542, .583, .625)]
    _, switch = min(candidates)
    frames = [pa]
    for index in range(1, FRAMES-1):
        t = index/(FRAMES-1)
        frames.append(warp(pa, backward, t) if t < switch else warp(pb, forward, 1-t))
    frames.append(pb)
    jump = max(difference(x, y) for x, y in zip(frames, frames[1:]))
    # A warp must actually reduce the worst temporal jump. Reject if it grows
    # the visible area enough to suggest a stretched limb or leaking edge.
    areas = [np.count_nonzero(f[:, :, 3] > 32) for f in frames]
    area_ok = max(areas) <= max(areas[0], areas[-1])*1.10
    accepted = baseline > .5 and jump < baseline*.84 and area_ok
    return [unpremultiply(f) for f in frames], {
        'accepted': bool(accepted), 'original_jump': round(baseline, 3),
        'largest_step': round(jump, 3), 'switch': switch, 'area_ok': bool(area_ok)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actions', nargs='*')
    args = parser.parse_args()
    cv2.setNumThreads(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    atlases, hashes = {}, {}
    def frame(ref):
        key, index = ref
        if key not in atlases:
            path = ROOT/'assets'/catalog()[key]['atlas']
            atlases[key] = np.array(Image.open(path).convert('RGBA'))
            hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        cols = catalog()[key]['columns']
        return atlases[key][index//cols*256:index//cols*256+256,
                            index%cols*256:index%cols*256+256].copy()
    pairs, report = {}, {}
    for n, (a, b) in enumerate(graph()):
        if args.actions and a[0] not in args.actions:
            continue
        key = f'{a[0]}:{a[1]}>{b[0]}:{b[1]}'
        frames, review = interpolate(frame(a), frame(b))
        report[key] = review
        if not review['accepted']:
            continue
        name = f'{a[0]}_{a[1]}--{b[0]}_{b[1]}.png'
        sheet = Image.new('RGBA', (256*COLUMNS, 256*((FRAMES+COLUMNS-1)//COLUMNS)))
        for i, image in enumerate(frames):
            sheet.paste(Image.fromarray(image), (i%COLUMNS*256, i//COLUMNS*256))
        sheet.save(OUTPUT/name, optimize=True)
        pairs[key] = {'file': name, 'frames': FRAMES, 'columns': COLUMNS}
        if n % 20 == 0:
            print(f'{n}: {key}', flush=True)
    payload = {'version': 1, 'method': 'single-source-bidirectional-warp',
               'source_sha256': hashes, 'pairs': pairs}
    (OUTPUT/'manifest.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    (OUTPUT/'quality-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Accepted {len(pairs)}/{len(report)} transitions', flush=True)


if __name__ == '__main__':
    main()
