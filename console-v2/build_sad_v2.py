"""Stage the longer sad clip without touching runtime assets."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build_action_inbetweens import interpolate  # noqa: E402

WORK = ROOT / 'action-work' / 'sad-v2'
POSES = WORK / 'poses'
KEYS = {name: POSES / f'{name}.png' for name in ('K1', 'K2', 'K3', 'K4', 'K5', 'K6')}
FEET_X = 127.0
FLOOR_Y = 250

# (kind, pose, target, frames, total_ms)
BEATS = [
    ('hold', 'K1', None, 1, 300),
    ('move', 'K1', 'K2', 5, 250),
    ('hold', 'K2', None, 1, 350),
    ('move', 'K2', 'N1', 4, 200),
    ('hold', 'N1', None, 1, 100),
    ('move', 'N1', 'K3', 4, 200),
    ('hold', 'K3', None, 1, 450),
    ('move', 'K3', 'N2', 4, 200),
    ('hold', 'N2', None, 1, 100),
    ('move', 'N2', 'K4', 4, 200),
    ('hold', 'K4', None, 1, 800),
    ('move', 'K4', 'N3', 2, 100),
    ('hold', 'N3', None, 1, 50),
    ('move', 'N3', 'K5', 2, 100),
    ('hold', 'K5', None, 1, 350),
    ('move', 'K5', 'K6', 5, 250),
    ('hold', 'K6', None, 1, 200),
]

PLACEHOLDERS = {'N1': 'K3', 'N2': 'K4', 'N3': 'K5'}


def load(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(np.uint8)


def feet_center(frame):
    alpha = frame[:, :, 3]
    ys, xs = np.where(alpha > 60)
    if not len(xs):
        return 128.0, 255
    bottom = int(ys.max())
    feet = ys >= bottom - 11
    return float(xs[feet].mean()), bottom


def shift_frame(frame, dx, dy):
    """Integer translate with a zero-alpha border, no resampling."""
    out = np.zeros_like(frame)
    h, w = frame.shape[:2]
    sx0, sx1 = max(0, -dx), min(w, w - dx)
    sy0, sy1 = max(0, -dy), min(h, h - dy)
    if sx1 <= sx0 or sy1 <= sy0:
        return out
    out[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] = frame[sy0:sy1, sx0:sx1]
    return out


def align_key(frame):
    cx, bottom = feet_center(frame)
    dx = int(round(FEET_X - cx))
    dy = int(round(FLOOR_Y - bottom))
    return shift_frame(frame, dx, dy), dx, dy


def smoothstep(t):
    return t * t * (3 - 2 * t)


def edge_strength(frame):
    a = np.asarray(frame).astype(np.float32)
    alpha = a[:, :, 3] / 255.0
    solid = alpha > 0.78
    if not solid.any():
        return 0.0
    lum = (a[:, :, :3] * alpha[..., None] + 240 * (1 - alpha[..., None])).mean(2)
    gy, gx = np.gradient(lum)
    return float(np.sqrt(gy ** 2 + gx ** 2)[solid].mean())


def match_edge(frame, target, limit=150):
    from PIL import ImageFilter
    best, best_percent = None, 0
    for percent in range(0, limit + 1, 10):
        image = Image.fromarray(frame)
        sharp = image if percent == 0 else image.filter(
            ImageFilter.UnsharpMask(radius=1.0, percent=percent, threshold=2))
        candidate = np.asarray(sharp)
        score = abs(edge_strength(candidate) - target)
        if best is None or score < best[0]:
            best, best_percent = (score, candidate), percent
        if edge_strength(candidate) > target:
            break
    return best[1], best_percent


def sample_indices(times):
    """Pick nearest of the 25 linear warp samples for each eased time."""
    return [max(1, min(23, int(round(t * 24)))) for t in times]


def build(poses, profile):
    frames, durations, log, is_key = [], [], [], []
    for kind, start, end, count, total in BEATS:
        if kind == 'hold':
            frames.append(poses[start])
            durations.append(total)
            is_key.append(True)
            log.append({'beat': start, 'frames': 1, 'ms': total})
            continue
        a, b = poses[start], poses[end]
        step = total / count
        eased = [smoothstep((i + 1) / (count + 1)) for i in range(count)]
        picks = sample_indices(eased)
        samples, quality = interpolate(a, b, ('sad', 0), ('sad', 1), profile)
        for pick in picks:
            frames.append(samples[pick])
            durations.append(int(round(step)))
            is_key.append(False)
        log.append({'beat': f'{start}>{end}', 'frames': count, 'ms': total,
                    'step': round(step, 1), 'picks': picks,
                    'accepted': quality['accepted'],
                    'peak': quality['playback_peak']})
    return frames, durations, log, is_key


def preview(frames, durations, path, caption=None):
    images = []
    for frame in frames:
        bg = Image.new('RGB', (256, 256), '#48505e')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        if caption:
            ImageDraw.Draw(bg).text((8, 8), caption, fill=(230, 236, 244))
        images.append(bg)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=durations, loop=0, disposal=2)


def contact(frames, path, cols=8):
    scale = 0.5
    side = int(256 * scale)
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new('RGB', (cols * side, rows * side), '#48505e')
    for index, frame in enumerate(frames):
        bg = Image.new('RGB', (side, side), '#48505e')
        sprite = Image.fromarray(frame).resize((side, side), Image.LANCZOS)
        bg.paste(sprite, (0, 0), sprite)
        ImageDraw.Draw(bg).text((4, 4), f'{index+1:02d}', fill=(255, 255, 255))
        sheet.paste(bg, ((index % cols) * side, (index // cols) * side))
    sheet.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(WORK / 'gray'))
    parser.add_argument('--new-pose', action='append', default=[],
                        help='pose=path, e.g. N1=.../n1.png')
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    generated = {}
    for spec in args.new_pose:
        name, raw = spec.split('=', 1)
        generated[name] = load(Path(raw))

    poses, moves = {}, {}
    for name, path in KEYS.items():
        frame, dx, dy = align_key(load(path))
        poses[name] = frame
        moves[name] = (dx, dy)
    for name in PLACEHOLDERS:
        if name in generated:
            source = generated[name]
        elif (POSES / f'{name}.png').exists():
            source = load(POSES / f'{name}.png')
        else:
            poses[name] = poses[PLACEHOLDERS[name]]
            moves[name] = moves[PLACEHOLDERS[name]]
            continue
        frame, dx, dy = align_key(source)
        poses[name] = frame
        moves[name] = (dx, dy)

    profile = {'sad': {'anchor_x': FEET_X, 'floor_y': FLOOR_Y,
                       'preserve_vertical': False, 'offsets': [[0, 0]] * 64}}
    frames, durations, log, is_key = build(poses, profile)

    key_edges = [edge_strength(frame) for frame, key in zip(frames, is_key) if key]
    target_edge = float(np.median(key_edges))
    sharpened = 0
    for index, (frame, key) in enumerate(zip(frames, is_key)):
        if key:
            continue
        if edge_strength(frame) < target_edge * 0.92:
            frames[index], percent = match_edge(frame, target_edge)
            sharpened += 1
    print(f'edge target {target_edge:.2f}, sharpened {sharpened} in-betweens')

    for index, frame in enumerate(frames):
        Image.fromarray(frame).save(out / f'{index+1:02d}.png')
    preview(frames, durations, out / 'preview.gif')
    contact(frames, out / 'contact.png')
    report = {
        'frames': len(frames),
        'total_ms': sum(durations),
        'durations': durations,
        'key_shift': {k: list(v) for k, v in moves.items()},
        'beats': log,
    }
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'durations'}, ensure_ascii=False, indent=1))
    print('frames', len(frames), 'total', sum(durations))


if __name__ == '__main__':
    main()
