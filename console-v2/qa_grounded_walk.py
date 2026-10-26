"""Render the real Qt pet pipeline over multiple cycles and profile paint cost."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
import statistics
import time
from pathlib import Path

from PIL import Image,ImageDraw
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtWidgets import QApplication

from pet import DesktopPet
from settings_model import Preferences

ROOT=Path(__file__).resolve().parent


def main():
    app=QApplication.instance() or QApplication([])
    pet=DesktopPet(Preferences(random_movement=False))
    pet.animator.timer.stop()
    pet.state.action_player.stop()
    pet.state.gait_until=float('inf')
    pet.state.gait_render_offset=(0.,0.)
    out=ROOT/'qa/gait-v2'
    out.mkdir(parents=True,exist_ok=True)
    headings=[('right',(1.,0.)),('left',(-1.,0.)),('depth',(.6,.8)),('up',(.6,-.8))]
    frames=[];cost=[]
    review=Image.new('RGB',(960,760),'#d0d9e0')
    try:
        for tick in range(120):
            canvas=Image.new('RGB',(1360,400),'#d0d9e0')
            for col,(label,vector) in enumerate(headings):
                clock=tick*65/60
                pet.state.direction=1 if vector[0]>0 else -1
                pet.state.gait_vector=vector
                pet.state.gait_clock=clock
                image=QImage(360,380,QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(Qt.GlobalColor.transparent)
                painter=QPainter(image);painter.scale(2,2)
                t=time.perf_counter()
                pet.renderer.draw(painter,pet.state)
                cost.append((time.perf_counter()-t)*1000)
                painter.end()
                image=image.convertToFormat(QImage.Format.Format_RGBA8888)
                pil=Image.frombytes('RGBA',(360,380),bytes(image.constBits()))
                # Fixed-camera travel, in logical pixel units, through 3 cycles.
                x=col*340+(145 if vector[0]<0 else 15)+round(vector[0]*clock)
                y=(130 if vector[1]<0 else 20)+round(vector[1]*clock)
                small=pil.resize((180,190),Image.Resampling.LANCZOS)
                canvas.paste(small,(x,y),small)
                ImageDraw.Draw(canvas).text((col*340+12,360),label,fill='#294456')
                if tick in (0,12,24,36):
                    row=(0,12,24,36).index(tick)
                    review.paste(pil.resize((180,190),Image.Resampling.LANCZOS),(col*240,row*190),pil.resize((180,190),Image.Resampling.LANCZOS))
            frames.append(canvas)
        review.save(out/'render-samples.png')
        frames[0].save(out/'walking.gif',save_all=True,append_images=frames[1:],duration=17,loop=0)
        metrics=dict(frames=len(cost),median_paint_ms=round(statistics.median(cost),3),
                     p95_paint_ms=round(sorted(cost)[int(len(cost)*.95)],3),
                     max_paint_ms=round(max(cost),3))
        (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        print(json.dumps(metrics))
    finally:
        pet.hide();pet.deleteLater()


if __name__=='__main__':main()
