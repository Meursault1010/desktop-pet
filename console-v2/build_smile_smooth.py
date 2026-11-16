"""Rebuild 开心闭眼微笑 with clean eyelid steps and arm in-betweens.

The shipped clip only had fully-open and fully-closed eyes, so the smoothing
flow invented broken half-lidded frames (one eye shut, one eye open) and then
popped the eyes open again in a single step. This build adds two drawn lid
states and three drawn arm states, scales every pose off the head width so the
batch shares one camera, and pastes a canonical eye band back onto every frame
after interpolation — the lids are never allowed to be flowed.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import build_action_library as library
from build_action_inbetweens import interpolate

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'action-work/smile-opt'
KEYS = WORK / 'keys'
OUT = WORK / 'clip'
ACTION = 'smile'
CELLS = WORK / 'cells'
FOOT_X, FLOOR_Y, SHIPPED_HEIGHT = 128.0, 251.0, 226

_spec = importlib.util.spec_from_file_location(
    'yuki_measure', Path(__file__).resolve().parents[1] / '.qoder/skills/yuki-motion/scripts/measure.py')
yuki_measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(yuki_measure)

POSES = {
    'P1_open': str(CELLS / 'k1.png'),
    'L1_half': 'vibe_images/smile-l1-halflid_*.png',
    'L2_mostly': 'vibe_images/smile-l2-nearly-closed_*.png',
    'P2_closed': str(CELLS / 'k2.png'),
    'P3_chest': str(CELLS / 'k3.png'),
    'A_open_arms': 'vibe_images/smile-armA-opening_*.png',
    'P4_wide': str(CELLS / 'k4.png'),
    'B_closing_arms': 'vibe_images/smile-armB-closing_*.png',
    'P5_cheek': str(CELLS / 'k5.png'),
    'C_lowering_arms': 'vibe_images/smile-armC-lowering_*.png',
}
CLOSED = {'P2_closed', 'P3_chest', 'A_open_arms', 'P4_wide', 'B_closing_arms', 'P5_cheek', 'C_lowering_arms'}

# (states, t, duration, tag) — one state is a hard pose, two is an interpolated sample
TIMELINE = [
    (('P1_open',), None, 110, 'neutral'),
    (('L1_half',), None, 85, 'half lid'),
    (('L2_mostly',), None, 80, 'slit'),
    (('P2_closed',), None, 150, 'eyes shut'),
    (('P2_closed', 'P3_chest'), 0.33, 70, 'hands lift'),
    (('P2_closed', 'P3_chest'), 0.66, 70, 'mouth opens'),
    (('P3_chest',), None, 140, 'hands at chest'),
    (('P3_chest', 'A_open_arms'), 0.33, 60, 'arms start out'),
    (('P3_chest', 'A_open_arms'), 0.66, 60, 'arms out'),
    (('A_open_arms',), None, 70, 'elbows away'),
    (('A_open_arms', 'P4_wide'), 0.33, 60, 'arms widening'),
    (('A_open_arms', 'P4_wide'), 0.66, 60, 'nearly wide'),
    (('P4_wide',), None, 150, 'arms wide'),
    (('P4_wide', 'B_closing_arms'), 0.33, 60, 'arms coming in'),
    (('P4_wide', 'B_closing_arms'), 0.66, 60, 'elbows in'),
    (('B_closing_arms',), None, 70, 'hands near face'),
    (('B_closing_arms', 'P5_cheek'), 0.33, 60, 'hands clasp'),
    (('B_closing_arms', 'P5_cheek'), 0.66, 60, 'clasped'),
    (('P5_cheek',), None, 210, 'biggest smile'),
    (('P5_cheek', 'C_lowering_arms'), 0.33, 60, 'hands drop'),
    (('P5_cheek', 'C_lowering_arms'), 0.66, 60, 'arms down'),
    (('C_lowering_arms',), None, 80, 'lowering'),
    (('C_lowering_arms', 'P2_closed'), 0.5, 70, 'arms settle'),
    (('P2_closed',), None, 140, 'settled, still shut'),
    (('L2_mostly',), None, 85, 'lid lifts'),
    (('L1_half',), None, 85, 'half open'),
    (('P1_open',), None, 300, 'back to neutral'),
]


def source(name):
    path = str(ROOT.parent / POSES[name])
    return sorted(glob.glob(path))[-1] if '*' in path else path


def silhouette(alpha):
    ys, xs = np.nonzero(alpha > 40)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def head_metrics(frame):
    """Head width and centre from the top slice of the silhouette."""
    alpha = frame[:, :, 3]
    left, top, right, bottom = silhouette(alpha)
    slice_bottom = top + int((bottom - top) * 0.22)
    band = alpha[top:slice_bottom, :]
    ys, xs = np.nonzero(band > 40)
    return float(xs.max() - xs.min() + 1), float(xs.mean()), float(top)


def foot_metrics(frame):
    alpha = frame[:, :, 3]
    left, top, right, bottom = silhouette(alpha)
    band = alpha[bottom - 12:bottom + 1, :]
    ys, xs = np.nonzero(band > 40)
    return float(xs.mean()), float(bottom)


def build_keys():
    KEYS.mkdir(parents=True, exist_ok=True)
    cut = {}
    for name in POSES:
        cut[name] = library.extract(Image.open(source(name)).convert('RGB'), chroma=True)
    base = np.asarray(cut['P1_open'])
    left, top, right, bottom = silhouette(base[:, :, 3])
    head_target = head_metrics(base)[0] * (SHIPPED_HEIGHT / (bottom - top + 1))
    keys = {}
    for name, sprite in cut.items():
        array = np.asarray(sprite)
        left, top, right, bottom = silhouette(array[:, :, 3])
        array = array[max(0, top - 2):bottom + 3, max(0, left - 2):right + 3]
        head_w = head_metrics(array)[0]
        factor = head_target / head_w
        resized = cv2.resize(array, (max(1, round(array.shape[1] * factor)), max(1, round(array.shape[0] * factor))),
                             interpolation=cv2.INTER_AREA)
        foot_x, floor = foot_metrics(resized)
        canvas = np.zeros((256, 256, 4), np.uint8)
        dx = int(round(FOOT_X - foot_x))
        dy = int(round(FLOOR_Y - floor))
        h, w = resized.shape[:2]
        sy0, sy1 = max(0, -dy), min(h, 256 - dy)
        sx0, sx1 = max(0, -dx), min(w, 256 - dx)
        canvas[dy + sy0:dy + sy1, dx + sx0:dx + sx1] = resized[sy0:sy1, sx0:sx1]
        keys[name] = canvas
        Image.fromarray(canvas).save(KEYS / f'{name}.png')
    return keys


def eye_cluster(frame):
    """Rows and columns of the widest dark cluster in the head — the eyes."""
    alpha = frame[:, :, 3]
    left, top, right, bottom = silhouette(alpha)
    rgb = frame[:, :, :3].astype(int)
    dark = (rgb.mean(2) < 135) & (alpha > 120)
    dark[:top + 55, :] = False
    dark[top + 105:, :] = False
    groups = []
    row = np.nonzero(dark.sum(1))[0]
    for index in row:
        span = np.nonzero(dark[index])[0]
        if groups and index - groups[-1][1] <= 2:
            groups[-1][1] = index
            groups[-1][2] = min(groups[-1][2], span.min())
            groups[-1][3] = max(groups[-1][3], span.max())
        else:
            groups.append([index, index, span.min(), span.max()])
    if not groups:
        raise ValueError('no eye pixels found')
    y0, y1, x0, x1 = max(groups, key=lambda g: g[3] - g[2])
    return int(x0) - 6, int(y0) - 4, int(x1) + 7, int(y1) + 5


def widen(box, below):
    x0, y0, x1, y1 = box
    return x0, y0 - 6, x1, y1 + below


def paste_patch(frame, donor, box, feather=2.2):
    """Template-match the donor patch into frame and paste it, feathered."""
    x0, y0, x1, y1 = box
    patch = donor[y0:y1, x0:x1]
    pad = 8
    sy, sx = max(0, y0 - pad), max(0, x0 - pad)
    search = frame[sy:y1 + pad, sx:x1 + pad, :3]
    result = cv2.matchTemplate(cv2.cvtColor(search, cv2.COLOR_RGB2GRAY),
                               cv2.cvtColor(patch[:, :, :3], cv2.COLOR_RGB2GRAY), cv2.TM_CCOEFF_NORMED)
    _, _, _, best = cv2.minMaxLoc(result)
    px, py = sx + best[0], sy + best[1]
    out = frame.copy()
    mask = np.zeros(patch.shape[:2], np.float32)
    cv2.rectangle(mask, (0, 0), (patch.shape[1] - 1, patch.shape[0] - 1), 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), feather)[..., None]
    region = out[py:py + patch.shape[0], px:px + patch.shape[1]].astype(np.float32)
    blended = region * (1 - mask) + patch.astype(np.float32) * mask
    out[py:py + patch.shape[0], px:px + patch.shape[1]] = blended.clip(0, 255).astype(np.uint8)
    return out


def compose_lids(keys):
    """Lid and closed states are P1's body with only the drawn face pasted in.

    The model repaints a pixel or two elsewhere each generation, so a hard cut
    between two whole frames would boil; sharing one body leaves only the face
    changing.
    """
    body = keys['P1_open']
    face_box = widen(eye_cluster(body), below=26)
    for name in ('L1_half', 'L2_mostly', 'P2_closed'):
        keys[name] = paste_patch(body, keys[name], face_box)
        Image.fromarray(keys[name]).save(KEYS / f'{name}.png')
    return keys


def build(keys):
    strips = {}

    def sample(states, t):
        if len(states) == 1:
            return keys[states[0]].copy()
        order = list(POSES)
        forward = order.index(states[0]) < order.index(states[1])
        pair = states if forward else tuple(reversed(states))
        if pair not in strips:
            frames, report = interpolate(keys[pair[0]], keys[pair[1]], (ACTION, 0), (ACTION, 1), profile={})
            strips[pair] = (frames, report)
            if not report['accepted']:
                print(f'REJECTED {pair}: {report}')
        band = strips[pair][0]
        return band[int(round((t if forward else 1.0 - t) * (len(band) - 1)))].copy()

    closed_eyes = eye_cluster(keys['P2_closed'])
    frames, tags = [], []
    for states, t, duration, tag in TIMELINE:
        frame = sample(states, t)
        # The flow may carry the lids anywhere, so every closed-section frame
        # gets the drawn closed eyes back. Lid beats are hard cuts and stay as
        # drawn.
        if all(name in CLOSED for name in states):
            frame = paste_patch(frame, keys['P2_closed'], closed_eyes)
        frames.append(frame)
        tags.append((tag, duration))
    return frames, tags, {f'{a}->{b}': r for (a, b), (_, r) in strips.items()}


def unify(frames):
    """Nudge every frame's line edge onto the idle anchor, softening as well as sharpening."""
    target = yuki_measure.metrics(
        np.asarray(Image.open(ROOT / 'assets/living-idle/open.png').convert('RGBA').crop((0, 0, 256, 256))))['edge']
    low, high = yuki_measure.ANCHOR['edge']
    out = []
    for frame in frames:
        image = Image.fromarray(frame)
        alpha = np.asarray(image)[:, :, 3]
        rgb = image.convert('RGB')
        candidates = [np.dstack([np.asarray(rgb.filter(ImageFilter.GaussianBlur(radius))), alpha])
                      for radius in (0.5, 0.4, 0.3, 0.2, 0.1)]
        candidates.append(frame)
        for step in range(10, 210, 10):
            sharpened = rgb.filter(ImageFilter.UnsharpMask(radius=1.0, percent=step, threshold=2))
            candidates.append(np.dstack([np.asarray(sharpened), alpha]))
        scored = [(abs(yuki_measure.metrics(item)['edge'] - target), index)
                  for index, item in enumerate(candidates)]
        best = min(scored)[1]
        edge = yuki_measure.metrics(candidates[best])['edge']
        if not low <= edge <= high:
            print(f'edge {edge} still outside {low}-{high}')
        out.append(candidates[best])
    return out


