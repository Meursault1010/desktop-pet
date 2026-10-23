import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
VISUAL = ROOT / 'visual'
SHEETS = VISUAL / 'sheets'
SHEETS.mkdir(parents=True, exist_ok=True)
items = json.loads((VISUAL / 'index.json').read_text(encoding='utf-8'))
items.sort(key=lambda item: item['index'])

COLS, ROWS = 5, 6
CELL_W, CELL_H = 440, 360
IMAGE_H = 312
PAD = 16
SHEET_W = COLS * CELL_W + PAD * 2
SHEET_H = ROWS * CELL_H + PAD * 2 + 48

title_font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 17)
meta_font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 13)
head_font = ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf', 22)


def ellipsize(draw, text, font, width):
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + '…', font=font) > width:
        text = text[:-1]
    return text + '…'


for sheet_index in range((len(items) + COLS * ROWS - 1) // (COLS * ROWS)):
    batch = items[sheet_index * COLS * ROWS:(sheet_index + 1) * COLS * ROWS]
    sheet = Image.new('RGB', (SHEET_W, SHEET_H), '#0d141b')
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD, PAD), f'YUKI DESIGN CORPUS / SHEET {sheet_index + 1:02d}', font=head_font, fill='#e8eef4')
    draw.text((SHEET_W - PAD - 260, PAD + 4), 'real websites · 2025–2026', font=meta_font, fill='#7c90a2')
    for local_index, item in enumerate(batch):
        col = local_index % COLS
        row = local_index // COLS
        x = PAD + col * CELL_W
        y = PAD + 48 + row * CELL_H
        thumb_path = VISUAL / 'thumbs' / f"{item['index']:03d}.jpg"
        cell_bg = '#131e27'
        draw.rounded_rectangle((x, y, x + CELL_W - 10, y + CELL_H - 10), radius=10, fill=cell_bg)
        if thumb_path.exists():
            try:
                image = Image.open(thumb_path).convert('RGB')
                image = ImageOps.contain(image, (CELL_W - 24, IMAGE_H), Image.Resampling.LANCZOS)
                px = x + (CELL_W - 10 - image.width) // 2
                py = y + 8 + (IMAGE_H - image.height) // 2
                sheet.paste(image, (px, py))
            except Exception as exc:
                draw.text((x + 16, y + 30), f'image error: {exc}', font=meta_font, fill='#d06a6a')
        else:
            draw.text((x + 16, y + 30), 'image missing', font=meta_font, fill='#d06a6a')
        title = ellipsize(draw, f"#{item['index']:03d}  {item['title']}", title_font, CELL_W - 34)
        draw.text((x + 14, y + IMAGE_H + 8), title, font=title_font, fill='#e8eef4')
        meta = ellipsize(draw, f"{item['host']}  ·  {item.get('group', '')}", meta_font, CELL_W - 34)
        draw.text((x + 14, y + IMAGE_H + 30), meta, font=meta_font, fill='#8fa2b3')
    target = SHEETS / f'sheet-{sheet_index + 1:02d}.jpg'
    sheet.save(target, quality=88, optimize=True)
    print(target.name, len(batch), target.stat().st_size // 1024, 'KB')
