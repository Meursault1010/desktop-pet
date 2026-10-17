"""Offline artwork preparation. Requires Pillow/numpy/OpenCV, not runtime dependencies.

Original artwork is never modified. Usage: python prepare_idle_assets.py SOURCE
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def build(source, root):
    output = root / 'assets/ice-blue-idle'
    output.mkdir(parents=True, exist_ok=True)
    qa = root / 'pet-sprite-work/final-qa'
    qa.mkdir(parents=True, exist_ok=True)
    frames = []
    manifest = []
    for index, file in enumerate(sorted(source.glob('idle_sequence_*.png')), 1):
        cv2.setRNGSeed(123)
        rgba = np.array(Image.open(file).convert('RGBA').resize((512, 512), Image.Resampling.LANCZOS))
        mask = np.zeros((512, 512), np.uint8)
        cv2.grabCut(cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR), mask,
                    (35, 4, 442, 504), np.zeros((1, 65), np.float64),
                    np.zeros((1, 65), np.float64), 4, cv2.GC_INIT_WITH_RECT)
        matte = ((mask == 1) | (mask == 3)).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(matte)
        assert count > 1, file
        matte = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
        rgba[:, :, 3] *= matte
        rgba[rgba[:, :, 3] == 0] = 0
        extracted = Image.fromarray(rgba)
        bbox = extracted.getbbox()
        # Normalize head-to-foot height and ground line, without fitting by hair width.
        sprite = extracted.crop(bbox)
        factor = 340 / sprite.height
        sprite = sprite.resize((round(sprite.width * factor), 340), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (384, 384))
        canvas.alpha_composite(sprite, ((384 - sprite.width) // 2, 36))
        clean = np.array(canvas)
        clean[clean[:, :, 3] == 0] = 0
        canvas = Image.fromarray(clean)
        name = f'{index:02d}.png'
        canvas.save(output / name)
        frames.append(canvas)
        manifest.append({'file': name, 'source': file.name, 'source_bounds': bbox})
    assert len(frames) == 12, 'Expected 12 input frames'
    (output / 'manifest.json').write_text(json.dumps({'canvas': [384, 384], 'frames': manifest}, ensure_ascii=False, indent=2), encoding='utf-8')
    sheet = Image.new('RGB', (960, 768), '#36414d')
    draw = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        x, y = (i % 4) * 240, (i // 4) * 256
        if i % 2:
            draw.rectangle((x, y, x + 239, y + 255), fill='#f4f6fa')
        sheet.paste(frame.resize((230, 230), Image.Resampling.LANCZOS), (x + 5, y), frame.resize((230, 230), Image.Resampling.LANCZOS))
        draw.text((x + 8, y + 236), f'Frame {i+1:02d}', fill='#7996b4')
    sheet.save(qa / 'contact-sheet.jpg')
    # Representative schedule only. Actual application schedules new random intervals.
    sequence = [(1, 2100), (4, 65), (10, 110), (6, 85), (1, 3300),
                (2, 180), (3, 180), (1, 1700), (4, 65), (10, 95),
                (6, 150), (10, 95), (11, 85), (12, 2600)]
    previews = []
    for frame, duration in sequence:
        bg = Image.new('RGB', (384, 384), '#36414d')
        bg.paste(frames[frame-1], mask=frames[frame-1].getchannel('A'))
        previews.append(bg)
    previews[0].save(qa / 'idle-preview.gif', save_all=True, append_images=previews[1:],
                     duration=[duration for _, duration in sequence], loop=0)
    print(f'Exported {len(frames)} transparent aligned frames to {output}')


if __name__ == '__main__':
    build(Path(sys.argv[1]), Path(__file__).resolve().parent)
