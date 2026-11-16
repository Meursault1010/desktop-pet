"""Rebuild 浅鞠行礼's lower body so the feet stop crossing and sinking.

The six source cells drew the feet three different ways (together, one turned
90°, crossed at the ankle) and at different sizes, so the optical-flow samples
melted them into diagonal, flattened shoes that also dropped below the floor
line. Here the lower legs and shoes of the neutral cell become the only master:
every frame gets the same two shoes, one parked half a step behind the other,
soles on the 250 line, with the stocking stretched to whatever gap the skirt
leaves. The upper body is untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/actions'
WORK = ROOT / 'action-work/curtsy-feet'
ACTION = 'curtsy'
FLOOR_Y = 250
LOCK_CENTER = 128.5
LOCK_FLOOR = 250
FAR_LIFT = 5
FAR_SCALE = 1.0
NEAR_SHIFT, FAR_SHIFT = 7, -10

_spec = importlib.util.spec_from_file_location(
    'yuki_measure', Path(__file__).resolve().parents[1] / '.qoder/skills/yuki-motion/scripts/measure.py')
yuki_measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yuki_measure)


SOURCE = WORK / 'source'


def load(index):
    base = SOURCE if SOURCE.exists() else ASSETS / ACTION
    return np.asarray(Image.open(base / f'{index + 1:02d}.png').convert('RGBA'))


def hem_cut(frame):
    """Lowest row that is still skirt-wide; everything below it is legs and shoes."""
    alpha = frame[:, :, 3]
    for y in range(255, 180, -1):
        xs = np.nonzero(alpha[y] > 40)[0]
        if len(xs) and xs.max() - xs.min() + 1 >= 45:
            return y
    return 200


def feet_span(frame, cut):
    alpha = frame[:, :, 3]
    ys, xs = np.nonzero(alpha[cut + 1:] > 40)
    return int(xs.min()), int(xs.max())


def paste(dst, sprite, x, y):
    h, w = sprite.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(256, x + w), min(256, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    src = sprite[sy0:sy0 + (y1 - y0), sx0:sx0 + (x1 - x0)]
    dst_rgb = dst[y0:y1, x0:x1, :3].astype(np.float32)
    dst_alpha = dst[y0:y1, x0:x1, 3:4].astype(np.float32) / 255.0
    src_rgb = src[:, :, :3].astype(np.float32)
    src_alpha = src[:, :, 3:4].astype(np.float32) / 255.0
    out_alpha = src_alpha + dst_alpha * (1 - src_alpha)
    out_rgb = (src_rgb * src_alpha + dst_rgb * dst_alpha * (1 - src_alpha)) / np.maximum(out_alpha, 1e-6)
    dst[y0:y1, x0:x1, :3] = out_rgb.clip(0, 255).astype(np.uint8)
    dst[y0:y1, x0:x1, 3:4] = (out_alpha * 255).clip(0, 255).astype(np.uint8)


class LowerBody:
    """One pair of legs and shoes, cut from the neutral frame and reused everywhere."""

    def __init__(self, base):
        cut = hem_cut(base)
        self.cut = cut
        bottom = int(np.nonzero(base[:, :, 3] > 40)[0].max())
        alpha = base[:, :, 3]
        ys, xs = np.nonzero(alpha[cut + 1:] > 40)
        left, right = int(xs.min()), int(xs.max())
        mid = (left + right) // 2
        # tight crops: each leg keeps its own silhouette, no shared gap column
        self.far = base[cut + 1:bottom + 1, left:mid].copy()
        self.near = base[cut + 1:bottom + 1, mid + 1:right + 2].copy()
        self.gap = mid - left
        self.stock_h = self._shoe_top(base) - (cut + 1)
        self.shoe_h = self.far.shape[0] - self.stock_h
        self.top = cut + 1

    @staticmethod
    def _shoe_top(base):
        rgb = base[:, :, :3].astype(int)
        alpha = base[:, :, 3]
        blue = (rgb[:, :, 2] - rgb[:, :, 0] > 50) & (rgb[:, :, 2] > 140) & (alpha > 200)
        rows = blue.sum(1)
        y = hem_cut(base) + 1
        # skip the dress's own blue band first: it also clears the colour test
        while y < 256 and rows[y] >= 4:
            y += 1
        while y < 256 and rows[y] < 4:
            y += 1
        return int(y)

    def sprite(self, unit, sole_y, scale, top_y):
        width = int(round(unit.shape[1] * scale))
        shoe_h = int(round(self.shoe_h * scale))
        stock_h = max(1, sole_y - shoe_h - top_y)
        stock = cv2.resize(unit[:self.stock_h], (width, stock_h), interpolation=cv2.INTER_LINEAR)
        shoe = cv2.resize(unit[self.stock_h:], (width, shoe_h), interpolation=cv2.INTER_AREA)
        return np.vstack([stock, shoe])

    def compose(self, frame):
        cut = hem_cut(frame)
        left, right = feet_span(frame, cut)
        out = frame.copy()
        out[cut + 1:, max(0, left - 10):min(256, right + 11)] = 0
        center = (left + right) / 2.0
        far = self.sprite(self.far, FLOOR_Y - FAR_LIFT, FAR_SCALE, cut + 1)
        paste(out, far, int(round(center + FAR_SHIFT - far.shape[1] / 2)), cut + 1)
        near = self.sprite(self.near, FLOOR_Y, 1.0, cut + 1)
        paste(out, near, int(round(center + NEAR_SHIFT - near.shape[1] / 2)), cut + 1)
        return out


def lock(frame):
    """Bake the marching offset into the pixels: the clip stops sliding and bobbing."""
    metrics = yuki_measure.metrics(frame)
    # align on the feet, not the bounding box: a bow moves the head and hair,
    # so bbox centring would swing the whole body sideways every frame.
    alpha = frame[:, :, 3]
    band = np.nonzero(alpha[max(0, metrics['bottom'] - 10):metrics['bottom'] + 1] > 40)[1]
    feet_cx = float(band.mean())
    dx = int(round(LOCK_CENTER - feet_cx))
    dy = int(round(LOCK_FLOOR - metrics['bottom']))
    out = np.zeros_like(frame)
    h, w = frame.shape[:2]
    sy0, sy1 = max(0, -dy), min(h, h - dy)
    sx0, sx1 = max(0, -dx), min(w, w - dx)
    out[dy + sy0:dy + sy1, dx + sx0:dx + sx1] = frame[sy0:sy1, sx0:sx1]
    return out


def build():
    frames = [load(i) for i in range(31)]
    body = LowerBody(frames[0])
    return [lock(body.compose(frame)) for frame in frames]


def preview(frames, durations):
    WORK.mkdir(parents=True, exist_ok=True)
    folder = WORK / 'frames'
    if folder.exists():
        for path in folder.glob('*.png'):
            path.unlink()
    folder.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        Image.fromarray(frame).save(folder / f'{index + 1:02d}.png')
    images = []
    for frame in frames:
        bg = Image.new('RGB', (256, 256), '#303b4c')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    images[0].save(WORK / 'preview.gif', save_all=True, append_images=images[1:], duration=durations, loop=0)
    cols, cell = 8, 150
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 18)), '#303b4c')
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x, y = index % cols * cell, index // cols * (cell + 18)
        thumb = Image.fromarray(frame).resize((cell, cell), Image.LANCZOS)
        bg = Image.new('RGB', (cell, cell), '#303b4c')
        bg.paste(thumb, (0, 0), thumb)
        sheet.paste(bg, (x, y + 12))
        draw.text((x + 3, y + 1), f'{index + 1:02d}', fill='#dbeafe')
    sheet.save(WORK / 'contact.jpg', quality=94)
    failing, bottoms, centres = [], [], []
    for index, frame in enumerate(frames):
        metrics = yuki_measure.metrics(frame)
        bottoms.append(metrics['bottom'])
        centres.append(metrics['center_x'])
        bad = [f'{key}={metrics[key]}' for key, limits in yuki_measure.ANCHOR.items()
               if not limits[0] <= metrics[key] <= limits[1]]
        if bad:
            failing.append((index + 1, bad))
    report = dict(frames=len(frames), duration_ms=sum(durations), durations=durations,
                  bottom_min=min(bottoms), bottom_max=max(bottoms),
                  centre_min=min(centres), centre_max=max(centres),
                  anchor_failures=failing[:10], failures=len(failing))
    (WORK / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    catalog = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
    durations = list(next(item for item in catalog if item['id'] == ACTION)['durations'])
    frames = build()
    report = preview(frames, durations)
    print(json.dumps(report, ensure_ascii=False))
    if args.apply:
        raise SystemExit('apply handled by action-work/curtsy-feet/publish.py')


if __name__ == '__main__':
    main()
