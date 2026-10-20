"""Compose approved-scope still previews with a separate soft zzz bubble."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent

def font(size, bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf', size)

def bubble():
    im = Image.new('RGBA', (420, 240))
    d = ImageDraw.Draw(im)
    # Soft cloud silhouette, little round thought beads instead of a pointed tail.
    fill = '#fbfdff'
    d.ellipse((65,34,359,195), fill=fill, outline='#c8d8f0', width=3)
    d.ellipse((111,15,230,131), fill=fill)
    d.ellipse((213,26,329,147), fill=fill)
    d.ellipse((75,183,100,208), fill='#e6edfb', outline='#c8d8f0', width=2)
    d.ellipse((52,213,65,226), fill='#f4f7ff', outline='#c8d8f0', width=2)
    d.arc((80,42,340,183), 220, 279, fill='#ffffff', width=8)
    for pos, size in [((124,100),32),((177,76),43),((238,53),55)]:
        d.text(pos,'z',font=font(size,True),fill='#8d9cd0',stroke_width=1,stroke_fill='#8d9cd0')
    return im

if __name__ == '__main__':
    raw = Image.open(HERE/'sleep-variants-raw.png').convert('RGBA')
    w,h=raw.size
    sheet = Image.new('RGBA',(1200,1100),'#f3f7fe')
    d = ImageDraw.Draw(sheet)
    d.text((40,24),'YUKI / SWEET DREAMS',font=font(30,True),fill='#384d74')
    d.text((40,70),'Four sleeping poses / One plain ice-blue pillow / Still previews only',font=font(17),fill='#7e8aa4')
    cloud=bubble()
    for n,label in enumerate(['01 / Side cuddle','02 / Curled up','03 / On her back','04 / Pillow snuggle']):
        x=28+(n%2)*600;y=115+(n//2)*485
        d.rounded_rectangle((x,y,x+572,y+464),radius=30,fill='#e9effa')
        d.text((x+24,y+18),label,font=font(19,True),fill='#536a92')
        crop=raw.crop(((n%2)*w//2,(n//2)*h//2,((n%2)+1)*w//2,((n//2)+1)*h//2))
        if crop.getextrema()[3][0] < 255:
            box=crop.getbbox()
            if box:crop=crop.crop(box)
        crop.thumbnail((475,330),Image.Resampling.LANCZOS)
        sheet.alpha_composite(crop,(x+(572-crop.width)//2,y+125+(330-crop.height)//2))
        b=cloud.resize((210,120),Image.Resampling.LANCZOS)
        sheet.alpha_composite(b,(x+310,y+38))
        crop.save(HERE/f'pose-{n+1:02}.png')
    sheet.convert('RGB').save(HERE/'sleep-variants-preview.jpg',quality=95)
    cloud.save(HERE/'zzz-bubble-preview.png')
    print('Saved sleep-variants-preview.jpg, pose-01..04.png, zzz-bubble-preview.png')
