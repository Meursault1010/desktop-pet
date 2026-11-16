"""Compare every action frame against the idle style reference.

Reports per-frame style distances so frames drawn in a different hand (different
line weight, palette, face or hair) stand out from the rest of the clip.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.color import rgb2lab

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT / 'assets/actions/blink/01.png'


def features(path):
    image = Image.open(path).convert('RGBA')
    a = np.asarray(image).astype(np.float32)
    alpha = a[:, :, 3] / 255.0
    solid = alpha > 0.78
    rgb = a[:, :, :3]
    lab = rgb2lab(rgb / 255)
    ys, xs = np.where(alpha > 0.24)
    top, bottom = int(ys.min()), int(ys.max())
    height = bottom - top + 1
    lum = (rgb * alpha[..., None] + 240 * (1 - alpha[..., None])).mean(2)
    gy, gx = np.gradient(lum)
    iris = ((np.arange(256)[:, None] >= top + 0.15 * height)
            & (np.arange(256)[:, None] <= top + 0.45 * height)
            & (alpha > 0.6) & ((rgb[:, :, 2] - rgb[:, :, 0]) > 55)
            & (rgb[:, :, 2] > 110) & (rgb[:, :, 0] < 150))
    labels, count = ndimage.label(iris)
    iris_px, iris_rgb = 0, None
    if count:
        sizes = ndimage.sum(iris, labels, np.arange(1, count + 1))
        keep = [i + 1 for i, s in enumerate(sizes) if s > 25]
        iris_px = int(sum(sizes[i - 1] for i in keep))
        if keep:
            mask = np.isin(labels, keep)
            iris_rgb = [round(float(v)) for v in rgb[mask].mean(0)]
    band = (np.arange(256)[:, None] >= top) & (np.arange(256)[:, None] <= top + 0.30 * height)
    ys2, xs2 = np.where(solid & band)
    head = float((xs2.max() - xs2.min() + 1) / height) if len(xs2) else 0.0
    return {
        'L': round(float(lab[:, :, 0][solid].mean()), 2),
        'Lsd': round(float(lab[:, :, 0][solid].std()), 2),
        'a': round(float(lab[:, :, 1][solid].mean()), 2),
        'b': round(float(lab[:, :, 2][solid].mean()), 2),
        'edge': round(float(np.sqrt(gy ** 2 + gx ** 2)[solid].mean()), 2),
        'iris': iris_px,
        'iris_rgb': iris_rgb,
        'head': round(head, 3),
        'h': height,
    }


def distance(one, ref, scale):
    parts = {
        'L': abs(one['L'] - ref['L']) / 2.0,
        'a': abs(one['a'] - ref['a']) / 1.0,
        'b': abs(one['b'] - ref['b']) / 1.5,
        'edge': abs(one['edge'] - ref['edge']) / max(0.5, ref['edge'] * 0.12),
        'head': abs(one['head'] - ref['head']) / max(0.01, ref['head'] * 0.08),
        'iris': abs(one['iris'] - ref['iris']) / max(20.0, ref['iris'] * 0.28),
    }
    if one['iris_rgb'] and ref['iris_rgb']:
        parts['iris_colour'] = float(np.abs(np.array(one['iris_rgb']) - np.array(ref['iris_rgb'])).mean()) / 18.0
    for key in parts:
        parts[key] *= scale.get(key, 1.0)
    return parts


def main():
    action = sys.argv[1]
    catalog = json.loads((ROOT / 'assets/actions/catalog.json').read_text(encoding='utf-8'))
    entry = next(item for item in catalog if item['id'] == action)
    ref = features(REFERENCE)
    print(f'reference {REFERENCE.name}: {json.dumps(ref, ensure_ascii=False)}')
    scale = {'L': 1.0, 'a': 1.0, 'b': 1.0, 'edge': 1.0, 'head': 1.0, 'iris': 1.0, 'iris_colour': 1.0}
    rows = []
    for index in range(1, entry['frames'] + 1):
        path = ROOT / 'assets/actions' / action / f'{index:02d}.png'
        data = features(path)
        parts = distance(data, ref, scale)
        rows.append((sum(parts.values()), index, data, parts))
    rows.sort(reverse=True)
    print(f'\n{action}: {entry["frames"]} frames, ranked by style distance (worst first)')
    for total, index, data, parts in rows:
        detail = ' '.join(f'{k}={v:.1f}' for k, v in sorted(parts.items(), key=lambda kv: -kv[1])[:4])
        print(f'  f{index:>2} score {total:5.2f}  L {data["L"]:5.1f} edge {data["edge"]:4.2f} '
              f'iris {data["iris"]:>3} head {data["head"]:.3f} h {data["h"]:>3} | {detail}')


if __name__ == '__main__':
    main()
