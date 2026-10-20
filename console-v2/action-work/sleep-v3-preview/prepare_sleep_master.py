"""Local cutout + restrained master-based breathing preview; no runtime writes."""
from pathlib import Path
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from compose_variants import font

HERE = Path(__file__).resolve().parent


def sleeping_letters(seconds):
    """Frame-free rounded letters; continuous drift with invisible loop reset."""
    scale = 3
    layer = Image.new('RGBA', (680*scale, 650*scale))
    glyph_font = ImageFont.truetype('C:/Windows/Fonts/comicbd.ttf', 32*scale)
    draw = ImageDraw.Draw(layer)
    for j in range(3):
        progress = (seconds/4.8+j/3) % 1
        # Smooth fades hide the reset, leaving two or three gently rising z's.
        opacity = round(210*min(1, progress/.18, (1-progress)/.25))
        x = 450+100*progress
        y = 161-54*progress
        draw.text((round(x*scale), round(y*scale)), 'z', font=glyph_font,
                  anchor='ls', fill=(114, 141, 199, opacity))
    return layer.resize((680, 650), Image.Resampling.LANCZOS)


def cutout(im):
    rgb = np.array(im.convert('RGB'))
    corners = np.concatenate([rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3),
                              rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    delta = np.linalg.norm(rgb.astype(float)-bg, axis=2)
    # Flood only the backdrop connected to the outer border. Keep pale interior
    # hair/pillow behind the continuous dark outline instead of colour-keying it.
    candidates = (delta < 30).astype('uint8')
    n, labels = cv2.connectedComponents(candidates, connectivity=4)
    ids = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    ids = ids[ids != 0]
    outside = np.isin(labels, ids)
    alpha = (~outside).astype('uint8')*255
    # Only discard isolated dust, never disconnected ears/strands by size rank.
    n, pieces, stats, _ = cv2.connectedComponentsWithStats((alpha > 0).astype('uint8'))
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < 6:
            alpha[pieces == i] = 0
    rgba = np.dstack([rgb, alpha])
    rgba[alpha == 0, :3] = 0
    return Image.fromarray(rgba)


def breathing(master, seconds):
    rgba = np.array(master).astype('float32')
    rgba[:, :, :3] *= rgba[:, :, 3:4]/255
    h, w = rgba.shape[:2]
    yy, xx = np.mgrid[:h, :w].astype('float32')
    # Approved pose: torso at lower-left of head, pillow lower-right.
    # Anchor the face, ears, hair crest, feet and entire pillow.
    nx, ny = xx/w, yy/h
    chest = np.exp(-((nx-.51)/.12)**2-((ny-.63)/.10)**2)
    phase = math.tau*seconds/4.8
    breath = math.sin(phase)
    dy = -.95*breath*chest
    dx = .35*breath*chest
    warped = cv2.remap(rgba, xx-dx, yy-dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    alpha = warped[:, :, 3:4]
    warped[:, :, :3] = np.divide(warped[:, :, :3]*255, alpha,
                                out=np.zeros_like(warped[:, :, :3]), where=alpha > 0)
    return Image.fromarray(np.clip(np.rint(warped), 0, 255).astype('uint8'))


def main():
    raw = Image.open(HERE/'sleep-right-v2-raw.png')
    master = cutout(raw.crop((815, 200, 1420, 785)))
    master.save(HERE/'sleep-right-02-master.png')
    # Use a conservative master-based motion, no interpolated different faces.
    frames = []
    for i in range(96):
        t = i/20
        sheet = Image.new('RGBA', (680, 650), '#eff4fc')
        draw = ImageDraw.Draw(sheet)
        draw.text((28, 22), 'YUKI / DEEP SLEEP', font=font(24, True), fill='#384d74')
        draw.text((28, 58), 'Pose 02 / right-facing / subtle breathing study', font=font(16), fill='#7e8aa4')
        character = breathing(master, t)
        character.thumbnail((530, 475), Image.Resampling.LANCZOS)
        sheet.alpha_composite(character, ((680-character.width)//2, 158))
        sheet.alpha_composite(sleeping_letters(t))
        frames.append(sheet.convert('RGB'))
    frames[0].save(HERE/'sleep-right-02-breathing.gif', save_all=True,
                   append_images=frames[1:], duration=50, loop=0, disposal=2)
    frames[0].save(HERE/'sleep-right-02-master-preview.png')
    print('Saved local master cutout and breathing study (not production assets).')


if __name__ == '__main__':
    main()
