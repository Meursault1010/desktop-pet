"""Nearest exposed, feasible support point on window or screen perimeter."""
from dataclasses import dataclass
import math
from icon_sleep import GEOMETRIES,pose_envelope
from icon_pose_geometry import PoseGeometry,silhouette_envelope
from locomotion import metadata

@dataclass(frozen=True)
class Landing:
    pose:str
    position:tuple[float,float]
    kind:str
    anchor:tuple[float,float]
    distance:float
    # Allowed grip coordinate on this edge, already reduced for full silhouette.
    interval:tuple[float,float]
    parameter:float

def geometry(pose):
    return GEOMETRIES[pose] if pose in GEOMETRIES else PoseGeometry(tuple(metadata()[pose]['contact']))

def envelope(size,bounds,pose):
    if pose in GEOMETRIES:return pose_envelope(size,bounds[pose],pose)
    l,t,r,b=metadata()[pose]['bounds'];pw,ph=size
    return silhouette_envelope(size,(max(0,l-.006),max(0,t-.006),min(1,r+.006),min(1,b+.006)),geometry(pose))

def contact_offset(size,pose):
    cx,cy=geometry(pose).contact;pw,ph=size
    return pw*(.03+.94*cx),ph*(.10+.88*cy)

def clamp(value,lo,hi):return max(lo,min(hi,value))

def candidates(rect,area,size,bounds,origin,variant=0,blocked=(),screen=False):
    """Project current character center onto every feasible edge, no fixed slots.

    Rejected points are behind a higher z-order window. Try projections onto
    exposed interval endpoints too, so a partially covered edge remains usable.
    """
    x,y,w,h=rect;ax,ay,aw,ah=area;pw,ph=size
    center=(origin[0]+pw*.5,origin[1]+ph*.5)
    top=['sit-front','sit-back','prone-front','prone-back'];top=top[variant%4:]+top[:variant%4]
    specs=[(p,'top',y,x,x+w) for p in top]+[('climb-left','left',x,y,y+h),('climb-right','right',x+w,y,y+h),('hang','bottom',y+h,x,x+w)]
    result=[]
    for priority,(pose,kind,line,lo,hi) in enumerate(specs):
        ox,oy=contact_offset(size,pose);l,t,r,b=envelope(size,bounds,pose)
        horizontal=kind in ('top','bottom')
        if horizontal:
            low=max(lo+12,ax+2+ox-l);high=min(hi-12,ax+aw-2+ox-r)
            fixed=line-oy
            if fixed+t<ay+2 or fixed+b>ay+ah-2:continue
            projected=center[0]
        else:
            low=max(lo+8,ay+2+oy-t)
            support=ph*.88*(metadata()[pose]['support_bottom']-geometry(pose).contact[1])
            high=min(hi-max(8,support),ay+ah-2+oy-b)
            fixed=line-ox
            if fixed+l<ax+2 or fixed+r>ax+aw-2:continue
            projected=center[1]
        if low>high:continue
        # Split the one-dimensional edge into exposed intervals. Inflate the
        # blockers by 3px so a grip never disappears under a higher window.
        spans=[(low,high)]
        for bx,by,bw,bh in blocked:
            crosses=by-3<=line<=by+bh+3 if horizontal else bx-3<=line<=bx+bw+3
            if not crosses:continue
            cutlo,cuthi=(bx-3,bx+bw+3) if horizontal else (by-3,by+bh+3)
            split=[]
            for a,z in spans:
                if cuthi<a or cutlo>z:split.append((a,z))
                else:
                    if a<cutlo:split.append((a,min(z,cutlo)))
                    if cuthi<z:split.append((max(a,cuthi),z))
            spans=split
        for a,z in spans:
            if z-a<2:continue
            p=clamp(projected,a,z)
            anchor=(p,line) if horizontal else (line,p)
            position=(anchor[0]-ox,anchor[1]-oy)
            distance=math.hypot(center[0]-anchor[0],center[1]-anchor[1])
            result.append((priority,Landing(pose,position,kind,anchor,distance,(a,z),p)))
    return result

def nearest(rect,area,size,bounds,origin,variant=0,blocked=()):
    choices=candidates(rect,area,size,bounds,origin,variant,blocked)
    if not choices:raise ValueError('附近没有足够空间抓住边框，请缩小宠物')
    # Pose preference only breaks equal-distance ties, never overrides locality.
    return min(choices,key=lambda pair:(round(pair[1].distance,6),pair[0]))[1]

def corner_landing(area,size,bounds,origin,preferred='right'):
    ax,ay,aw,ah=area;choices=[]
    for corner,pose in (('left','perch-back'),('right','perch-front')):
        l,t,r,b=envelope(size,bounds,pose)
        if r-l>aw-24 or b-t>ah-12:continue
        px=ax+12-l if corner=='left' else ax+aw-12-r;py=ay+ah-6-b
        distance=math.hypot(px-origin[0],py-origin[1])
        landing=Landing(pose,(px,py),'corner',(px+l,py+b),distance,(0,0),0)
        choices.append((distance,corner!=preferred,landing))
    if not choices:raise ValueError('屏幕空间不足，请缩小宠物')
    return min(choices,key=lambda item:(round(item[0],6),item[1]))[2]


def screen_landings(area,size,bounds,origin,blocked=()):
    """Inside-facing grips at screen sides/top; grounded rest at bottom."""
    ax,ay,aw,ah=area;pw,ph=size;result=[]
    for pose,kind in [('climb-right','left'),('climb-left','right'),('hang','top'),('perch-front','bottom'),('perch-back','bottom')]:
        ox,oy=contact_offset(size,pose);l,t,r,b=envelope(size,bounds,pose)
        if kind in ('left','right'):
            px=ax+3-l if kind=='left' else ax+aw-3-r
            lo=ay+3+oy-t;hi=ay+ah-3+oy-b;p=clamp(origin[1]+ph*.5,lo,hi)
            position=(px,p-oy);anchor=(px+ox,p);interval=(lo,hi)
        else:
            py=ay+3-t if kind=='top' else ay+ah-3-b
            lo=ax+3+ox-l;hi=ax+aw-3+ox-r;p=clamp(origin[0]+pw*.5,lo,hi)
            position=(p-ox,py);anchor=(p,py+oy);interval=(lo,hi)
        if lo>hi:continue
        # Do not grip a desktop boundary hidden by an application.
        if any(bx-4<=anchor[0]<=bx+bw+4 and by-4<=anchor[1]<=by+bh+4 for bx,by,bw,bh in blocked):continue
        distance=math.hypot(origin[0]+pw*.5-anchor[0],origin[1]+ph*.5-anchor[1])
        result.append(Landing(pose,position,kind,anchor,distance,interval,p))
    return result
