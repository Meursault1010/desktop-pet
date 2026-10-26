"""Probe the four authored walk cells: align, scale, ground, and measure feet."""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from build_autoplay_assets import extract  # noqa: E402
SHEET = ROOT / 'action-work/approved-walk/reviewed-sheet.png'
TMP = __import__('pathlib').Path('C:/Users/meursault/AppData/Local/Temp')


def cutout(cell):
    image = extract(cell)
    a = np.array(image)
    n, labels, stats, _ = cv2.connectedComponentsWithStats((a[:, :, 3] > 16).astype(np.uint8), 8)
    if n > 1:
        keep = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = (labels == keep).astype(np.uint8) * 255
        a[:, :, 3] = np.minimum(a[:, :, 3], mask)
        a[a[:, :, 3] == 0] = 0
    return Image.fromarray(a)


def premultiplied(image):
    a = np.asarray(image).astype(np.float32)
    a[:, :, :3] *= a[:, :, 3:4] / 255
    return a[:, :, :3]


def align_to(reference, image):
    # Upper body only: loosely hanging hair and the stepping legs differ.
    ref = premultiplied(reference)[:600]
    cur = premultiplied(image)[:600]
    pad = 80
    canvas = np.zeros((ref.shape[0] + 2 * pad, ref.shape[1] + 2 * pad, 3), np.float32)
    canvas[pad:pad + cur.shape[0], pad:pad + cur.shape[1]] = cur
    result = cv2.matchTemplate(canvas, ref, cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(result)
    return x - pad, y - pad, score


def feet(image):
    a = np.asarray(image)
    alpha = a[:, :, 3]
    ys, _ = np.where(alpha > 32)
    bottom = ys.max()
    region = (alpha > 32)
    region[:bottom - 60] = False
    n, labels, stats, _ = cv2.connectedComponentsWithStats(region.astype(np.uint8), 8)
    found = []
    for j in range(1, n):
        area = stats[j, cv2.CC_STAT_AREA]
        if area < 40:
            continue
        x, y, w, h = stats[j, :4]
        mask = labels == j
        yy = np.where(mask)[0]
        sole = int(yy.max())
        found.append(dict(x=int(x), w=int(w), top=int(y), sole=sole, area=int(area)))
    return sorted(found, key=lambda f: f['x'])


def main():
    sheet = Image.open(SHEET).convert('RGBA')
    W, H = sheet.size
    cells = [cutout(sheet.crop((i * W // 4, 0, (i + 1) * W // 4, H))) for i in range(4)]
    reference = cells[1]
    page = Image.new('RGBA', (4 * 320, 360), (238, 243, 250, 255))
    for i, cell in enumerate(cells):
        dx, dy, score = align_to(reference, cell)
        moved = Image.new('RGBA', cell.size)
        moved.alpha_composite(cell, (dx, dy))
        box = moved.getbbox()
        cut = moved.crop(box)
        cut = cut.resize((round(cut.width * 231 / cut.height), 231), Image.Resampling.LANCZOS)
        base = Image.new('RGBA', (256, 256))
        base.alpha_composite(cut, ((256 - cut.width) // 2, 249 - cut.height))
        base.save(TMP / f'aligned-{i}.png')
        print(i, 'shift', dx, dy, 'score', round(score, 3), 'bbox', box, 'feet', feet(base))
        page.alpha_composite(base.crop((32, 0, 288, 360)), (i * 320 + 32, 0))
    page.convert('RGB').resize((page.width * 2, page.height * 2), Image.Resampling.LANCZOS).save(
        TMP / 'aligned-poses.png')


if __name__ == '__main__':
    main()
