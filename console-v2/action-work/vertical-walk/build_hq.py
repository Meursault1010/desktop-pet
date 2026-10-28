"""Render the detailed vertical walk at 512px source resolution."""
import os
from pathlib import Path

os.environ.setdefault('VERTICAL_WALK_SCALE', '2')

import build
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = build.ROOT
OUT = Path('C:/Users/meursault/Documents/ChatGPT/桌面宠物/console-v2/output/vertical-walk-v5-hq')
OUT.mkdir(parents=True, exist_ok=True)
FONT = 'C:/Windows/Fonts/msyh.ttc'


def label(draw, xy, text, size=22, fill='#eef5fb'):
    draw.text(xy, text, font=ImageFont.truetype(FONT, size), fill=fill)


def contact(frames, path):
    cell = 512
    top = 48
    background = '#263747'
    sheet = Image.new('RGB', (cell * 4, (top + cell) * 2), background)
    draw = ImageDraw.Draw(sheet)
    quarter = [round(build.FRAMES * i / 4) for i in range(4)]
    for row, (name, title) in enumerate((('up', '向上走 · 背身 · 512 源'),
                                         ('down', '向下走 · 正身 · 512 源'))):
        y = row * (top + cell) + top
        label(draw, (14, row * (top + cell) + 12), title, 22)
        for column, index in enumerate(quarter):
            tile = Image.new('RGBA', (cell, cell), '#1d2b38')
            tile.alpha_composite(frames[name][index])
            sheet.paste(tile.convert('RGB'), (column * cell, y))
            label(draw, (column * cell + 10, y + 8), f'{index:02d}', 16, '#9fb3c8')
    sheet.save(path)


def gif(frames, name, path):
    canvas_size = 600
    frames_out = []
    for index, frame in enumerate(frames):
        canvas = Image.new('RGB', (canvas_size, canvas_size), '#2a3b4d')
        draw = ImageDraw.Draw(canvas)
        label(draw, (18, 12), '向上走 · 背身' if name == 'up' else '向下走 · 正身', 22)
        canvas.paste(frame.convert('RGB'), (44, 50), frame)
        frames_out.append(canvas)
    frames_out[0].save(path, save_all=True, append_images=frames_out[1:],
                       duration=build.FRAME_MS, loop=0, optimize=True)


def still(frames, name, path):
    index = build.FRAMES // 4
    canvas = Image.new('RGB', (600, 600), '#2a3b4d')
    draw = ImageDraw.Draw(canvas)
    label(draw, (18, 12), '向上走 · 背身' if name == 'up' else '向下走 · 正身', 22)
    canvas.paste(frames[index].convert('RGB'), (44, 50), frames[index])
    canvas.save(path)


def main():
    data = {}
    for name in ('up', 'down'):
        image = build.normalize(build.cutout(ROOT / 'raw' / f'{name}-master.png'))
        image.save(ROOT / 'normalized' / f'{name}-hq.png')
        cut_y, split_x, legs, masks = build.leg_analysis(image)
        body, layers = build.make_layers(image, cut_y, masks)
        frames = [build.render(body, layers, index / build.FRAMES)
                  for index in range(build.FRAMES)]
        data[name] = frames
        print(name, 'cut', cut_y, 'split', round(split_x, 2),
              'feet', [round(layer['foot_x'], 1) for layer in layers])
        frame_dir = ROOT / 'preview-hq' / f'walk-{name}'
        frame_dir.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(frames):
            frame.save(frame_dir / f'{index:02}.png')
        still(frames, name, OUT / f'{name}-walk-still.png')
        gif(frames, name, OUT / f'{name}-walk.gif')
    contact(data, OUT / 'vertical-walk-contact.png')


if __name__ == '__main__':
    main()
