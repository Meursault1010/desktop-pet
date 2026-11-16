"""Interruptible local errands; never opens files or moves desktop icons."""
import math
import random
import time
from dataclasses import replace
from datetime import datetime
from play_policy import PlayPolicy
from locomotion import walking_speed
from patrol_depth import PatrolDepth
from patrol_passage import ScreenPassage
from input_activity import idle_seconds

from desktop_icons import desktop_exposed
from action_player import catalog, lazy_roll_timeline
from icon_sleep import logical_rect, alpha_region, placement, NEW_POSES
from icon_pose_geometry import icon_surface
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QCursor
from PySide6.QtCore import QRectF


MEALS = ((7, 9, 'breakfast', '早餐时间，慢慢吃一点。'),
         (12, 14, 'lunch', '午饭时间到了，先填饱小肚子。'),
         (18, 20, 'dinner', '吃过晚饭，再懒懒地待一会儿。'))

# At the slowest desktop tempos a cross-desktop icon visit can take most of a
# minute. It still fits the activity budget, and it is what "go to the icons"
# means on a wide screen.
ICON_ERRAND_SECONDS = 40.
# Free walks are mostly a fallback when no icon errand is available, but one
# walk may now reach anywhere on the usable desktop instead of a short shuffle.
STROLL_SECONDS = 90.

# Behind an app window the pet is invisible, so a visit needs to be long enough
# that minimising the window reveals an interaction in progress. Prefer poses
# that read as contact with the icon from a single glance.
BACKSTAGE_KINDS = ('perch', 'lean', 'read', 'observe')
BACKSTAGE_HOLD = (30., 50.)
BACKSTAGE_WAIT = (45., 90.)
BACKSTAGE_REVEAL_HOLD = 12.
# Passive frame visits reuse a warm window list instead of scanning on arrival.
WINDOW_SCAN_TTL = 45.
WINDOW_SCAN_INTERVAL = 25.


def due_meal(at, completed):
    for start, end, key, line in MEALS:
        stamp = at.date().isoformat()+'/'+key
        if start <= at.hour < end and completed.get(key) != stamp:
            return key, stamp, line
    return None


