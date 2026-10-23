"""Interruptible local errands; never opens files or moves desktop icons."""
import math
import random
import time
from datetime import datetime
from play_policy import PlayPolicy
from input_activity import idle_seconds

from desktop_icons import desktop_exposed
from action_player import catalog, lazy_roll_timeline
from icon_sleep import logical_rect, alpha_region, placement
from icon_pose_geometry import icon_surface
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor
from PySide6.QtCore import QRectF


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
        self.last_pet_click = time.monotonic()
        self.next_affection = self.last_pet_click+300
        self.until = 0.
        self.probe_at = 0.
        self.icon_started = None
        self.lean_pose = 'left'
        self.meal = None
        self.roll_origin = None
        self.policy = PlayPolicy()
        self.task_id = 0
        self.reason = '以待机为主，等待安全的小目标'
        self.next_intent = '安静待机'
        self.owned_generation = None
        self.steps = []
        self.story = ''
        self.last_tick = None
        self.last_speech = -float('inf')
        self.moving_since = None
        self.finished = False
        self.waypoints = []
        self.owns_mask = False
        self.climb = None
        self.ground = None
        self.perch = None
        self.interruption = None
        self.geometry = None
        self.segment_at = 0.
        self.no_target_streak = 0
        self.probe_ms = 0.
        self.last_position = None
        self.replans = 0
        self.completed = {key: store.settings.value('routine/meals/'+key, '') for _, _, key, _ in MEALS}

    @property
    def active(self):
        return self.phase != 'idle'

    def record_pet_click(self, now=None):
        now = time.monotonic() if now is None else now
        self.last_pet_click = now
        self.next_affection = now+300

    def snapshot(self):
        return dict(active=self.active, phase=self.phase, activity=self.label,
                    task_id=self.task_id, target_id=self.target['id'] if self.target else None,
                    next_intent=self.next_intent, reason=self.reason,
                    target='附近的图标' if self.target else '原地' if self.active else '尚未选择',
                    path_probe_ms=round(self.probe_ms, 2),
                    energy=round(self.policy.energy), curiosity=round(self.policy.curiosity))

    def cancel(self, now=None, reason=None, *, failed=False):
        now = time.monotonic() if now is None else now
        was = self.active
        if failed:
            self.no_target_streak += 1
            self.policy.fail(self.target['id'] if self.target else None,now)
        player = self.pet.state.action_player
        if (self.owned_start is not None and player.started == self.owned_start
                and player.generation == self.owned_generation):
            player.stop()
        owned_icon = self.kind == 'lean' and self.icon_started == self.icons.started and self.icons.target is self.target
        if owned_icon:
            self.icons.wake('休息好了')
        if was:
            if self.owns_mask or owned_icon:
                self.pet.clearMask()
            self.pet.state.travel_position = None
            self.pet.state.walking = False
            self.pet.state.gait_until = 0
            self.pet.state.next_action = now+random.uniform(15, 25)
            self.pet.state.ambient.defer(now, self.pet.preferences.activity)
        self.phase, self.kind, self.label = 'idle', '', ''
        self.target = self.destination = self.owned_start = None
        self.icon_started = self.meal = self.roll_origin = None
        self.owned_generation = None
        self.steps = []
        self.waypoints = []
        self.owns_mask = False
        self.climb = self.ground = self.perch = None
        self.geometry = None
        self.replans = 0
        self.story = ''
        self.moving_since = None
        self.next_intent = '安静待机，稍后重新观察'
        self.reason = reason or ('活动完成，歇一会儿' if self.finished else '先陪伴用户，稍后重新选择')
        self.finished = False
        self.task_id += 1
        pace = {'少动': 1.6, '默认': 1., '活跃': .75}[self.pet.preferences.activity]
        self.next_at = now+random.uniform(60, 120)*pace
        if failed:
            self.next_at = now+min(120,random.uniform(30,60)*2**min(2,max(0,self.no_target_streak-2)))
        if was:
            self.pet.state_changed.emit()

    def interrupt(self, kind, now=None):
        """Cooldown starts after the interaction ends, never from mouse-down."""
        now = time.monotonic() if now is None else now
        self.cancel(now)
        self.interruption = kind
        self.reason = {'menu':'菜单交互中，暂不移动', 'chat':'正在和你说话',
                       'drag':'刚被拖动，先陪你一会儿', 'click':'回应你的互动'}[kind]

    def settle_interruption(self, now):
        if not self.interruption:
            return
        low, high = {'menu':(10,20), 'chat':(30,60), 'drag':(20,40), 'click':(20,40)}[self.interruption]
        self.next_at = now+random.uniform(low, high)
        self.reason = {'menu':'菜单已关闭，先歇一会儿', 'chat':'对话刚结束，先安静陪伴',
                       'drag':'刚被拖动，先陪你一会儿', 'click':'刚刚回应你，先安静陪伴'}[self.interruption]
        self.interruption = None

    def capture_geometry(self):
        p = self.pet
        screen = p.screen()
        if screen is None:
            return None
        return (screen, screen.geometry().getRect(), screen.availableGeometry().getRect(),
                screen.devicePixelRatio(), p.width(), p.height())

    def blocked(self):
        p, s = self.pet, self.pet.state
        return (s.sleep.transitioning or not p.isVisible() or not p.desired_visible() or p.presence.active
                or p.drag_origin is not None or s.physics.active or p.preferences.quiet
                or p.preferences.paused or not p.preferences.random_movement
                or not p.preferences.autonomous_play
                or (self.target is not None and not p.preferences.autonomous_icons)
                or bool(s.music and s.music.active)
                or s.travel_target is not None
                or bool(getattr(p.controller, 'quick_pending', None))
                or bool(p.bubble.parts and p.bubble.kind != 'ambient')
                or bool(s.edge_attachment and s.edge_attachment.active)
                or QApplication.activePopupWidget() is not None
                or bool(self.icons.target and not (self.kind == 'lean' and self.icons.target is self.target
                                                   and self.icon_started == self.icons.started)))

    def exposed(self, position, screen, size=None):
        started = time.perf_counter()
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
        finally:
            self.probe_ms = (time.perf_counter()-started)*1000

    def route_exposed(self, destination, screen):
        if screen is None or destination is None or screen != self.pet.screen():
            return False
        area = screen.availableGeometry()
        if not (area.contains(round(destination[0]), round(destination[1])) and
                area.contains(round(destination[0]+self.pet.width()-1), round(destination[1]+self.pet.height()-1))):
            return False
        x, y = min(self.pet.x(),destination[0]), min(self.pet.y(),destination[1])
        return self.exposed((x,y), screen,
            (abs(self.pet.x()-destination[0])+self.pet.width(), abs(self.pet.y()-destination[1])+self.pet.height()))

    def icon_destination(self):
        p = self.pet
        candidates = []
        if not p.preferences.autonomous_icons or self.icons.error:
            return None
        now = time.monotonic()
        pointer = QCursor.pos()
        radius = min(360, p.height()*2, max(65, p.preferences.speed)*7)
        for icon in self.icons.icons:
            try:
                rect, screen = logical_rect(icon['rect'])
                area = screen.availableGeometry()
                x, y, w, h = rect
                # Rest below the icon, with the head tucked beneath its lower edge.
                px = round(max(area.left(), min(area.right()-p.width()+1, x+w/2-p.width()/2)))
                py = round(max(area.top(), min(area.bottom()-p.height()+1, y+h-p.height()*.38)))
                distance = math.hypot(px-p.x(), py-p.y())
                avoid = max(120, p.height()*.65)
                margin = min(px-area.left(),area.right()-px-p.width()+1,
                             py-area.top(),area.bottom()-py-p.height()+1)
                space = max(0.,min(1.,margin/max(1,p.width()*.5)))
                score = self.policy.score(icon['id'], distance, radius, space,
                                          1.-self.policy.energy/100, now)
                if (distance <= radius and score is not None
                        and math.hypot(pointer.x()-(px+p.width()/2), pointer.y()-(py+p.height()/2)) >= avoid):
                    candidates.append((score, distance, icon, (px, py), screen))
            except (ValueError, KeyError):
                continue
        candidates.sort(key=lambda item: item[0], reverse=True)
        # Limit synchronous window probes per decision, not one per icon.
        safe = []
        for candidate in candidates[:8]:
            if self.route_exposed(candidate[3],candidate[4]):
                safe.append(candidate)
                if len(safe) == 3:
                    break
        return random.choices(safe, weights=[c[0] for c in safe])[0][1:] if safe else None

    def replan_target(self, current, now):
        if self.replans or self.phase not in ('observing','walking') or self.icons.error:
            return False
        try:
            old,screen = logical_rect(self.target['rect'])
            new,new_screen = logical_rect(current['rect'])
        except ValueError:
            return False
        if screen != new_screen or new_screen != self.pet.screen():
            return False
        dx,dy = new[0]-old[0],new[1]-old[1]
        destination = (round(self.destination[0]+dx),round(self.destination[1]+dy))
        distance = math.dist((self.pet.x(),self.pet.y()),destination)
        seconds = distance/max(65,self.pet.preferences.speed)
        elapsed = now-self.moving_since if self.moving_since is not None else 0.
        pointer = QCursor.pos()
        if (math.hypot(dx,dy)>self.pet.height() or seconds*1.5+2+elapsed>12
                or seconds>self.policy.remaining(now,self.pet.preferences.activity)
                or not self.route_exposed(destination,screen)
                or math.hypot(pointer.x()-destination[0]-self.pet.width()/2,
                              pointer.y()-destination[1]-self.pet.height()/2)<max(120,self.pet.height()*.65)):
            return False
        perch = (round(self.perch[0]+dx),round(self.perch[1]+dy)) if self.perch else None
        if perch and not self.route_exposed(perch,screen):
            return False
        self.target,self.destination,self.perch = current,destination,perch
        self.waypoints=[(round(x+dx),round(y+dy)) for x,y in self.waypoints]
        self.replans += 1
        self.phase='observing'
        self.until=now+1
        self.pet.state.travel_position=None
        self.pet.state.walking=False
        self.pet.state.gait_until=0
        self.reason='图标位置变化，停下重新确认一次'
        self.pet.state_changed.emit()
        return True

    def beside_icon(self, icon, screen):
        """Keep reading/observation off labels; other icons are soft obstacles."""
        p = self.pet
        x,y,w,h = logical_rect(icon['rect'])[0]
        label = QRectF(*logical_rect(icon['label_rect'])[0]) if icon.get('label_rect') else QRectF(x,y+h,w,24)
        positions = [(round(x-p.width()*.94),round(y+h*.5-p.height()*.5)),
                     (round(x+w-p.width()*.06),round(y+h*.5-p.height()*.5))]
        pointer = QCursor.pos()
        candidates = []
        for position in positions:
            body = QRectF(position[0]+p.width()*.08,position[1]+p.height()*.10,
                          p.width()*.84,p.height()*.85)
            distance = math.dist((p.x(),p.y()),position)
            if (body.intersects(label) or distance > min(360,p.height()*2)
                    or not self.route_exposed(position,screen)
                    or math.hypot(pointer.x()-body.center().x(),pointer.y()-body.center().y()) < max(120,p.height()*.65)):
                continue
            penalty = 0.
            for other in self.icons.icons:
                if other['id'] == icon['id']:
                    continue
                for rect in (other['rect'],other.get('label_rect')):
                    if rect is None:
                        continue
                    try:
                        bounds,other_screen = logical_rect(rect)
                    except ValueError:
                        continue
                    if other_screen == screen:
                        overlap = body.intersected(QRectF(*bounds))
                        penalty += max(0,overlap.width())*max(0,overlap.height())
            candidates.append((distance+penalty/max(1,p.width()),position))
        return min(candidates,key=lambda item:item[0])[1] if candidates else None

    def play(self, key, now, duration=None):
        s = self.pet.state
        if self.geometry is None:
            self.geometry = self.capture_geometry()
        s.ambient.current = None
        s.walking = False
        s.gait_until = 0
        s.action_player.play(key, now=now, loop=key == 'sleep')
        if key.startswith('lazy-roll-'):
            # A play story is exactly one turn; manual/ambient rolls retain
            # their existing sequence. Resting poses never move the window.
            order, durations = lazy_roll_timeline(catalog()[key], cycles=1)
            s.action_player.frame_order = order
            s.action_player.action = dict(catalog()[key], durations=durations)
        self.owned_start = now
        self.owned_generation = s.action_player.generation
        self.until = now+(duration if duration is not None else sum(s.action_player.action['durations'])/1000)
        self.phase = 'doing'
        self.pet.state_changed.emit()

    def complete(self, now):
        self.no_target_streak = 0
        if self.story:
            self.policy.complete(self.story, self.target['id'] if self.target else None,
                                 now, random.uniform(180, 360))
            p = self.pet
            if (self.story != 'affection' and p.preferences.autonomous_speech and now-self.last_speech >= 180
                    and not p.bubble.parts and random.random() < .12):
                self.last_speech = now
                p.bubble.say('这个小角落刚刚好。' if self.target else '歇一会儿，再陪你。', 'ambient')
        self.finished = True
        self.cancel(now)

    def queue_action(self, key, now):
        if self.owns_mask:
            self.pet.clearMask()
            self.owns_mask = False
        if key not in catalog():
            self.complete(now)
            return
        self.play(key, now)
        if catalog()[key].get('ground_idle') or catalog()[key]['frames'] == 1:
            self.pet.state.ambient.play(self.pet.state.action_player, key, now)
            self.pet.state.ambient.current = None
            self.owned_generation = self.pet.state.action_player.generation
            self.until = now+sum(self.pet.state.action_player.action['durations'])/1000
        # Vary quiet holds, never slow down sitting down, blinking or rising.
        interval = ((20,50) if self.kind == 'read' and key.startswith('reading-pose-') else
                    (10,25) if key.startswith('sit-') else (15,35) if key == 'prone-rest' else None)
        if interval:
            player = self.pet.state.action_player
            durations = list(player.action['durations'])
            order = player.frame_order
            if player.action['frames'] == 1:
                slots = [0]
            else:
                base = 4 if key == 'prone-rest' else 3
                slots = [i for i, frame in enumerate(order or ())
                         if frame == base and 3 <= i < len(durations)-3]
            if slots:
                desired = random.uniform(*interval)*1000
                fixed = sum(d for i,d in enumerate(durations) if i not in slots)
                hold = max(len(slots)*100, desired-fixed)
                for i in slots:
                    durations[i] = hold/len(slots)
                player.action = dict(player.action,durations=durations)
                self.until = now+sum(durations)/1000

    def arrived(self, now):
        self.moving_since = None
        self.pet.state.gait_until = 0
        if self.kind == 'sleep_site':
            self.pet.state.sleep.set_rest_site(self.pet,self.target,self.icons)
            self.finished = True
            self.cancel(now, '已到安全休息点，准备入睡')
            return
        if self.kind == 'perch':
            self.ground = (self.pet.x(),self.pet.y())
            self.play('play-climb-up', now)
            self.climb = (self.ground, self.perch, now, self.until-now)
            self.next_intent = '抓稳爬上，坐一会儿，再爬下'
            return
        if self.waypoints:
            self.destination = self.waypoints.pop(0)
            self.phase = 'observing'
            self.until = now+random.uniform(1, 2)
            self.next_intent = '停一下，再走向另一侧'
            return
        if self.kind == 'lean':
            try:
                before = (self.pet.x(), self.pet.y())
                self.icons.start(self.target['id'], instant=True, auto_pose=True, pose=self.lean_pose)
                self.icon_started = self.icons.started
                if math.dist(before, self.icons.destination) > 3:
                    # Geometry changed since planning; never teleport into contact.
                    self.pet.move(*before)
                    self.cancel(now, '接触点改变，改为安静休息')
                    return
                self.destination = self.icons.destination
                self.phase = 'resting'
                self.until = now+random.uniform(20, 45)
                self.next_intent = '靠一会儿，然后回到待机'
            except ValueError:
                self.cancel(now, '接触姿势不适配')
        else:
            chains = {
                'observe': ['curious', 'sit-relaxed'],
                'read': [random.choice(('reading-pose-1', 'reading-pose-2')), 'sit-neat'],
                'stroll': ['curious', 'sit-relaxed'],
                'tea': ['stretch', 'tea', 'sit-neat'],
                'rest': ['prone-rest'],
                'orbit': ['curious', 'sit-relaxed'],
                'peek': ['play-peek', 'sit-relaxed'],
            }
            self.steps = chains.get(self.kind, ['sit-relaxed'])
            self.next_intent = '完成小动作后安静休息'
            self.queue_action(self.steps.pop(0), now)
            if self.kind == 'peek':
                self.owns_mask = self.mask_icon()

    def begin_sleep_site(self, now):
        """One optional short approach; SleepCycle owns all sleep and wake logic."""
        if self.active:
            self.cancel(now, '到睡眠时间，收起玩耍计划')
        if self.blocked() or not self.pet.preferences.autonomous_icons:
            return False
        # Never wait for a slow/failed scan before sleeping in place.
        if now-self.icons.scanned_at > 3:
            self.icons.refresh()
            return False
        candidate = self.icon_destination()
        if not candidate:
            return False
        _, target, destination, screen = candidate
        distance = math.dist((self.pet.x(),self.pet.y()), destination)
        seconds = distance/max(65,self.pet.preferences.speed)
        if seconds > min(6., self.policy.remaining(now,self.pet.preferences.activity)):
            return False
        self.target, self.destination, self.screen = target, destination, screen
        self.kind, self.label = 'sleep_site', '走到图标旁，准备睡觉'
        self.story = ''
        self.task_id += 1
        self.phase = 'walking'
        self.until = now+min(9.,seconds*1.5+1)
        self.moving_since = now
        self.probe_at = self.segment_at = now
        self.geometry = self.capture_geometry()
        self.next_intent = '到达就入睡；无路则原地睡，不等待图标'
        self.reason = '正式睡眠时段，附近有安全的休息位置'
        self.pet.state.travel_position = None
        self.pet.state_changed.emit()
        return True

    def tick(self, now, dt, at=None):
        at = at or datetime.now()
        p, s = self.pet, self.pet.state
        self.last_tick = now
        position = (p.x(),p.y())
        moving = self.active and self.last_position is not None and position != self.last_position
        self.last_position = position
        self.policy.advance(now, dt, moving, s.sleep.active)
        self.policy.prune(now)
        if self.blocked():
            if self.active:
                self.cancel(now)
            if not self.interruption:
                self.reason = ('安静或暂停模式，原地陪伴' if p.preferences.quiet or p.preferences.paused
                           else '睡眠或用户交互优先，暂不玩耍')
            return
        self.settle_interruption(now)
        if self.active:
            if self.geometry is not None and self.geometry != self.capture_geometry():
                self.cancel(now, '屏幕或人物尺寸变化，重新确认接触点')
                return
            wants_move = self.phase == 'walking' or self.roll_origin or self.climb
            if wants_move and (self.policy.remaining(now, p.preferences.activity) <= 0
                           or (self.moving_since is not None and now-self.moving_since >= 12)):
                self.cancel(now, '走动预算已到，休息一下')
                return
            if self.target and now >= self.probe_at:
                self.probe_at = now+1
                if now-self.icons.scanned_at > 3:
                    self.icons.refresh()
                current = next((i for i in self.icons.icons if i['id'] == self.target['id']), None)
                if current and current['rect'] != self.target['rect'] and self.replan_target(current,now):
                    return
                if (not current or current['rect'] != self.target['rect'] or self.icons.error
                        or not self.route_exposed(self.destination, self.screen)):
                    self.cancel(now, '目标已变化或路径被遮挡，稍后再看', failed=True)
                    return
                pointer = QCursor.pos()
                if math.hypot(pointer.x()-self.destination[0]-p.width()/2,
                              pointer.y()-self.destination[1]-p.height()/2) < max(120,p.height()*.65):
                    self.cancel(now, '鼠标来到附近，先让开活动空间')
                    return
            elif (self.phase == 'walking' or self.roll_origin) and now >= self.probe_at:
                self.probe_at = now+1
                destination = (self.roll_origin[0],self.roll_origin[1]+self.roll_origin[2]) if self.roll_origin else self.destination
                if not self.route_exposed(destination, p.screen()):
                    self.cancel(now, '桌面路径被遮挡，停止探索', failed=True)
                    return
            if self.phase == 'observing':
                if self.target:
                    current = next((i for i in self.icons.icons if i['id'] == self.target['id']), None)
                    if not current or current['rect'] != self.target['rect'] or self.icons.error:
                        self.cancel(now, '观察目标已变化')
                        return
                if now < self.until:
                    return
                if self.destination is None:
                    self.arrived(now)
                else:
                    self.phase = 'walking'
                    distance = math.dist((p.x(), p.y()), self.destination)
                    self.until = now+min(12, distance/max(1, p.preferences.speed)*1.5+2)
                    self.moving_since = now
                    p.state_changed.emit()
                return
            if (self.kind == 'roll' and s.action_player.action is None and now >= self.until
                    and s.action_player.started == self.owned_start
                    and s.action_player.generation == self.owned_generation+1):
                self.kind, self.label = 'rest', '打滚后，趴着歇一会儿'
                self.roll_origin = None
                self.queue_action('prone-rest', now)
                return
            if (self.phase == 'doing' and self.meal and s.action_player.action is None and now >= self.until
                    and s.action_player.started == self.owned_start
                    and s.action_player.generation == self.owned_generation+1):
                key, stamp = self.meal
                self.completed[key] = stamp
                self.store.settings.setValue('routine/meals/'+key, stamp)
                self.store.sync()
            # User-selected actions must never be stopped or overwritten.
            if (self.phase == 'doing' and s.action_player.action is None and now >= self.until
                    and s.action_player.started == self.owned_start
                    and s.action_player.generation == self.owned_generation+1):
                self.owned_start = self.owned_generation = None
                if self.kind == 'perch':
                    if self.climb:
                        p.move(*self.climb[1])
                        self.climb = None
                        if self.next_intent == '正在爬下，随后安静休息':
                            self.complete(now)
                        else:
                            self.play('play-top-rest', now, random.uniform(15,35))
                            s.action_player.loop = True
                            self.phase = 'perched'
                            self.next_intent = '坐稳休息，然后扶着边缘爬下'
                        return
                if self.steps:
                    if due_meal(at,self.completed) and self.story:
                        self.complete(now)
                        self.reason = '小动作收稳，接下来吃饭'
                    else:
                        self.queue_action(self.steps.pop(0), now)
                else:
                    self.complete(now)
                return
            if self.owned_start is not None and (s.action_player.action is None or s.action_player.started != self.owned_start
                                               or s.action_player.generation != self.owned_generation):
                self.cancel(now)
                return
            if now >= self.until:
                if self.phase == 'perched':
                    self.play('play-climb-down', now)
                    self.climb = ((p.x(),p.y()),self.ground,now,self.until-now)
                    self.next_intent = '正在爬下，随后安静休息'
                elif self.phase == 'resting':
                    self.complete(now)
                else:
                    self.cancel(now, '路线超时，先停下来')
                return
            if self.climb:
                start,end,started,duration = self.climb
                sample = s.action_player.motion_sample(now)
                if sample:
                    before,after,progress = sample
                    phases = ((0.,0.,.25,.65,.90,1.) if before[0] == 'play-climb-up'
                              else (0.,0.,.20,.55,.85,1.))
                    t = phases[before[1]]+(phases[after[1]]-phases[before[1]])*progress
                else:
                    t = 1.
                p.move(*(round(a+(b-a)*t) for a,b in zip(start,end)))
                s.position_x = float(p.x())
                return
            if self.phase == 'walking':
                if now >= self.segment_at:
                    self.segment_at = now+.2
                    distance = math.dist((p.x(), p.y()), self.destination)
                    fraction = min(1., max(65,p.preferences.speed)*.25/max(.01,distance))
                    segment = tuple(a+(b-a)*fraction for a,b in zip((p.x(),p.y()), self.destination))
                    if not self.route_exposed(segment, self.screen):
                        self.cancel(now, '下一步被遮挡，停止探索', failed=True)
                        return
                distance = math.dist((p.x(), p.y()), self.destination)
                speed = max(10, max(65,p.preferences.speed)*min(1., distance/18))
                if p.advance_to(self.destination, dt, speed=speed):
                    self.arrived(now)
                    return
                return
            if self.kind == 'roll' and self.roll_origin:
                # Use the same phase-locked movement as ambient/manual rolls.
                p.animator.advance_roll(now)
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
        if (now >= self.next_affection and now-self.last_pet_click >= 300
                and 7 <= at.hour < 23 and s.routine.period['walk'] > 0
                and 'affection' in catalog()):
            self.next_affection = now+300
            self.kind = self.story = 'affection'
            self.label = '好久没被点到，撒个娇'
            self.next_intent = '撒娇后安静陪伴'
            self.reason = '已经五分钟没有点击互动'
            self.task_id += 1
            self.play('affection',now)
            return
        if now >= self.next_snack and 9 <= at.hour < 21:
            self.kind, self.label = 'snack', '偷偷吃点小零食'
            self.next_snack = now+random.uniform(1200, 2400)
            self.play('eat', now)
            p.bubble.say('只吃一小口零食……真的就一小口。', 'ambient')
            return
        if now < self.next_at:
            return
        idle = idle_seconds()
        if idle is not None and idle < 2 and random.random() < .75:
            self.next_at = now+random.uniform(30,60)
            self.reason = '用户正在操作，先安静陪伴'
            return
        # A due patrol gets one free-slot opportunity, rather than repeatedly
        # deferring behind ambient's timer. Active ambient clips still finish.
        if at.hour >= 23 or at.hour < 7 or s.routine.period['walk'] <= 0:
            self.reason = '作息需要安静休息'
            return
        if now < self.policy.quiet_until or self.policy.remaining(now, p.preferences.activity) < 2:
            self.reason = '玩过了，先安静休息'
            self.next_at = max(now+30, self.policy.quiet_until)
            return
        pace = {'少动': 1.6, '默认': 1., '活跃': .75}[p.preferences.activity]
        self.next_at = now+random.uniform(60, 120)*pace/max(.3, s.routine.period['walk'])
        if now-self.icons.scanned_at > 30:
            self.icons.refresh()
        candidate = self.icon_destination()
        icon_kinds = [k for k in ('observe', 'lean', 'read', 'orbit', 'peek', 'perch')
                      if self.policy.available(k, now) and (k != 'peek' or 'play-peek' in catalog())
                      and (k != 'perch' or all(key in catalog() for key in ('play-climb-up','play-top-rest','play-climb-down')))]
        if candidate and icon_kinds and random.random() < .65:
            _, self.target, self.destination, self.screen = candidate
            self.kind = random.choice(icon_kinds)
            self.label = {'observe':'去看看附近的小角落', 'lean':'去图标旁靠一会儿',
                          'read':'找个位置读一会儿', 'orbit':'绕这个小角落走半圈', 'peek':'藏一点点，再看看你',
                          'perch':'抓住边缘，爬上图标坐坐'}[self.kind]
            if self.kind in ('read','observe'):
                beside = self.beside_icon(self.target,self.screen)
                if beside is None:
                    self.cancel(now,'图标文字旁没有安全空位，继续待机',failed=True)
                    return
                self.destination = beside
            if self.kind == 'perch':
                rect,_ = logical_rect(self.target['rect'])
                image = self.icons.cache_images.get(self.target['id'])
                x,y,w,h = icon_surface(rect,image)
                # Authored seat contact in the common 256px action canvas;
                # PetRenderer draws it at (10,25,160,160) on a 180x190 view.
                sx,sy = p.width()/180,p.height()/190
                cx,cy = catalog()['play-top-rest']['support_contact']
                self.perch = (round(x+w/2-(10+160*cx)*sx),round(y-(25+160*cy)*sy))
                required = sum(sum(catalog()[key]['durations']) for key in ('play-climb-up','play-climb-down'))/1000
                required += math.dist((p.x(),p.y()),self.destination)/max(65,p.preferences.speed)
                if (image is None or w < p.width()*.15 or not self.route_exposed(self.perch,self.screen)
                        or required+1 > self.policy.remaining(now,p.preferences.activity)):
                    self.kind, self.label, self.perch = 'observe', '图标上方不适合，留在旁边坐坐', None
                    beside = self.beside_icon(self.target,self.screen)
                    if beside is None:
                        self.cancel(now,'图标文字旁没有安全空位，继续待机',failed=True)
                        return
                    self.destination = beside
            if self.kind == 'orbit':
                x,y,w,h = logical_rect(self.target['rect'])[0]
                side = -1 if p.x()+p.width()/2 < x+w/2 else 1
                first = (round(x-p.width()*.75 if side < 0 else x+w-p.width()*.25), round(y+h-p.height()*.25))
                second = (round(x+w-p.width()*.25 if side < 0 else x-p.width()*.75), round(y+h-p.height()*.25))
                area = self.screen.availableGeometry()
                if not all(area.contains(int(px), int(py)) and
                           area.contains(int(px+p.width()-1), int(py+p.height()-1)) and
                           self.route_exposed((px,py), self.screen) for px,py in (first,second)):
                    self.cancel(now, '图标旁没有足够的绕行空间',failed=True)
                    return
                if (math.dist((p.x(),p.y()), first)+math.dist(first,second))/max(1,p.preferences.speed) > min(10,self.policy.remaining(now,p.preferences.activity)):
                    self.cancel(now, '这次绕行太远，继续待机')
                    return
                self.destination = first
                self.waypoints = [second]
            if self.kind == 'lean':
                self.icons.load_poses()
                self.lean_pose = random.choice(('left', 'right'))
                rect, _ = logical_rect(self.target['rect'])
                try:
                    self.lean_pose, self.destination = placement(rect, (p.width(),p.height()), self.lean_pose,
                        {**self.icons.options, 'offset_x':0, 'offset_y':0}, self.screen.availableGeometry().getRect(), self.icons.bounds)
                except ValueError:
                    self.cancel(now, '这里没有合适的支撑点')
                    return
        else:
            self.target = None
            choices = [k for k in ('roll', 'stroll', 'tea', 'rest') if self.policy.available(k, now)]
            if not choices:
                self.reason = '最近的小故事仍在冷却，继续待机'
                return
            self.kind = random.choice(choices)
            self.label = {'roll':'翻个身就歇着', 'stroll':'小步看看桌面', 'tea':'下午的小茶歇', 'rest':'坐趴着休息'}[self.kind]
            if self.kind == 'roll':
                self.story = self.kind
                area = p.screen_area()
                action_id = random.choice(('lazy-roll-toward','lazy-roll-away'))
                from action_player import ROLL_DIRECTION
                direction = ROLL_DIRECTION[action_id]
                room = area.bottom()-p.y()-p.height()+1 if direction > 0 else p.y()-area.top()
                if room < min(35,p.height()*.3):
                    self.cancel(now, '翻身空间不足，继续待机')
                    return
                distance = direction*min(70*p.height()/180, max(0,room))
                if self.route_exposed((p.x(),p.y()+distance), p.screen()):
                    self.task_id += 1
                    self.play(action_id, now)
                    self.roll_origin = (p.x(), p.y(), distance)
                    self.moving_since = now
                else:
                    self.cancel(now, '翻身区域被遮挡',failed=True)
                return
            if self.kind in ('tea', 'rest'):
                self.destination = None
            else:
                area = p.screen_area()
                x = round(max(area.left(), min(area.right()-p.width()+1, p.x()+random.choice((-1,1))*random.uniform(70,180))))
                y = round(max(area.top(), min(area.bottom()-p.height()+1, p.y()+random.uniform(-85,85))))
                self.destination = (x, y)
                self.screen = p.screen()
        if self.destination is not None:
            distance = math.dist((p.x(), p.y()), self.destination)
            seconds = distance/max(1, p.preferences.speed)
            pointer = QCursor.pos()
            if (seconds*1.5+2 > 12 or seconds > self.policy.remaining(now, p.preferences.activity)
                    or not self.route_exposed(self.destination, self.screen)
                    or math.hypot(pointer.x()-self.destination[0]-p.width()/2,
                                  pointer.y()-self.destination[1]-p.height()/2) < max(120,p.height()*.65)):
                self.cancel(now, '空间、鼠标避让或移动预算不适合，继续待机',failed=True)
                return
        self.story = self.kind
        self.task_id += 1
        self.phase = 'observing'
        self.until = now+random.uniform(1, 2)
        self.probe_at = now
        self.reason = '附近路径可见，当前没有用户交互'
        self.geometry = self.capture_geometry()
        self.next_intent = '先观察，再走近；条件改变就放弃'
        s.walking = False
        s.travel_position = None
        p.state_changed.emit()

    def mask_icon(self):
        image = self.icons.cache_images.get(self.target['id'])
        if image is None:
            return False
        x,y,w,h = logical_rect(self.target['rect'])[0]
        glyph = alpha_region(image.scaled(max(1,round(w)), max(1,round(h))))
        from PySide6.QtGui import QRegion
        self.pet.setMask(QRegion(self.pet.rect()).subtracted(glyph.translated(round(x-self.pet.x()), round(y-self.pet.y()))))
        return True
