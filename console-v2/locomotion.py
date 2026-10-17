"""Distance-driven character motion; no shared action-player side effects."""
from pathlib import Path
import json,math
from functools import lru_cache
from PySide6.QtGui import QPixmap
ROOT=Path(__file__).resolve().parent/'assets/motion-v2'

@lru_cache(maxsize=1)
def metadata():return json.loads((ROOT/'clips.json').read_text(encoding='utf-8'))

@lru_cache(maxsize=5)
def frames(name):
    result=tuple(QPixmap(str(ROOT/name/f'{i:02}.png')) for i in range(metadata()[name]['frames']))
    if any(p.isNull() for p in result):raise ValueError('缺少走路或抓框动画素材')
    return result

def frame(name,distance=0.,elapsed=0.,moving=True,direction=1):
    spec=metadata()[name]
    if name=='hang':index=int(elapsed/spec.get('cycle',3)*spec['frames'])%spec['frames']
    else:index=int(max(0,distance)/spec['stride']*spec['frames'])%spec['frames']
    if direction<0 and name.startswith('climb'):index=(-index)%spec['frames']
    return frames(name)[index]

def step_towards(origin,target,speed,dt):
    """Bound movement by speed and dt; return new position and actual distance."""
    dx,dy=target[0]-origin[0],target[1]-origin[1];length=math.hypot(dx,dy)
    distance=min(length,max(0,speed)*max(0,min(.1,dt)))
    if length<1e-8:return tuple(target),0.,True
    ratio=distance/length
    return (origin[0]+dx*ratio,origin[1]+dy*ratio),distance,length<=distance+.01
