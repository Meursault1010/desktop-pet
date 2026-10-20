"""Build a compact visual comparison of raw and aligned generated frames."""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from build_frame_alignment import ASSETS


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / '.electron-build' / 'frame-alignment-preview.png'
SAMPLE_ACTIONS = ('wait', 'work', 'yawn', 'afraid', 'stretch', 'screen')
CELL = 256
SCALE = 0.5
GAP = 18
LABEL_HEIGHT = 24
BACKGROUND = '#e8eff6'


def main():
    profile = json.loads((ASSETS / 'frame-alignment.json').read_text(encoding='utf-8'))['actions']
    rows = []
    for action_id in SAMPLE_ACTIONS:
        action = profile[action_id]
        frames = []
        for index, (dx, dy) in enumerate(action['offsets']):
            frame = Image.open(ASSETS / action_id / f'{index + 1:02d}.png').convert('RGBA')
            aligned = Image.new('RGBA', frame.size)
            aligned.alpha_composite(frame, (round(dx), round(dy)))
            frames.append((frame, aligned))
        rows.append((action_id, frames))

    frames_per_row = max(len(frames) for _, frames in rows)
    cell_w = round(CELL * SCALE)
    row_h = round(CELL * SCALE) + LABEL_HEIGHT
    width = GAP + frames_per_row * (cell_w * 2 + GAP) + GAP
    height = GAP + len(rows) * (row_h + GAP) + GAP
    sheet = Image.new('RGB', (width, height), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for row, (action_id, frames) in enumerate(rows):
        y = GAP + row * (row_h + GAP)
        draw.text((GAP, y), f'{action_id}: raw / aligned', fill='#315273')
        for index, (raw, aligned) in enumerate(frames):
            x = GAP + index * (cell_w * 2 + GAP)
            y_image = y + LABEL_HEIGHT
            sheet.paste(raw.resize((cell_w, cell_w), Image.Resampling.LANCZOS), (x, y_image),
                        raw.resize((cell_w, cell_w), Image.Resampling.LANCZOS))
            x_aligned = x + cell_w + GAP
            sheet.paste(aligned.resize((cell_w, cell_w), Image.Resampling.LANCZOS),
                        (x_aligned, y_image),
                        aligned.resize((cell_w, cell_w), Image.Resampling.LANCZOS))
            draw.text((x + 3, y_image + 3), f'{index + 1}', fill='#52708a')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUTPUT)
    print(OUTPUT)


if __name__ == '__main__':
    main()
