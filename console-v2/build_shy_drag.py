"""Publish face-only edits; silhouettes, clothing and palm anchors stay exact."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFilter,ImageChops

root=Path(__file__).resolve().parent
work=root/'action-work/shy-drag'
sheet=Image.open(work/'generated.png').convert('RGBA').resize((1536,1024))
polygons={
 'upper-left':[(118,61),(147,65),(165,78),(155,94),(132,97),(119,85)],
 'up':[(119,64),(139,64),(146,79),(143,94),(128,100),(115,94),(114,79)],
 'upper-right':[(119,77),(137,65),(155,68),(155,82),(141,95),(128,100)],
 'left':[(88,70),(128,70),(134,82),(123,94),(102,96),(88,86)],
 'down':[(88,76),(131,76),(136,89),(126,101),(105,103),(88,93)],
 'right':[(116,71),(151,75),(155,87),(146,99),(128,98),(116,89)],
}
for i,(name,polygon) in enumerate(polygons.items()):
    path=root/f'assets/drag-resist/{name}.png'
    backup=work/f'original-{name}.png'
    if not backup.exists():backup.write_bytes(path.read_bytes())
    base=Image.open(backup).convert('RGBA')
    generated=sheet.crop((i%3*512,i//3*512,i%3*512+512,i//3*512+512)).resize((256,256),Image.Resampling.LANCZOS)
    mask=Image.new('L',(256,256))
    ImageDraw.Draw(mask).polygon(polygon,fill=255)
    mask=mask.filter(ImageFilter.GaussianBlur(1.1))
    mask=ImageChops.multiply(mask,base.getchannel('A'))
    result=Image.composite(generated,base,mask)
    result.putalpha(base.getchannel('A'))
    result.save(path)
