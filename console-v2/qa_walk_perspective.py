"""Two directions, a complete slow cycle, and close-up foot perspectives."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PIL import Image,ImageDraw
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage,QPainter
from walk_rig import paint,HOME
from locomotion import walk_stride,walking_speed


def main():
    app=QApplication.instance() or QApplication([])
    root=Path(__file__).resolve().parent.parent/'output';root.mkdir(exist_ok=True)
    frames=[];review=Image.new('RGB',(1024,900),'#202b40')
    # Match the runtime stride and cadence, including short-step revisions.
    count=64
    stride=walk_stride('walk-right')
    duration=round(stride/walking_speed(48)*1000/count/10)*10
    for i in range(count):
        canvas=Image.new('RGB',(1024,300),'#202b40');draw=ImageDraw.Draw(canvas)
        clock=i/count*stride
        for col,name in enumerate(('walk-right','walk-left')):
            im=QImage(256,256,QImage.Format.Format_RGBA8888);im.fill(0)
            painter=QPainter(im);paint(painter,QRectF(0,0,256,256),name,clock);painter.end()
            pil=Image.frombytes('RGBA',(256,256),bytes(im.constBits()))
            sign=1 if col==0 else -1
            x=col*512+10+(0 if sign==1 else round(stride*256/160))+round(sign*clock*256/160)
            canvas.paste(pil,(x,22),pil)
            close=pil.crop((80,204,184,254)).resize((208,100),Image.Resampling.NEAREST)
            canvas.paste(close,(col*512+296,140),close)
            draw.text((col*512+12,8),name,fill='#d8e7f7')
            # Separate fixed-camera ground tracks, not a floating far foot.
            for leg,(_,baseline) in enumerate(HOME):
                y=22+round(baseline)
                for start in range(col*512+8,col*512+280,8):
                    draw.line((start,y,start+3,y),fill='#40516a' if leg==0 else '#6b829c')
            draw.text((col*512+298,115),'Foot detail',fill='#afc7e5')
        frames.append(canvas)
        if i in (0,21,43):review.paste(canvas,(0,(0,21,43).index(i)*300))
    frames[0].save(root/'yuki-walk-perspective-preview.gif',save_all=True,append_images=frames[1:],duration=duration,loop=0)
    review.save(root/'yuki-walk-perspective-review.png')
    print('Saved walk perspective preview and contact sheet.')


if __name__=='__main__':main()
