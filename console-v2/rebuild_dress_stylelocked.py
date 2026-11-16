"""Build a denser dress-tidying clip from the original keyframes only.

Every new frame is a flow warp between the approved key poses; no generative
repaint is involved, so the idle-state art style stays byte-consistent.
"""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from build_action_inbetweens import interpolate
from build_smoothed_actions import fit_frame

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / 'action-work/smooth/dress/original'
OUT = ROOT / 'output/dress-stylelocked'
# In-betweens per key-pose segment. The last segment includes the settle.
COUNTS = (4, 5, 6, 6, 6)
TARGET = 2600.0
RADIUS = 0.8
MAX_AMOUNT = 220
GRADIENT_CAP = 150.0


def load(key):
    return np.asarray(Image.open(ORIGINAL / f'{key:02d}.png').convert('RGBA')).astype(np.uint8)


def gray_on_sheet(frame):
    alpha = frame[:, :, 3:4] / 255
    colour = frame[:, :, :3] * alpha + 235 * (1 - alpha)
    return np.asarray(Image.fromarray(colour.astype(np.uint8)).convert('L'))


def sharpness(frame):
    import cv2
    gray = gray_on_sheet(frame)
    mask = frame[:, :, 3] > 64
    lap = float(np.var(cv2.Laplacian(gray, cv2.CV_32F)[mask]))
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    grad = float(np.mean(np.hypot(gx, gy)[mask]))
    return lap, grad


def sharpen(frame, amount):
    source = Image.fromarray(frame)
    rgb = source.convert('RGB').filter(
        ImageFilter.UnsharpMask(radius=RADIUS, percent=amount, threshold=2))
    result = rgb.convert('RGBA')
    result.putalpha(source.getchannel('A'))
    pixels = np.asarray(result).copy()
    pixels[pixels[:, :, 3] == 0] = 0
    return pixels


def level_detail(frame):
    before, grad_before = sharpness(frame)
    if before >= TARGET:
        return frame, 0, before, before
    best = (abs(before-TARGET), 0, frame, before)
    for amount in range(20, MAX_AMOUNT+1, 20):
        candidate = sharpen(frame, amount)
        lap, grad = sharpness(candidate)
        if grad <= GRADIENT_CAP and abs(lap-TARGET) < best[0]:
            best = (abs(lap-TARGET), amount, candidate, lap)
    _, amount, chosen, after = best
    return chosen, amount, before, after


def build():
    keys = [load(i) for i in range(1, 7)]
    frames = [keys[0]]
    key_indices = {0}
    reports = []
    for index, count in enumerate(COUNTS):
        left, right = keys[index], keys[index+1]
        strip, review = interpolate(left, right, ('dress', index), ('dress', index+1), profile={})
        picks = np.linspace(1, len(strip)-2, count)
        indices = sorted({int(round(value)) for value in picks})
        while len(indices) < count:
            for value in range(1, len(strip)-1):
                if value not in indices:
                    indices.append(value)
                    break
            indices.sort()
        for pick in indices:
            frames.append(fit_frame(strip[pick]))
        frames.append(right)
        key_indices.add(len(frames)-1)
        reports.append({'segment': [index+1, index+2], 'count': count,
                        **{key: review[key] for key in ('accepted','largest_step','construction','playback_peak')}})
    return keys, frames, key_indices, reports


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    keys, frames, key_indices, reports = build()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'frames').mkdir(exist_ok=True)
    levels = []
    for index, frame in enumerate(frames):
        if index in key_indices:
            # Keep the original key poses untouched; only flow frames are softened.
            before = sharpness(frame)[0]
            chosen, amount, after = frame, 0, before
        else:
            chosen, amount, before, after = level_detail(frame)
        Image.fromarray(chosen).save(OUT/'frames'/f'{index+1:02d}.png')
        levels.append((index+1, round(before, 1), amount, round(after, 1)))
    durations = []
    for index in range(len(frames)):
        durations.append(100 if index in key_indices else 55)
    durations[-1] = 180
    images = []
    for frame in frames:
        bg = Image.new('RGB', (256, 256), '#303b4c')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    images[0].save(OUT/'dress-stylelocked.gif', save_all=True,
                   append_images=images[1:], duration=durations, loop=0)
    print('frames', len(frames), 'duration', sum(durations), 'ms')
    print('sharpness', levels)
    print('segments', reports)
    if args.apply:
        raise SystemExit('apply is intentionally left for review; the runtime action is unchanged')


if __name__ == '__main__':
    main()
