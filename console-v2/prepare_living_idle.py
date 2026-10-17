"""Offline continuous deformation of existing artwork; no image-generation API.

Pillow/numpy/OpenCV are build-time only. Runtime uses three cached Qt atlases.
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
COUNT = 64
SIZE = 256
DURATION = 4.8


def prepare():
    source = ROOT / 'assets/ice-blue-idle'
    output = ROOT / 'assets/living-idle'
    output.mkdir(parents=True, exist_ok=True)
    qa = ROOT / 'pet-sprite-work/living-qa'
    qa.mkdir(parents=True, exist_ok=True)
    base = np.array(Image.open(source / '01.png').convert('RGBA')).astype(np.float32) / 255
    yy, xx = np.mgrid[:384, :384].astype(np.float32)
    # Change only the eye interior, preserving hair, accessories and body identity.
    eye_mask = np.clip((xx-143)/8, 0, 1) * np.clip((237-xx)/8, 0, 1)
    eye_mask *= np.clip((yy-128)/4, 0, 1) * np.clip((160-yy)/4, 0, 1)
    expressions = {'open': base}
    for name, file in [('half', '04.png'), ('closed', '10.png')]:
        art = np.array(Image.open(source / file).convert('RGBA')).astype(np.float32)/255
        expressions[name] = base*(1-eye_mask[..., None]) + art*eye_mask[..., None]
    atlases = {name: Image.new('RGBA', (SIZE*8, SIZE*8)) for name in expressions}
    previews = []
    for index in range(COUNT):
        phase = 2*math.pi*index/COUNT
        breath = math.sin(phase)
        anchor = np.clip((369-yy)/72, 0, 1)
        # ~1.5px up/down at default size; no sliding feet.
        dy = -3.6*breath*anchor
        chest = np.exp(-((yy-226)/60)**2)
        dx = (xx-192)*.014*breath*chest
        side = np.clip((np.abs(xx-192)-43)/35, 0, 1)
        hair = side*np.clip((yy-138)/78, 0, 1)*np.clip((334-yy)/34, 0, 1)
        lag = (yy-138)/125
        sway = 5.5*np.sin(phase-lag) + 1.4*np.sin(2*phase+xx/95-lag)
        dx += hair*sway
        dy += hair*.85*np.sin(phase-lag+.7)
        # Keep all facial features coherent; side weights are zero over the face.
        map_x = (xx-dx).astype(np.float32)
        map_y = (yy-dy).astype(np.float32)
        for name, art in expressions.items():
            # Premultiplied sampling prevents dark fringes around white hair.
            premult = art.copy()
            premult[:, :, :3] *= premult[:, :, 3:4]
            warped = cv2.remap(premult, map_x, map_y, cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT)
            warped = cv2.resize(warped, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
            alpha = warped[:, :, 3:4]
            warped[:, :, :3] = np.divide(warped[:, :, :3], alpha,
                                        out=np.zeros_like(warped[:, :, :3]), where=alpha > 1e-6)
            pixels = np.uint8(np.clip(warped*255, 0, 255))
            pixels[pixels[:, :, 3] == 0] = 0
            frame = Image.fromarray(pixels)
            atlases[name].paste(frame, ((index%8)*SIZE, (index//8)*SIZE))
            if name == 'open':
                previews.append(frame)
    for name, atlas in atlases.items():
        atlas.save(output / f'{name}.png')
    (output / 'manifest.json').write_text(json.dumps({
        'version': 1, 'frames': COUNT, 'cell': SIZE, 'columns': 8,
        'duration': DURATION, 'expressions': list(expressions),
        'source': 'ice-blue-idle/01.png,04.png,10.png',
        'motion': 'continuous grounded breathing and delayed side-hair sway',
    }, indent=2), encoding='utf-8')
    sheet = Image.new('RGB', (256*4, 290*2), '#35414d')
    draw = ImageDraw.Draw(sheet)
    for i, index in enumerate(range(0, COUNT, 8)):
        x, y = (i%4)*256, (i//4)*290
        sheet.paste(previews[index], (x, y), previews[index])
        draw.text((x+12, y+264), f't={index*DURATION/COUNT:.1f}s', fill='white')
    sheet.save(qa / 'motion-contact.jpg')
    movie = []
    for cycle in range(2):
        for i, frame in enumerate(previews):
            # QA preview includes one representative blink per cycle, runtime is random.
            name = 'closed' if i in (37,38) else 'half' if i in (36,39) else 'open'
            if name != 'open':
                frame = atlases[name].crop(((i%8)*SIZE, (i//8)*SIZE, (i%8+1)*SIZE, (i//8+1)*SIZE))
            bg = Image.new('RGB', (SIZE, SIZE), '#35414d' if cycle == 0 else '#f2f4f9')
            bg.paste(frame, mask=frame.getchannel('A'))
            movie.append(bg)
    movie[0].save(qa / 'living-idle.gif', save_all=True, append_images=movie[1:],
                  duration=round(DURATION*1000/COUNT), loop=0)
    print(f'Built {COUNT} continuous phases x 3 eye states: {output}')


if __name__ == '__main__':
    prepare()
