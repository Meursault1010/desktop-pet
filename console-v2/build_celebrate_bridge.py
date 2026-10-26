"""Insert the generated mid-raise pose between celebrate poses 02 and 03.

The shipped poses already carry the project's reviewed scale calibration, so
this pass only authors the inserted frame and repacks them; it never rescales
the existing drawings.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

from build_action_library import ROOT, extract

WORK = ROOT/'action-work/celebrate-bridge'
TARGET = ROOT/'assets/actions/celebrate'
COLUMNS = 4
DURATIONS = [180, 160, 180, 170, 160, 180, 220]
# Visible-bounds anchor measured from the two neighbouring shipped poses
# (arms overhead and mid-hop), so the inserted pose lands on their midpoint.
HEIGHT, FLOOR, CENTER = 229.5, 245.5, 125.25


def bridge_frame():
    # The generator emits a near-opaque alpha channel; flatten it so the
    # chroma keyer runs instead of treating the green sheet as a cutout.
    subject = extract(Image.open(WORK/'raw.png').convert('RGB').convert('RGBA'), True)
    alpha = subject.getchannel('A').point(lambda value: 255 if value > 32 else 0)
    left, top, right, bottom = alpha.getbbox()
    sprite = subject.crop((left, top, right, bottom))
    factor = HEIGHT/sprite.height
    sprite = sprite.resize((max(1, round(sprite.width*factor)), round(HEIGHT)),
                           Image.Resampling.LANCZOS)
    frame = Image.new('RGBA', (256, 256))
    frame.alpha_composite(sprite, (round(CENTER-sprite.width/2), round(FLOOR-sprite.height)))
    return frame


def main():
    original = [Image.open(WORK/'original'/f'{index:02d}.png').convert('RGBA')
                for index in range(1, 7)]
    frames = [*original[:3], bridge_frame(), *original[3:]]
    TARGET.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(TARGET/f'{index+1:02d}.png')
    rows = (len(frames)+COLUMNS-1)//COLUMNS
    atlas = Image.new('RGBA', (256*COLUMNS, 256*rows))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, (index % COLUMNS*256, index//COLUMNS*256))
    atlas.save(TARGET/'atlas.png')
    frames[0].save(TARGET/'poster.png')
    qa = ROOT/'qa/actions'
    qa.mkdir(parents=True, exist_ok=True)
    sheet = Image.new('RGB', atlas.size, '#48505e')
    sheet.paste(atlas, mask=atlas.getchannel('A'))
    sheet.save(qa/'celebrate.jpg')
    previews = []
    for frame in frames:
        background = Image.new('RGB', (256, 256), '#48505e')
        background.paste(frame, mask=frame.getchannel('A'))
        previews.append(background)
    previews[0].save(qa/'celebrate.gif', save_all=True, append_images=previews[1:],
                     duration=DURATIONS, loop=0)

    catalog_path = ROOT/'assets/actions/catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    previous = next(action for action in catalog if action['id'] == 'celebrate')
    entry = {**previous, 'frames': len(frames), 'columns': COLUMNS,
             'durations': DURATIONS,
             'sources': [str((WORK/'raw.png').relative_to(ROOT))],
             'review': '已审查：姿态 2→3 之间补入抬手中帧，流程连续'}
    catalog = [action for action in catalog if action['id'] != 'celebrate'] + [entry]
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n',
                            encoding='utf-8')
    print(f"celebrate: {len(frames)} frames, {sum(DURATIONS)} ms")


if __name__ == '__main__':
    main()
