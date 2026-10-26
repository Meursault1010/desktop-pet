"""Manual-drop attachment to native window/screen surfaces.

Explicit drops and airborne contact initiate attachment; timers only follow support.
Never activates or moves another app.
"""
import math
import os
import random
import time
from PySide6.QtCore import QObject,QTimer,QRectF
from PySide6.QtGui import QGuiApplication,QPainter
from icon_sleep import GEOMETRIES,pose_envelope
from icon_pose_geometry import sprite_rect
from window_edges import inspect_foreground,foreground_process,visible_surfaces

DEFAULTS=dict(enabled=False,windows=True,screens=True,corner='right',delay=8)

def validated(values):
    if not isinstance(values,dict) or set(values)-set(DEFAULTS):raise ValueError('未知边缘附着设置')
    result={**DEFAULTS,**values}
    for k in ('enabled','windows','screens'):
        if type(result[k]) is not bool:raise ValueError('边缘附着开关必须为布尔值')
    if result['corner'] not in ('left','right'):raise ValueError('请选择左侧或右侧角落')
    if type(result['delay']) is not int or not 2<=result['delay']<=60:raise ValueError('停留时间应在 2～60 秒之间')
    return result


def logical_surface(surface,screens):
    # Match native monitor origins, not a window point that can cross displays.
    mx,my,mw,mh=surface.monitor
    screen=min(screens,key=lambda s:abs(s.geometry().x()-mx)+abs(s.geometry().y()-my))
    ratio=screen.devicePixelRatio();geo=screen.geometry()
    def convert(rect):
        x,y,w,h=rect
        return geo.x()+(x-mx)/ratio,geo.y()+(y-my)/ratio,w/ratio,h/ratio
    return convert(surface.rect),convert(surface.work_area),screen


def edge_placement(rect,area,size,bounds,corner='right',fullscreen=False,variant=0,origin=None):
    """Compatibility wrapper; runtime and QA use the same nearest geometry."""
    from edge_geometry import nearest,corner_landing
    if origin is None:
        origin=(area[0] if corner=='left' and fullscreen else area[0]+area[2]-size[0] if fullscreen else rect[0]+rect[2]/2-size[0]/2,rect[1]-size[1])
    landing=corner_landing(area,size,bounds,origin,corner) if fullscreen else nearest(rect,area,size,bounds,origin,variant)
    return landing.pose,tuple(round(v) for v in landing.position),landing.kind


