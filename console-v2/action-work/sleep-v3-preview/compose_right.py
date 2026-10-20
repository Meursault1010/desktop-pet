from pathlib import Path
from PIL import Image, ImageDraw
from compose_variants import bubble, font

HERE=Path(__file__).resolve().parent
raw=Image.open(HERE/'sleep-right-v2-raw.png').convert('RGBA')
w,h=raw.size
sheet=Image.new('RGBA',(1200,670),'#f3f7fe')
d=ImageDraw.Draw(sheet)
d.text((35,22),'YUKI / RIGHT-FACING SLEEP',font=font(27,True),fill='#384d74')
d.text((35,66),'Selected poses 01 & 02 / Plain pillow / Preview only',font=font(17),fill='#7e8aa4')
for n,label in enumerate(['01 / Side cuddle - right','02 / Curled up - right']):
    x=22+n*600;y=108
    d.rounded_rectangle((x,y,x+556,640),radius=30,fill='#e9effa')
    d.text((x+23,y+18),label,font=font(19,True),fill='#536a92')
    # Preview artwork has a pale backdrop, not production transparency.
    # Keep the full ears, hair, shoes and pillow inside each inspected crop.
    bounds=[(80,200,740,785),(815,200,1420,785)]
    crop=raw.crop(bounds[n])
    crop.thumbnail((500,340),Image.Resampling.LANCZOS)
    sheet.alpha_composite(crop,(x+(556-crop.width)//2,y+180+(340-crop.height)//2))
    sheet.alpha_composite(bubble().resize((210,120),Image.Resampling.LANCZOS),(x+304,y+53))
    crop.save(HERE/f'pose-{n+1:02}-right.png')
sheet.convert('RGB').save(HERE/'sleep-right-preview.jpg',quality=95)
print('Saved sleep-right-preview.jpg')
