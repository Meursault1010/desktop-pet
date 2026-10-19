"""Prepare only the approved throw/impact sheets; preserve all other assets."""
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'action-work/physics-v1'
NAMES = {'throw-flight': '被抛出 · 空中飞行', 'impact-left': '撞左边 · 软弹回',
         'impact-right': '撞右边 · 软弹回', 'impact-ceiling': '撞顶部 · 护住猫耳',
         'impact-floor': '撞底部 · 脚尖回弹'}


def cutout(image):
    """Extract the enclosing blue outline without losing pale hair highlights."""
    a = np.array(image.convert('RGBA'))
    if a[:, :, 3].min() < 250:
        return Image.fromarray(a)
    rgb = a[:, :, :3]
    # The blue outline encloses white hair; color seeding plus enclosed contour
    # filling preserves highlights which generic GrabCut mistakes for backdrop.
    chroma = rgb.max(2).astype(int) - rgb.min(2).astype(int)
    blue = rgb[:, :, 2].astype(int) - rgb[:, :, 0].astype(int)
    matte = ((chroma > 12) & (blue > 4)).astype('uint8') * 255
    matte = cv2.morphologyEx(matte, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(matte, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError('No character outline found')
    matte[:] = 0
    cv2.drawContours(matte, [max(contours, key=cv2.contourArea)], -1, 255, cv2.FILLED)
    a[:, :, 3] = matte
    a[matte == 0] = 0
    return Image.fromarray(a)


def prepare():
    entries = []
    qa = ROOT / 'qa/physics-v1'
    qa.mkdir(parents=True, exist_ok=True)
    for action_id, name in NAMES.items():
        raw = Image.open(WORK / f'{action_id}-raw.png')
        cols, rows = (3, 4) if action_id == 'throw-flight' else (4, 2)
        # Generated flight rows drift slightly from an ideal equal grid.
        # Cut in the actual empty gutters to preserve shoes and hair tips.
        ys = [0, 338, 660, 984, raw.height] if cols == 3 else [0, raw.height//2, raw.height]
        images = [cutout(raw.crop((round(c*raw.width/cols), ys[r],
                                  round((c+1)*raw.width/cols), ys[r+1])))
                  for r in range(rows) for c in range(cols)]
        # Use one factor for the whole clip, no independent frame stretching.
        # All clips share the same target body envelope as existing actions.
        boxes = [im.getbbox() for im in images]
        if not all(boxes):
            raise ValueError(f'Empty cutout: {action_id}')
        factor = min(220 / max(b[2]-b[0] for b in boxes),
                     222 / max(b[3]-b[1] for b in boxes))
        out = ROOT / 'assets/actions' / action_id
        out.mkdir(parents=True, exist_ok=True)
        atlas = Image.new('RGBA', (1024, ((len(images)+3)//4)*256))
        frames = []
        for i, (im, box) in enumerate(zip(images, boxes)):
            sprite = im.crop(box)
            sprite = sprite.resize((round(sprite.width*factor), round(sprite.height*factor)), Image.Resampling.LANCZOS)
            frame = Image.new('RGBA', (256, 256))
            # Stable bottom baseline. Pose height changes remain authored.
            frame.alpha_composite(sprite, ((256-sprite.width)//2, 244-sprite.height))
            frame.save(out / f'{i+1:02d}.png')
            frames.append(frame)
            atlas.alpha_composite(frame, ((i%4)*256, (i//4)*256))
        atlas.save(out / 'atlas.png')
        frames[0].save(out / 'poster.png')
        preview = Image.new('RGB', atlas.size, '#303f56')
        preview.paste(atlas, mask=atlas.getchannel('A'))
        preview.save(qa / f'{action_id}.jpg')
        durations = [85]*12 if cols == 3 else [75, 65, 45, 55, 65, 75, 90, 100]
        gif = []
        for frame in frames:
            bg = Image.new('RGB', frame.size, '#303f56')
            bg.paste(frame, mask=frame.getchannel('A'))
            gif.append(bg)
        gif[0].save(qa/f'{action_id}.gif', save_all=True, append_images=gif[1:], duration=durations, loop=0)
        entries.append(dict(id=action_id, name=name, category='物理互动', origin='generated',
                            frames=len(frames), columns=4, cell=256, durations=durations,
                            atlas=f'actions/{action_id}/atlas.png', poster=f'actions/{action_id}/poster.png',
                            sources=[f'action-work/physics-v1/{action_id}-raw.png'],
                            scale_calibrated=True, pixel_art=False, physics_only=True,
                            review='已检查角色与帧顺序；棋盘格背景已本地抠除'))
        shutil.copytree(out, ROOT/'frontend/public/actions'/action_id, dirs_exist_ok=True)
        print(action_id, raw.size, '=>', len(frames), 'RGBA frames')
    catalog = ROOT/'assets/actions/catalog.json'
    existing = json.loads(catalog.read_text(encoding='utf-8'))
    existing = [a for a in existing if a['id'] not in NAMES] + entries
    catalog.write_text(json.dumps(existing, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    shutil.copy2(catalog, ROOT/'frontend/public/actions/catalog.json')


if __name__ == '__main__':
    prepare()