class EdgeAttachment(QObject):
    def __init__(self,pet,store,poses):
        super().__init__(pet);self.pet=pet;self.store=store;self.poses=poses
        values={k:store.settings.value('edge_attachment/'+k,v) for k,v in DEFAULTS.items()}
        for k in ('enabled','windows','screens'):values[k]=str(values[k]).lower()=='true'
        try:values['delay']=int(values['delay']);self.options=validated(values)
        except (TypeError,ValueError):self.options=dict(DEFAULTS)
        self.active=False;self.handle=None;self.side='perch-back';self.kind='';self.message='等待自然停靠';self.error=''
        self.pending=None;self.pending_since=0.;self.until=time.monotonic()+self.options['delay']
        self.started=0.;self.destination=None;self.variant=random.randrange(4)
        self.phase='idle';self.landing=None;self.interval=(0,0);self.parameter=0.;self.fraction=.5
        self.distance=0.;self.crawl_direction=1;self.crawl_target=None;self.next_move=0.;self.screen=None
        self.hold_until=0.
        self.climb_clock=0.;self.crawl_phase=0.
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.tick)
        self.animation=QTimer(self);self.animation.setInterval(16);self.animation.timeout.connect(self.animate)
        pet.state.edge_attachment=self

    def snapshot(self):return dict(options=self.options,active=self.active,kind=self.kind,message=self.message,error=self.error,direction=self.side)

    def configure(self,values):
        self.options=validated({**self.options,**values})
        for key,value in self.options.items():self.store.settings.setValue('edge_attachment/'+key,value)
        saved=self.store.sync();self.release(cooldown=0)
        self.timer.stop();self.message='拖到边框后松手停靠'
        self.pet.state_changed.emit()
        if not saved:raise ValueError('边缘设置已应用，但无法保存到本机')

    def release(self,cooldown=20):
        was=self.active;self.active=False;self.handle=None;self.pending=None;self.destination=None;self.phase='idle'
        self.animation.stop();self.until=time.monotonic()+cooldown;self.message='等待自然停靠'
        self.hold_until=0.
        self.variant=random.randrange(4)
        self.pet.state.position_x=float(self.pet.x())
        self.pet.state.gait_until=0;self.pet.state.travel_position=None
        if not self.options['enabled']:self.timer.stop()
        if was:self.pet.update();self.pet.state_changed.emit()

    def busy(self):
        s=self.pet.state
        return (not self.pet.isVisible() or self.pet.drag_origin is not None or bool(self.poses.target)
                or s.action_player.action is not None or s.jump_started is not None or s.travel_target is not None)

    def excluded(self):
        return (os.getppid(),int(os.environ.get('PET_CONTROL_PID','0')))

    def choices(self,surfaces,size=None,origin=None,*,cached_only=False,autonomous=False):
        from edge_geometry import candidates,corner_landing,screen_landings
        screens=QGuiApplication.screens();size=size or (self.pet.width(),self.pet.height());origin=origin or (self.pet.x(),self.pet.y())
        result=[];higher=[];foreground=None if cached_only else inspect_foreground(self.excluded())
        # During a mouse grab the pet may own foreground focus. The first
        # external visible surface still identifies the fullscreen page.
        if foreground is None and surfaces:foreground=surfaces[0]
        # Fullscreen content takes priority over desktop boundaries underneath.
        if not autonomous and self.options['windows'] and foreground and (foreground.fullscreen or foreground.maximized):
            rect,area,screen=logical_surface(foreground,screens)
            if foreground.fullscreen:area=screen.geometry().getRect()
            return [(corner_landing(area,size,self.poses.bounds,origin,self.options['corner']),foreground,screen,rect)]
        for surface in surfaces:
            rect,area,screen=logical_surface(surface,screens)
            if self.options['windows']:
                for _,landing in candidates(rect,area,size,self.poses.bounds,origin,self.variant,higher):
                    result.append((landing,surface,screen,rect))
            higher.append(rect)
        if self.options['screens']:
            for screen in screens:
                area=screen.availableGeometry().getRect()
                for landing in screen_landings(area,size,self.poses.bounds,origin,() if autonomous else higher):
                    result.append((landing,None,screen,area))
        return result

    def drop_candidate(self,surfaces,point,origin=None,size=None):
        self.poses.load_poses()
        origin=origin or (self.pet.x(),self.pet.y());size=size or (self.pet.width(),self.pet.height())
        limit=max(48,size[0]*.6)
        choices=[]
        for item in self.choices(surfaces,size,origin,cached_only=True):
            landing=item[0]
            shift=math.hypot(landing.position[0]-origin[0],landing.position[1]-origin[1])
            # Corner projection is only valid close to that corner. A drop in
            # the middle of a fullscreen page must never teleport across it.
            cursor=math.hypot(point.x()-landing.anchor[0],point.y()-landing.anchor[1])
            if shift<=limit or (landing.kind!='corner' and cursor<=28 and shift<=limit*1.6):
                choices.append((shift,item))
        return min(choices,key=lambda pair:pair[0])[1] if choices else None

    def on_drop(self,surfaces,point):
        """Immediate manual landing, independent of dwell, walking and pause."""
        if not self.pet.preferences.auto_snap:return False
        candidate=self.drop_candidate(surfaces,point)
        if candidate is None:return False
        return self.attach(candidate)

    def flight_targets(self,surfaces):
        """Use cached native surfaces; never enumerate windows in a physics tick."""
        if not self.pet.preferences.auto_snap or not self.options['windows']:return []
        from edge_geometry import candidates
        self.poses.load_poses()
        size=(self.pet.width(),self.pet.height());origin=(self.pet.x(),self.pet.y())
        screens=QGuiApplication.screens();higher=[];result=[]
        key=(tuple(surfaces),size,self.variant,tuple((s.geometry().getRect(),s.devicePixelRatio()) for s in screens))
        if getattr(self,'_flight_key',None)==key:return self._flight_targets
        for surface in surfaces:
            rect,area,screen=logical_surface(surface,screens)
            if surface.fullscreen:area=screen.geometry().getRect()
            for _,landing in candidates(rect,area,size,self.poses.bounds,origin,self.variant,higher):
                result.append((landing,surface,screen,rect))
            higher.append(rect)
        self._flight_key=key;self._flight_targets=result
        return result

    def catch_flight(self,start,end,targets):
        if not self.pet.preferences.auto_snap or not self.pet.state.physics.flying:return False
        from edge_geometry import flight_intersection
        candidate=flight_intersection(start,end,(self.pet.width(),self.pet.height()),targets)
        return self.attach(candidate) if candidate is not None else False

    def attach(self,candidate,*,autonomous=False):
        """Shared immediate landing for a manual drop or a real airborne contact."""
        landing,surface,screen,rect=candidate
        self.autonomous = autonomous
        self.set_landing(landing,rect);self.handle=surface.handle if surface else None;self.screen=screen
        now=time.monotonic();self.active=True;self.phase='resting';self.started=now;self.last_tick=now
        self.distance=0.;self.crawl_target=None;self.next_move=now+random.uniform(2,5);self.until=0
        self.climb_clock=0.;self.crawl_phase=0.
        self.hold_until=0.
        state=self.pet.state;state.physics.cancel();state.travel_target=None;state.travel_position=None;state.walking=False
        self.pet.animator.timer.setInterval(16)
        state.jump_started=None;state.action_player.stop();state.gait_until=0
        self.pet.move(*(round(v) for v in self.destination));state.position_x=float(self.pet.x())
        self.message={'top':'上沿 · 轻松休息','bottom':'下沿 · 抓紧晃晃','left':'侧边 · 抓框爬行','right':'侧边 · 抓框爬行','corner':'角落 · 自然休息'}[self.kind]
        self.error='';self.timer.start();self.animation.start();self.pet.update();self.pet.state_changed.emit()
        return True

    def set_landing(self,landing,rect):
        self.landing=landing;self.side=landing.pose;self.kind=landing.kind;self.destination=landing.position
        self.interval=landing.interval;self.parameter=landing.parameter
        x,y,w,h=rect
        self.fraction=(self.parameter-(y if self.kind in ('left','right') else x))/max(1,h if self.kind in ('left','right') else w)
        self.surface_rect=rect

    def follow(self,surfaces):
        from edge_geometry import candidates,corner_landing,screen_landings
        size=(self.pet.width(),self.pet.height());origin=(self.pet.x(),self.pet.y());higher=[]
        if self.handle:
            target=next((s for s in surfaces if s.handle==self.handle),None)
            if target is None:return False
            rect,area,self.screen=logical_surface(target,QGuiApplication.screens())
            for other in surfaces:
                if other.handle==self.handle:break
                higher.append(logical_surface(other,QGuiApplication.screens())[0])
            full=target.fullscreen or target.maximized
            if target.fullscreen:area=self.screen.geometry().getRect()
            if full and self.kind=='corner':
                # Keep the same corner when a full window is passively moved.
                preferred='left' if self.side=='perch-back' else 'right'
                landing=corner_landing(area,size,self.poses.bounds,(-1e7,origin[1]) if preferred=='left' else (1e7,origin[1]),preferred)
                self.set_landing(landing,rect);return True
            if self.kind=='corner':return False
            choices=[l for _,l in candidates(rect,area,size,self.poses.bounds,origin,self.variant,higher) if l.pose==self.side and l.kind==self.kind]
        else:
            if self.screen not in QGuiApplication.screens():return False
            rect=self.screen.availableGeometry().getRect()
            higher=[logical_surface(s,QGuiApplication.screens())[0] for s in surfaces]
            choices=[l for l in screen_landings(rect,size,self.poses.bounds,origin,() if getattr(self,'autonomous',False) else higher) if l.pose==self.side and l.kind==self.kind]
        if not choices:return False
        x,y,w,h=rect;p=(y+h*self.fraction) if self.kind in ('left','right') else (x+w*self.fraction)
        landing=min(choices,key=lambda l:abs(max(l.interval[0],min(l.interval[1],p))-p))
        p=max(landing.interval[0],min(landing.interval[1],p));delta=p-landing.parameter
        from dataclasses import replace
        horizontal=self.kind in ('top','bottom')
        position=(landing.position[0]+(delta if horizontal else 0),landing.position[1]+(0 if horizontal else delta))
        anchor=(landing.anchor[0]+(delta if horizontal else 0),landing.anchor[1]+(0 if horizontal else delta))
        old=self.parameter
        self.set_landing(replace(landing,position=position,anchor=anchor,parameter=p),rect)
        # Crawl targets are relative to the supporting window, too.
        if self.crawl_target is not None:self.crawl_target+=p-old
        return True

    def tick(self):
        if self.pet.presence.active:return
        # No autonomous search: only follow an already established grip.
        if not self.active:return
        if self.busy():return
        try:
            preview=self.pet.snap_preview
            preview.request_surfaces(force=True)
            if not preview.surfaces_at or time.monotonic()-preview.surfaces_at>.75:return
            surfaces=preview.surfaces
            if not self.follow(surfaces):self.release(cooldown=2)
        except Exception as error:
            self.error=str(error);self.release(cooldown=5);self.pet.state_changed.emit()

    def animate(self):
        if self.pet.presence.active:
            self.last_tick=time.monotonic()
            return
        if not self.active or self.destination is None:return
        now=time.monotonic();dt=max(0,min(.1,now-self.last_tick));self.last_tick=now
        paused=self.pet.preferences.paused or self.pet.preferences.quiet
        if self.phase=='approaching':
            if paused:return
            if self.pet.advance_to(self.destination,dt):
                self.phase='resting';self.started=now;self.pet.state.gait_until=0
                self.message={'top':'上沿 · 轻松休息','bottom':'下沿 · 抓紧晃晃','left':'侧边 · 抓框爬行','right':'侧边 · 抓框爬行','corner':'角落 · 自然休息'}[self.kind]
                self.pet.state_changed.emit()
        else:
            # Only side grips crawl. A passive window translation never advances
            # gait distance and never changes the support pose.
            crawling=self.side.startswith('climb')
            if crawling and not paused:
                if self.crawl_target is None and now>=self.next_move and now>=self.hold_until:
                    lo,hi=self.interval
                    self.crawl_target=max(lo,min(hi,self.parameter+random.choice((-1,1))*random.uniform(25,100)))
                if self.crawl_target is not None:
                    lo,hi=self.interval;self.crawl_target=max(lo,min(hi,self.crawl_target))
                    from climb_rig import pull_progress
                    scale=self.pet.height()*.88/256
                    delta=self.crawl_target-self.parameter
                    # Ease each pull, slowing at the grip handoff. Use signed
                    # local travel so reversing never resets the hand pose.
                    next_phase=self.crawl_phase+math.copysign(12*dt/scale,delta)
                    travel=(pull_progress(next_phase)-pull_progress(self.crawl_phase))*scale
                    step=math.copysign(min(abs(delta),abs(travel)),delta)
                    self.crawl_phase=next_phase;self.climb_clock+=step/scale
                    self.crawl_direction=1 if step>=0 else -1;self.distance+=abs(step)
                    self.parameter+=step;self.destination=(self.destination[0],self.destination[1]+step)
                    x,y,w,h=self.surface_rect;self.fraction=(self.parameter-y)/max(1,h)
                    if abs(delta)<=abs(step)+.01:self.crawl_target=None;self.next_move=now+random.uniform(2,5)
            self.pet.move(*(round(v) for v in self.destination));self.pet.state.position_x=float(self.pet.x())
        self.pet.update()

    def paint(self,painter):
        if not self.active or self.phase=='approaching':return False
        from locomotion import frame
        from edge_geometry import geometry
        elapsed=time.monotonic()-self.started
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.side in GEOMETRIES:
            rect=QRectF(*sprite_rect((self.pet.width(),self.pet.height()),GEOMETRIES[self.side],math.sin(elapsed*math.tau/4.2),.55))
            pixmap=self.poses.pose_pixmap(self.side,elapsed)
        else:
            rect=QRectF(*sprite_rect((self.pet.width(),self.pet.height()),geometry(self.side),0,0))
            if self.side.startswith('climb'):
                from climb_rig import paint as paint_climb
                paint_climb(painter,rect,self.side,self.climb_clock)
                return True
            moving=self.crawl_target is not None and not (self.pet.preferences.paused or self.pet.preferences.quiet)
            pixmap=frame(self.side,self.distance,elapsed,moving,self.crawl_direction)
        painter.drawPixmap(rect,pixmap,QRectF(0,0,256,256));return True

    def cleanup(self):self.timer.stop();self.release(cooldown=0)
