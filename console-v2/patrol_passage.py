"""Horizontal screen exits; layer changes only while completely out of view."""
import random
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication
from locomotion import walking_speed


class ScreenPassage:
    def __init__(self, pet, depth):
        self.pet, self.depth = pet, depth
        self.active = False
        self.screen = None
        self.phase = ''

    def begin(self, now):
        p = self.pet
        self.screen = p.screen()
        self.area = self.screen.geometry()
        self.home = (p.x(), p.y())
        sides=[]
        for side,x in (('left',self.area.left()-p.width()-4),('right',self.area.right()+5)):
            outside=QRect(x,p.y(),p.width(),p.height())
            if not any(s!=self.screen and s.geometry().intersects(outside) for s in QGuiApplication.screens()):
                sides.append(side)
        if not sides:
            return False
        self.sides=sides
        side = random.choice(sides)
        self.destination = (self.area.left()-p.width()-4 if side == 'left' else self.area.right()+5, p.y())
        self.phase, self.active = 'leaving', True
        # Deadline follows real displacement, not the raw preference value:
        # walking_speed scales it down, so a fast-looking budget cancelled
        # slow walkers before they ever reached the edge.
        self.speed = max(10., walking_speed(p.preferences.speed))
        self.deadline = now+abs(p.x()-self.destination[0])/self.speed*2+10
        p.state.travel_position = None
        return True

    def tick(self, now, dt):
        p = self.pet
        if p.screen() != self.screen or self.screen.geometry() != self.area or now > self.deadline:
            self.cancel()
            return True
        self.depth.update(now)
        if not p.advance_to(self.destination, dt):
            return False
        if self.phase == 'leaving':
            self.depth.cross_edge(self.screen)
            # Relocation happens entirely outside the visible screen. The
            # return remains horizontal, never an unsupported upward walk.
            left = random.choice(self.sides) == 'left'
            # Keep the same height on every layout. Randomising y while the
            # pet is invisible reads as a fake climb, not as a layer change.
            y = self.home[1]
            x = self.area.left()-p.width()-4 if left else self.area.right()+5
            p.move(x,y)
            p.state.position_x = float(x)
            p.state.travel_position = None
            self.destination = (self.area.left()+12 if left else self.area.right()-p.width()-11,y)
            self.phase = 'returning'
            self.deadline = now+abs(p.x()-self.destination[0])/self.speed*2+10
            self.depth.update(now)
            return False
        self.active = False
        p.state.travel_position = None
        p.state.gait_until = 0
        return True

    def cancel(self):
        if not self.active:
            return
        p = self.pet
        area = p.screen_area()
        body = QRect(p.x(),p.y(),p.width(),p.height())
        if not area.contains(body):
            p.move(max(area.left(),min(area.right()-p.width()+1,p.x())),
                   max(area.top(),min(area.bottom()-p.height()+1,p.y())))
        p.state.position_x = float(p.x())
        p.state.travel_position = None
        p.state.gait_until = 0
        self.active = False
