"""Preview the authored recovery through DesktopPet with its real timeline."""
import os,random,json
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from pet import DesktopPet
from settings_model import Preferences
ROOT=Path(__file__).resolve().parent;OUT=ROOT.parent/'output/dance-rest-20261023'
app=QApplication([]);pet=DesktopPet(replace(Preferences(),random_movement=False,auto_snap=False))
pet.show();pet.animator.timer.stop();pet.bubble.timer.stop()
with patch('action_player.random',random.Random(23)):pet.dance_recovery.start(100)
player=pet.state.action_player;durations=player.action['durations'];order=player.frame_order
frames=[];elapsed=0
for index,duration in enumerate(durations):
    now=100+(elapsed+duration*.5)/1000;elapsed+=duration
    image=QImage(180,190,QImage.Format.Format_RGBA8888);image.fill(0);painter=QPainter(image)
    with patch('pet.time.monotonic',return_value=now):pet.renderer.draw_pose(painter,pet.state)
    painter.end();sprite=Image.frombytes('RGBA',(180,190),bytes(image.bits()))
    canvas=Image.new('RGBA',(360,240),'#263747');canvas.alpha_composite(sprite,(90,24));frames.append(canvas.convert('RGB'))
frames[0].save(OUT/'dance-rest-live-preview.webp',save_all=True,append_images=frames[1:],duration=durations,loop=0,quality=95,method=3)
(OUT/'preview-timeline.json').write_text(json.dumps({'frame_order':order,'durations':durations,'seconds':sum(durations)/1000},indent=2),encoding='utf-8')
print('Rendered recovery:',len(frames),'slots;',sum(durations)/1000,'seconds')
pet.close()
