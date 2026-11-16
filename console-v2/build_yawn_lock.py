"""Pin 打哈欠 to the floor and centre without touching a single pixel value.

The shipped clip was authored across six free-standing generations: the sprite
slides ±26px sideways and, from frame 10 on, the whole character floats 14px
above the floor. `authored_motion` forces offset (0,0) at runtime, so the
alignment table never reached the pet — the drift is what plays today.

Every frame moves by an integer vector so nothing is resampled; the pose,
edges and antialiasing stay exactly as drawn.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/actions'
WORK = ROOT / 'action-work/yawn-lock'
ACTION = 'yawn'
FLOOR_Y = 250.0
CENTER_X = 128.5

_spec = importlib.util.spec_from_file_location(
    'yuki_measure', Path(__file__).resolve().parents[1] / '.qoder/skills/yuki-motion/scripts/measure.py')
yuki_measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yuki_measure)


def shift(frame, dx, dy):
    out = np.zeros_like(frame)
    h, w = frame.shape[:2]
    sy0, sy1 = max(0, -dy), min(h, h - dy)
    sx0, sx1 = max(0, -dx), min(w, w - dx)
    out[dy + sy0:dy + sy1, dx + sx0:dx + sx1] = frame[sy0:sy1, sx0:sx1]
    return out


def load_catalog():
    catalog = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
    return next(item for item in catalog if item['id'] == ACTION)


def build():
    entry = load_catalog()
    frames, moves = [], []
    for index in range(entry['frames']):
        frame = np.asarray(Image.open(ASSETS / ACTION / f'{index + 1:02d}.png').convert('RGBA'))
        metrics = yuki_measure.metrics(frame)
        dx = int(round(CENTER_X - metrics['center_x']))
        dy = int(round(FLOOR_Y - metrics['bottom']))
        frames.append(shift(frame, dx, dy))
        moves.append((dx, dy))
    return frames, list(entry['durations']), moves


def preview(frames, durations, moves):
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
    diffs = []
    for a, b in zip(frames, frames[1:]):
        mask = np.maximum(a[:, :, 3], b[:, :, 3]) > 16
        diffs.append(round(float(np.abs(a[:, :, :3].astype(np.int16) - b[:, :, :3].astype(np.int16))[mask].mean()), 1))
    failing = []
    for index, frame in enumerate(frames):
        metrics = yuki_measure.metrics(frame)
        bad = [f'{key}={metrics[key]}' for key, limits in yuki_measure.ANCHOR.items()
               if not limits[0] <= metrics[key] <= limits[1]]
        if bad:
            failing.append((index + 1, bad))
    report = dict(frames=len(frames), duration_ms=sum(durations), durations=durations,
                  moves=moves, peak_diff=max(diffs), diffs=diffs,
                  anchor_failures=failing, failures=len(failing))
    (WORK / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    frames, durations, moves = build()
    report = preview(frames, durations, moves)
    print(json.dumps({key: value for key, value in report.items() if key not in ('diffs', 'moves', 'durations')},
                     ensure_ascii=False))
    if args.apply:
        raise SystemExit('apply handled by action-work/yawn-lock/publish.py')


if __name__ == '__main__':
    main()
