"""Dense, style-locked dress clip built only from the original keyframes."""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from skimage import restoration

from build_action_inbetweens import interpolate
from build_smoothed_actions import fit_frame

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / 'action-work/smooth/dress/original'
RESTORE_BLEND = 0.45
RESTORE_ITERATIONS = 8


def load(key):
    return np.asarray(Image.open(ORIGINAL / f'{key:02d}.png').convert('RGBA')).astype(np.uint8)


def psf(sigma=0.7):
    size = int(sigma * 6) | 1
    axis = np.arange(size) - size // 2
    xx, yy = np.meshgrid(axis, axis)
    kernel = np.exp(-(xx ** 2 + yy ** 2) / (2 * sigma * sigma))
    return kernel / kernel.sum()


def shift(frame, dx):
    canvas = np.zeros_like(frame)
    if dx >= 0:
        canvas[:, dx:] = frame[:, :256-dx]
    else:
        canvas[:, :256+dx] = frame[:, -dx:]
    return canvas


def foot_center(frame):
    alpha = frame[:, :, 3]
    ys, xs = np.where(alpha > 32)
    bottom = ys >= ys.max() - 14
    return float(xs[bottom].mean())


def restore(frame):
    arr = frame.astype(np.float32)
    alpha = arr[:, :, 3:4] / 255
    rgb = arr[:, :, :3]
    on_gray = rgb * alpha + 235 * (1 - alpha)
    kernel = psf()
    sharp = np.zeros_like(on_gray)
    for channel in range(3):
        sharp[:, :, channel] = restoration.richardson_lucy(
            on_gray[:, :, channel] / 255, kernel,
            num_iter=RESTORE_ITERATIONS, clip=False)
    sharp = np.clip(sharp * 255, 0, 255)
    blend = rgb * (1 - RESTORE_BLEND) + sharp * RESTORE_BLEND
    result = np.dstack([np.clip(blend, 0, 255), arr[:, :, 3]]).astype(np.uint8)
    result[result[:, :, 3] == 0] = 0
    return result


def build(counts):
    keys = [load(i) for i in range(1, 7)]
    frames = [keys[0]]
    key_indices = {0}
    for segment, count in enumerate(counts):
        strip, _ = interpolate(keys[segment], keys[segment+1],
                               ('dress', segment), ('dress', segment+1), profile={})
        picks = sorted({int(round(value)) for value in np.linspace(1, len(strip)-2, count)})
        for pick in picks:
            frames.append(fit_frame(strip[pick]))
        frames.append(keys[segment+1])
        key_indices.add(len(frames)-1)
    return frames, key_indices


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='output/dress-stylelocked-dense')
    parser.add_argument('--counts', default='8,8,9,9,9')
    parser.add_argument('--key-ms', type=int, default=80)
    parser.add_argument('--inbetween-ms', type=int, default=30)
    parser.add_argument('--final-ms', type=int, default=120)
    return parser.parse_args()


def main():
    args = parse_args()
    out = ROOT / args.out
    counts = tuple(int(value) for value in args.counts.split(','))
    if len(counts) != 5:
        raise SystemExit('counts must contain five segments')
    out.mkdir(parents=True, exist_ok=True)
    (out/'frames').mkdir(exist_ok=True)
    for old in (out/'frames').glob('*.png'):
        old.unlink()
    frames, key_indices = build(counts)
    fixed = []
    for index, frame in enumerate(frames):
        frame = shift(frame, int(round(128 - foot_center(frame))))
        if index not in key_indices:
            frame = restore(frame)
        fixed.append(frame)
        Image.fromarray(frame).save(out/'frames'/f'{index+1:02d}.png')
    durations = [args.key_ms if index in key_indices else args.inbetween_ms
                 for index in range(len(fixed))]
    durations[-1] = args.final_ms
    images = []
    for frame in fixed:
        bg = Image.new('RGB', (256, 256), '#303b4c')
        bg.paste(Image.fromarray(frame), (0, 0), Image.fromarray(frame))
        images.append(bg)
    images[0].save(out/f'{out.name}.gif', save_all=True,
                   append_images=images[1:], duration=durations, loop=0)
    for part, (start, end) in enumerate(((0, (len(fixed)+1)//2), ((len(fixed)+1)//2, len(fixed))), 1):
        cols, cell = 7, 260
        rows = (end-start+cols-1)//cols
        sheet = Image.new('RGB', (cols*cell, rows*(cell+20)), (48, 59, 76))
        draw = ImageDraw.Draw(sheet)
        for offset, index in enumerate(range(start, end)):
            thumb = Image.fromarray(fixed[index]).resize((cell, cell), Image.Resampling.LANCZOS)
            x, y = offset % cols * cell, offset // cols * (cell + 20)
            sheet.paste(thumb, (x, y + 20), thumb)
            draw.text((x + 4, y + 2), str(index+1), fill=(220, 230, 240))
        sheet.save(out/f'audit-{part}.png')
    feet = [foot_center(frame) for frame in fixed]
    print('frames', len(fixed), 'duration', sum(durations), 'ms',
          'fps', round(len(fixed)/(sum(durations)/1000), 1))
    print('key indices', sorted(index+1 for index in key_indices))
    print('foot range', round(min(feet), 2), round(max(feet), 2))


if __name__ == '__main__':
    main()
