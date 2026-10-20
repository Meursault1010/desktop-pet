"""Local, read-only contact sheets for character identity review.

Keep whole poses visible: hair movement must be judged in its pose, rather
than mistaken for an asset offset or replaced with a front-facing hair patch.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent / '.electron-build' / 'character-consistency'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    actions = json.loads((ROOT / 'assets/actions/catalog.json').read_text(encoding='utf-8'))
    sheets = []
    for page in range(0, len(actions), 12):
        group = actions[page:page+12]
        sheet = Image.new('RGB', (1020, len(group)*158+160), '#e8eff6')
        draw = ImageDraw.Draw(sheet)
        idle = Image.open(ROOT / 'assets/living-idle/open.png').convert('RGBA').crop((0, 0, 256, 256))
        idle.thumbnail((144, 144), Image.Resampling.LANCZOS)
        sheet.paste(idle, (180, 10), idle)
        draw.text((12, 22), 'Reference: living idle', fill='#315273')
        for row, action in enumerate(group):
            atlas = Image.open(ROOT / 'assets' / action['atlas']).convert('RGBA')
            count = action['frames']
            indices = sorted(set((0, count//4, count//2, count*3//4, count-1)))
            y = 160+row*158
            draw.text((12, y+12), action['id'], fill='#315273')
            for col, index in enumerate(indices):
                x = 175+col*166
                box = (index % action['columns']*256, index//action['columns']*256)
                frame = atlas.crop((*box, box[0]+256, box[1]+256))
                frame.thumbnail((144, 144), Image.Resampling.LANCZOS)
                sheet.paste(frame, (x, y), frame)
                draw.text((x, y+140), str(index), fill='#315273')
        path = OUTPUT / f'poses-{page//12+1}.jpg'
        sheet.save(path, quality=94)
        sheets.append(str(path))
    print('\n'.join(sheets))


if __name__ == '__main__':
    main()
