"""Rebuild the body-locked screen clip with a single warp and even sharpness.

Warped in-between frames arrive softer than the key poses. This pass registers
the pristine pre-body-lock frames once (instead of warping them twice), then
levels the high-frequency detail of every frame to the same target.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

import stabilize_screen_action as base

ROOT = base.ROOT
ASSETS = base.ASSETS
ACTION = base.ACTION
WORK = base.WORK
SOURCE = WORK / 'source'
SOURCE_ALIGNMENT = WORK / 'source-alignment.json'
STAGE = WORK / 'clarified'
TARGET = 3000.0
RADIUS = 0.8
MAX_AMOUNT = 340
GRADIENT_CAP = 155.0


def measurements(frame):
    alpha = frame[:, :, 3] / 255.0
    gray = cv2.cvtColor(
        (frame[:, :, :3] * alpha[..., None] + 235 * (1 - alpha[..., None])).astype(np.uint8),
        cv2.COLOR_RGB2GRAY)
    mask = frame[:, :, 3] > 64
    laplacian = float(np.var(cv2.Laplacian(gray, cv2.CV_32F)[mask]))
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    gradient = float(np.mean(np.hypot(gx, gy)[mask]))
    return laplacian, gradient


def sharpen(frame, amount):
    source = Image.fromarray(frame)
    rgb = source.convert('RGB').filter(
        ImageFilter.UnsharpMask(radius=RADIUS, percent=amount, threshold=2))
    result = rgb.convert('RGBA')
    result.putalpha(source.getchannel('A'))
    pixels = np.asarray(result).copy()
    pixels[pixels[:, :, 3] == 0] = 0
    return pixels


def total_matrix(translation, inverse):
    offset = np.vstack([np.float32([[1, 0, translation[0]], [0, 1, translation[1]]]),
                        [0, 0, 1]])
    return (np.vstack([inverse, [0, 0, 1]]) @ offset)[:2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    entry = next(item for item in json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
                 if item['id'] == ACTION)
    if not args.force and entry.get('body_lock') == 'euclidean-stable-body+clarity':
        raise SystemExit('screen already has the clarity pass; pass --force to rebuild it')
    source = args.source
    if not (source / '01.png').exists() or not SOURCE_ALIGNMENT.exists():
        raise SystemExit('staged pre-body-lock frames are missing; restore source/ and source-alignment.json')
    offsets = json.loads(SOURCE_ALIGNMENT.read_text(encoding='utf-8'))['offsets']
    if len(offsets) != entry['frames']:
        raise SystemExit('source alignment does not match the frame count')
    originals = [base.load_rgba(source / f'{index + 1:02d}.png')
                 for index in range(entry['frames'])]
    placed = [base.translate(frame, offsets[index]) for index, frame in enumerate(originals)]
    reference_index = int(entry.get('loop_start', 0))
    reference = placed[reference_index]
    registered = []
    coefficients = []
    for frame in placed:
        inverse, cc = base.register(reference, frame)
        registered.append(inverse)
        coefficients.append(cc)
    stable = []
    for index, frame in enumerate(originals):
        stable.append(base.warp(frame, total_matrix(offsets[index], registered[index])))
    stable, fitted = base.fit_frames(stable)

    sharpened = []
    details = []
    for index, frame in enumerate(stable):
        before, gradient_before = measurements(frame)
        amount = 0
        chosen = frame
        after, gradient_after = before, gradient_before
        if before < TARGET:
            best = (abs(before - TARGET), 0, frame, before, gradient_before)
            for candidate_amount in range(20, MAX_AMOUNT + 1, 20):
                candidate = sharpen(frame, candidate_amount)
                lap, grad = measurements(candidate)
                if grad <= GRADIENT_CAP and abs(lap - TARGET) < best[0]:
                    best = (abs(lap - TARGET), candidate_amount, candidate, lap, grad)
            _, amount, chosen, after, gradient_after = best
        sharpened.append(chosen)
        details.append({
            'frame': index + 1,
            'amount': amount,
            'sharpness_before': round(before, 3),
            'sharpness_after': round(after, 3),
            'gradient_before': round(gradient_before, 3),
            'gradient_after': round(gradient_after, 3),
        })

    heads = [base.head_center(frame) for frame in sharpened]
    lowers = [base.lower_body(frame) for frame in sharpened]
    boxes = [base.visible_box(frame) for frame in sharpened]
    before_values = [item['sharpness_before'] for item in details]
    after_values = [item['sharpness_after'] for item in details]

    STAGE.mkdir(parents=True, exist_ok=True)
    (STAGE / 'frames').mkdir(exist_ok=True)
    for index, frame in enumerate(sharpened):
        Image.fromarray(frame).save(STAGE / 'frames' / f'{index + 1:02d}.png')
    atlas = base.build_atlas(sharpened, entry['columns'])
    atlas.save(STAGE / 'atlas.png')
    poster = Image.fromarray(sharpened[reference_index])
    poster.save(STAGE / 'poster.png')
    base.preview_gif(sharpened, entry['durations'], STAGE / 'preview.gif')
    base.contact_sheet(sharpened, STAGE / 'contact.jpg',
                       [f'{index + 1:02d}' for index in range(len(sharpened))])

    report = {
        'action': ACTION,
        'reference_frame': reference_index + 1,
        'method': 'single-warp-euclidean-body-lock+adaptive-unsharp',
        'frames': len(sharpened),
        'fitted_shift': fitted,
        'ecc_min': round(min(coefficients), 5),
        'head_x_range': round(max(h[0] for h in heads) - min(h[0] for h in heads), 3),
        'head_y_range': round(max(h[1] for h in heads) - min(h[1] for h in heads), 3),
        'lower_center_x_range': round(max(l[0] for l in lowers) - min(l[0] for l in lowers), 3),
        'foot_center_x_range': round(max(l[3] for l in lowers) - min(l[3] for l in lowers), 3),
        'floor_range': round(max(b[3] for b in boxes) - min(b[3] for b in boxes), 3),
        'fit_within_canvas': min(b[0] for b in boxes) >= 0 and max(b[2] for b in boxes) <= 255,
        'target_sharpness': TARGET,
        'sharpness_radius': RADIUS,
        'gradient_cap': GRADIENT_CAP,
        'sharpness_before': {'min': round(min(before_values), 3),
                             'median': round(float(np.median(before_values)), 3),
                             'max': round(max(before_values), 3)},
        'sharpness_after': {'min': round(min(after_values), 3),
                            'median': round(float(np.median(after_values)), 3),
                            'max': round(max(after_values), 3)},
        'frames_detail': details,
    }
    base.write_json(STAGE / 'metrics.json', report)
    print(json.dumps({key: value for key, value in report.items() if key != 'frames_detail'},
                     ensure_ascii=False, indent=2))
    if args.apply:
        base.apply(sharpened, atlas, poster, entry, report,
                   prefix='backup-screen-clarify',
                   review='身体锁定 · 清晰化 · 取出后持续持屏操作')
        catalog_path = ASSETS / 'catalog.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        for item in catalog:
            if item['id'] == ACTION:
                item['body_lock'] = 'euclidean-stable-body+clarity'
        base.write_json(catalog_path, catalog)
        public_path = base.PUBLIC / 'catalog.json'
        public = json.loads(public_path.read_text(encoding='utf-8'))
        for item in public:
            if item['id'] == ACTION:
                item['body_lock'] = 'euclidean-stable-body+clarity'
        base.write_json(public_path, public)


if __name__ == '__main__':
    main()
