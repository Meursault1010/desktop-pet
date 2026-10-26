"""Distance-driven character motion; no shared action-player side effects."""
from pathlib import Path
import json,math
from functools import lru_cache
from PySide6.QtGui import QPixmap
ROOT=Path(__file__).resolve().parent/'assets/motion-v2'
WALK_PADDING=0
# The live rig uses the baked 40px stride so the feet have room to separate
# and then cross. Travel speed stays at the previous value: longer steps,
# calmer cadence.
WALK_STRIDE_FACTOR=1.
WALK_SPEED_FACTOR=.65*.7


def walking_speed(requested):
    """One shared tempo for displacement and the distance-driven foot cycle."""
    return max(0.,float(requested))*WALK_SPEED_FACTOR


def contact_progress(phases,index,progress):
    """Monotone cubic travel: keep authored grip holds, smooth pull boundaries."""
    if index>=len(phases)-1:return phases[-1]
    index=max(0,min(len(phases)-2,index));t=max(0.,min(1.,progress))
    a,b=phases[index:index+2]
    def slope(i):
        if i==0 or i==len(phases)-1:return 0.
        left,right=phases[i]-phases[i-1],phases[i+1]-phases[i]
        return 2*left*right/(left+right) if left*right>0 else 0.
    return ((2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*slope(index)
            +(-2*t**3+3*t*t)*b+(t**3-t*t)*slope(index+1))

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


# The baked clips carry the actual support trajectory. A stride is authored
# explicitly: inferring it from quantized extrema can shrink it to a few pixels.
WALK_CONTACTS = {name: tuple(tuple(p) for p in metadata()[name]['contacts'])
                 for name in ('walk-right','walk-left')}


def walk_stride(name):
    return float(metadata()[name]['stride'])*WALK_STRIDE_FACTOR


def ground_progress(clock, stride):
    """Travel remains continuous through foot changes; no stop every half-step."""
    return max(0.,clock)


def depth_stride(name,vector=None):
    # Screen-space depth must not accelerate the legs several times per step.
    return 1.


def gait_advance(clock, name, speed, dt, scale=1.,vector=None):
    distance=walking_speed(speed)*max(0.,min(.1,dt))
    return distance,clock+distance/max(.01,scale)


def support_sample(name, clock, vector=None):
    contacts=WALK_CONTACTS[name]
    phase=(max(0.,clock)/walk_stride(name))%1
    index=min(len(contacts)-1,int(phase*len(contacts)))
    from walk_rig import sample
    vector=vector if vector is not None else (1. if name=='walk-right' else -1.,0.)
    samples,support,_=sample(clock,walk_stride(name),vector)
    x,y=samples[support][3]
    return index,contacts[index],(256-x if name=='walk-left' else x,y)


def planted_frame(name,clock,vector=None):
    """Sample finished artwork; the paint path never deforms or decodes pixels."""
    index=int((max(0.,clock)/walk_stride(name))%1*len(WALK_CONTACTS[name]))
    return frames(name)[index]
