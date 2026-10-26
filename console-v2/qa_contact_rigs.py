"""Render the real runtime rigs against fixed floor and rail guides."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json,time,statistics
from pathlib import Path
from PIL import Image,ImageDraw
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPainter,QImage
from PySide6.QtCore import QRectF
from walk_rig import paint as walk
from climb_rig import paint as climb


def main():
    app=QApplication.instance() or QApplication([])
    root=Path(__file__).resolve().parent.parent/'output'
    root.mkdir(exist_ok=True)
    frames=[];cost=[];review=Image.new('RGB',(1100,960),'#202b40')
    for i in range(120):
        canvas=Image.new('RGB',(1100,320),'#202b40');draw=ImageDraw.Draw(canvas)
        for col,name in enumerate(('walk-right','walk-left','climb-left','climb-right')):
            image=QImage(256,256,QImage.Format.Format_RGBA8888);image.fill(0)
            painter=QPainter(image);start=time.perf_counter()
            if col<2:walk(painter,QRectF(0,0,256,256),name,i/120*40)
            else:climb(painter,QRectF(0,0,256,256),name,i/120*16)
            cost.append((time.perf_counter()-start)*1000);painter.end()
            pil=Image.frombytes('RGBA',(256,256),bytes(image.constBits()))
            x=col*275+5+(round(i/120*64)*(1 if col==0 else -1) if col<2 else 0)
            if col==1:x+=64
            y=38 if col<2 else 38+round(i/120*16)
            draw.text((col*275+12,12),name,fill='#c6d9f5')
            if col<2:draw.line((col*275,287,col*275+274,287),fill='#7593b8')
            else:
                rail=col*275+5+(176 if col==2 else 80)
                draw.line((rail,25,rail,310),fill='#7593b8')
            canvas.paste(pil,(x,y),pil)
        frames.append(canvas)
        if i in (0,40,80):review.paste(canvas,(0,(0,40,80).index(i)*320))
    frames[0].save(root/'yuki-contact-motion-preview.gif',save_all=True,append_images=frames[1:],duration=20,loop=0)
    review.save(root/'yuki-contact-motion-review.png')
    report=dict(samples=len(cost),median_ms=round(statistics.median(cost),3),p95_ms=round(sorted(cost)[int(len(cost)*.95)],3),max_ms=round(max(cost),3))
    (root/'yuki-contact-motion-metrics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(report)


if __name__=='__main__':main()
