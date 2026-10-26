"""Build a restrained gait from the user-approved three-quarter master.

Only the legs are articulated. No optical flow, changing head scale or
independently generated hair/embroidery is introduced between samples.
"""
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

from build_autoplay_assets import extract

ROOT = Path(__file__).resolve().parent


def main():
    source = ROOT / 'action-work/approved-walk/reviewed-sheet.png'
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT.parent / 'output/yuki-walk-three-quarter-preview.png', source)
    sheet = Image.open(source).convert('RGBA')
    # The second cell has a complete, isolated silhouette; the neighbouring
    # cells contain overlapping loose hair and must not become animation keys.
    cut = extract(sheet.crop((384, 0, 768, 1024)))
    cut = cut.crop(cut.getbbox())
    # Idle's opaque height is 308/384*180 = 144.375 logical pixels;
    # gait draws at 160/256, so the corresponding master is exactly 231px.
    cut = cut.resize((round(cut.width * 231 / cut.height), 231), Image.Resampling.LANCZOS)
    base = Image.new('RGBA', (256, 256))
    base.alpha_composite(cut, ((256-cut.width)//2, 249-cut.height))
    out = ROOT / 'assets/motion-v2'
    base.save(out / 'approved-walk-master.png')
    # Both legs continue under the skirt. The skirt is composited last,
    # concealing the articulation seam while keeping its pixels identical.
    body = base.copy()
    legs = []
    for box, pivot in [((94, 214, 129, 256), (120, 211)),
                       ((129, 214, 166, 256), (136, 211))]:
        layer = Image.new('RGBA', base.size)
        layer.paste(base.crop(box), box[:2])
        body.paste((0, 0, 0, 0), box)
        legs.append((layer, pivot))
    right, contacts = [], []
    for i in range(60):
        phase = i / 60 * math.tau
        layers = [im.rotate(sign*8*math.cos(phase), Image.Resampling.BICUBIC,
                            center=pivot) for (im, pivot), sign in zip(legs, (-1, 1))]
        image = Image.new('RGBA', base.size)
        for layer in layers:
            image.alpha_composite(layer)
        image.alpha_composite(body)
        # Actual sole contact of the support leg, rather than old-art anchors.
        support = layers[1 if i < 30 else 0]
        alpha = np.array(support.getchannel('A'))
        ys, xs = np.where(alpha > 160)
        sole_y = int(ys.max())
        sole_x = float(np.median(xs[ys >= sole_y-1]))
        contacts.append([sole_x, sole_y])
        right.append(image)
    meta_path = out / 'clips.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    for name, images, soles in [
        ('walk-right', right, contacts),
        ('walk-left', [im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for im in right],
         [[255-x, y] for x, y in contacts]),
    ]:
        folder = out / name
        folder.mkdir(exist_ok=True)
        for i, im in enumerate(images):
            im.save(folder / f'{i:02}.png')
        boxes = [im.getbbox() for im in images]
        meta[name].update(frames=60, baseline=249/256,
                          bounds=[min(b[0] for b in boxes)/256, min(b[1] for b in boxes)/256,
                                  max(b[2] for b in boxes)/256, max(b[3] for b in boxes)/256],
                          contacts=soles, method='approved-single-master-leg-articulation',
                          optical_flow=False)
        meta[name]['stride'] = 48.
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    # Presence uses the same normalized artwork and footprint as ordinary gait.
    presence = ROOT / 'assets/presence'
    for kind, count in [('enter', 10), ('exit', 7)]:
        for i in range(1, count+1):
            image = Image.new('RGBA', (384, 384))
            image.alpha_composite(right[(i*10)%60].resize((341,341), Image.Resampling.LANCZOS), (21,32))
            target = presence / f'{kind}-{i:02}.png'
            temporary = target.with_suffix('.building.png')
            image.save(temporary)
            temporary.replace(target)
    preview = []
    for i in range(120):
        canvas = Image.new('RGBA', (600,280), '#263747')
        canvas.alpha_composite(right[i%60], (20+round(i*2.5), 10))
        preview.append(canvas.convert('RGB'))
    preview[0].save(ROOT.parent/'output/yuki-approved-walk.gif', save_all=True,
                    append_images=preview[1:], duration=20, loop=0)
    # The approved master and presence art remain this builder's inputs.
    # Publish the calibrated rigid rig last so a rebuild cannot restore the
    # older tiny-stride motion or its secondary runtime deformation.
    from build_grounded_walk import build
    build()
    print('Published approved model and calibrated grounded walk rig.')


if __name__ == '__main__':
    main()