def preview(frames, tags):
    OUT.mkdir(parents=True, exist_ok=True)
    folder = OUT / 'frames'
    folder.mkdir(parents=True, exist_ok=True)
    durations = [d for _, d in tags]
    for index, frame in enumerate(frames):
        Image.fromarray(frame).save(folder / f'{index + 1:02d}.png')
    images = []
    for frame in frames:
        bg = Image.new('RGB', (256, 256), '#303b4c')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    images[0].save(OUT / 'preview.gif', save_all=True, append_images=images[1:], duration=durations, loop=0)
    cols, cell = 7, 170
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 22)), '#303b4c')
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x, y = index % cols * cell, index // cols * (cell + 22)
        thumb = Image.fromarray(frame).resize((cell, cell), Image.LANCZOS)
        bg = Image.new('RGB', (cell, cell), '#303b4c')
        bg.paste(thumb, (0, 0), thumb)
        sheet.paste(bg, (x, y + 14))
        draw.text((x + 3, y + 2), f'{index + 1:02d} {tags[index][0]}', fill='#dbeafe')
    sheet.save(OUT / 'contact.jpg', quality=94)
    diffs = []
    for a, b in zip(frames, frames[1:]):
        mask = np.maximum(a[:, :, 3], b[:, :, 3]) > 16
        diffs.append(round(float(np.abs(a[:, :, :3].astype(np.int16) - b[:, :, :3].astype(np.int16))[mask].mean()), 1))
    report = dict(frames=len(frames), duration_ms=sum(durations), diffs=diffs, peak=max(diffs))
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    keys = compose_lids(build_keys())
    frames, tags, strips = build(keys)
    frames = unify(frames)
    report = preview(frames, tags)
    print(json.dumps({k: v for k, v in report.items() if k != 'eye_bands'}, ensure_ascii=False)[:600])
    for pair, result in strips.items():
        if not result['accepted']:
            print('strip rejected', pair, result)
    if args.apply:
        raise SystemExit('apply not wired yet; preview only')


if __name__ == '__main__':
    main()
