"""Densify the shipped 开心闭眼微笑 without moving its body.

The shipped clip only had open and shut eyes, so the in-between step invented
torn lids on frame 2, 3 and 22 and then popped the eyes open. This build keeps
every shipped body frame as it plays today (runtime alignment baked in), paints
the two missing lid states on with a soft ellipse that stays on the face, and
inserts one interpolated sample inside every same-state gap so the motion is
sampled twice as often over the same total length. Lid states stay hard cuts.
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

from build_action_inbetweens import interpolate

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/actions'
WORK = ROOT / 'action-work/smile-densify'
ACTION = 'smile'

_spec = importlib.util.spec_from_file_location(
    'yuki_measure', Path(__file__).resolve().parents[1] / '.qoder/skills/yuki-motion/scripts/measure.py')
yuki_measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yuki_measure)

LIDS = {1: 'L1_half', 2: 'L2_mostly', 21: 'L2_mostly', 22: 'L1_half'}
EYE_ELLIPSE = ((128, 95), (44, 20))


def shift(frame, offset):
    dx, dy = int(round(offset[0])), int(round(offset[1]))
    out = np.zeros_like(frame)
    h, w = frame.shape[:2]
    sy0, sy1 = max(0, -dy), min(h, 256 - dy)
    sx0, sx1 = max(0, -dx), min(w, 256 - dx)
    out[dy + sy0:dy + sy1, dx + sx0:dx + sx1] = frame[sy0:sy1, sx0:sx1]
    return out


def load_shipped():
    catalog = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
    entry = next(item for item in catalog if item['id'] == ACTION)
    alignment = json.loads((ASSETS / 'frame-alignment.json').read_text(encoding='utf-8'))
    offsets = alignment['actions'][ACTION]['offsets']
    frames = []
    for index in range(entry['frames']):
        frame = np.asarray(Image.open(ASSETS / ACTION / f'{index + 1:02d}.png').convert('RGBA'))
        frames.append(shift(frame, offsets[index]))
    return frames, list(entry['durations'])


def best_shift(donor, target, box=(80, 68, 182, 150), span=5):
    """Whole-face registration. The eyes are too small and the lash too dark for
    cluster or template matching — both lock onto the wrong copy — but the face
    outline and nose give one unambiguous answer."""
    x0, y0, x1, y1 = box
    ref = target[y0:y1, x0:x1, :3].astype(np.float32)
    best = (1e9, 0, 0)
    for dy in range(-span, span + 1):
        for dx in range(-span, span + 1):
            probe = donor[y0 - dy:y1 - dy, x0 - dx:x1 - dx, :3].astype(np.float32)
            score = float(np.abs(probe - ref).mean())
            if score < best[0]:
                best = (score, dx, dy)
    return best[1], best[2]


def eye_mask():
    mask = np.zeros((256, 256), np.uint8)
    (cx, cy), (rx, ry) = EYE_ELLIPSE
    cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 1, -1)
    return mask


def paste(target, donor, mask, dx, dy, feather=1.4):
    moved = shift(donor, (dx, dy))
    weight = shift(mask, (dx, dy)).astype(np.float32)
    weight = cv2.GaussianBlur(weight, (0, 0), feather)[..., None]
    out = target.astype(np.float32)
    out[:, :, :3] = out[:, :, :3] * (1 - weight) + moved[:, :, :3].astype(np.float32) * weight
    return out.clip(0, 255).astype(np.uint8)


def settle(frame, edge_target, aa_target):
    """Flow-warped samples lose edge bite and smear the silhouette.

    Unsharp the RGB only — sharpening alpha would chew the cutout — and steepen
    the alpha ramp so the mid sits on the same style anchor as its neighbours.
    """
    rgb = frame[:, :, :3].astype(np.float32)
    alpha = frame[:, :, 3].astype(np.float32)
    edge_lo, edge_hi = yuki_measure.ANCHOR['edge']
    aa_lo, aa_hi = yuki_measure.ANCHOR['aa']
    edge_target = min(edge_hi - 0.25, max(edge_lo + 0.15, edge_target))
    aa_target = min(aa_hi - 0.004, max(aa_lo + 0.004, aa_target))
    best, best_score = frame, 1e9
    for k in (1.0, 1.06, 1.12, 1.18, 1.24, 1.32, 1.4):
        cand = frame.copy()
        cand[:, :, 3] = (np.clip((alpha / 255 - 0.5) * k + 0.5, 0, 1) * 255).round().astype(np.uint8)
        blur = cv2.GaussianBlur(rgb, (0, 0), 1.05)
        for amount in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.3, 1.6):
            out = cand.copy()
            out[:, :, :3] = np.clip(rgb + amount * (rgb - blur), 0, 255).astype(np.uint8)
            metrics = yuki_measure.metrics(out)
            inside = edge_lo <= metrics['edge'] <= edge_hi and aa_lo <= metrics['aa'] <= aa_hi
            score = (0.0 if inside else 100.0) \
                + abs(metrics['edge'] - edge_target) / 0.5 + abs(metrics['aa'] - aa_target) / 0.02
            if score < best_score:
                best, best_score = out, score
    return best


def build(keys):
    frames, durations = load_shipped()
    dx, dy = best_shift(keys['P1_open'], frames[0])
    mask = eye_mask()
    for index, name in LIDS.items():
        frames[index] = paste(frames[index], keys[name], mask, dx, dy)
    states = (['open', 'half', 'slit'] + ['closed'] * 18 + ['slit', 'half', 'open', 'open'])[:len(frames)]

    out = []
    for index, (frame, state, duration) in enumerate(zip(frames, states, durations)):
        if index + 1 >= len(frames) or states[index + 1] != state:
            out.append((frame, state, duration))
            continue
        nxt = frames[index + 1]
        strip, report = interpolate(frame, nxt, (ACTION, index), (ACTION, index + 1), profile={})
        if not report['accepted']:
            print(f'skip gap {index + 1}->{index + 2}: peak={report["playback_peak"]}')
            out.append((frame, state, duration))
            continue
        ends = [yuki_measure.metrics(item) for item in (frame, nxt)]
        mid = settle(strip[len(strip) // 2],
                     sum(item['edge'] for item in ends) / 2,
                     sum(item['aa'] for item in ends) / 2)
        half = max(30, duration // 2)
        out.append((frame, state, half))
        out.append((mid, state, max(30, duration - half)))
    frames = [item[0] for item in out]
    states = [item[1] for item in out]
    durations = [item[2] for item in out]
    return frames, states, durations


def preview(frames, states, durations):
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
        draw.text((x + 3, y + 1), f'{index + 1:02d} {states[index]}', fill='#dbeafe')
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
    report = dict(frames=len(frames), duration_ms=sum(durations), durations=durations, peak_diff=max(diffs),
                  diffs=diffs, anchor_failures=failing[:8], failures=len(failing))
    (WORK / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keys', default=str(ROOT / 'action-work/smile-opt/keys'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    keys = {path.stem: np.asarray(Image.open(path).convert('RGBA')) for path in sorted(Path(args.keys).glob('*.png'))}
    frames, states, durations = build(keys)
    report = preview(frames, states, durations)
    print(json.dumps({k: v for k, v in report.items() if k != 'diffs'}, ensure_ascii=False))
    if args.apply:
        raise SystemExit('apply not wired yet; preview only')


if __name__ == '__main__':
    main()
