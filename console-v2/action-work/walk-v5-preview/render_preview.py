"""Render the crossing stride: live sheet, foot close-ups and a GIF."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import QRectF

OUT = Path(__file__).resolve().parent
FONT = 'C:/Windows/Fonts/msyh.ttc'
FONT_BOLD = 'C:/Windows/Fonts/msyhbd.ttc'
app = QApplication.instance() or QApplication([])

from walk_rig import paint, HOME, NEAR_LEG, FAR_LEG
from locomotion import walk_stride

NEAR_FLOOR = HOME[NEAR_LEG][1]
FAR_FLOOR = HOME[FAR_LEG][1]


def sprite(name, phase, size=256):
    image = QImage(size, size, QImage.Format.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    paint(painter, QRectF(0, 0, size, size), name, phase * walk_stride(name))
    painter.end()
    return Image.frombuffer('RGBA', (size, size), bytes(image.constBits()), 'raw', 'RGBA',
                            image.bytesPerLine(), 1).copy()


def checker(width, height, cell=8):
    image = Image.new('RGB', (width, height), '#f6f3ec')
    draw = ImageDraw.Draw(image)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill='#e9e5dc')
    return image


def font(size, bold=False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def dashed(draw, x0, x1, y, fill, dash=18, gap=10):
    x = x0
    while x < x1:
        draw.line([x, y, min(x + dash, x1), y], fill=fill, width=2)
        x += dash + gap


def actual_size_sheet():
    phases = [i / 8 for i in range(8)]
    cell, gap, label = 160, 10, 76
    width = label + len(phases) * (cell + gap) + 22
    height = 78 + 2 * 196 + 58
    sheet = Image.new('RGB', (width, height), '#faf8f2')
    draw = ImageDraw.Draw(sheet)
    draw.text((24, 18), 'Yuki · 走路动作 · 双脚交叠修正', font=font(26, True), fill='#2d3440')
    draw.text((24, 52), '实际显示尺寸 160px，直接来自运行时 walk_rig；两脚绕裙摆中线交错，经过时相叠。',
              font=font(14), fill='#6f7580')
    draw.line([24, 76, width - 24, 76], fill='#ded9cc', width=1)
    for row, (name, title) in enumerate((('walk-right', '向右走'), ('walk-left', '向左走'))):
        top = 88 + row * 196
        draw.text((24, top + 64), title, font=font(17, True), fill='#39414d')
        for col, phase in enumerate(phases):
            x = label + col * (cell + gap)
            bg = checker(cell, cell)
            ImageDraw.Draw(bg).line([0, 156, cell, 156], fill='#cfc8b8', width=1)
            image = sprite(name, phase, 160)
            bg.paste(image, (0, 0), image)
            sheet.paste(bg, (x, top))
            draw.text((x, top + cell + 6), f'{phase * 100:.1f}%', font=font(12), fill='#8a8f98')
    draw.text((24, height - 44),
              '两腿仍按半周期交错，只做刚体平移：鞋与袜保持原画笔触 1:1，无旋转、无缩放、无重绘。',
              font=font(14), fill='#4a515c')
    draw.text((24, height - 24),
              '远脚保持原画 242/256 景深并始终在近脚之后；步幅 40（移动速度不变）；裙摆下移 4/256。',
              font=font(14), fill='#4a515c')
    sheet.save(OUT / 'walk-preview.png')


def feet_sheet():
    phases = [i / 8 for i in range(8)]
    crop = (54, 186, 204, 256)  # 150 x 70 source pixels
    zoom, gap, pad, caption = 4, 12, 16, 30
    cw, ch = (crop[2] - crop[0]) * zoom, (crop[3] - crop[1]) * zoom
    cols, rows = 3, 3
    width = pad * 2 + cols * cw + (cols - 1) * gap
    height = 124 + rows * (ch + caption + gap) + 40
    sheet = Image.new('RGB', (width, height), '#faf8f2')
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 18), '双脚交叠特写 · 4× 源像素', font=font(24, True), fill='#2d3440')
    draw.text((pad, 52), '迈步时远脚从近脚后方经过，两鞋轮廓相叠；远脚保持原画 242/256 的景深高度。',
              font=font(14), fill='#6f7580')
    draw.line([pad, 82, pad + 34, 82], fill='#b9b09c', width=2)
    draw.text((pad + 44, 73), '近脚地面', font=font(13), fill='#6f7580')
    dashed(draw, pad + 160, pad + 194, 82, '#cf8f84')
    draw.text((pad + 204, 73), '远脚原画底面', font=font(13), fill='#6f7580')
    cells = [('原画参考', None, None)] + [
        (f'{phase * 100:.1f}% · 帧 {round(phase * 120) % 120:02d}', 'walk-right', phase)
        for phase in phases]
    for index, (title, name, phase) in enumerate(cells):
        col, row = index % cols, index // cols
        x, y = pad + col * (cw + gap), 124 + row * (ch + caption + gap)
        if name is None:
            source = Image.open(OUT.parent.parent / 'assets/motion-v2/approved-walk-master.png')
            bg = checker(cw, ch)
            canvas = Image.new('RGBA', (256, 256))
            canvas.alpha_composite(source.convert('RGBA'))
            feet = canvas.crop(crop).resize((cw, ch), Image.Resampling.NEAREST)
        else:
            bg = checker(cw, ch)
            feet = sprite(name, phase, 256).crop(crop).resize((cw, ch), Image.Resampling.NEAREST)
        solid_y = int((NEAR_FLOOR - crop[1]) / (crop[3] - crop[1]) * ch)
        far_y = int((FAR_FLOOR - crop[1]) / (crop[3] - crop[1]) * ch)
        ImageDraw.Draw(bg).line([0, solid_y, cw, solid_y], fill='#b9b09c', width=1)
        dashed(ImageDraw.Draw(bg), 0, cw, far_y, '#cf8f84', dash=14, gap=8)
        sheet.paste(bg, (x, y))
        sheet.paste(feet, (x, y), feet)
        d = ImageDraw.Draw(sheet)
        d.text((x, y + ch + 7), title, font=font(14, True if name is None else False),
               fill='#39414d' if name is None else '#6f7580')
    draw.text((pad, height - 26),
              '每一格都是同一张原画鞋子的平移绘制；两脚摆动中心收拢到裙摆中线，经过时自然交叠。',
              font=font(13), fill='#4a515c')
    sheet.save(OUT / 'walk-feet-zoom.png')


def gif():
    frames = []
    count, size, scale = 40, 160, 2
    pane_w, pane_h, header = size * scale + 24, size * scale + 12, 34
    width = pane_w * 2 + 24
    for i in range(count):
        phase = i / count
        frame = Image.new('RGB', (width, header + pane_h + 30), '#faf8f2')
        draw = ImageDraw.Draw(frame)
        draw.text((12, 7), 'Yuki 走路 · 2× 放大 · 双脚交叠版', font=font(15, True), fill='#39414d')
        for col, (name, title) in enumerate((('walk-right', '向右走'), ('walk-left', '向左走'))):
            x = 12 + col * (pane_w + 12)
            bg = checker(pane_w, pane_h)
            near_y = 6 + int(NEAR_FLOOR / 256 * size * scale)
            ImageDraw.Draw(bg).line([0, near_y, pane_w, near_y], fill='#cfc8b8', width=1)
            image = sprite(name, phase, size).resize((size * scale, size * scale), Image.Resampling.LANCZOS)
            bg.paste(image, (12, 6), image)
            frame.paste(bg, (x, header))
            label = font(13, True)
            draw.text((x + (pane_w - draw.textlength(title, font=label)) / 2, header + pane_h + 5),
                      title, font=label, fill='#39414d')
        frames.append(frame.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))
    frames[0].save(OUT / 'walk-runtime.gif', save_all=True, append_images=frames[1:], duration=50,
                   loop=0, optimize=True)


if __name__ == '__main__':
    actual_size_sheet()
    feet_sheet()
    gif()
    for path in sorted(OUT.glob('walk-*')):
        print(path.name, path.stat().st_size)
