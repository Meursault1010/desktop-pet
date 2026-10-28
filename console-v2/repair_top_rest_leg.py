"""Restore the hollow left calf shared by the climb/top-rest pose.

The generated climb[5] keyframe lost the left calf fill. Adjacent climb[6] has
the same seated pose with both legs intact, so its left leg is aligned to the
broken shoe and composited into the hole. Run after build_autoplay_assets.py,
then rebuild the affected bridges:

    python build_action_inbetweens.py --actions play-climb-up play-climb-down play-top-rest
"""
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image

import build_autoplay_assets as build

ROOT = Path(__file__).resolve().parent
POLYGON = ((58, 140), (96, 142), (100, 184), (54, 188), (50, 152))
TARGETS = (('play-top-rest', 0), ('play-top-rest', 1),
           ('play-climb-up', 5), ('play-climb-down', 0))


def layout_frames():
    climb = build.cells(build.WORK/'climb-keyframes.png')
    boxes = [im.getbbox() for im in climb]
    ref = boxes[0]
    left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
    right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
    factor = min(222/(ref[3]-ref[1]), 248/(right-left), 248/(bottom-top))
    dx = max(3-left*factor, min(128-(ref[0]+ref[2])/2*factor, 253-right*factor))
    dy = max(3-top*factor, min(251-ref[3]*factor, 253-bottom*factor))
    frames = []
    for image, box in zip(climb, boxes):
        crop = image.crop(box)
        sprite = crop.resize((round(crop.width*factor), round(crop.height*factor)),
                             Image.Resampling.LANCZOS)
        x, y = round(box[0]*factor+dx), round(box[1]*factor+dy)
        frame = Image.new('RGBA', (256, 256))
        frame.alpha_composite(sprite, (x, y))
        frames.append(frame)
    return frames


def left_shoe(frame):
    rgba = np.array(frame.convert('RGBA')).astype(int)
    rgb, alpha = rgba[:, :, :3], rgba[:, :, 3]
    mask = ((alpha > 100) & (rgb[:, :, 2] > rgb[:, :, 0]+20)
            & (rgb[:, :, 2] > 120) & (rgb[:, :, 1] > 70)
            & (np.indices(alpha.shape)[0] > 185)).astype(np.uint8)
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask, 8)
    shoes = [(stats[i, cv2.CC_STAT_AREA], centers[i])
             for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= 60]
    return min(shoes, key=lambda item: item[1][0])[1] if shoes else None


def enclosed_hole(alpha):
    solid = (alpha > 20).astype(np.uint8)
    inverse = (1-solid).astype(np.uint8)
    flooded = inverse.copy()
    mask = np.zeros((alpha.shape[0]+2, alpha.shape[1]+2), np.uint8)
    for x, y in ((0, 0), (alpha.shape[1]-1, 0),
                 (0, alpha.shape[0]-1), (alpha.shape[1]-1, alpha.shape[0]-1)):
        if flooded[y, x]:
            cv2.floodFill(flooded, mask, (x, y), 2)
    hole = (inverse == 1) & (flooded != 2)
    roi = np.zeros_like(hole)
    roi[135:190, 60:105] = 1
    return hole & roi


def premultiply(image):
    result = image.copy()
    result[:, :, :3] *= image[:, :, 3:4]/255
    return result


def unpremultiply(image):
    result = image.copy()
    rgb = np.divide(result[:, :, :3]*255, result[:, :, 3:4],
                    out=np.zeros_like(result[:, :, :3]), where=result[:, :, 3:4] > 0)
    result[:, :, :3] = np.clip(np.rint(rgb), 0, 255)
    result[:, :, 3] = np.clip(np.rint(result[:, :, 3]), 0, 255)
    return result


def repair(target, donor):
    source = np.array(target.convert('RGBA')).astype(np.float32)
    hole = enclosed_hole(source[:, :, 3].astype(np.uint8))
    if hole.sum() < 200:
        # Already repaired; keep the frame so the script can be rerun safely.
        return target
    target_shoe, donor_shoe = left_shoe(target), left_shoe(donor)
    if target_shoe is None or donor_shoe is None:
        raise ValueError('Could not align the donor shoe')
    dx, dy = target_shoe[0]-donor_shoe[0], target_shoe[1]-donor_shoe[1]
    shifted = donor.transform(donor.size, Image.AFFINE,
                              (1, 0, -dx, 0, 1, -dy), resample=Image.BICUBIC)
    shifted = np.array(shifted).astype(np.float32)
    mask = np.zeros((256, 256), np.uint8)
    cv2.fillPoly(mask, [np.array(POLYGON, np.int32)], 255)
    weight = (mask.astype(np.float32)/255)*(shifted[:, :, 3] > 0)
    weight = cv2.GaussianBlur(weight, (5, 5), 1.0)
    weight = (weight*(shifted[:, :, 3]/255.0))[:, :, None]
    blended = unpremultiply(premultiply(source)*(1-weight) + premultiply(shifted)*weight)
    result = Image.fromarray(blended.astype(np.uint8))
    if enclosed_hole(np.array(result)[:, :, 3]).sum() > 40:
        raise ValueError('The repaired frame still has a visible hole')
    return result


def write_action(action, index, frame):
    folder = ROOT/'assets/actions'/action
    atlas = Image.open(folder/'atlas.png').convert('RGBA')
    atlas.paste(frame, (index % 4*256, index//4*256))
    atlas.save(folder/'atlas.png')
    frame.save(folder/f'{index+1:02d}.png')
    if index == 0:
        frame.save(folder/'poster.png')
    public = ROOT/'frontend/public/actions'/action
    atlas.save(public/'atlas.webp', lossless=True, exact=True)
    Image.open(folder/'poster.png').convert('RGBA').save(
        public/'poster.webp', lossless=True, exact=True)


def main():
    frames = layout_frames()
    donor = frames[6]
    repaired = repair(frames[5], donor)
    for action, index in TARGETS:
        write_action(action, index, repaired)
    print('Repaired', ', '.join(f'{action}:{index}' for action, index in TARGETS))
    print('Rebuild bridges: python build_action_inbetweens.py '
          '--actions play-climb-up play-climb-down play-top-rest')


if __name__ == '__main__':
    sys.exit(main())
