"""Bake the approved master into a translation-only walk with whole legs.

The skirt hem and its outline stay on the body. Each leg is cut per column at
its first visible skin row, so the visible thigh belongs to the leg instead of
being left behind as a static patch. The leg mask is extended up to the hip
line with the thigh's own skin tone; the skirt always covers that extension.
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/motion-v2'
SAMPLES = 120
AMPLITUDE = 16.
LIFT = 15.
FAR_LIFT = .8
BASELINE = 249.
UPSCALE = 4
BODY_DROP = 0.
STANCE_GAP = 10.5
WALK_CENTER = 128.
LEG_SCAN_START = 840
LEG_SCAN_END = 940
HIP = 204
LEG_X0 = 85
LEG_X1 = 180


def sole(image):
    alpha = np.asarray(image.getchannel('A'))
    ys, xs = np.where(alpha > 160)
    bottom = int(ys.max())
    return float(np.median(xs[ys >= bottom])), float(bottom)


def translate(image, x, y):
    return image.transform(image.size, Image.Transform.AFFINE,
                           (1, 0, -x*UPSCALE, 0, 1, -y*UPSCALE),
                           Image.Resampling.BICUBIC)


def _leg_cut(hard):
    """First row below the skirt with two separated leg runs and no hem strip."""
    for y in range(LEG_SCAN_START // UPSCALE, LEG_SCAN_END // UPSCALE):
        runs, start = [], None
        for x, value in enumerate(hard[y]):
            if value and start is None:
                start = x
            elif not value and start is not None:
                runs.append((start, x))
                start = None
        if start is not None:
            runs.append((start, len(hard[y])))
        runs = [run for run in runs if run[1] - run[0] >= 2]
        if len(runs) != 2:
            continue
        widths = [run[1] - run[0] for run in runs]
        gap = runs[1][0] - runs[0][1]
        if all(2 <= width <= 25 for width in widths) and gap >= 20:
            return y, (runs[0][1] + runs[1][0]) / 2
    raise ValueError('无法找到裙摆下的双腿分离线')


def _skin_mask(rgb):
    peach = ((rgb[:, :, 0] > rgb[:, :, 2] + 8)
             & (rgb[:, :, 0] > rgb[:, :, 1] + 3)
             & (rgb[:, :, 0] > 170))
    shadow = ((rgb[:, :, 0] > rgb[:, :, 1] + 12)
              & (rgb[:, :, 0] > 90)
              & (rgb[:, :, 0] > rgb[:, :, 2] - 25))
    return peach | shadow


def _first_leg_row(alpha, x, hip):
    """First leg pixel after a clear gap under the skirt."""
    ys = np.flatnonzero(alpha[hip:, x] > 0)
    if not len(ys):
        return -1
    if ys[0] > 2:
        return hip + int(ys[0])
    gaps = np.flatnonzero(np.diff(ys) > 1)
    if len(gaps):
        return hip + int(ys[gaps[0] + 1])
    return -1


def _cuts(hard, skin, alpha, split):
    """Per-column first visible skin row, falling back to the leg outline."""
    cuts = np.full(hard.shape[1], -1, int)
    tops = {}
    for x in range(LEG_X0, LEG_X1):
        rows = np.flatnonzero(skin[HIP:226, x] & (hard[HIP:226, x] > 0))
        skin_top = HIP + int(rows[0]) if len(rows) else -1
        if skin_top >= 0:
            tops[x] = skin_top
        gap = _first_leg_row(alpha, x, HIP)
        if skin_top >= 0:
            cuts[x] = min(skin_top, gap) if gap >= 0 else skin_top
        else:
            cuts[x] = gap
    far_skin = [x for x in tops if x < split]
    near_skin = [x for x in tops if x >= split]

    def outer(x):
        if x < split:
            return bool(far_skin) and x < min(far_skin)
        return bool(near_skin) and x > max(near_skin)

    skin_cols = sorted(tops)
    for x in range(LEG_X0, LEG_X1):
        if x in tops or not alpha[216:, x].any():
            continue
        same = [c for c in skin_cols if (c < split) == (x < split)]
        if not same:
            continue
        near = min(same, key=lambda c: abs(c - x))
        if abs(near - x) > 8:
            continue
        base = tops[near] + (2 if outer(x) else 0)
        if cuts[x] < 0 or cuts[x] - base >= 3:
            cuts[x] = base
    return cuts, tops


def _clean(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    clean = np.zeros_like(mask)
    for index in range(1, count):
        if stats[index, cv2.CC_STAT_AREA] >= 120:
            clean |= (labels == index).astype(np.uint8)
    return clean


def segment(base, split):
    rgba = np.asarray(base)
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3].astype(np.int16)
    hard = cv2.morphologyEx((alpha > 100).astype(np.uint8),
                            cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    skin = _skin_mask(rgb)
    cuts, tops = _cuts(hard, skin, alpha, split)

    masks = []
    for left in (True, False):
        mask = np.zeros_like(hard)
        cols = range(LEG_X0, split) if left else range(split, LEG_X1)
        for x in cols:
            cut = cuts[x]
            if cut < 0:
                continue
            start = HIP if x in tops else cut
            mask[start:, x] = hard[start:, x]
        masks.append(_clean(mask))
    return masks, cuts, tops



def _to_256(base, alpha):
    pixels = np.asarray(base).copy()
    pixels[:, :, 3] = alpha
    return Image.fromarray(pixels, 'RGBA')


def build():
    base = Image.open(ASSETS / 'approved-walk-master.png').convert('RGBA')
    pixels = np.asarray(base)
    base_alpha = pixels[:, :, 3].copy()
    base_rgb = pixels[:, :, :3].copy()
    hard = cv2.morphologyEx((base_alpha > 100).astype(np.uint8),
                            cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    _, split = _leg_cut(hard)
    split = int(round(split))
    masks, cuts, tops = segment(base, split)

    body_alpha = base_alpha.copy()
    for x in range(LEG_X0, LEG_X1):
        cut = cuts[x]
        if cut >= 0:
            body_alpha[cut:, x] = 0
    body = _to_256(base, body_alpha)
    legs = []
    for index, mask in enumerate(masks):
        alpha = (base_alpha.astype(np.float32) * mask).clip(0, 255)
        rgb = base_rgb.copy()
        cols = range(LEG_X0, split) if index == 0 else range(split, LEG_X1)
        for x in cols:
            if x not in tops:
                continue
            cut = cuts[x]
            top = tops[x]
            if cut <= HIP:
                continue
            skin = np.median(rgb[top:min(256, top + 3), x],
                             axis=0).astype(np.uint8)
            rgb[HIP:cut, x] = skin
        legs.append(Image.fromarray(
            np.dstack([rgb, alpha.astype(np.uint8)]), 'RGBA'))

    body_hi = body.resize((256 * UPSCALE, 256 * UPSCALE),
                          Image.Resampling.LANCZOS)
    legs_hi = [leg.resize((256 * UPSCALE, 256 * UPSCALE),
                          Image.Resampling.LANCZOS) for leg in legs]

    rig_folder = ASSETS / 'walk-rig'
    rig_folder.mkdir(exist_ok=True)
    body.save(rig_folder / 'body.png')
    for index, leg in enumerate(legs):
        leg.save(rig_folder / f'leg-{index}.png')

    anchors = [sole(leg) for leg in legs]
    homes = [(WALK_CENTER - STANCE_GAP / 2, anchors[0][1]),
             (WALK_CENTER + STANCE_GAP / 2, anchors[1][1])]
    rig = []
    for index, leg in enumerate(legs):
        side_tops = [cut for x, cut in tops.items()
                     if (x < split) == (index == 0)]
        alpha = np.asarray(leg.getchannel('A'))
        boundary = []
        for x in range(256):
            ys = np.flatnonzero(alpha[:, x] > 160)
            if len(ys):
                boundary.append([float(x), float(ys[-1])])
        for y in range(256):
            xs = np.flatnonzero(alpha[y] > 160)
            if len(xs):
                boundary.extend([[float(xs[0]), float(y)],
                                 [float(xs[-1]), float(y)]])
        rig.append(dict(anchor=list(anchors[index]), home=list(homes[index]),
                        pivot=[120, 207] if index == 0 else [136, 207],
                        sock_top=float(np.median(side_tops)) if side_tops else HIP,
                        boundary=boundary))
    (rig_folder / 'rig.json').write_text(json.dumps(rig), encoding='utf-8')

    images, contacts = [], []
    for i in range(SAMPLES):
        phase = i / SAMPLES
        support = 1 if phase < .5 else 0
        t = (phase * 2) % 1
        image = Image.new('RGBA', body_hi.size)
        contact = [0., 0.]
        for leg, (source, anchor, home) in enumerate(zip(legs_hi, anchors, homes)):
            if leg == support:
                shift = AMPLITUDE * (1 - 2 * t)
                lift = 0.
                contact = [home[0] + shift, home[1]]
            else:
                shift = AMPLITUDE * (-1 - 2 * t + 12 * t * t - 8 * t * t * t)
                lift = (LIFT * (FAR_LIFT if leg == 0 else 1.)
                        * math.sin(math.pi * t) ** 2)
            image.alpha_composite(translate(source, home[0] - anchor[0] + shift,
                                            -lift))
        image.alpha_composite(translate(body_hi, 0, BODY_DROP))
        images.append(image.resize((256, 256), Image.Resampling.LANCZOS))
        contacts.append(contact)

    meta_path = ASSETS / 'clips.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    for name, keys, points in [
        ('walk-right', images, contacts),
        ('walk-left', [im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for im in images],
         [[255 - x, y] for x, y in contacts]),
    ]:
        folder = ASSETS / name
        folder.mkdir(exist_ok=True)
        for i, image in enumerate(keys):
            image.save(folder / f'{i:02}.png')
        boxes = [im.getbbox() for im in keys]
        meta[name].update(frames=SAMPLES, stride=4 * AMPLITUDE * 160 / 256,
                          baseline=BASELINE / 256, contacts=points,
                          bounds=[min(b[0] for b in boxes) / 256,
                                  min(b[1] for b in boxes) / 256,
                                  max(b[2] for b in boxes) / 256,
                                  max(b[3] for b in boxes) / 256],
                          method='thigh-cut-translation-walk-v6',
                          optical_flow=False)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n',
                         encoding='utf-8')
    return images


if __name__ == '__main__':
    build()
    print('Rebuilt horizontal walk with whole-leg thigh cuts and clean skirt hem.')
