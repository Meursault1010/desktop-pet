"""Lock the pocket-screen body in place without redrawing the action.

The reviewed 41-frame clip already animates the pocket retrieval and the taps.
Only the whole-sprite drift is removed: every frame is registered to the first
operating pose with a euclidean transform estimated from the stable body
regions (head, shoulders, skirt, feet), excluding the moving arms and device.
"""
import argparse
import json
import math
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/actions'
ACTION = 'screen'
PUBLIC = ROOT / 'frontend/public/actions'
WORK = ROOT / 'action-work/screen-stabilize'
# The hands and the device occupy this box; they must not steer registration.
EXCLUDED_BOX = (70, 95, 190, 205)
THRESHOLD = 32


def load_rgba(path):
    return np.asarray(Image.open(path).convert('RGBA')).astype(np.uint8)


def premultiply(image):
    image = image.astype(np.float32)
    image[:, :, :3] *= image[:, :, 3:4] / 255
    return image


def unpremultiply(image):
    image = image.copy()
    image[:, :, :3] = np.divide(image[:, :, :3], image[:, :, 3:4] / 255,
                                out=np.zeros_like(image[:, :, :3]),
                                where=image[:, :, 3:4] > 0)
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def translate(image, offset):
    dx, dy = float(offset[0]), float(offset[1])
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def warp(image, matrix):
    fixed = cv2.warpAffine(premultiply(image), matrix, (image.shape[1], image.shape[0]),
                           flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT,
                           borderValue=0)
    return unpremultiply(fixed)


def gray_on_sheet(image):
    alpha = image[:, :, 3:4] / 255
    colour = image[:, :, :3] * alpha + 235 * (1 - alpha)
    return cv2.cvtColor(np.clip(colour, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)


def head_center(image):
    alpha = image[:, :, 3]
    ys, xs = np.where(alpha > THRESHOLD)
    limit = ys.min() + min(100, ys.max() - ys.min())
    top = ys <= limit
    return float(xs[top].mean()), float(ys[top].mean())


def lower_body(image):
    alpha = image[:, :, 3]
    ys, xs = np.where(alpha > THRESHOLD)
    lower = ys >= 170
    bottom = ys >= ys.max() - 12
    return (float(xs[lower].mean()), float(ys[lower].mean()), float(ys.max()),
            float(xs[bottom].mean()))


def visible_box(image):
    alpha = image[:, :, 3]
    ys, xs = np.where(alpha > 0)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def register(reference, frame):
    mask = np.zeros(reference.shape[:2], np.uint8)
    mask[reference[:, :, 3] > THRESHOLD] = 255
    x0, y0, x1, y1 = EXCLUDED_BOX
    mask[y0:y1, x0:x1] = 0
    mask = cv2.erode(mask, np.ones((5, 5), np.uint8))
    matrix = np.eye(2, 3, dtype=np.float32)
    cc, matrix = cv2.findTransformECC(
        gray_on_sheet(reference), gray_on_sheet(frame), matrix,
        cv2.MOTION_EUCLIDEAN,
        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-7),
        mask, 5)
    inverse = np.linalg.inv(np.vstack([matrix, [0, 0, 1]]))[:2]
    return inverse, float(cc)


def fit_frames(frames):
    """Keep every frame inside the canvas with a one-pixel margin."""
    boxes = [visible_box(frame) for frame in frames]
    dx = dy = 0
    if min(box[0] for box in boxes) < 1:
        dx = 1 - min(box[0] for box in boxes)
    if max(box[2] for box in boxes) > 254:
        dx = 254 - max(box[2] for box in boxes)
    if min(box[1] for box in boxes) < 1:
        dy = 1 - min(box[1] for box in boxes)
    if max(box[3] for box in boxes) > 254:
        dy = 254 - max(box[3] for box in boxes)
    if dx or dy:
        frames = [translate(frame, (dx, dy)) for frame in frames]
    return frames, (int(dx), int(dy))


