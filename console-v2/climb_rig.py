"""Small, contact-driven climbing from one unchanged, approved pose.

Only the arm regions articulate. Hair, face and clothing never interpolate
between separately drawn images. Distance is measured in sprite pixels.
"""
import math
from functools import lru_cache
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QPainter,QPainterPath,QPixmap,QTransform

STRIDE=16.
SAMPLES=60


def hand_sample(distance,direction=1):
    phase=(distance/STRIDE)%1.
    support=0 if phase<.5 else 1
    t=(phase*2)%1.
    shifts=[]
    for hand in range(2):
        shift=4.*(1-2*t) if hand==support else 4.*(-1-2*t+12*t*t-8*t*t*t)
        shifts.append(direction*shift)
    return tuple(shifts),support


def _weight(y,hand):
    # Raised palm -> forearm -> shoulder. The shoulders stay on the body.
    if hand==0:return max(0.,min(1.,(80.-y)/14.))
    return max(0.,min(1.,(125.-y)/27.))*max(0.,min(1.,(y-76.)/8.))


@lru_cache(maxsize=128)
def _image(name,index,direction):
    from locomotion import frames
    source=frames(name)[0]
    result=QPixmap(256,256);result.fill(Qt.GlobalColor.transparent)
    painter=QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    shifts,_=hand_sample(index/SAMPLES*STRIDE,direction)
    # Distinct reference art for each side; do not mirror the hair ornament.
    left=name=='climb-left'
    xs=(151.,158.,165.,173.,184.,196.) if left else (60.,72.,80.,88.,96.,105.)
    ys=(20.,32.,48.,64.,72.,80.,88.,96.,108.,118.,126.)
    roi=QRectF(xs[0],ys[0],xs[-1]-xs[0],ys[-1]-ys[0])
    outside=QPainterPath();outside.addRect(QRectF(0,0,256,256))
    cut=QPainterPath();cut.addRect(roi)
    painter.setClipPath(outside.subtracted(cut));painter.drawPixmap(0,0,source)
    painter.setClipping(False)

    def destination(x,y):
        weight=max(0.,min(1.,(x-151.)/22.)) if left else max(0.,min(1.,(105.-x)/25.))
        return QPointF(x,y+weight*sum(s*_weight(y,h) for h,s in enumerate(shifts)))

    for x0,x1 in zip(xs,xs[1:]):
        for y0,y1 in zip(ys,ys[1:]):
            points=((x0,y0),(x1,y0),(x1,y1),(x0,y1))
            mapped=[destination(x,y) for x,y in points]
            for indices in ((0,1,2),(0,2,3)):
                a,b,c=[points[i] for i in indices]
                da,db,dc=[mapped[i] for i in indices]
                determinant=(b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])
                by=((b[0]-a[0])*(dc.y()-da.y())-(c[0]-a[0])*(db.y()-da.y()))/determinant
                ay=((db.y()-da.y())*(c[1]-a[1])-(dc.y()-da.y())*(b[1]-a[1]))/determinant
                offset=da.y()-ay*a[0]-by*a[1]
                path=QPainterPath(da);path.lineTo(db);path.lineTo(dc);path.closeSubpath()
                painter.save();painter.setClipPath(path)
                painter.setTransform(QTransform(1.,ay,0.,by,0.,offset))
                patch=QRectF(x0,y0,x1-x0,y1-y0)
                painter.drawPixmap(patch,source,patch);painter.restore()
    painter.end()
    return result


def paint(painter,rect,name,distance,direction=1):
    index=round((distance/STRIDE)%1.*SAMPLES)%SAMPLES
    image=_image(name,index,direction)
    painter.drawPixmap(rect,image,QRectF(0,0,256,256))


def pull_progress(clock):
    """Body advances during the pull, easing at the handoff of each grip."""
    half=STRIDE/2.
    count=math.floor(clock/half)
    t=clock/half-count
    return (count+t*t*(3-2*t))*half
