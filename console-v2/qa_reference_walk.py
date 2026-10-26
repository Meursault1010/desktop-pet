"""Unapplied gait study: current rendered feet versus a sagittal 3D sketch."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import math
from pathlib import Path
from PIL import Image,ImageDraw
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QRectF
from walk_rig import paint


def foot(phase):
    p=phase%1
    if p<.6:return 14-28*p/.6,0
    t=(p-.6)/.4
    return -14+28*(3*t*t-2*t*t*t),8*math.sin(math.pi*t)**2


def joints(phase,lateral):
    x,lift=foot(phase)
    hip=(0,33+.3*math.cos(phase*math.tau*2))
    ankle=(x,1+lift)
    dx,dz=x-hip[0],ankle[1]-hip[1]
    distance=math.hypot(dx,dz)
    # Equal, constant 18-unit thigh/shin; flexion follows the sagittal plane.
    bend=math.sqrt(max(0,18**2-distance**2/4))
    knee=((hip[0]+x)/2-dz/distance*bend,
          (hip[1]+ankle[1])/2+dx/distance*bend)
    return [(a,lateral,z) for a,z in (hip,knee,ankle)]


def main():
    app=QApplication.instance() or QApplication([])
    canvas=Image.new('RGB',(1120,700),'#202b40');d=ImageDraw.Draw(canvas)
    d.text((24,18),'WALK STUDY / current rendering and reference-based joint sketch',fill='#e9f3ff')
    d.text((24,45),'Study only - reference sketch is NOT applied to Yuki',fill='#a6c6da')
    labels=('CONTACT','DOWN / LOAD','PASSING','UP / PREPARE')
    for col,p in enumerate((0,.125,.25,.375)):
        left=col*280
        d.text((left+18,85),labels[col],fill='#d5e9fd')
        im=QImage(256,256,QImage.Format.Format_RGBA8888);im.fill(0)
        q=QPainter(im);paint(q,QRectF(0,0,256,256),'walk-right',p*40);q.end()
        sprite=Image.frombytes('RGBA',(256,256),bytes(im.constBits()))
        crop=sprite.crop((83,195,185,254)).resize((244,141),Image.Resampling.LANCZOS)
        canvas.paste(crop,(left+18,126),crop)
        d.text((left+18,285),'CURRENT / fixed-height foot tracks',fill='#b7c6d9')
        def project(v):
            x,y,z=v
            return left+134+3*(.84*x+.54*y),570+3*(.23*x-.35*y-.94*z)
        # Far leg first; projection, rather than changed bone lengths, creates
        # the size and overlap differences. Both feet share one ground plane.
        hips=[]
        for phase,lateral,color in ((p+.5,6,'#738da8'),(p,-6,'#cceeff')):
            hip,knee,ankle=map(project,joints(phase,lateral));hips.append(hip)
            d.line((hip,knee,ankle),fill=color,width=13)
            for point in (hip,knee,ankle):
                x,y=point;d.ellipse((x-5,y-5,x+5,y+5),fill='#60bde4')
            ax,ay=ankle;d.line((ax-9,ay+4,ax+15,ay+9),fill=color,width=7)
        d.line(hips,fill='#d8e8fa',width=8)
        hx=sum(v[0] for v in hips)/2;hy=sum(v[1] for v in hips)/2
        d.line((hx,hy,hx,hy-72),fill='#d8e8fa',width=10)
        d.line((left+32,591,left+248,591),fill='#52637a',width=1)
        d.text((left+18,618),'REFERENCE JOINT STUDY',fill='#cceeff')
    d.text((24,660),'Equal bone lengths / knee flexion / projected foot depth / stable near-far identity',fill='#9bb9d3')
    dest=Path(__file__).resolve().parent.parent/'output/yuki-walk-reference-study.png'
    canvas.save(dest)
    print(dest)


if __name__=='__main__':main()
