"""Render actual DesktopPet drawing and live window choreography offscreen."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QRect
from pet import DesktopPet
from settings_model import Preferences
from music_dance_asset import preload,metadata
from action_player import catalog

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'output/dance-no-flow-20261023'
OUT.mkdir(exist_ok=True,parents=True)
app=QApplication([])
pet=DesktopPet(replace(Preferences(),random_movement=False,auto_snap=False))
pet.move(210,105);pet.show();pet.animator.timer.stop();pet.bubble.timer.stop()
pet.screen_area=lambda:QRect(0,0,600,320)
pet.state.action_player.play('music-waltz',now=100,loop=True)
meta=catalog()['music-waltz'];frames=[];positions=[]
clock=[0]
for duration in meta['durations']:clock.append(clock[-1]+duration)
preview_durations=[]
for i in range(meta['frames']):
    now=100+clock[i]/1000
    preview_durations.append(meta['durations'][i])
    index=pet.state.action_player.frame(now)
    preload(index//metadata()['per_page']).result(timeout=20)
    pet.dance_stage.advance(now)
    image=QImage(180,190,QImage.Format.Format_RGBA8888);image.fill(0)
    painter=QPainter(image)
    with patch('pet.time.monotonic',return_value=now):pet.renderer.draw_pose(painter,pet.state)
    painter.end()
    sprite=Image.frombytes('RGBA',(180,190),bytes(image.bits()))
    canvas=Image.new('RGBA',(600,320),'#263747');canvas.alpha_composite(sprite,(pet.x(),pet.y()))
    frames.append(canvas.convert('RGB'));positions.append((pet.x(),pet.y()))
frames[0].save(OUT/'dance-footwork-live-preview.webp',save_all=True,append_images=frames[1:],duration=preview_durations,loop=0,quality=92,method=3)
review=Image.new('RGB',(1200,320),'#263747')
for i in range(8):
    review.paste(frames[round(i*(len(frames)-1)/7)].resize((300,160)),(i%4*300,i//4*160))
# Unstretched representative frame for direct inspection.
frames[len(frames)//2].save(OUT/'live-midpoint.png')
review.save(OUT/'live-motion-review.jpg',quality=94)
print('Rendered',len(frames),'live preview frames; x range',min(x for x,y in positions),max(x for x,y in positions),'y range',min(y for x,y in positions),max(y for x,y in positions),flush=True)
pet.close()
