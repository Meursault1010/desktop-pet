"""Interruptible local errands; never opens files or moves desktop icons."""
import math
import random
import time
from datetime import datetime

from desktop_icons import desktop_exposed
from action_player import catalog
from icon_sleep import logical_rect, alpha_region, placement
from PySide6.QtWidgets import QApplication


MEALS = ((7, 9, 'breakfast', '早餐时间，慢慢吃一点。'),
         (12, 14, 'lunch', '午饭时间到了，先填饱小肚子。'),
         (18, 20, 'dinner', '吃过晚饭，再懒懒地待一会儿。'))


def due_meal(at, completed):
    for start, end, key, line in MEALS:
        stamp = at.date().isoformat()+'/'+key
        if start <= at.hour < end and completed.get(key) != stamp:
            return key, stamp, line
    return None


class Patrol:
    def __init__(self, pet, icons, store):
        self.pet, self.icons, self.store = pet, icons, store
        self.phase = 'idle'
        self.kind = ''
        self.label = ''
        self.destination = None
        self.target = None
        self.owned_start = None
        self.next_at = time.monotonic()+random.uniform(45, 80)
        self.next_snack = time.monotonic()+random.uniform(1200, 2400)
        self.until = 0.
        self.probe_at = 0.
        self.icon_started = None
        self.lean_pose = 'left'
        self.meal = None
        self.roll_origin = None
        self.completed = {key: store.settings.value('routine/meals/'+key, '') for _, _, key, _ in MEALS}

    @property
    def active(self):
        return self.phase != 'idle'

    def snapshot(self):
        return dict(active=self.active, phase=self.phase, activity=self.label)

    def cancel(self, now=None):
        now = time.monotonic() if now is None else now
        was = self.active
        player = self.pet.state.action_player
        if self.owned_start is not None and player.started == self.owned_start:
            player.stop()
        owned_icon = self.kind == 'lean' and self.icon_started == self.icons.started and self.icons.target is self.target
        if owned_icon:
            self.icons.wake('休息好了')
        if was:
            if self.kind != 'lean' or owned_icon:
                self.pet.clearMask()
            self.pet.state.travel_position = None
            self.pet.state.walking = False
            self.pet.state.gait_until = 0
            self.pet.state.next_action = now+random.uniform(15, 25)
            self.pet.state.ambient.defer(now, self.pet.preferences.activity)
        self.phase, self.kind, self.label = 'idle', '', ''
        self.target = self.destination = self.owned_start = None
        self.icon_started = self.meal = self.roll_origin = None
        pace = {'少动': 1.6, '默认': 1., '活跃': .75}[self.pet.preferences.activity]
        self.next_at = now+random.uniform(80, 170)*pace
        if was:
            self.pet.state_changed.emit()

    def blocked(self):
        p, s = self.pet, self.pet.state
        return (not p.isVisible() or not p.desired_visible() or p.presence.active
                or p.drag_origin is not None or s.physics.active or p.preferences.quiet
                or p.preferences.paused or not p.preferences.random_movement
                or bool(s.music and s.music.active)
                or s.travel_target is not None
                or bool(getattr(p.controller, 'quick_pending', None))
                or bool(p.bubble.parts and p.bubble.kind != 'ambient')
                or bool(s.edge_attachment and s.edge_attachment.active)
                or QApplication.activePopupWidget() is not None
                or bool(self.icons.target and not (self.kind == 'lean' and self.icons.target is self.target
                                                   and self.icon_started == self.icons.started)))

    def exposed(self, position, screen, size=None):
        area = screen.geometry()
        scale = screen.devicePixelRatio()
        x, y = position
        physical = (round(area.x()+(x-area.x())*scale),
                    round(area.y()+(y-area.y())*scale),
                    round((size or (self.pet.width(),self.pet.height()))[0]*scale),
                    round((size or (self.pet.width(),self.pet.height()))[1]*scale))
        try:
            return desktop_exposed(physical, int(self.pet.winId()), (int(self.pet.bubble.winId()),))
        except (OSError, RuntimeError):
            return False

    def route_exposed(self, destination, screen):
        if screen != self.pet.screen():
            return False
        x, y = min(self.pet.x(),destination[0]), min(self.pet.y(),destination[1])
        return self.exposed((x,y), screen,
            (abs(self.pet.x()-destination[0])+self.pet.width(), abs(self.pet.y()-destination[1])+self.pet.height()))

    def icon_destination(self):
        p = self.pet
        candidates = []
        for icon in self.icons.icons:
            try:
                rect, screen = logical_rect(icon['rect'])
                area = screen.availableGeometry()
                x, y, w, h = rect
                # Rest below the icon, with the head tucked beneath its lower edge.
                px = round(max(area.left(), min(area.right()-p.width()+1, x+w/2-p.width()/2)))
                py = round(max(area.top(), min(area.bottom()-p.height()+1, y+h-p.height()*.38)))
                distance = math.hypot(px-p.x(), py-p.y())
                if distance <= min(360, max(65, p.preferences.speed)*7) and self.route_exposed((px, py), screen):
                    candidates.append((distance, icon, (px, py), screen))
            except (ValueError, KeyError):
                continue
        candidates.sort(key=lambda item: item[0])
        return random.choice(candidates[:3]) if candidates else None

    def play(self, key, now, duration=None):
        s = self.pet.state
        s.ambient.current = None
        s.walking = False
        s.gait_until = 0
        s.action_player.play(key, now=now, loop=key == 'sleep')
        self.owned_start = now
        self.until = now+(duration if duration is not None else sum(s.action_player.action['durations'])/1000)
        self.phase = 'doing'
        self.pet.state_changed.emit()

    def tick(self, now, dt, at=None):
        at = at or datetime.now()
        p, s = self.pet, self.pet.state
        if self.blocked():
            if self.active:
                self.cancel(now)
            return
        if self.active:
            if self.kind == 'roll' and s.action_player.action is None and now >= self.until:
                self.kind, self.label = 'rest', '打滚后，趴着歇一会儿'
                self.roll_origin = None
                self.play('prone-rest', now-sum(catalog()['prone-rest']['durations'][:3])/1000)
                return
            if self.phase == 'doing' and self.meal and s.action_player.action is None and now >= self.until:
                key, stamp = self.meal
                self.completed[key] = stamp
                self.store.settings.setValue('routine/meals/'+key, stamp)
                self.store.sync()
            # User-selected actions must never be stopped or overwritten.
            if self.owned_start is not None and (s.action_player.action is None or s.action_player.started != self.owned_start):
                self.cancel(now)
                return
            if self.target and now >= self.probe_at:
                self.probe_at = now+1
                if now-self.icons.scanned_at > 3:
                    self.icons.refresh()
                current = next((i for i in self.icons.icons if i['id'] == self.target['id']), None)
                if (not current or current['rect'] != self.target['rect'] or self.icons.error
                        or not self.route_exposed(self.destination, self.screen)):
                    self.cancel(now)
                    return
            elif (self.phase == 'walking' or self.roll_origin) and now >= self.probe_at:
                self.probe_at = now+1
                destination = (self.roll_origin[0]+self.roll_origin[2],self.roll_origin[1]) if self.roll_origin else self.destination
                if not self.route_exposed(destination, p.screen()):
                    self.cancel(now)
                    return
            if now >= self.until:
                self.cancel(now)
                return
            if self.phase == 'walking':
                if p.advance_to(self.destination, dt):
                    s.gait_until = 0
                    if self.kind == 'lean':
                        try:
                            self.icons.start(self.target['id'], instant=True, auto_pose=True, pose=self.lean_pose)
                            self.icon_started = self.icons.started
                            if self.icons.side not in ('left','right','back','front'):
                                self.cancel(now)
                                return
                            self.destination = self.icons.destination
                            self.phase = 'resting'
                            self.until = now+random.uniform(25, 55)
                            if not p.bubble.parts and random.random() < .3:
                                p.bubble.say('借这个小角落，靠一小会儿。', 'ambient')
                        except ValueError:
                            self.cancel(now)
                    elif self.kind == 'nap':
                        self.play('sleep', now, random.uniform(70, 140))
                        self.mask_icon()
                    else:
                        self.play(random.choice(('curious','sit-swing','stretch')), now)
                return
            if self.kind == 'roll' and self.roll_origin:
                start_x, y, distance = self.roll_origin
                progress = min(1., max(0., (now-self.owned_start)/(self.until-self.owned_start)))
                # Smooth sideward travel accompanies the authored side roll.
                x = round(start_x+distance*(progress*progress*(3-2*progress)))
                p.move(x, y)
                s.position_x = float(x)
            return
        if s.action_player.action is not None or s.ambient.current or s.walking:
            return
        # After an interruption allow time for the user's interaction to finish.
        meal = due_meal(at, self.completed) if now >= getattr(self, 'meal_retry_at', 0) else None
        if meal:
            key, stamp, line = meal
            self.kind, self.label = 'meal', '吃饭时间'
            self.meal = key, stamp
            self.meal_retry_at = now+90
            self.next_snack = max(self.next_snack, now+900)
            self.play('eat', now)
            p.bubble.say(line, 'ambient')
            return
        if now >= self.next_snack and 9 <= at.hour < 21:
            self.kind, self.label = 'snack', '偷偷吃点小零食'
            self.next_snack = now+random.uniform(1200, 2400)
            self.play('eat', now)
            p.bubble.say('只吃一小口零食……真的就一小口。', 'ambient')
            return
        if now < self.next_at:
            return
        pace = {'少动': 1.6, '默认': 1., '活跃': .75}[p.preferences.activity]
        self.next_at = now+random.uniform(80, 170)*pace/max(.3, s.routine.period['walk'])
        if at.hour >= 23 or at.hour < 6:
            return
        if now-self.icons.scanned_at > 30:
            self.icons.refresh()
        candidate = self.icon_destination()
        if candidate and random.random() < .65:
            _, self.target, self.destination, self.screen = candidate
            self.kind = random.choice(('nap', 'lean')) if at.hour in (12,13,21,22) else random.choice(('lean','lean','nap'))
            self.label = '找个图标躲着小睡' if self.kind == 'nap' else '去图标旁靠一会儿'
            if self.kind == 'lean':
                self.lean_pose = random.choice(('left','right'))
                rect, _ = logical_rect(self.target['rect'])
                try:
                    self.lean_pose, self.destination = placement(rect, (p.width(),p.height()), self.lean_pose,
                        {**self.icons.options, 'offset_x':0, 'offset_y':0}, self.screen.availableGeometry().getRect(), self.icons.bounds)
                except ValueError:
                    self.target = None
                    self.kind, self.label = '', ''
                    return
                if not self.route_exposed(self.destination, self.screen):
                    self.target = None
                    self.kind, self.label = '', ''
                    return
        elif random.random() < .45:
            self.kind, self.label = 'roll', '懒懒地打个滚'
            area = p.screen_area()
            direction = random.choice((-1,1))
            distance = max(area.left()-p.x(), min(area.right()-p.width()+1-p.x(), direction*70*p.width()/180))
            if self.route_exposed((p.x()+distance,p.y()), p.screen()):
                self.play(random.choice(('lazy-roll-toward','lazy-roll-away')), now)
                self.roll_origin = (p.x(), p.y(), distance)
            else:
                self.kind, self.label = '', ''
            return
        else:
            area = p.screen_area()
            x = round(max(area.left(), min(area.right()-p.width()+1, p.x()+random.choice((-1,1))*random.uniform(70,180))))
            y = round(max(area.top(), min(area.bottom()-p.height()+1, p.y()+random.uniform(-85,85))))
            self.destination = (x, y)
            screen = p.screen()
            if not self.route_exposed(self.destination, screen) or abs(x-p.x()) < 35:
                return
            self.kind, self.label = 'stroll', '小步巡视桌面'
        self.phase = 'walking'
        self.until = now+9
        self.probe_at = now+1
        s.walking = False
        s.travel_position = None
        p.state_changed.emit()

    def mask_icon(self):
        image = self.icons.cache_images.get(self.target['id'])
        if image is None:
            return
        x,y,w,h = logical_rect(self.target['rect'])[0]
        glyph = alpha_region(image.scaled(max(1,round(w)), max(1,round(h))))
        from PySide6.QtGui import QRegion
        self.pet.setMask(QRegion(self.pet.rect()).subtracted(glyph.translated(round(x-self.pet.x()), round(y-self.pet.y()))))
