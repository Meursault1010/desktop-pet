"""One synchronous drop decision; background icon discovery never moves the pet."""
import math
import time
from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication
from icon_sleep import logical_rect
from edge_attachment import logical_surface
from window_edges import visible_surfaces


def icon_candidate(pet,point,surfaces):
    poses=pet.state.icon_sleep
    if not poses or time.monotonic()-poses.scanned_at>3:return None
    screens=QGuiApplication.screens()
    blockers=[logical_surface(s,screens)[0] for s in surfaces]
    choices=[]
    for icon in poses.icons:
        try:rect,_=logical_rect(icon['rect'])
        except ValueError:continue
        x,y,w,h=rect;cx=x+w/2;cy=y+h/2
        if any(bx< x+w and bx+bw>x and by<y+h and by+bh>y for bx,by,bw,bh in blockers):continue
        # The pointer may be on the head or skirt. Accept actual body overlap,
        # or a pointer just beside the glyph, without considering icon labels.
        px,py=point.x(),point.y()
        pointer=math.hypot(max(x-px,0,px-x-w),max(y-py,0,py-y-h))
        foot=math.hypot(pet.x()+pet.width()*.5-cx,pet.y()+pet.height()*.75-cy)
        radius=min(poses.options['snap_distance'],max(36,pet.width()*.45))
        if pointer<=min(30,radius) or foot<=radius:
            choices.append((min(pointer,foot),icon['id']))
    return min(choices)[1] if choices else None


def settle_drop(pet,point=None):
    if not pet.preferences.auto_snap or not pet.isVisible():return False
    point=point or QPoint(pet.x()+pet.width()//2,pet.y()+pet.height()//2)
    edge=pet.state.edge_attachment
    try:
        surfaces=visible_surfaces(edge.excluded() if edge else ())
        target=icon_candidate(pet,point,surfaces)
        if target:
            pet.state.icon_sleep.start(target,instant=True,auto_pose=True)
            return True
        return bool(edge and edge.on_drop(surfaces,point))
    except (ValueError,OSError,RuntimeError) as error:
        if edge:edge.error=str(error)
        return False
