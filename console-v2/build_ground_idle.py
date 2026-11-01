"""Cut reviewed AI keyframes, ground them uniformly, and publish Qt/Web atlases."""
from pathlib import Path
from statistics import median
import argparse
import json
import shutil
from PIL import Image, ImageDraw
from generate_ground_idle import SPECS, WORK, ROOT


def cutout(cell):
    cell = cell.convert('RGBA')
    w, h = cell.size
    samples = [cell.getpixel(p)[:3] for p in ((2, 2), (w-3, 2), (2, h-3), (w-3, h-3))]
    key = tuple(median(c[i] for c in samples) for i in range(3))
    strength = key[1]-max(key[0], key[2])
    if strength < 80:
        raise ValueError('Expected solid green background')
    pixels = []
    for r, g, b, _ in cell.getdata():
        alpha = max(0., min(1., 1-max(0, g-max(r, b)-15)/55))
        if alpha < .08:
            pixels.append((0, 0, 0, 0))
        else:
            rgb = tuple(round(max(0, min(255, (v-k*(1-alpha))/alpha))) for v, k in zip((r,g,b), key))
            pixels.append((*rgb, round(alpha*255)))
    cell.putdata(pixels)
    # Eliminate stray isolated generated flecks; never reshape the character.
    alpha = cell.getchannel('A').point(lambda a: 255 if a > 30 else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError('Empty character')
    return cell, bbox


def prepare(key, publish=False):
    raw = WORK/key/'raw.png'
    sheet = Image.open(raw).convert('RGBA')
    # Generated rows can drift slightly from mathematical thirds. Locate an
    # actual clear green gap to avoid clipping ears or importing adjacent feet.
    def foreground(y):
        return sum(1 for r,g,b,a in sheet.crop((0,y,sheet.width,y+1)).getdata()
                   if g-max(r,b) < 70)
    counts = [foreground(y) for y in range(sheet.height)]
    rows = [0]
    for boundary in (sheet.height/3, 2*sheet.height/3):
        candidates = range(round(boundary)-70, round(boundary)+71)
        rows.append(min(candidates, key=lambda y: (sum(counts[y-4:y+5]), abs(y-boundary))))
    rows.append(sheet.height)
    cells = []
    for r in range(3):
        # Locate column gaps separately in each row: wide lying poses can
        # shift the generated grid and spill into a mathematical neighbour.
        counts_x = [sum(1 for red,g,b,a in sheet.crop((x,rows[r],x+1,rows[r+1])).getdata()
                        if g-max(red,b) < 70) for x in range(sheet.width)]
        columns = [0]
        for boundary in (sheet.width/4, sheet.width/2, 3*sheet.width/4):
            candidates = range(round(boundary)-80, round(boundary)+81)
            columns.append(min(candidates, key=lambda x: (sum(counts_x[x-3:x+4]), abs(x-boundary))))
        columns.append(sheet.width)
        cells.extend(cutout(sheet.crop((columns[c], rows[r], columns[c+1], rows[r+1])))
                     for c in range(4))
    # Single sequence-wide scale, respecting the character's smaller height
    # when sitting or lying. Every pose rests on the same floor.
    scale = min(220/max(b[2]-b[0] for _, b in cells),
                222/max(b[3]-b[1] for _, b in cells))
    frames = []
    for cell, bbox in cells:
        sprite = cell.crop(bbox)
        sprite = sprite.resize((max(1, round(sprite.width*scale)), max(1, round(sprite.height*scale))), Image.Resampling.LANCZOS)
        frame = Image.new('RGBA', (256, 256))
        frame.alpha_composite(sprite, ((256-sprite.width)//2, 248-sprite.height))
        frames.append(frame)
    # This builder only publishes the reviewed sitting and prone idle poses.
    repeats = {'sit-neat': 5, 'sit-relaxed': 6, 'sit-swing': 4, 'prone-chin': 5, 'prone-rest': 6}[key]
    order = list(range(3)) + list(range(3,9))*repeats + list(range(9,12))
    duration = {3: 650, 4: 600, 5: 500, 6: 110, 7: 500, 8: 600}
    durations = [duration.get(i, 260) for i in order]
    entry, exit = ({
        'sit-neat': ((320, 400, 380), (320, 340, 360)),
        'sit-relaxed': ((320, 400, 380), (320, 340, 360)),
        'sit-swing': ((320, 400, 380), (320, 340, 360)),
        'prone-chin': ((360, 480, 460), (340, 380, 400)),
        'prone-rest': ((360, 480, 460), (340, 380, 400)),
    }[key])
    durations[:3] = entry
    durations[-3:] = exit
    animation = [frames[i] for i in order]
    atlas = Image.new('RGBA', (1024, ((len(animation)+3)//4)*256))
    for i, frame in enumerate(animation):
        atlas.alpha_composite(frame, ((i%4)*256, (i//4)*256))
    review = Image.new('RGB', (1024, 3*280), '#24334a')
    draw = ImageDraw.Draw(review)
    for i, frame in enumerate(frames):
        review.paste(frame, ((i%4)*256, (i//4)*280), frame)
        draw.text(((i%4)*256+8, (i//4)*280+258), f'{key} / {i+1}', fill='white')
    review.save(WORK/key/'review.jpg')
    previews = []
    for frame in animation:
        bg = Image.new('RGB', (256,256), '#24334a')
        bg.paste(frame, mask=frame.getchannel('A'))
        previews.append(bg)
    previews[0].save(WORK/key/'preview.gif', save_all=True, append_images=previews[1:], duration=durations, loop=0)
    if not publish:
        return
    if not (WORK/key/'reviewed.txt').exists():
        raise ValueError(f'Must visually review {key} before publishing')
    out = ROOT/'assets/actions'/key
    out.mkdir(parents=True, exist_ok=True)
    atlas.save(out/'atlas.png')
    for i, frame in enumerate(animation):
        frame.save(out/f'{i+1:02d}.png')
    animation[4].save(out/'poster.png')
    result = dict(id=key, name=SPECS[key][0], category='待机',
                  origin='generated', frames=len(animation), columns=4, cell=256,
                  durations=durations, atlas=f'actions/{key}/atlas.png', poster=f'actions/{key}/poster.png',
                  sources=[str(raw.relative_to(ROOT))], review='已审查：完整入姿、停留及收姿', ground_idle=True)
    manifest = ROOT/'assets/actions/catalog.json'
    entries = json.loads(manifest.read_text(encoding='utf-8'))
    entries = [entry for entry in entries if entry['id'] != key]+[result]
    manifest.write_text(json.dumps(entries, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    shutil.copytree(out, ROOT/'frontend/public/actions'/key, dirs_exist_ok=True)
    shutil.copyfile(manifest, ROOT/'frontend/public/actions/catalog.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', choices=SPECS)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    manifest = ROOT/'assets/actions/catalog.json'
    shipped = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
    for key in [args.only] if args.only else SPECS:
        # A later lock script re-baked this clip's placement into the pixels;
        # re-cutting the sheet here would put the sideways slide back.
        entry = next((item for item in shipped if item['id'] == key), None)
        if entry and entry.get('body_locked'):
            print(f'SKIP {key}: ships locked authored frames', flush=True)
            continue
        if (WORK/key/'raw.png').exists():
            prepare(key, args.publish)
            print(f'PREPARED {key}', flush=True)
