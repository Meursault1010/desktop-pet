"""Flag action frames whose line weight or palette drifts from their own clip.

Every frame is compared with the median of its own action (so pose, lean and
prop differences do not count) and with the idle style reference. Output is a
list of outlier frames worth touching up or redrawing.
"""
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.color import rgb2lab

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'assets/actions/blink/01.png'


def measure(path):
    a = np.asarray(Image.open(path).convert('RGBA')).astype(np.float32)
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


def main():
    only = sys.argv[1:]
    catalog = json.loads((ROOT / 'assets/actions/catalog.json').read_text(encoding='utf-8'))
    ref = measure(REFERENCE)
    print(f'idle reference: edge {ref["edge"]:.2f} L {ref["L"]:.1f} a {ref["a"]:.2f} b {ref["b"]:.2f}')
    flagged = []
    for entry in catalog:
        action = entry['id']
        if only and action not in only:
            continue
        if entry.get('physics_only') or action in ('dragged', 'music-waltz'):
            continue
        folder = ROOT / 'assets/actions' / action
        frames = sorted(folder.glob('[0-9][0-9].png'))
        if len(frames) < 3:
            continue
        data = [measure(path) for path in frames]
        med = {key: statistics.median(item[key] for item in data) for key in ('edge', 'L', 'a', 'b')}
        for index, item in enumerate(data, 1):
            edge_dev = (item['edge'] - med['edge']) / max(0.1, med['edge'])
            colour_dev = max(abs(item['L'] - med['L']) / 2.0,
                             abs(item['a'] - med['a']) / 1.0,
                             abs(item['b'] - med['b']) / 1.5)
            if abs(edge_dev) > 0.14 or colour_dev > 1.4:
                flagged.append((action, index, item, med, edge_dev, colour_dev))
    print(f'\nflagged frames: {len(flagged)}')
    for action, index, item, med, edge_dev, colour_dev in sorted(flagged, key=lambda row: -abs(row[4])):
        print(f'  {action:<16} f{index:<3} edge {item["edge"]:5.2f} (clip {med["edge"]:5.2f}, {edge_dev:+5.0%}) '
              f'L {item["L"]:5.1f} a {item["a"]:5.2f} b {item["b"]:6.2f} colour-dev {colour_dev:.1f}')


if __name__ == '__main__':
    main()
