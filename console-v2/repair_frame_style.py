"""Bring one action frame back to its clip's line weight and palette.

Only global, reversible adjustments: unsharp until the frame's edge strength
matches the clip median, then a Lab mean offset onto the same median. No
geometry, no repaint.
"""
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from skimage.color import lab2rgb, rgb2lab

ROOT = Path(__file__).resolve().parent


def measure(image):
    a = np.asarray(image).astype(np.float32)
    alpha = a[:, :, 3] / 255.0
    solid = alpha > 0.78
    rgb = a[:, :, :3]
    lab = rgb2lab(rgb / 255)
    lum = (rgb * alpha[..., None] + 240 * (1 - alpha[..., None])).mean(2)
    gy, gx = np.gradient(lum)
    return {
        'edge': float(np.sqrt(gy ** 2 + gx ** 2)[solid].mean()),
        'L': float(lab[:, :, 0][solid].mean()),
        'a': float(lab[:, :, 1][solid].mean()),
        'b': float(lab[:, :, 2][solid].mean()),
    }


def clip_median(action, skip):
    folder = ROOT / 'assets/actions' / action
    stats = []
    for path in sorted(folder.glob('[0-9][0-9].png')):
        if path.name in skip:
            continue
        stats.append(measure(Image.open(path).convert('RGBA')))
    return {key: statistics.median(item[key] for item in stats) for key in ('edge', 'L', 'a', 'b')}


def repair(path, target):
    image = Image.open(path).convert('RGBA')
    best, best_percent = None, 0
    for percent in range(0, 260, 10):
        sharp = image if percent == 0 else image.filter(
            ImageFilter.UnsharpMask(radius=1.0, percent=percent, threshold=2))
        score = abs(measure(sharp)['edge'] - target['edge'])
        if best is None or score < best[0]:
            best, best_percent = (score, sharp), percent
        if measure(sharp)['edge'] > target['edge']:
            break
    sharp = best[1]
    a = np.asarray(sharp).astype(np.float32) / 255
    solid = a[:, :, 3] > 0.4
    lab = rgb2lab(a[:, :, :3])
    current = lab[solid].mean(0)
    delta = np.array([target['L'] - current[0], target['a'] - current[1], target['b'] - current[2]])
    out = np.clip(lab2rgb(lab + delta), 0, 1)
    result = Image.fromarray(np.rint(np.dstack([out, a[:, :, 3]]) * 255).astype(np.uint8))
    return result, best_percent, measure(result)


def main():
    action, frame = sys.argv[1], sys.argv[2]
    path = ROOT / 'assets/actions' / action / f'{frame}.png'
    target = clip_median(action, {path.name})
    print('clip median', {k: round(v, 2) for k, v in target.items()})
    before = measure(Image.open(path).convert('RGBA'))
    print('before', {k: round(v, 2) for k, v in before.items()})
    fixed, percent, after = repair(path, target)
    fixed.save(path)
    print('after ', {k: round(v, 2) for k, v in after.items()}, 'unsharp', percent)


if __name__ == '__main__':
    main()
