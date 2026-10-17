"""Render all four edge cases using deployed art; never touch user settings."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication
from icon_sleep import DEFAULTS, placement, pose_bounds

app=QApplication([])
root=Path(__file__).parent
poses={side:QPixmap(str(root/'assets/icon-sleep'/f'{side}.png')) for side in ('left','back','right')}
bounds={side:pose_bounds(pixmap.toImage()) for side,pixmap in poses.items()}
canvas=QImage(1000,700,QImage.Format.Format_ARGB32_Premultiplied)
canvas.fill(QColor('#111827')); draw=QPainter(canvas)
for index,icon in enumerate(((0,0,34,34),(446,0,34,34),(0,286,34,34),(446,286,34,34))):
    draw.save();draw.translate((index%2)*500+10,(index//2)*350+20)
    draw.setClipRect(0,0,480,320);draw.fillRect(0,0,480,320,QColor('#334155'))
    side,(x,y)=placement(icon,(196,207),'left',DEFAULTS,(0,0,480,320),bounds)
    # Largest inhalation: the most conservative vertical extent.
    height=207*.88*1.009;width=196*.94
    draw.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    draw.drawPixmap(QRectF(x+(196-width)/2,y+207*.98-height,width,height),poses[side],QRectF(0,0,256,256))
    ix,iy,iw,ih=icon
    draw.fillRect(QRectF(ix,iy,iw,ih),QColor('#fbbf24'))
    draw.setPen(QColor('#ffffff'));draw.drawText(150,170,f'preferred: left / actual: {side}')
    draw.restore()
draw.end()
output=root/'qa/icon-sleep/edges-fixed.png';output.parent.mkdir(parents=True,exist_ok=True)
canvas.save(str(output));print(output)