def build_atlas(frames, columns):
    atlas = Image.new('RGBA', (columns * 256, math.ceil(len(frames) / columns) * 256))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(Image.fromarray(frame),
                              ((index % columns) * 256, (index // columns) * 256))
    return atlas


def preview_gif(frames, durations, path, start=0):
    images = []
    for frame in frames[start:]:
        bg = Image.new('RGB', (256, 256), '#303b4c')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=durations[start:], loop=0)


def contact_sheet(frames, path, names=None):
    cols, cell = 7, 256
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new('RGB', (cols * cell, rows * (cell + 22)), '#303b4c')
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x, y = index % cols * cell, index // cols * (cell + 22)
        sheet.paste(Image.fromarray(frame), (x, y), Image.fromarray(frame))
        draw.text((x + 8, y + cell + 3), names[index] if names else f'{index + 1:02d}',
                  fill='#dbeafe')
    sheet.save(path, quality=92)


def shift_profile(offsets, count):
    values = list(offsets or [])
    if len(values) < count:
        values.extend([[0., 0.]] * (count - len(values)))
    return values[:count]


def write_json(path, payload):
    existing = path.read_bytes()[:512] if path.exists() else b''
    newline = '\r\n' if b'\r\n' in existing else '\n'
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    path.write_bytes(text.replace('\n', newline).encode('utf-8'))


def apply(frames, atlas, poster, entry, report,
          prefix='backup-screen-bodylock', review='身体锁定 · 取出后持续持屏操作'):
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = ROOT / f'{prefix}-{stamp}'
    backup.mkdir()
    shutil.copytree(ASSETS / ACTION, backup / ACTION)
    for name in ('catalog.json', 'frame-alignment.json'):
        shutil.copy2(ASSETS / name, backup / name)
    for name in ('screen.gif', 'screen-operating.gif', 'screen.jpg'):
        source = ROOT / 'qa/actions' / name
        if source.exists():
            shutil.copy2(source, backup / name)
    for name in ('atlas.webp', 'poster.webp'):
        source = PUBLIC / ACTION / name
        if source.exists():
            shutil.copy2(source, backup / name)
    shutil.copy2(PUBLIC / 'catalog.json', backup / 'public-catalog.json')

    folder = ASSETS / ACTION
    for path in folder.glob('[0-9][0-9].png'):
        path.unlink()
    for index, frame in enumerate(frames):
        temporary = folder / f'{index + 1:02d}.png.{os.getpid()}.tmp'
        Image.fromarray(frame).save(temporary, format='PNG')
        os.replace(temporary, folder / f'{index + 1:02d}.png')
    atlas.save(folder / 'atlas.png')
    poster.save(folder / 'poster.png')

    public = PUBLIC / ACTION
    atlas.save(public / 'atlas.webp', lossless=True, exact=True)
    poster.save(public / 'poster.webp', lossless=True, exact=True)

    catalog_path = ASSETS / 'catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    for item in catalog:
        if item['id'] != ACTION:
            continue
        item.update(body_locked=True, body_lock='euclidean-stable-body',
                    review=review)
    write_json(catalog_path, catalog)

    public_catalog_path = PUBLIC / 'catalog.json'
    public_catalog = json.loads(public_catalog_path.read_text(encoding='utf-8'))
    for item in public_catalog:
        if item['id'] != ACTION:
            continue
        item.update(body_locked=True, body_lock='euclidean-stable-body',
                    review=review)
    write_json(public_catalog_path, public_catalog)

    alignment_path = ASSETS / 'frame-alignment.json'
    alignment = json.loads(alignment_path.read_text(encoding='utf-8'))
    alignment['actions'][ACTION] = {
        'anchor_x': 128.0, 'floor_y': 252.0, 'preserve_vertical': True,
        'body_locked': True, 'offsets': [[0.0, 0.0]] * len(frames),
    }
    alignment['transitions'] = {key: value for key, value in alignment.get('transitions', {}).items()
                                if not key.startswith(ACTION + ':')}
    write_json(alignment_path, alignment)

    durations = entry['durations']
    preview_gif(frames, durations, ROOT / 'qa/actions/screen.gif')
    preview_gif(frames, durations, ROOT / 'qa/actions/screen-operating.gif',
                start=entry.get('loop_start', 0))
    contact_sheet(frames, ROOT / 'qa/actions/screen.jpg')
    report['backup'] = str(backup)
    write_json(WORK / 'report.json', report)
    print(f'Applied body-locked screen action. Backup: {backup}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--force', action='store_true',
                        help='Re-register a clip that is already body-locked')
    args = parser.parse_args()
    catalog = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
    entry = next(item for item in catalog if item['id'] == ACTION)
    if entry.get('body_locked') and not args.force:
        raise SystemExit('screen is already body-locked; pass --force to re-register it')
    alignment = json.loads((ASSETS / 'frame-alignment.json').read_text(encoding='utf-8'))
    offsets = shift_profile(alignment['actions'][ACTION]['offsets'], entry['frames'])
    source = [load_rgba(ASSETS / ACTION / f'{index + 1:02d}.png')
              for index in range(entry['frames'])]
    placed = [translate(frame, offsets[index]) for index, frame in enumerate(source)]
    reference_index = int(entry.get('loop_start', 0))
    reference = placed[reference_index]
    stable = []
    transforms = []
    coefficients = []
    for frame in placed:
        matrix, cc = register(reference, frame)
        stable.append(warp(frame, matrix))
        transforms.append([[round(float(value), 6) for value in row] for row in matrix])
        coefficients.append(round(cc, 5))
    stable, fitted = fit_frames(stable)
    heads = [head_center(frame) for frame in stable]
    lowers = [lower_body(frame) for frame in stable]
    boxes = [visible_box(frame) for frame in stable]
    names = [f'{index + 1:02d}' for index in range(len(stable))]

    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'frames').mkdir(exist_ok=True)
    for index, frame in enumerate(stable):
        Image.fromarray(frame).save(WORK / 'frames' / f'{index + 1:02d}.png')
    atlas = build_atlas(stable, entry['columns'])
    atlas.save(WORK / 'atlas.png')
    poster = Image.fromarray(stable[reference_index])
    poster.save(WORK / 'poster.png')
    preview_gif(stable, entry['durations'], WORK / 'preview.gif')
    contact_sheet(stable, WORK / 'contact.jpg', names)

    report = {
        'action': ACTION,
        'reference_frame': reference_index + 1,
        'method': 'euclidean-stable-body-ecc',
        'excluded_box': list(EXCLUDED_BOX),
        'frames': len(stable),
        'fitted_shift': fitted,
        'ecc_min': min(coefficients),
        'head_x_range': round(max(h[0] for h in heads) - min(h[0] for h in heads), 3),
        'head_y_range': round(max(h[1] for h in heads) - min(h[1] for h in heads), 3),
        'lower_center_x_range': round(max(l[0] for l in lowers) - min(l[0] for l in lowers), 3),
        'foot_center_x_range': round(max(l[3] for l in lowers) - min(l[3] for l in lowers), 3),
        'floor_range': round(max(b[3] for b in boxes) - min(b[3] for b in boxes), 3),
        'fit_within_canvas': min(b[0] for b in boxes) >= 0 and max(b[2] for b in boxes) <= 255,
        'transforms': transforms,
        'coefficients': coefficients,
    }
    write_json(WORK / 'report.json', report)
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('transforms', 'coefficients')},
                     ensure_ascii=False, indent=2))
    if args.apply:
        apply(stable, atlas, poster, entry, report)


if __name__ == '__main__':
    main()
