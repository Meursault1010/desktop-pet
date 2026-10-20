"""Label the revised key poses for human review; not an animation atlas."""
from pathlib import Path
from PIL import Image, ImageDraw
from compose_variants import font

HERE = Path(__file__).resolve().parent
raw = Image.open(HERE/'sleep-transitions-v2-raw.png').convert('RGBA')
sheet = Image.new('RGBA', (1200, 1050), '#f3f7fe')
d = ImageDraw.Draw(sheet)
d.text((32, 22), 'YUKI / SLEEP & WAKE', font=font(28, True), fill='#384d74')
d.text((32, 65), 'Right-facing pose 02 / Key-pose review / Not applied', font=font(17), fill='#7e8aa4')
labels = ['01 / Drowsy', '02 / Settling down', '03 / Asleep',
          '04 / Stirring', '05 / Opening eyes', '06 / Waking slowly']
for i, label in enumerate(labels):
    col, row = i%3, i//3
    x, y = 15+col*398, 112+row*464
    d.rounded_rectangle((x, y, x+380, y+448), radius=23, fill='#e9f3ff')
    d.text((x+18, y+16), label, font=font(18, True), fill='#536a92')
    crop = raw.crop((col*raw.width//3, row*raw.height//2,
                     (col+1)*raw.width//3, (row+1)*raw.height//2))
    crop.thumbnail((370, 370), Image.Resampling.LANCZOS)
    sheet.alpha_composite(crop, (x+(380-crop.width)//2, y+65))
sheet.convert('RGB').save(HERE/'sleep-transitions-review.jpg', quality=96)
print('Saved sleep-transitions-review.jpg')
