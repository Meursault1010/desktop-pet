"""Pointer-anchored, articulated reach with a fixed grab point.

Generated directional palms/eyes supply the expression. A small mesh bends
arms toward the actual click while the torso, hair and legs struggle around
that fixed point. Qt only: no imaging packages added to the installation.
"""
import json
import math
import time
from pathlib import Path
from functools import lru_cache
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QImage,QPainter,QPixmap,QPolygonF,QTransform,QPainterPath
ROOT=Path(__file__).parent/'assets/drag-resist'


def direction(target):
    x,y=target
    if y<85:
        return 'upper-left' if x<70 else 'upper-right' if x>110 else 'up'
    if y>135:return 'down'
    return 'left' if x<90 else 'right'


@lru_cache(maxsize=6)
def asset(name):return QPixmap(str(ROOT/f'{name}.png'))


class DragFeedback:
    def __init__(self,target):
        self.target=target;self.name=direction(target);self.started=time.monotonic()
        self.hand=tuple(json.loads((ROOT/'poses.json').read_text(encoding='utf-8'))[self.name]['hand'])
        self.delta=(target[0]-10-self.hand[0]*.625,target[1]-25-self.hand[1]*.625)
        self.frames={}

    def body_origin(self):
        tx,ty=self.target;dx,dy=self.delta
        return 210-tx+10+dx*.6,220-ty+25+dy*.6

    def vertex(self,x,y,phase):
        hx,hy=self.hand;dx,dy=self.delta;ox,oy=self.body_origin()
        distance=math.hypot(x-hx,y-hy)
        # Smooth local hand bend; the palm center has exact unit weight.
        weight=math.exp(-(distance/64)**2)
        effort=math.sin(phase)*1.8
        depth=max(0,min(1,(y-80)/170))
        return QPointF(ox+x*.625+dx*.4*weight+effort*(1-weight)*depth,
                       oy+y*.625+dy*.4*weight+math.sin(phase*2)*.7*(1-weight)*depth)

    def image(self,index):
        if index in self.frames:return self.frames[index]
        phase=index*math.tau/16
        image=QImage(420,440,QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
        p=QPainter(image);p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        hx,hy=self.hand
        xs=sorted(set([*range(0,257,16),hx]));ys=sorted(set([*range(0,257,16),hy]))
        pixmap=asset(self.name)
        # Piecewise affine triangles cannot fold on the modest local hand bend.
        for x1,x2 in zip(xs,xs[1:]):
            for y1,y2 in zip(ys,ys[1:]):
                corners=[(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
                for ids in ((0,1,2),(0,2,3)):
                    a,b,c=[corners[i] for i in ids]
                    source=QPolygonF([QPointF(*a),QPointF(*b),QPointF(*c),QPointF(a[0]+c[0]-b[0],a[1]+c[1]-b[1])])
                    aa,bb,cc=[self.vertex(*corners[i],phase) for i in ids]
                    dest=QPolygonF([aa,bb,cc,aa+cc-bb])
                    transform=QTransform();success=QTransform.quadToQuad(source,dest,transform)
                    if not success:continue
                    path=QPainterPath();path.addPolygon(QPolygonF([aa,bb,cc]));p.save();p.setClipPath(path);p.setTransform(transform)
                    p.drawPixmap(0,0,pixmap);p.restore()
        p.end();self.frames[index]=image
        return image

    def paint(self,painter,now=None):
        elapsed=max(0,(now or time.monotonic())-self.started)
        index=int(elapsed*16/1.1)%16
        painter.drawImage(0,0,self.image(index))

