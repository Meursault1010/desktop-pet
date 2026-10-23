"""Render the shipping presence controller into a desktop-space preview."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import Qt
from PIL import Image,ImageDraw
from pet_presence import Presence
app=QApplication([])
out=Path(__file__).resolve().parent.parent/'output/yuki-presence-keyframes'
frames=[]
for side,home in [('right',(300,35)),('left',(110,35))]:
    for visible in (True,False):
        p=Presence();p.begin(visible,now=10,position=home,area=(0,0,600,240),size=(180,190))
        for i in range(round(p.duration*30)+1):
            now=10+min(p.duration,i/30)
            image=QImage(180,190,QImage.Format.Format_RGBA8888);image.fill(Qt.GlobalColor.transparent)
            painter=QPainter(image);p.paint(painter,now);painter.end()
            sprite=Image.frombytes('RGBA',(180,190),bytes(image.bits()))
            canvas=Image.new('RGBA',(600,240),'#263747')
            x,y=p.position(now);canvas.alpha_composite(sprite,(round(x),round(y)))
            draw=ImageDraw.Draw(canvas);draw.text((14,12),f'{side} / {"ARRIVAL" if visible else "DEPARTURE"}',fill='white')
            frames.append(canvas.convert('RGB'))
frames[0].save(out/'presence-preview.gif',save_all=True,append_images=frames[1:],duration=33,loop=0)
frames[len(frames)//8].save(out/'presence-preview.png')
print('Saved',len(frames),'preview frames')
