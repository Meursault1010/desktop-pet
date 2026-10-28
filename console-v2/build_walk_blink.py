"""Bake walk blink bodies by borrowing the idle blink eyelids.

The walk body is a different drawing from the idle atlas, so its eyes cannot
use the idle frames directly. Frame 1 of the idle half/closed atlases shares
the neutral head pose; its eye patch is scaled and placed over the walk eye
sockets, colour-matched to the surrounding skin, and feathered so the walk
body keeps every non-eye pixel untouched.

Rerun this after rebuilding assets/motion-v2/walk-rig/body.png.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
WALK = ROOT / 'assets/motion-v2/walk-rig'
IDLE = ROOT / 'assets/living-idle'
FRAME = 1

# Eye centres: neutral idle frame -> approved walk body.
IDLE_EYES = ((120.5, 97.5), (157.5, 98.5))
WALK_EYES = ((135.0, 85.0), (167.5, 87.0))
# Soft sockets that still cover every lash pixel of the walk drawing.
SOCKETS = ((119, 73, 152, 97), (151, 75, 185, 99))
FEATHER = 1.8
# The walk iris is taller than the idle one; nudge the borrowed lid down so
# the half blink still closes it far enough.
PATCH_DROP = .75


def _affine():
    sm = tuple((a + b) / 2 for a, b in zip(*IDLE_EYES))
    dm = tuple((a + b) / 2 for a, b in zip(*WALK_EYES))
    scale = math.dist(*WALK_EYES) / math.dist(*IDLE_EYES)
    angle = (math.atan2(WALK_EYES[1][1] - WALK_EYES[0][1],
                        WALK_EYES[1][0] - WALK_EYES[0][0])
             - math.atan2(IDLE_EYES[1][1] - IDLE_EYES[0][1],
                          IDLE_EYES[1][0] - IDLE_EYES[0][0]))
    c, s = math.cos(angle), math.sin(angle)
    a, b, d, e = c / scale, s / scale, -s / scale, c / scale
    return (a, b, sm[0] - a * dm[0] - b * dm[1],
            d, e, sm[1] - d * dm[0] - e * dm[1] - PATCH_DROP)


def _socket_mask():
    mask = Image.new('L', (256, 256), 0)
    draw = ImageDraw.Draw(mask)
    for box in SOCKETS:
        draw.ellipse(box, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(FEATHER))


def build():
    body = Image.open(WALK / 'body.png').convert('RGBA')
    bpx = np.asarray(body).astype(int)
    mask = _socket_mask()
    selected = np.asarray(mask) > 8
    transform = _affine()
    for expression in ('half', 'closed'):
        atlas = Image.open(IDLE / f'{expression}.png').convert('RGBA')
        source = atlas.crop(((FRAME % 8) * 256, (FRAME // 8) * 256,
                             (FRAME % 8 + 1) * 256, (FRAME // 8 + 1) * 256))
        patch = source.transform((256, 256), Image.Transform.AFFINE,
                                 transform, Image.Resampling.BICUBIC)
        px = np.asarray(patch).astype(int)
        # Match only opaque, bright, low-chroma skin so the dark lash keeps
        # its authored colour and the patch edge disappears into the cheek.
        bright = px[:, :, :3].min(axis=2) > 190
        chroma = px[:, :, :3].max(axis=2) - px[:, :, :3].min(axis=2) < 22
        skin = selected & (px[:, :, 3] > 250) & (bpx[:, :, 3] > 250) & bright & chroma
        offset = np.median((bpx[:, :, :3] - px[:, :, :3])[skin], axis=0)
        px[:, :, :3] = np.clip(px[:, :, :3] + offset.reshape(1, 1, 3), 0, 255)
        patch = Image.fromarray(px.astype(np.uint8), 'RGBA')
        patch.putalpha(ImageChops.multiply(patch.getchannel('A'), mask))
        Image.alpha_composite(body, patch).save(WALK / f'body-{expression}.png')
        print(f'body-{expression}.png  skin offset {offset.round(1).tolist()}')


if __name__ == '__main__':
    build()
