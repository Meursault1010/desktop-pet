"""Pointer-anchored body with compact, bashful reaching hands.

Generated compact arms/eyes supply the expression. A rigid, uniform sprite
transform adds effort without stretching anatomy. Qt only at runtime.
"""
import json
import math
import time
from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QImage,QPainter,QPixmap,QTransform
ROOT=Path(__file__).parent/'assets/drag-resist'


def direction(target):
    x,y=target
    if y<85:
        return 'upper-left' if x<70 else 'upper-right' if x>110 else 'up'
    if y>135:return 'down'
    return 'left' if x<90 else 'right'


@lru_cache(maxsize=6)
def asset(name):
    return QPixmap(str(ROOT/f'{name}.png'))


@lru_cache(maxsize=1)
def poses():
    return json.loads((ROOT/'poses.json').read_text(encoding='utf-8'))


def warm_assets():
    # Decode once before input, never block the first mouse move on PNG I/O.
    for name in poses():
        asset(name)


class DragFeedback:
    def __init__(self,target,compact=False):
        self.compact=compact
        self.target=target;self.name=direction(target);self.started=time.monotonic()
        self.hand=tuple(poses()[self.name]['hand'])
        self.delta=(target[0]-10-self.hand[0]*.625,target[1]-25-self.hand[1]*.625)
        self.frames={}

    def body_origin(self):
        if self.compact:return 10,25
        tx,ty=self.target
        return 210-tx+10,220-ty+25

    def vertex(self,x,y,phase):
        hx,hy=self.hand;dx,dy=self.delta;ox,oy=self.body_origin()
        distance=math.hypot(x-hx,y-hy)
        # Smooth local hand bend; the palm center has exact unit weight.
        weight=math.exp(-(distance/64)**2)
        # Tiny repeated attempts, never stretch the art until palms reach the
        # pointer. The body stays anchored to the original mouse grab point.
        reach=min(1.,7/max(.001,math.hypot(dx,dy)))
        effort_scale=.72+.28*math.sin(phase)
        rx,ry=dx*reach*effort_scale,dy*reach*effort_scale
        effort=math.sin(phase)*1.8+math.sin(phase*3)*.45
        depth=max(0,min(1,(y-80)/170))
        return QPointF(ox+x*.625+rx*weight+effort*(1-weight)*depth,
                       oy+y*.625+ry*weight+math.sin(phase*2)*.7*(1-weight)*depth)

    def image(self,index):
        if index in self.frames:return self.frames[index]
        width,height=(180,190) if self.compact else (420,440)
        image=QImage(width,height,QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
        p=QPainter(image);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        pixmap=asset(self.name)
        # One cached sprite transform instead of hundreds of clipped triangles
        # on the GUI thread. Compact arms retain their authored proportions.
        p.setTransform(self.sprite_transform(index))
        p.drawPixmap(QRectF(-80,-80,160,160),pixmap,QRectF(0,0,256,256))
        p.end();self.frames[index]=image
        return image

    def sprite_transform(self,index):
        phase=index*math.tau/32
        ox,oy=self.body_origin()
        transform=QTransform()
        transform.translate(ox+80,oy+80)
        transform.rotate(math.sin(phase)*.9)
        transform.translate(math.sin(phase*3)*.45,math.sin(phase*2)*.6)
        return transform

    def paint(self,painter,now=None):
        elapsed=max(0,(now or time.monotonic())-self.started)
        index=int(elapsed*32/1.1)%32
        painter.drawImage(0,0,self.image(index))

