"""Short, self-closing native Windows movement check; no saved preferences."""
import json
import math
import statistics
import sys
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from pet import DesktopPet
from settings_model import Preferences


def main():
    capture='--no-capture' not in sys.argv
    app=QApplication([])
    pet=DesktopPet(Preferences(random_movement=False,auto_snap=False))
    pet.state.sleep.awake_until=float('inf')
    area=app.primaryScreen().availableGeometry()
    x,y=area.left()+80,area.top()+max(30,(area.height()-pet.height())//2)
    pet.move(x,y)
    targets=[(x+110,y),(x+170,y+50),(x+60,y+80),(x,y)]
    frames=[];intervals=[];backwards=[];phase_resets=[]
    previous=[None];last_clock=[None];last_time=[time.perf_counter()];ticks=[0];segment=[0]
    root=Path(__file__).resolve().parent/'qa/gait-v2'
    root.mkdir(parents=True,exist_ok=True)
    pet.state.travel_target=targets[0]
    pet.state.ambient.next_at=float('inf')
    timer=QTimer()

    def finish():
        timer.stop();pet.animator.timer.stop()
        metrics=dict(platform=app.platformName(),capture=capture,segments=segment[0],completed=segment[0]==len(targets),samples=len(intervals),
                     median_tick_ms=round(statistics.median(intervals),2),
                     p95_tick_ms=round(sorted(intervals)[int(len(intervals)*.95)],2),
                     max_tick_ms=round(max(intervals),2),backwards_steps=len(backwards),
                     unexpected_phase_resets=len(phase_resets))
        (root/('native-metrics.json' if capture else 'native-timing.json')).write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        if frames:frames[0].save(root/'native-walking.gif',save_all=True,append_images=frames[1:],duration=64,loop=0)
        print(json.dumps(metrics),flush=True)
        pet.hide();pet.close();app.quit()

    def inspect():
        now=time.perf_counter();intervals.append((now-last_time[0])*1000);last_time[0]=now
        position=(pet.x(),pet.y())
        target=targets[segment[0]]
        if previous[0] is not None:
            movement=tuple(v-a for v,a in zip(position,previous[0]))
            heading=tuple(v-a for v,a in zip(target,previous[0]))
            if sum(a*b for a,b in zip(movement,heading))<-.1:backwards.append(position)
        if last_clock[0] is not None and pet.state.gait_clock<last_clock[0]-1e-6:phase_resets.append(position)
        previous[0]=position;last_clock[0]=pet.state.gait_clock;ticks[0]+=1
        if capture and ticks[0]%4==0:
            q=pet.grab().toImage().convertToFormat(pet.renderer.last_image.Format.Format_RGBA8888)
            im=Image.frombytes('RGBA',(q.width(),q.height()),bytes(q.constBits()))
            canvas=Image.new('RGB',(480,340),'#d0d9e0')
            canvas.paste(im,(position[0]-x+60,position[1]-y+40),im)
            frames.append(canvas)
        if pet.state.travel_target is None:
            segment[0]+=1;previous[0]=None
            if segment[0]==len(targets):finish();return
            pet.state.travel_target=targets[segment[0]]
        if len(intervals)>1500:finish()

    timer.timeout.connect(inspect)
    pet.show();timer.start(16)
    app.exec()


if __name__=='__main__':main()
