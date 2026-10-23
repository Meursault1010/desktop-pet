from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math
import cv2
import numpy as np

ROOT = Path(__file__).parent
src_path = ROOT / 'waltz-turnaround-contact.png'
src = Image.open(src_path).convert('RGB')
arr = np.array(src)
H, W = arr.shape[:2]
# Model produced 5 columns x 2 rows (ten figures), despite the requested 12.
cols, rows = 5, 2
cell_w, cell_h = W // cols, H // rows
frames = []

for i in range(cols * rows):
    col, row = i % cols, i // cols
    x0, y0 = col * cell_w, row * cell_h
    cell = arr[y0:y0+cell_h, x0:x0+cell_w].copy()
    # Checkerboard pixels are nearly neutral; connected-component removal preserves
    # neutral hair/skin enclosed by the blue character outlines.
    mx, mn = cell.max(axis=2), cell.min(axis=2)
    neutral_bg = ((mx - mn) < 13) & (mn > 222)
    flood = np.zeros((cell_h + 2, cell_w + 2), np.uint8)
    bg = neutral_bg.astype(np.uint8)
    for xx in range(cell_w):
        if bg[0, xx]: cv2.floodFill(bg, flood, (xx, 0), 2)
        if bg[cell_h-1, xx]: cv2.floodFill(bg, flood, (xx, cell_h-1), 2)
    for yy in range(cell_h):
        if bg[yy, 0]: cv2.floodFill(bg, flood, (0, yy), 2)
        if bg[yy, cell_w-1]: cv2.floodFill(bg, flood, (cell_w-1, yy), 2)
    alpha = np.where(bg == 2, 0, 255).astype(np.uint8)
    # soften only the binary segmentation by a minimal antialias fringe
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.45)
    rgba = np.dstack([cell, alpha])
    image = Image.fromarray(rgba, 'RGBA')
    # Trim transparent margins while retaining uniform canvas around figure.
    bbox = image.getchannel('A').getbbox()
    image = image.crop(bbox)
    frames.append(image)

# Contact sheet for visual review
thumb_w, thumb_h = 250, 320
sheet = Image.new('RGBA', (cols * thumb_w, rows * thumb_h), (242, 247, 252, 255))
for i, frame in enumerate(frames):
    thumb = frame.copy(); thumb.thumbnail((thumb_w-18, thumb_h-18), Image.Resampling.LANCZOS)
    x = (i % cols) * thumb_w + (thumb_w-thumb.width)//2
    y = (i // cols) * thumb_h + (thumb_h-thumb.height)//2
    sheet.alpha_composite(thumb, (x, y))
sheet.convert('RGB').save(ROOT / 'waltz-turnaround-cutouts-review.jpg', quality=92)

# Short 2.5D turn preview. Existing contact sheet lacks the requested 12 poses,
# so use its ten actual distinct views and interpolate their display timing only.
CW, CH = 680, 520
ground_y = 445
anim = []
N = 80
for k in range(N):
    t = k / N
    phase = 2 * math.pi * t
    p = t * len(frames)
    idx = int(p) % len(frames)
    f = p - int(p)
    # Hold recognizable side/back key views a little; avoid fast flicker.
    pose = frames[idx]
    # Gentle apparent depth and shallow elliptical travel.
    depth = math.cos(phase)
    scale = 0.46 + 0.055 * (depth + 1) / 2
    x = CW/2 + 105*math.sin(phase) + 14*math.sin(2*phase)
    lift = 8 + 9*max(0, math.sin(3*phase+0.4))
    angle = 1.4 * math.sin(phase)
    pw, ph = pose.size
    out_size = (round(pw*scale), round(ph*scale))
    char = pose.resize(out_size, Image.Resampling.LANCZOS).rotate(angle, Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new('RGBA', (CW, CH), (248, 250, 253, 255))
    d = ImageDraw.Draw(canvas, 'RGBA')
    # faint stage glow and grounding ellipse
    d.ellipse((x-65, ground_y-3, x+65, ground_y+13), fill=(101, 145, 198, 37))
    canvas.alpha_composite(char, (round(x-char.width/2), round(ground_y-lift-char.height)))
    anim.append(canvas.convert('RGB'))

anim[0].save(ROOT / 'waltz-turnaround-motion-preview.gif', save_all=True,
             append_images=anim[1:], duration=75, loop=0, optimize=False)
anim[0].save(ROOT / 'waltz-turnaround-motion-preview.png')
print(f'cutout poses={len(frames)}; contact={ROOT / "waltz-turnaround-cutouts-review.jpg"}; gif={ROOT / "waltz-turnaround-motion-preview.gif"}')