class Patrol:
    def __init__(self, pet, icons, store):
        self.pet, self.icons, self.store = pet, icons, store
        self.exploring = False
        self.depth = PatrolDepth(pet)
        self.passage = ScreenPassage(pet, self.depth)
        self.next_passage = time.monotonic()+random.uniform(45,90)
        # Idle companionship keeps a low-frequency window list warm so a
        # passive frame visit never has to enumerate the desktop synchronously.
        self.next_window_scan = time.monotonic()+8
        self.edge_candidate = None
        self.edge_started = None
        self.edge_retry_at = 0.
        self.edge_retry_until = 0.
        self.demo = False
        self.demo_at = None
        self.demo_until = 0.
        self.demo_restore_idle = False
        self.support_position = None
        self.support_stage = ''
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
        self.lean_intro = False
        self.lean_intro_done = False
        self.meal = None
        self.roll_origin = None
        self.policy = PlayPolicy()
        self.task_id = 0
        self.reason = '以待机为主，等待安全的小目标'
        self.next_intent = '安静待机'
        self.owned_generation = None
        self.steps = []
        self.story = ''
        self.last_story_action = None
        self.pending_story_action = None
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
        self.arrive_at = None
        self.step_at = None
        self.icon_followup = False
        self.backstage = None
        self.backstage_next = 0.
        self.last_depth = 'front'
        self.next_pointer_reaction = time.monotonic()+random.uniform(12, 25)
        self.next_environment_reaction = time.monotonic()+random.uniform(8, 18)
        self.completed = {key: store.settings.value('routine/meals/'+key, '') for _, _, key, _ in MEALS}

    @property
    def active(self):
        return self.phase != 'idle'

    def suspend(self, now=None, reason=None):
        """Interrupt an errand and give up the back layer immediately.

        Click, menu, drag, hide/show, quiet/pause, screen changes and tool
        reactions all take over the pet. A mask or z-order override from an
        abandoned backstage route must never outlive that plan.
        """
        self.cancel(now, reason)
        self.release_depth()

    def release_depth(self):
        if not self.depth.engaged and not self.passage.active:
            return
        self.passage.cancel()
        self.depth.release()
        self.last_depth = 'front'
        self.pet.state_changed.emit()

    def random_destination(self):
        p = self.pet
        area = p.screen_area()
        pointer = QCursor.pos()
        walking = max(1., walking_speed(p.preferences.speed))
        # Keep the sampled span inside the same budget allows_travel enforces,
        # then let a single free walk reach the far side of the desktop.
        reach = walking*(STROLL_SECONDS-2.)/1.5
        span = math.hypot(area.width(), area.height())
        low = min(120., max(48., reach*.35))
        high = max(low+20., min(span, reach))
        # Sample fresh goals, not an ordered list or a return route.
        for _ in range(16):
            angle = random.uniform(0, math.tau)
            radius = random.uniform(low, high)
            destination = (round(max(area.left(), min(area.right()-p.width()+1,p.x()+math.cos(angle)*radius))),
                           round(max(p.y(), min(area.bottom()-p.height()+1,p.y()+max(0,math.sin(angle))*radius))))
            distance = math.dist((p.x(), p.y()), destination)
            # Never hand the caller a stroll its own travel budget will reject.
            if (distance >= min(120., max(60., reach*.45))
                    and self.allows_travel(distance/walking)
                    and self.route_exposed(destination,p.screen(),through_windows=self.exploring)
                    and math.hypot(pointer.x()-destination[0]-p.width()/2,
                                   pointer.y()-destination[1]-p.height()/2) >= max(120,p.height()*.65)):
                return destination
        return None

    def fallback_stroll(self, now, reason):
        """An unusable icon must not strand explicit exploration in idle."""
        self.cancel(now, reason, failed=True)
        if not self.exploring or self.blocked():
            return
        p, s = self.pet, self.pet.state
        destination = self.random_destination()
        if destination is None:
            self.reason = reason+'；附近也没有安全走动空间'
            return
        seconds = math.dist((p.x(),p.y()),destination)/max(1,walking_speed(p.preferences.speed))
        if not self.allows_travel(seconds) or seconds > self.policy.remaining(now,p.preferences.activity):
            self.reason = '走动预算不足，稍后继续巡逻'
            return
        self.kind = self.story = 'stroll'
        self.label = '小步看看桌面'
        self.destination, self.screen = destination, p.screen()
        self.phase, self.until = 'observing', now+.3
        self.probe_at = now
        self.geometry = self.capture_geometry()
        self.reason = reason+'；改走附近安全空位'
        self.next_intent = '先观察，再走向新的随机位置'
        s.walking, s.travel_position = False, None
        p.state_changed.emit()

    def record_pet_click(self, now=None):
        now = time.monotonic() if now is None else now
        self.last_pet_click = now
        self.next_affection = now+300

    def snapshot(self):
        return dict(active=self.active, exploring=self.exploring, phase=self.phase, activity=self.label,
                    window_depth=self.depth.mode,
                    task_id=self.task_id, target_id=self.target['id'] if self.target else None,
                    next_intent=self.next_intent, reason=self.reason,
                    target=('窗口边框' if self.kind == 'edge' and not self.exploring else
                            '窗口或屏幕侧边' if self.kind == 'edge' else '屏幕外的返回入口' if self.passage.active else
                            '窗口后面的图标' if self.backstage else '附近的图标' if self.target else
                            '随机桌面位置' if self.destination is not None else '原地' if self.active else '尚未选择'),
                    path_probe_ms=round(self.probe_ms, 2),
                    energy=round(self.policy.energy), curiosity=round(self.policy.curiosity))

    def cancel(self, now=None, reason=None, *, failed=False):
        """End one errand; external interruptions must call suspend()."""
        now = time.monotonic() if now is None else now
        if self.demo:
            self.finish_demo()
        if self.backstage:
            # Space out hidden visits; while windows keep covering the icons
            # the pet should not chain one staged interaction into the next.
            self.backstage_next = now+random.uniform(*BACKSTAGE_WAIT)
        self.backstage = None
        was = self.active
        self.passage.cancel()
        edge = self.pet.state.edge_attachment
        if self.edge_started is not None and edge.active and edge.started == self.edge_started:
            edge.release(cooldown=0)
        if not self.exploring:
            self.depth.release()
            self.last_depth = 'front'
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
        if self.owns_mask:
            self.pet.masker.clear('peek')
        if was:
            self.pet.state.travel_position = None
            self.pet.state.walking = False
            self.pet.state.gait_until = 0
            self.pet.state.ambient.defer(now, self.pet.preferences.activity)
        self.phase, self.kind, self.label = 'idle', '', ''
        self.target = self.destination = self.owned_start = None
        self.icon_started = self.meal = self.roll_origin = None
        self.lean_intro = False
        self.lean_intro_done = False
        self.owned_generation = None
        self.steps = []
        self.waypoints = []
        self.owns_mask = False
        self.climb = self.ground = self.perch = None
        self.support_position = None
        self.support_stage = ''
        self.edge_candidate = self.edge_started = None
        self.geometry = None
        self.replans = 0
        self.story = ''
        self.last_story_action = None
        self.pending_story_action = None
        self.moving_since = None
        self.arrive_at = self.step_at = None
        self.next_intent = '安静待机，稍后重新观察'
        self.reason = reason or ('活动完成，歇一会儿' if self.finished else '先陪伴用户，稍后重新选择')
        self.finished = False
        self.task_id += 1
        pace = {'少动': 1.6, '默认': 1., '活跃': .75}[self.pet.preferences.activity]
        self.next_at = now+random.uniform(60, 120)*pace
        if failed:
            self.next_at = now+min(120,random.uniform(30,60)*2**min(2,max(0,self.no_target_streak-2)))
        if self.exploring:
            self.next_at = now+random.uniform(3,8) if not failed else now+random.uniform(8,15)
            self.next_intent = '巡逻中，稍作停留后随机选择新目标'
        if was:
            self.pet.state_changed.emit()

    def interrupt(self, kind, now=None):
        """Cooldown starts after the interaction ends, never from mouse-down."""
        now = time.monotonic() if now is None else now
        self.suspend(now)
        self.edge_retry_at = self.edge_retry_until = 0.
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

    def blocked(self, *, ignore_sleep=False, ignore_support=False):
        p, s = self.pet, self.pet.state
        return ((s.sleep.transitioning and not ignore_sleep) or not p.isVisible() or not p.desired_visible() or p.presence.active
                or p.drag_origin is not None or s.physics.active or p.preferences.quiet
                or p.preferences.paused or not p.preferences.random_movement
                or not p.preferences.autonomous_play
                or (self.target is not None and not p.preferences.autonomous_icons)
                or bool(not ignore_support and not self.demo
                        and not p.preferences.autonomous_windows and self.edge_is_window())
                or bool(s.music and s.music.active)
                or s.travel_target is not None
                or bool(getattr(p.controller, 'quick_pending', None))
                or bool(p.bubble.parts and p.bubble.kind != 'ambient')
                or bool(not ignore_support and s.edge_attachment and s.edge_attachment.active
                        and not (self.edge_started is not None and s.edge_attachment.started == self.edge_started))
                or QApplication.activePopupWidget() is not None
                or bool(not ignore_support and self.icons.target and not (self.kind == 'lean' and self.icons.target is self.target
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

    def route_exposed(self, destination, screen, *, through_windows=False):
        if screen is None or destination is None or screen != self.pet.screen():
            return False
        if self.exploring and self.kind == 'edge' and self.edge_candidate is not None:
            return destination[1] >= self.pet.y()-1 and self.edge_valid()
        area = screen.availableGeometry()
        if not (area.contains(round(destination[0]), round(destination[1])) and
                area.contains(round(destination[0]+self.pet.width()-1), round(destination[1]+self.pet.height()-1))):
            return False
        # Only the real icon/contact area must be exposed. A window under
        # the approach route must not make every desktop icon unreachable.
        if self.exploring:
            if through_windows or (self.kind == 'stroll' and self.target is None):
                return True
            if self.target is not None:
                rect, icon_screen = logical_rect(self.target['rect'])
                return icon_screen == screen and (self.depth.mode == 'back' or self.exposed(rect[:2],screen,rect[2:]))
        if self.target is not None and self.icon_walk():
            # Check the icon itself, not the whole route: an always-on-top pet
            # may cross a window, but it must only settle beside visible icons.
            rect, icon_screen = logical_rect(self.target['rect'])
            return icon_screen == screen and self.exposed(rect[:2],screen,rect[2:])
        x, y = min(self.pet.x(),destination[0]), min(self.pet.y(),destination[1])
        return self.exposed((x,y), screen,
            (abs(self.pet.x()-destination[0])+self.pet.width(), abs(self.pet.y()-destination[1])+self.pet.height()))

    def travel_limit(self):
        """Icon errands may cross the desktop; free walks have a longer bound."""
        return ICON_ERRAND_SECONDS if self.target is not None else STROLL_SECONDS

    def allows_travel(self, seconds, elapsed=0.):
        """Free walks keep a safety margin; icon errands may use the screen."""
        if self.target is not None:
            return seconds+elapsed <= self.travel_limit()
        return seconds*1.5+2+elapsed <= self.travel_limit()

    def icon_walk(self):
        """Icon errands may approach icons higher on the desktop.

        Free strolls still never float upward. Climbed icons still need the
        authored climb-up contact after arrival; walking upward alone never
        glues the pet to an icon.
        """
        return self.target is not None and self.kind in ('observe','read','lean',
                                                         'orbit','peek','perch')

    def covered_by_surface(self, rect, screen):
        """How strongly visible app windows hide an icon (2 = topmost)."""
        x, y, w, h = rect
        area = max(1, w*h)
        for index, (_, (bounds, _, surface_screen)) in enumerate(self.depth.surfaces):
            if surface_screen != screen:
                continue
            bx, by, bw, bh = bounds
            overlap = (max(0., min(x+w, bx+bw)-max(x, bx))
                       * max(0., min(y+h, by+bh)-max(y, by)))
            if overlap >= area*.5:
                return 2 if index == 0 else 1
        return 0

    def icon_destination(self, *, hidden=False):
        p = self.pet
        candidates = []
        if not p.preferences.autonomous_icons or self.icons.error:
            return None
        if hidden and (not self.exploring or self.depth.mode != 'back'):
            return None
        now = time.monotonic()
        pointer = QCursor.pos()
        # Icons live around the desktop edges while the pet roams anywhere, so
        # a speed-sized radius left every icon out of range once she drifted
        # away from them. Reach the whole screen; scoring still prefers near.
        area = p.screen_area()
        radius = min(1100, max(320, math.hypot(area.width(), area.height())*.5))
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
                        and distance/max(1,walking_speed(p.preferences.speed)) <= ICON_ERRAND_SECONDS
                        and math.hypot(pointer.x()-(px+p.width()/2), pointer.y()-(py+p.height()/2)) >= avoid):
                    candidates.append((score, distance, icon, (px, py), screen))
            except (ValueError, KeyError):
                continue
        candidates.sort(key=lambda item: item[0], reverse=True)
        if hidden:
            # Prefer icons behind the topmost app: that is the window the user
            # is most likely to minimise next. Surface rects come from the
            # depth scan, so no extra synchronous exposure probes are needed.
            safe = []
            for candidate in candidates:
                if candidate[4] != p.screen():
                    continue
                rect, _ = logical_rect(candidate[2]['rect'])
                rank = self.covered_by_surface(rect, candidate[4])
                if rank:
                    safe.append((rank, candidate))
            if not safe:
                return None
            best = max(rank for rank, _ in safe)
            safe = [candidate for rank, candidate in safe if rank == best][:3]
        else:
            # Limit synchronous window probes per decision, not one per icon.
            safe = []
            for candidate in candidates[:8]:
                rect, _ = logical_rect(candidate[2]['rect'])
                if ((self.exploring and (self.depth.mode == 'back' or self.exposed(rect[:2],candidate[4],rect[2:])))
                        or (not self.exploring and self.exposed(rect[:2],candidate[4],rect[2:]))):
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
        seconds = distance/max(1,walking_speed(self.pet.preferences.speed))
        elapsed = now-self.moving_since if self.moving_since is not None else 0.
        pointer = QCursor.pos()
        if ((destination[1] < self.pet.y()-1 and not self.icon_walk())
                or math.hypot(dx,dy)>self.pet.height() or not self.allows_travel(seconds,elapsed)
                or seconds>self.policy.remaining(now,self.pet.preferences.activity)
                or not self.route_exposed(destination,screen)
                or math.hypot(pointer.x()-destination[0]-self.pet.width()/2,
                              pointer.y()-destination[1]-self.pet.height()/2)<max(120,self.pet.height()*.65)):
            return False
        perch = (round(self.perch[0]+dx),round(self.perch[1]+dy)) if self.perch else None
        if perch and not self.route_exposed(perch,screen):
            return False
        self.target,self.destination,self.perch = current,destination,perch
        if self.support_position is not None:
            self.support_position = (round(self.support_position[0]+dx),round(self.support_position[1]+dy))
        self.waypoints=[(round(x+dx),round(y+dy)) for x,y in self.waypoints]
        self.replans += 1
        self.phase='observing'
        self.until=now+1
        self.arrive_at = self.step_at = None
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

    def look(self, key, now):
        """Play one authored standing glance without claiming a story."""
        s = self.pet.state
        if key not in catalog():
            return False
        s.ambient.current = None
        s.walking = False
        s.gait_until = 0
        s.travel_position = None
        s.action_player.play(key, now=now)
        self.owned_start = now
        self.owned_generation = s.action_player.generation
        self.until = now+sum(s.action_player.action['durations'])/1000
        return True

    def pointer_near(self):
        p = self.pet
        pointer = QCursor.pos()
        return math.hypot(pointer.x()-(p.x()+p.width()/2),
                          pointer.y()-(p.y()+p.height()/2)) <= max(140, p.height()*.8)

    def react(self, now, key, label, reason):
        """One short notice action owned by Patrol, then back to idle."""
        s = self.pet.state
        if s.action_player.action is not None or not self.look(key, now):
            return False
        self.phase = 'reacting'
        self.kind = self.story = ''
        self.target = self.destination = None
        self.label = label
        self.reason = reason
        self.next_intent = '看完周围，再决定下一步'
        self.task_id += 1
        self.pet.state_changed.emit()
        return True

    def react_change(self, now, key, reason):
        if self.active or now < self.next_environment_reaction:
            return False
        if self.pet.state.action_player.action is not None:
            return False
        self.next_environment_reaction = now+random.uniform(35, 60)
        return self.react(now, key, '注意到变化', reason)

    def play(self, key, now, duration=None, handover=None):
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
        if handover:
            from action_inbetweens import manifest, pair_key, prefetch
            before, after = handover
            if pair_key(before, after) in manifest():
                transition = .34
                s.action_player.begin_handover(before, after, now, transition)
                prefetch(((before, after),))
                self.owned_start = s.action_player.started
                self.until += transition
        self.phase = 'doing'
        self.pet.state_changed.emit()

    def complete(self, now):
        self.no_target_streak = 0
        if self.story:
            self.policy.complete(self.story, self.target['id'] if self.target else None,
                                 now, random.uniform(180, 360), exploring=self.exploring)
            p = self.pet
            if (self.story != 'affection' and p.preferences.autonomous_speech and now-self.last_speech >= 180
                    and not p.bubble.parts and random.random() < .12):
                self.last_speech = now
                p.bubble.say('这个小角落刚刚好。' if self.target else '歇一会儿，再陪你。', 'ambient')
        self.finished = True
        self.cancel(now)

    def queue_action(self, key, now):
        if self.owns_mask:
            self.pet.masker.clear('peek')
            self.owns_mask = False
        if key not in catalog():
            self.complete(now)
            return
        previous = self.last_story_action if self.story else None
        if self.story == 'read' and previous is None and key in ('reading-pose-1', 'reading-pose-2'):
            # Sit down with the authored neutral entry before holding a static
            # seated reading sprite; the later sit-neat step is the exit.
            self.pending_story_action = key
            self.play('sit-neat', now)
            player = self.pet.state.action_player
            player.frame_order = [0, 1, 2, 3]
            player.action = dict(player.action,
                                 durations=[*catalog()['sit-neat']['durations'][:3], 1100])
            self.until = now+sum(player.action['durations'])/1000
            self.last_story_action = '__sit-entry__'
            return
        handovers = {
            'reading-pose-1': (('reading-pose-1', 0), ('sit-neat', 3), True),
            'reading-pose-2': (('reading-pose-2', 0), ('sit-neat', 3), True),
            'reading-pose-3': (('reading-pose-3', 0), ('sit-neat', 0), False),
            'stretch': (('stretch', catalog()['stretch']['frames']-1), ('tea', 0), False),
            'tea': (('tea', catalog()['tea']['frames']-1), ('sit-neat', 0), False),
            'play-peek': (('play-peek', catalog()['play-peek']['frames']-1), ('sit-relaxed', 0), False),
        }
        handover = handovers.get(previous) if self.story else None
        if self.story and previous == '__sit-entry__' and key in ('reading-pose-1', 'reading-pose-2'):
            handover = (('sit-neat', 3), (key, 0), False)
        if handover and handover[0][0] != key:
            handover = None
        from action_inbetweens import manifest, pair_key, prefetch
        if handover and pair_key(handover[0], handover[1]) not in manifest():
            handover = None
        skip_entry = bool(handover and handover[2])
        self.play(key, now)
        if catalog()[key].get('ground_idle') or catalog()[key]['frames'] == 1:
            self.pet.state.ambient.play(self.pet.state.action_player, key, now, skip_entry=skip_entry)
            self.pet.state.ambient.current = None
            self.owned_generation = self.pet.state.action_player.generation
            self.until = now+sum(self.pet.state.action_player.action['durations'])/1000
        if handover:
            before, after, _ = handover
            duration = .34
            self.pet.state.action_player.begin_handover(before, after, now, duration)
            prefetch(((before, after),))
            self.owned_start = self.pet.state.action_player.started
            self.until += duration
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
                if handover:
                    self.until += .34
        if self.story:
            self.last_story_action = key

    def arrived(self, now):
        self.moving_since = None
        self.arrive_at = self.step_at = None
        if self.pet.state.action_player.action is None:
            self.owned_start = self.owned_generation = None
        self.pet.state.gait_until = 0
        if self.kind == 'edge':
            if not self.edge_valid():
                self.fallback_stroll(now,'边框已变化，重新寻找支撑')
                return
            self.pet.state.edge_attachment.attach(self.edge_candidate,autonomous=True)
            self.edge_started = self.pet.state.edge_attachment.started
            self.phase, self.until = 'edge_hold', now+random.uniform(18,35)
            edge = self.pet.state.edge_attachment
            if self.demo:
                self.until = now+14
                edge.crawl_target = max(edge.interval[0],edge.parameter-180)
                # Hold the top of the demo instead of wandering back down.
                edge.hold_until = self.until
                self.next_intent = '沿边缘向上爬一段，演示结束后松手'
            elif self.exploring:
                edge.crawl_target = max(edge.interval[0],edge.parameter-random.uniform(30,90))
                self.next_intent = '抓住边框向上爬一段，再随机停留或离开'
            else:
                # Passive visits stay shorter and may crawl either way, so the
                # same window does not always produce the same upward gesture.
                self.until = now+random.uniform(15,28)
                lo, hi = edge.interval
                moves = []
                if edge.parameter-lo >= 25:
                    moves.append(max(lo,edge.parameter-random.uniform(25,70)))
                if hi-edge.parameter >= 25:
                    moves.append(min(hi,edge.parameter+random.uniform(25,70)))
                edge.crawl_target = random.choice(moves) if moves else None
                self.next_intent = '在窗口边框上抓一会儿，再松手离开'
            return
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
            self.until = now+random.uniform(.1, .25)
            self.reason = '绕过图标，继续走向另一侧'
            self.next_intent = '不摆查看姿势，直接绕到另一侧'
            return
        if self.kind == 'lean':
            if self.support_position is not None:
                self.ground = (self.pet.x(),self.pet.y())
                self.support_stage = 'up'
                self.play('play-climb-up',now)
                self.climb = (self.ground,self.support_position,now,self.until-now)
                self.next_intent = '接触图标后攀爬，坐下或趴着休息'
                return
            self.start_icon_hold(now)
        else:
            chains = {
                'observe': ['sit-relaxed'],
                'read': [random.choice(('reading-pose-1', 'reading-pose-2', 'reading-pose-3')), 'sit-neat'],
                'stroll': ['hair-tuck'] if random.uniform(0,1) < .55 else [],
                'tea': ['stretch', 'tea', 'sit-neat'],
                'rest': ['prone-rest'],
                'orbit': ['hair-tuck'] if random.uniform(0,1) < .4 else [],
                'peek': ['play-peek', 'sit-relaxed'],
            }
            self.steps = chains.get(self.kind, ['sit-relaxed'])
            self.next_intent = '完成互动后继续随机探索'
            if self.steps:
                self.queue_action(self.steps.pop(0), now)
            else:
                self.complete(now)
                return
            if self.kind == 'peek':
                self.owns_mask = self.mask_icon()

    def start_icon_hold(self, now):
        if self.kind == 'lean':
            if not self.lean_intro_done and 'play-lean' in catalog():
                self.lean_intro = True
                self.lean_intro_done = True
                self.play('play-lean', now)
                self.next_intent = '靠近图标，做一个短暂的依靠动作，再进入稳定倚靠姿势'
                return
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
                self.until = now+(random.uniform(*BACKSTAGE_HOLD) if self.backstage
                                  else random.uniform(20, 45))
                self.next_intent = '依靠、坐着或趴一会儿，再继续探索'
            except ValueError:
                self.cancel(now, '接触姿势不适配')

    def watch_backstage(self, now):
        """Notice the covering window disappearing and keep the pose visible."""
        visit = self.backstage
        if visit is None or self.target is None or not self.active:
            return
        if visit['revealed_at'] is None:
            if now < visit['probe_at']:
                return
            visit['probe_at'] = now+.5
            try:
                rect, screen = logical_rect(self.target['rect'])
            except (ValueError, KeyError):
                return
            if self.covered_by_surface(rect, screen):
                return
            visit['revealed_at'] = now
            self.reason = '挡在前面的窗口移开了，留在图标旁让你看一会儿'
            self.next_intent = '被发现后再和图标待十几秒，然后继续巡逻'
            self.pet.state_changed.emit()
        if self.phase in ('perched', 'resting'):
            # Both holds are driven by `until`; extend only after a real
            # reveal so the user catches an ongoing interaction, not a finish.
            self.until = max(self.until, visit['revealed_at']+BACKSTAGE_REVEAL_HOLD)

    def passive_edge_ready(self, now):
        preview = self.pet.snap_preview
        return bool(preview.surfaces and preview.surfaces_at
                    and now-preview.surfaces_at <= WINDOW_SCAN_TTL)

    def begin_edge(self, now, *, demo=False):
        """Approach a side at the current height; only then acquire a grip."""
        p, edge = self.pet, self.pet.state.edge_attachment
        if edge is None or (not self.exploring and demo):
            return False
        passive = not self.exploring
        if not demo and passive and not p.preferences.autonomous_windows:
            return False
        if not demo and not self.policy.available('edge',now,exploring=self.exploring,
                                                  unrestricted=p.preferences.activity == '活跃'):
            return False
        preview = p.snap_preview
        if passive:
            # Idle visits only use the cache warmed by Patrol; stale data is
            # replaced asynchronously instead of blocking on a desktop scan.
            if not preview.surfaces_at or now-preview.surfaces_at > WINDOW_SCAN_TTL:
                preview.request_surfaces(force=True)
                return False
        else:
            preview.request_surfaces(force=True)
            if not preview.surfaces_at or now-preview.surfaces_at > 2:
                # The scanner is asynchronous. Treat "not scanned yet" as a reason
                # to retry, not as proof that no edge exists.
                if not self.edge_retry_until:
                    self.edge_retry_until = now+3.2
                self.edge_retry_at = now+.8
                return False
        self.edge_retry_at = self.edge_retry_until = 0
        self.icons.load_poses()
        try:
            choices = edge.choices(preview.surfaces,autonomous=True)
        except (ValueError,OSError,RuntimeError):
            return False
        valid = []
        for landing,surface,screen,rect in choices:
            if screen != p.screen() or landing.kind not in ('left','right'):
                continue
            if not demo and surface is not None and not p.preferences.autonomous_windows:
                continue
            if passive and (surface is None or getattr(surface,'fullscreen',False)
                            or getattr(surface,'maximized',False)):
                # A screen edge or a fullscreen/maximized border is not a
                # movable window frame; passive visits only use real windows.
                continue
            # Grasp height equals walking height: never float upward to a grip.
            parameter = landing.parameter+p.y()-landing.position[1]
            if not landing.interval[0] <= parameter <= landing.interval[1]:
                continue
            x = round(landing.position[0])
            if not demo and abs(x-p.x()) > max(360,p.width()*3):
                continue
            seconds = abs(x-p.x())/max(1,walking_speed(p.preferences.speed))
            if not demo and (not self.allows_travel(seconds)
                             or seconds > self.policy.remaining(now,p.preferences.activity)):
                continue
            pointer = QCursor.pos()
            if math.hypot(pointer.x()-x-p.width()/2,pointer.y()-p.y()-p.height()/2) < max(120,p.height()*.65):
                continue
            landing = replace(landing,position=(x,p.y()),parameter=parameter,
                              anchor=(landing.anchor[0],landing.anchor[1]+parameter-landing.parameter))
            valid.append((landing,surface,screen,rect))
        if not valid:
            return False
        self.edge_candidate = (min(valid,key=lambda item:abs(item[0].position[0]-p.x()))
                               if demo else random.choice(valid))
        if passive:
            # Arrival revalidates the landing against this list; refresh it
            # while she walks rather than trusting a minute-old snapshot.
            preview.request_surfaces(force=True)
        self.kind = self.story = 'edge'
        self.label = ('演示攀爬：走向最近的侧边' if demo else
                      '去窗口边框旁抓一会儿' if passive else '走近边框，抓住后攀爬')
        self.target = None
        self.destination = self.edge_candidate[0].position
        self.screen = self.edge_candidate[2]
        self.geometry = self.capture_geometry()
        self.phase, self.until = 'observing', now+(1. if demo else .6)
        self.task_id += 1
        self.probe_at = now
        self.reason = ('演示边缘攀爬' if demo else
                       '附近的窗口边框看起来可以抓一下' if passive else
                       '附近有可抓握的窗口或屏幕侧边')
        self.next_intent = ('走到侧边后抓住边缘向上爬' if demo else
                            '先横向走近，接触窗口边框后再攀爬' if passive else
                            '先横向走近，接触边框后再向上爬')
        p.state.travel_position = None
        p.state_changed.emit()
        return True

    def edge_is_window(self):
        return (self.kind == 'edge' and self.edge_candidate is not None
                and self.edge_candidate[1] is not None)

    def edge_valid(self):
        if self.edge_candidate is None:
            return False
        _,surface,screen,_ = self.edge_candidate
        edge = self.pet.state.edge_attachment
        if screen != self.pet.screen():
            return False
        if surface is None:
            return edge.options['screens']
        self.pet.snap_preview.request_surfaces()
        current = next((s for s in self.pet.snap_preview.surfaces if s.handle == surface.handle),None)
        return bool(edge.options['windows'] and current and current.rect == surface.rect)

    def demo_edge(self, now=None):
        """Force one visible side climb without waiting for a random patrol."""
        now = time.monotonic() if now is None else now
        self.demo_restore_idle = not self.exploring
        self.start_once(now)
        self.demo = True
        self.demo_at = now+.05
        self.demo_until = now+4.
        self.next_at = now+30
        self.reason = '演示边缘攀爬'
        self.next_intent = '先走到最近的侧边，抓住后向上爬'
        self.pet.snap_preview.request_surfaces(force=True)
        self.pet.state_changed.emit()

    def finish_demo(self):
        if not self.demo:
            return
        self.demo = False
        self.demo_at = None
        self.demo_until = 0.
        if self.demo_restore_idle:
            self.exploring = False
            self.next_intent = '演示结束，恢复待机'
        self.demo_restore_idle = False

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
        seconds = distance/max(1,walking_speed(self.pet.preferences.speed))
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
            # Blocked ticks stop refreshing depth. Never leave the pet behind
            # a mask that no longer has a running plan to clear it.
            self.release_depth()
            if not self.interruption:
                self.reason = ('安静或暂停模式，原地陪伴' if p.preferences.quiet or p.preferences.paused
                           else '睡眠或用户交互优先，暂不玩耍')
            return
        self.settle_interruption(now)
        if (not self.active and not self.exploring and not self.demo
                and p.preferences.autonomous_windows and now >= self.next_window_scan):
            p.snap_preview.request_surfaces(force=True)
            self.next_window_scan = now+WINDOW_SCAN_INTERVAL
        if not self.active and (self.exploring or self.demo):
            if self.demo and self.demo_at is not None and now >= self.demo_at:
                if now > self.demo_until:
                    self.demo = False
                    self.demo_at = None
                    self.reason = '附近没有可抓取的侧边，演示结束'
                    self.next_at = now+5
                    self.pet.state_changed.emit()
                else:
                    self.demo_at = now+.5
                    if self.begin_edge(now, demo=True):
                        self.demo_at = None
                        return
            elif self.edge_retry_at and now >= self.edge_retry_at:
                if now > self.edge_retry_until:
                    self.edge_retry_at = self.edge_retry_until = 0
                elif self.begin_edge(now):
                    return
        if self.exploring:
            self.depth.update(now)
            if self.depth.mode != self.last_depth:
                self.last_depth = self.depth.mode
                if self.depth.mode == 'back':
                    # The first decision after stepping behind windows should
                    # find a covered icon instead of a free stroll.
                    self.backstage_next = now
            self.watch_backstage(now)
        if self.step_at is not None:
            if s.action_player.action is not None:
                self.cancel(now)
                return
            if now < self.step_at:
                return
            self.step_at = None
            if self.steps:
                self.queue_action(self.steps.pop(0), now)
            else:
                self.complete(now)
            return
        if self.passage.active:
            if self.passage.tick(now,dt):
                self.complete(now)
            return
        if self.phase == 'reacting':
            if now < self.until and s.action_player.action is not None:
                return
            if (self.owned_start is not None and s.action_player.started == self.owned_start
                    and s.action_player.generation == self.owned_generation):
                s.action_player.stop()
            self.owned_start = self.owned_generation = None
            self.phase = 'idle'
            self.label = ''
            self.reason = '看完周围，继续待机'
            self.next_intent = '继续待机或选择下一件小事'
            self.next_at = max(self.next_at, now+random.uniform(4, 8))
            p.state_changed.emit()
            return
        if self.active:
            if self.phase == 'edge_hold':
                edge = s.edge_attachment
                if not edge.active or edge.started != self.edge_started:
                    self.finish_demo()
                    self.complete(now)
                elif now >= self.until:
                    edge.release(cooldown=0)
                    self.edge_started = None
                    self.finish_demo()
                    self.complete(now)
                return
            if self.geometry is not None and self.geometry != self.capture_geometry():
                self.cancel(now, '屏幕或人物尺寸变化，重新确认接触点')
                self.react_change(now, 'listen', '屏幕或人物尺寸变了，重新看看')
                return
            wants_move = self.phase == 'walking' or self.roll_origin or self.climb
            if wants_move and (self.policy.remaining(now, p.preferences.activity) <= 0
                           or (not self.exploring and self.moving_since is not None
                               and now-self.moving_since >= self.travel_limit())):
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
                    moved = bool(current and current['rect'] != self.target['rect'])
                    self.cancel(now, '目标已变化或路径被遮挡，稍后再看', failed=True)
                    self.react_change(now, 'curious' if moved else 'listen',
                                      '目标或路径刚刚变了，停下来看看')
                    return
                pointer = QCursor.pos()
                if math.hypot(pointer.x()-self.destination[0]-p.width()/2,
                              pointer.y()-self.destination[1]-p.height()/2) < max(120,p.height()*.65):
                    self.cancel(now, '鼠标来到附近，先让开活动空间')
                    return
            elif (self.phase == 'walking' or self.roll_origin) and now >= self.probe_at:
                self.probe_at = now+1
                if self.kind == 'edge' and not self.exploring and not self.edge_valid():
                    self.cancel(now, '窗口边框已移动或消失，停下重新确认', failed=True)
                    return
                destination = (self.roll_origin[0],self.roll_origin[1]+self.roll_origin[2]) if self.roll_origin else self.destination
                if not self.route_exposed(destination, p.screen()):
                    self.cancel(now, '桌面路径被遮挡，停止探索', failed=True)
                    self.react_change(now, 'listen', '前面的路被挡住了，先停一下')
                    return
                pointer = QCursor.pos()
                if self.phase == 'walking' and math.hypot(pointer.x()-p.x()-p.width()/2,
                                                        pointer.y()-p.y()-p.height()/2) < max(100,p.height()*.5):
                    self.cancel(now, '鼠标来到附近，停下让出空间')
                    return
            if self.phase == 'observing':
                if self.target:
                    current = next((i for i in self.icons.icons if i['id'] == self.target['id']), None)
                    if not current or current['rect'] != self.target['rect'] or self.icons.error:
                        self.cancel(now, '观察目标已变化')
                        self.react_change(now, 'curious', '目标刚刚变了，停下来看看')
                        return
                if now < self.until:
                    return
                # Finish our own clip cleanly; never stop a user action.
                if (self.owned_start is not None and s.action_player.started == self.owned_start
                        and s.action_player.generation == self.owned_generation):
                    s.action_player.stop()
                self.owned_start = self.owned_generation = None
                if self.destination is None:
                    self.arrived(now)
                else:
                    self.phase = 'walking'
                    distance = math.dist((p.x(), p.y()), self.destination)
                    seconds = distance/max(1,walking_speed(p.preferences.speed))*1.5+2
                    self.until = now+(seconds if self.exploring or self.target is not None
                                      or self.kind == 'edge' else min(12,seconds))
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
                if self.kind == 'lean' and self.lean_intro:
                    self.lean_intro = False
                    self.start_icon_hold(now)
                    return
                if self.kind == 'lean' and self.climb:
                    p.move(*self.climb[1])
                    s.position_x = float(p.x())
                    self.climb = None
                    if self.support_stage == 'down':
                        self.complete(now)
                    else:
                        self.start_icon_hold(now)
                    return
                if self.kind == 'perch':
                    if self.climb:
                        p.move(*self.climb[1])
                        self.climb = None
                        if self.next_intent == '正在爬下，随后安静休息':
                            self.complete(now)
                        else:
                            hold = (random.uniform(*BACKSTAGE_HOLD) if self.backstage
                                    else random.uniform(15,35))
                            self.play('play-top-rest', now, hold,
                                      handover=(('play-climb-up', catalog()['play-climb-up']['frames']-1),
                                                ('play-top-rest', 0)))
                            s.action_player.loop = True
                            self.phase = 'perched'
                            self.next_intent = '坐稳休息，然后扶着边缘爬下'
                        return
                if self.pending_story_action:
                    key = self.pending_story_action
                    self.pending_story_action = None
                    self.queue_action(key, now)
                    return
                if self.steps:
                    if due_meal(at,self.completed) and self.story:
                        self.complete(now)
                        self.reason = '小动作收稳，接下来吃饭'
                    else:
                        # Keep the final authored pose on screen until the
                        # next step starts; the renderer handles its handover.
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
                    last_frame = s.action_player.frame(now)
                    bridge = (('play-top-rest', last_frame), ('play-climb-down', 0)) if last_frame in (0, 1) else None
                    self.play('play-climb-down', now, handover=bridge)
                    self.climb = ((p.x(),p.y()),self.ground,now,self.until-now)
                    self.next_intent = '正在爬下，随后安静休息'
                elif self.phase == 'resting':
                    if self.kind == 'lean' and self.support_position is not None:
                        self.icons.wake('休息好了，扶着图标下来')
                        self.icon_started = None
                        self.support_stage = 'down'
                        origin = (p.x(),p.y())
                        self.play('play-climb-down',now)
                        self.climb = (origin,self.ground,now,self.until-now)
                    else:
                        self.complete(now)
                else:
                    self.cancel(now, '路线超时，先停下来')
                return
            if self.climb:
                start,end,started,duration = self.climb
                sample = s.action_player.motion_sample(now)
                if sample:
                    before,after,progress = sample
                    phases = ((0.,0.,.30,.55,.80,1.,1.,1.,1.,1.) if before[0] == 'play-climb-up'
                              else (0.,0.,0.,0.,.24,1.,1.,1.))
                    from locomotion import contact_progress
                    t = phases[min(before[1],len(phases)-1)] if before==after else contact_progress(phases,before[1],progress)
                else:
                    t = 1.
                p.move(*(round(a+(b-a)*t) for a,b in zip(start,end)))
                s.position_x = float(p.x())
                return
            if self.phase == 'walking':
                if self.arrive_at is not None:
                    if now < self.arrive_at:
                        return
                    self.arrive_at = None
                    self.arrived(now)
                    return
                if self.destination[1] < p.y()-1 and not self.icon_walk():
                    self.cancel(now,'未接触支撑，不向上行走',failed=True)
                    return
                if self.exploring and self.kind == 'stroll' and self.target is None:
                    self.depth.update(now)
                if now >= self.segment_at:
                    self.segment_at = now+.2
                    distance = math.dist((p.x(), p.y()), self.destination)
                    fraction = min(1., p.preferences.speed*.25/max(.01,distance))
                    segment = tuple(a+(b-a)*fraction for a,b in zip((p.x(),p.y()), self.destination))
                    if not self.route_exposed(segment, self.screen):
                        self.cancel(now, '下一步被遮挡，停止探索', failed=True)
                        self.react_change(now, 'listen', '下一步被挡住了，停下来看看')
                        return
                distance = math.dist((p.x(), p.y()), self.destination)
                speed = max(4, p.preferences.speed*min(1., distance/18))
                if p.advance_to(self.destination, dt, speed=speed):
                    if self.kind == 'sleep_site':
                        self.arrived(now)
                        return
                    self.arrive_at = now+random.uniform(.35, .6)
                    self.moving_since = None
                    self.until = max(self.until, self.arrive_at+.05)
                    s.walking = False
                    s.travel_position = None
                    s.gait_until = 0
                    return
                if self.exploring and self.kind == 'stroll' and self.target is None:
                    self.depth.update(now)
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
        if ((7 <= at.hour < 23 or self.exploring) and now >= self.next_pointer_reaction
                and self.pointer_near()):
            pointer = QCursor.pos()
            distance = math.hypot(pointer.x()-(p.x()+p.width()/2),
                                  pointer.y()-(p.y()+p.height()/2))
            key = 'curious' if distance <= max(110,p.height()*.6) else 'listen'
            if self.react(now, key, '注意到你', '鼠标靠近，看看你在做什么'):
                self.next_pointer_reaction = now+random.uniform(30, 50)
                return
        if now < self.next_at:
            return
        idle = idle_seconds()
        if (not self.exploring and not self.icon_followup and idle is not None
                and idle < 2 and random.random() < .75):
            self.next_at = now+random.uniform(30,60)
            self.reason = '用户正在操作，先安静陪伴'
            return
        # A due patrol gets one free-slot opportunity, rather than repeatedly
        # deferring behind ambient's timer. Active ambient clips still finish.
        if not self.exploring and (at.hour >= 23 or at.hour < 7 or s.routine.period['walk'] <= 0):
            self.reason = '作息需要安静休息'
            self.next_at = now+30
            return
        if (not self.exploring and now < self.policy.quiet_until) or self.policy.remaining(now, p.preferences.activity) < 2:
            self.reason = '玩过了，先安静休息'
            self.next_at = max(now+30, self.policy.quiet_until)
            return
        pace = {'少动': 1.6, '默认': 1., '活跃': .75}[p.preferences.activity]
        self.next_at = now+random.uniform(60, 120)*pace/max(.3, s.routine.period['walk'])
        if now-self.icons.scanned_at > 30:
            self.icons.refresh()
        followup, self.icon_followup = self.icon_followup, False
        backstage = (self.exploring and self.depth.mode == 'back'
                     and now >= self.backstage_next)
        candidate = self.icon_destination(hidden=True) if backstage else self.icon_destination()
        if backstage and candidate is None:
            # No icon is currently behind a window. Resume the normal patrol
            # and retry later instead of forcing an invisible errand.
            self.backstage_next = now+30.
            backstage = False
            candidate = self.icon_destination()
        if (self.exploring and not backstage and not getattr(self,'first_walk',False)
                and now >= self.next_passage
                and random.random() < .25 and self.passage.begin(now)):
            self.next_passage = now+random.uniform(60,120)
            self.kind = self.story = 'depth_trip'
            self.label = '走出屏幕，换一侧回来'
            self.target = None
            self.phase = 'screen_passage'
            self.task_id += 1
            self.reason = '从屏幕外切换窗口前后层级'
            self.next_intent = '完全离开屏幕后换层，再从随机侧边走回来'
            p.state_changed.emit()
            return
        if (self.exploring and not backstage and not getattr(self,'first_walk',False)
                and p.preferences.autonomous_windows
                and random.random() < .28 and self.begin_edge(now)):
            return
        if (not self.exploring and not followup and p.preferences.autonomous_windows
                and self.passive_edge_ready(now)
                and random.random() < (.30 if candidate else .55)
                and self.begin_edge(now)):
            return
        icon_kinds = [k for k in ('observe', 'lean', 'read', 'orbit', 'peek', 'perch')
                      if self.policy.available(k, now, exploring=self.exploring, unrestricted=p.preferences.activity == '活跃') and (k != 'peek' or 'play-peek' in catalog())
                      and (k != 'perch' or all(key in catalog() for key in ('play-climb-up','play-top-rest','play-climb-down')))]
        if backstage:
            preferred = [kind for kind in BACKSTAGE_KINDS if kind in icon_kinds]
            if preferred:
                icon_kinds = preferred
            else:
                backstage = False
                self.backstage_next = now+30.
        first_walk = self.exploring and getattr(self, 'first_walk', False)
        self.first_walk = False
        if (candidate and icon_kinds and
                (backstage or first_walk or followup
                 or random.random() < (.95 if self.exploring else .85))):
            _, self.target, self.destination, self.screen = candidate
            self.backstage = ({'revealed_at': None, 'probe_at': 0., 'planned_at': now}
                              if backstage else None)
            self.kind = (next(kind for kind in BACKSTAGE_KINDS if kind in icon_kinds)
                         if backstage else random.choice(icon_kinds))
            self.label = ('在窗口后面和图标玩' if backstage else
                          {'observe':'去看看附近的小角落', 'lean':'去图标旁靠一会儿',
                           'read':'找个位置读一会儿', 'orbit':'绕这个小角落走半圈', 'peek':'藏一点点，再看看你',
                           'perch':'抓住边缘，爬上图标坐坐'}[self.kind])
            if self.kind in ('read','observe'):
                beside = self.beside_icon(self.target,self.screen)
                if beside is None:
                    self.fallback_stroll(now,'图标文字旁没有安全空位')
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
                required += math.dist((p.x(),p.y()),self.destination)/max(1,walking_speed(p.preferences.speed))
                if (image is None or w < p.width()*.15 or not self.route_exposed(self.perch,self.screen)
                        or required+1 > self.policy.remaining(now,p.preferences.activity)):
                    if backstage and 'lean' in icon_kinds:
                        # Keep contact with the icon instead of retreating to
                        # a plain sit when the top is too small to climb.
                        self.kind, self.label, self.perch = 'lean', '在窗口后面靠着图标', None
                    else:
                        self.kind, self.label, self.perch = 'observe', '图标上方不适合，留在旁边坐坐', None
                        beside = self.beside_icon(self.target,self.screen)
                        if beside is None:
                            self.fallback_stroll(now,'图标文字旁没有安全空位')
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
                    self.fallback_stroll(now, '图标旁没有足够的绕行空间')
                    return
                if (math.dist((p.x(),p.y()), first)+math.dist(first,second))/max(1,walking_speed(p.preferences.speed)) > min(10,self.policy.remaining(now,p.preferences.activity)):
                    self.fallback_stroll(now, '这次绕行太远')
                    return
                self.destination = first
                self.waypoints = [second]
            if self.kind == 'lean':
                self.icons.load_poses()
                self.lean_pose = random.choice(('left','right',*NEW_POSES))
                rect, _ = logical_rect(self.target['rect'])
                support = icon_surface(rect,self.icons.cache_images.get(self.target['id'])) if self.lean_pose in NEW_POSES else rect
                try:
                    self.lean_pose, final = placement(support, (p.width(),p.height()), self.lean_pose,
                        {**self.icons.options, 'offset_x':0, 'offset_y':0}, self.screen.availableGeometry().getRect(), self.icons.bounds)
                    self.destination = final
                    if final[1] < p.y()-1:
                        contact_y = rect[1]+rect[3]
                        if p.y() <= contact_y <= p.y()+p.height():
                            self.support_position = final
                            self.destination = (final[0],p.y())
                        else:
                            # The icon sits higher up the desktop: walk to it
                            # and lean there. Grabbing an out-of-reach edge
                            # would animate a climb through empty air.
                            self.support_position = None
                            self.destination = final
                except ValueError:
                    self.fallback_stroll(now, '这里没有合适的支撑点')
                    return
        else:
            self.target = None
            pool = ('roll','stroll') if self.exploring else ('roll','stroll','tea','rest')
            choices = [k for k in pool if self.policy.available(k, now, exploring=self.exploring, unrestricted=p.preferences.activity == '活跃')]
            if self.exploring and (self.policy.energy >= 15 or p.preferences.activity == '活跃') and 'stroll' not in choices:
                choices.append('stroll')
            if not choices:
                self.reason = '最近的小故事仍在冷却，继续待机'
                return
            self.kind = 'stroll' if first_walk and 'stroll' in choices else random.choice(choices)
            self.label = {'roll':'翻个身就歇着', 'stroll':'小步看看桌面', 'tea':'下午的小茶歇', 'rest':'坐趴着休息'}[self.kind]
            if self.kind == 'roll':
                self.story = self.kind
                area = p.screen_area()
                action_id = 'lazy-roll-away' if self.exploring else random.choice(('lazy-roll-toward','lazy-roll-away'))
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
                self.destination = self.random_destination()
                self.screen = p.screen()
                if self.destination is None:
                    self.cancel(now, '附近没有安全空位，停下来观察后再选择', failed=True)
                    return
        distance = 0.
        if self.destination is not None:
            if self.destination[1] < p.y()-1 and not self.icon_walk():
                self.fallback_stroll(now,'尚未接触可攀爬对象，不向上走')
                return
            distance = math.dist((p.x(), p.y()), self.destination)
            seconds = distance/max(1, walking_speed(p.preferences.speed))
            pointer = QCursor.pos()
            if (not self.allows_travel(seconds) or seconds > self.policy.remaining(now, p.preferences.activity)
                    or not self.route_exposed(self.destination, self.screen)
                    or math.hypot(pointer.x()-self.destination[0]-p.width()/2,
                                  pointer.y()-self.destination[1]-p.height()/2) < max(120,p.height()*.65)):
                self.cancel(now, '空间、鼠标避让或移动预算不适合，继续待机',failed=True)
                return
        self.story = self.kind
        self.task_id += 1
        self.phase = 'observing'
        self.probe_at = now
        # No authored departure glance: stopping/starting a walk must not
        # pin a canned look pose. The brief beat only revalidates the route.
        self.until = now+random.uniform(.1, .25)
        self.reason = '图标在窗口后面，悄悄过去和它玩一会儿' if backstage else '目标可见，直接靠近'
        self.geometry = self.capture_geometry()
        self.next_intent = ('窗口移开时保持互动，让你看见' if backstage
                            else '直接走向目标；条件改变就放弃')
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
        self.pet.masker.set('peek', QRegion(self.pet.rect()).subtracted(glyph.translated(round(x-self.pet.x()), round(y-self.pet.y()))))
        return True
