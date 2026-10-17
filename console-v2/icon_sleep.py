"""Desktop-icon sleep interaction, asynchronous discovery and Qt coordinates."""
import math
import random
import json
import time
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, QTimer, QPoint, QRect, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QPixmap, QRegion, QTransform
from desktop_icons import scan_desktop, set_input_passthrough
from icon_pose_geometry import PoseGeometry, sprite_rect, silhouette_envelope, target_contact, icon_surface

DEFAULTS = dict(direction='auto', offset_x=0, offset_y=0, breath=55, duration=0, auto_snap=False, snap_distance=100)
LIMITS = dict(offset_x=(-100,100),offset_y=(-100,100),breath=(0,100),duration=(0,120),snap_distance=(30,240))
POSES=('left','right','back','front')
POSE_NAMES=dict(left='左侧背靠',right='右侧背靠',back='背对屏幕',front='正面背靠')
# Contact on normalized sprite canvas, at the shoulder blade rather than feet.
CONTACTS=dict(left=(.76,.48),right=(.24,.48),back=(.76,.49),front=(.50,.48))
ASSET_ROOT=Path(__file__).parent/'assets/icon-interactions'
NEW_POSES=json.loads((ASSET_ROOT/'poses.json').read_text(encoding='utf-8'))
GEOMETRIES={key:PoseGeometry(tuple(value['contact']),value['support'],value['target_x']) for key,value in NEW_POSES.items()}
POSES=(*POSES,*NEW_POSES)
POSE_NAMES.update({key:value['name'] for key,value in NEW_POSES.items()})
CONTACTS.update({key:tuple(value['contact']) for key,value in NEW_POSES.items()})


def pose_envelope(size,bounds,side):
    if side in GEOMETRIES:
        l,t,r,b=bounds;pad=3/256
        return silhouette_envelope(size,(max(0,l-pad),max(0,t-pad),min(1,r+pad),min(1,b+pad)),GEOMETRIES[side])
    return body_bounds(size,bounds)


def alpha_region(image):
    """Protect every nonzero icon pixel, including antialiased edges."""
    image=image.convertToFormat(QImage.Format.Format_RGBA8888)
    data=bytes(image.constBits()); stride=image.bytesPerLine(); region=QRegion()
    for y in range(image.height()):
        start=None
        for x in range(image.width()+1):
            opaque=x<image.width() and data[y*stride+x*4+3]>0
            if opaque and start is None: start=x
            elif not opaque and start is not None:
                region=region.united(QRegion(start,y,x-start,1));start=None
    return region


def skirt_region(image):
    """Semantic dress matte for these white-haired, blue-dress sprites.

    Only saturated blue below the waist is allowed behind the support. White
    hair, skin and pale hair shadows stay foreground, including long hair tips.
    This deliberately prefers a missed pale dress trim over cutting any hair.
    """
    source=image.convertToFormat(QImage.Format.Format_RGBA8888)
    pixels=bytes(source.constBits());stride=source.bytesPerLine()
    matte=QImage(source.size(),QImage.Format.Format_ARGB32);matte.fill(0)
    for y in range(round(source.height()*.62),source.height()):
        for x in range(source.width()):
            i=y*stride+x*4;r,g,b,a=pixels[i:i+4]
            if a and b>80 and r<b*.70 and b-r>40:
                matte.setPixel(x,y,0xffffffff)
    return alpha_region(matte)


def validated(values):
    if not isinstance(values,dict) or any(k not in DEFAULTS for k in values):
        raise ValueError('未知依靠设置')
    result={**DEFAULTS,**values}
    for key,value in result.items():
        if key in LIMITS:
            low,high=LIMITS[key]
            if type(value) is not int or not low<=value<=high: raise ValueError(f'{key} 超出允许范围')
        elif key=='direction' and value not in ('auto',*POSES): raise ValueError('未知依靠方向')
        elif key=='auto_snap' and type(value) is not bool: raise ValueError('自动依靠必须为开关值')
    return result


def pose_bounds(image):
    """Normalized nontransparent silhouette, including faint antialiased pixels."""
    image=image.convertToFormat(QImage.Format.Format_RGBA8888)
    data=bytes(image.constBits()); stride=image.bytesPerLine()
    xs=[]; ys=[]
    for y in range(image.height()):
        for x in range(image.width()):
            if data[y*stride+x*4+3]: xs.append(x); ys.append(y)
    if not xs: raise ValueError('依靠睡眠素材为空白')
    return (min(xs)/image.width(),min(ys)/image.height(),
            (max(xs)+1)/image.width(),(max(ys)+1)/image.height())


def body_bounds(size, bounds):
    """Conservative silhouette envelope over the complete breathing cycle."""
    width,height=size; left,top,right,bottom=bounds
    heights=[height*.88*(1-.009),height*.88*(1+.009)]
    return (width*.03+width*.94*left,
            min(height*.98-h+h*top for h in heights),
            width*.03+width*.94*right,
            max(height*.98-h+h*bottom for h in heights))


def placement(rect, size, direction, options, area, bounds=None):
    """Prefer exact contact; at edges switch poses, then minimally shift the body.

    Transparent window margins and adjacent desktop icons are not obstacles.
    bounds maps each pose to its normalized alpha silhouette.
    """
    x,y,w,h=rect; width,height=size
    candidates=[]
    order=['sit-front','sit-back','prone-front','prone-back','perch-front','perch-back','left','right','back']
    if direction in ('left','right','back','front') or not bounds or not any(s in bounds for s in NEW_POSES):order=['left','right','back']
    if bounds:order=[s for s in order if s in bounds]
    if direction!='auto': order=[direction]+[s for s in order if s!=direction]
    for priority,side in enumerate(order):
        if side in GEOMETRIES: cx,cy=target_contact(rect,GEOMETRIES[side])
        else:
            cx=x+(w*.10 if side in ('left','back') else w*.90 if side=='right' else w*.50)
            cy=y+h*.50
        contact_x,contact_y=CONTACTS[side]
        px=cx-width*(.03+.94*contact_x)+options['offset_x']
        py=cy-height*(.10+.88*contact_y)+options['offset_y']
        ax,ay,aw,ah=area
        left,top,right,bottom=pose_envelope(size,(bounds or {}).get(side,(0,0,1,1)),side)
        low_x,high_x=math.ceil(ax-left+1),math.floor(ax+aw-right-1)
        low_y,high_y=math.ceil(ay-top+1),math.floor(ay+ah-bottom-1)
        if low_x>high_x or low_y>high_y: continue
        px,py=round(px),round(py)
        fit_x=max(low_x,min(px,high_x)); fit_y=max(low_y,min(py,high_y))
        shift=abs(fit_x-px)+abs(fit_y-py)
        candidates.append((shift,priority,side,fit_x,fit_y))
    if not candidates: raise ValueError('当前屏幕无法完整显示睡姿，请缩小宠物')
    _,_,side,px,py=min(candidates)
    return side,(px,py)


class Scanner(QThread):
    completed=Signal(object)
    def __init__(self, target=None, parent=None, image_ids=()):
        super().__init__(parent); self.target=target;self.image_ids=image_ids
    def run(self):
        try:
            result=scan_desktop(self.target,self.image_ids)
            result['requested_id']=self.target
            self.completed.emit(result)
        except Exception as error:
            self.completed.emit({'error':str(error)})


def logical_rect(rect):
    # Windows reports physical coordinates; Qt keeps screen origins in its
    # virtual-desktop layout and sizes in device-independent pixels.
    for screen in QGuiApplication.screens():
        geo=screen.geometry(); ratio=screen.devicePixelRatio()
        px,py=geo.x(),geo.y()
        if px<=rect['x']<px+geo.width()*ratio and py<=rect['y']<py+geo.height()*ratio:
            return (px+(rect['x']-px)/ratio,py+(rect['y']-py)/ratio,rect['width']/ratio,rect['height']/ratio),screen
    raise ValueError('目标图标不在当前显示器范围内')


class IconSleep(QObject):
    def __init__(self,pet,store):
        super().__init__(pet); self.pet=pet; self.store=store
        values={k:store.settings.value('icon_sleep/'+k,v) for k,v in DEFAULTS.items()}
        for k in LIMITS:
            try: values[k]=int(values[k])
            except (ValueError,TypeError): values[k]=DEFAULTS[k]
        values['auto_snap']=str(values['auto_snap']).lower()=='true'
        try: self.options=validated(values)
        except ValueError: self.options=dict(DEFAULTS)
        self.icons=[]; self.target=None; self.phase='idle'; self.message=''; self.error=''
        self.worker=None; self.closed=False; self.image=None; self.exposed=True; self.side='left'; self.rect=None
        self.icon_images={}; self.glyph_regions={}
        self.started=0; self.origin=None; self.destination=None; self.pixmaps={}; self.bounds={};self.skirts={}
        self.frames={}
        self.watch=QTimer(self); self.watch.setInterval(700); self.watch.timeout.connect(self.refresh)
        self.animation=QTimer(self); self.animation.setInterval(33); self.animation.timeout.connect(self.tick)
        pet.state.icon_sleep=self
        self.cache_images={};self.scanned_at=0.;self.auto_direction=None
        self.sync_watch()

    def sync_watch(self):
        if self.closed:return
        if self.target or self.pet.preferences.auto_snap:
            self.watch.start()
            if not self.icons:self.refresh()
        else:self.watch.stop()

    def snapshot(self):
        return dict(icons=self.icons,options=self.options,phase=self.phase,target_id=self.target['id'] if self.target else None,
                    direction=self.side,message=self.message,error=self.error,scanning=bool(self.worker and self.worker.isRunning()))

    def changed(self):
        self.pet.state_changed.emit()

    def configure(self,values):
        self.options=validated({**self.options,**values})
        if 'direction' in values:self.auto_direction=None
        for key,value in self.options.items(): self.store.settings.setValue('icon_sleep/'+key,value)
        if not self.store.sync(): raise ValueError('依靠设置已应用，但无法保存到本机')
        if self.target:
            try: self.align()
            except ValueError:
                self.wake('位置调整后空间不足，已醒来'); raise
        elif self.pet.preferences.auto_snap:
            self.watch.start(); self.refresh()
        else:
            self.watch.stop()
        self.mark_available()
        self.changed()

    def mark_available(self):
        self.load_poses()
        for icon in self.icons:
            try:
                rect,screen=logical_rect(icon['rect']); area=screen.availableGeometry()
                placement(rect,(self.pet.width(),self.pet.height()),self.options['direction'],self.options,area.getRect(),self.bounds)
                icon['available']=True
            except ValueError: icon['available']=False

    def refresh(self):
        if self.closed:return
        if self.worker and self.worker.isRunning(): return
        self.worker=Scanner(self.target['id'] if self.target else None,parent=self,
                            image_ids=[i['id'] for i in self.icons if i['id'] not in self.cache_images] if self.pet.preferences.auto_snap else ())
        worker=self.worker
        worker.completed.connect(self.scanned)
        def finished():
            if self.worker is worker:self.worker=None
            worker.deleteLater()
        worker.finished.connect(finished)
        self.worker.start()

    def scanned(self,result):
        if self.closed:return
        if 'error' in result:
            self.error=result['error']
            if self.target: self.wake('桌面暂不可用，已醒来')
            self.changed(); return
        self.error=''; self.icons=result['icons']; self.mark_available()
        self.scanned_at=time.monotonic()
        self.cache_images={k:v for k,v in {**self.cache_images,**result.get('images',{})}.items() if any(i['id']==k for i in self.icons)}
        if self.target:
            current=next((i for i in self.icons if i['id']==self.target['id']),None)
            if not current or current['rect']!=self.target['rect']:
                self.wake('图标已移动或移除，已醒来')
            else:
                if result.get('requested_id')==self.target['id']:
                    self.icon_images=result.get('images',{})
                    self.glyph_regions.clear()
                if result['image'] is not None and result.get('requested_id')==self.target['id']:
                    self.image=result['image']
                if self.image is None and result.get('requested_id')==self.target['id']:
                    self.wake('无法读取图标轮廓，已取消依靠')
                elif self.side in GEOMETRIES and result.get('requested_id')==self.target['id']:
                    try:self.align()
                    except ValueError:self.wake('图标边缘空间不足，已离开')
                self.update_mask()
        self.changed()

    def load_poses(self):
        for side in POSES:
            if side in self.pixmaps: continue
            path=ASSET_ROOT/side/'base.png' if side in NEW_POSES else Path(__file__).parent/'assets/icon-sleep-v2'/f'{side}.png'
            pixmap=QPixmap(str(path))
            if pixmap.isNull(): raise ValueError('缺少依靠睡眠素材')
            self.bounds[side]=pose_bounds(pixmap.toImage())
            if side in NEW_POSES:
                matte=QImage(str(ASSET_ROOT/side/'skirt.png')).convertToFormat(QImage.Format.Format_RGBA8888)
                # Grayscale mask files are opaque: turn their luminance into alpha.
                region=QRegion()
                for y in range(matte.height()):
                    start=None
                    for x in range(matte.width()+1):
                        opaque=x<matte.width() and matte.pixelColor(x,y).red()>128
                        if opaque and start is None:start=x
                        elif not opaque and start is not None:
                            region=region.united(QRegion(start,y,x-start,1));start=None
                self.skirts[side]=region
            else:self.skirts[side]=skirt_region(pixmap.toImage())
            self.pixmaps[side]=pixmap

    def start(self,icon_id,instant=False,auto_pose=False):
        if not self.pet.isVisible(): raise ValueError('请先显示宠物')
        icon=next((i for i in self.icons if i['id']==icon_id),None)
        if not icon: raise ValueError('请先刷新并选择桌面图标')
        self.load_poses()
        edge=getattr(self.pet.state,'edge_attachment',None)
        if edge:edge.release(cooldown=20)
        self.wake('')
        self.target=icon; self.image=self.cache_images.get(icon_id); self.exposed=True;self.icon_images={};self.glyph_regions={}
        self.auto_direction=random.choice(('sit-front','sit-back','prone-front','prone-back','perch-front','perch-back')) if auto_pose else None
        try: self.align()
        except ValueError:
            self.target=None; raise
        self.origin=(self.pet.x(),self.pet.y()); self.started=time.monotonic(); self.last_tick=self.started; self.phase='approaching'
        self.pet.state.travel_target=None;self.pet.state.travel_position=None
        self.pet.state.action_player.stop(); self.pet.state.jump_started=None; self.pet.state.walking=False
        self.message='正在靠近 · '+icon['name']
        if instant:
            self.phase='sleeping';self.pet.move(*self.destination)
            self.pet.state.gait_until=0;self.message=POSE_NAMES[self.side]+' · '+icon['name']
            self.update_mask()
        self.watch.start(); self.animation.start(); self.refresh(); self.changed()

    def align(self):
        self.rect,screen=logical_rect(self.target['rect'])
        area=screen.availableGeometry()
        direction=self.auto_direction or self.options['direction']
        support=icon_surface(self.rect,self.image) if direction not in ('left','right','back','front') else self.rect
        options={**self.options,'offset_x':0,'offset_y':0} if self.auto_direction else self.options
        self.side,self.destination=placement(support,(self.pet.width(),self.pet.height()),direction,options,area.getRect(),self.bounds)
        if self.phase=='sleeping': self.pet.move(*self.destination)
        self.update_mask()

    def update_mask(self):
        if not self.target or not self.rect or self.phase!='sleeping': return
        region=QRegion(self.pet.rect())
        x,y,w,h=self.rect
        local=QRect(round(x-self.pet.x()),round(y-self.pet.y()),max(1,round(w)),max(1,round(h)))
        if self.image is not None:
            key=(self.target['id'],local.width(),local.height())
            if key not in self.glyph_regions:
                self.glyph_regions[key]=alpha_region(self.image.scaled(local.width(),local.height()))
            glyph=self.glyph_regions[key].translated(local.topLeft())
            pose=self.pose_rect()
            transform=QTransform().translate(pose.x(),pose.y()).scale(pose.width()/256,pose.height()/256)
            skirt=transform.map(self.skirts[self.side])
            region=region.subtracted(glyph.intersected(skirt))
        # No holes for text or other icons. Hair is never in the cutout matte.
        self.pet.setMask(region)

    def tick(self):
        if not self.target: return
        now=time.monotonic()
        if self.phase=='approaching':
            dt=now-getattr(self,'last_tick',now);self.last_tick=now
            arrived=self.pet.advance_to(self.destination,dt)
            if arrived:
                self.phase='sleeping'; self.started=now; self.message=POSE_NAMES[self.side]+' · '+self.target['name']
                self.pet.state.gait_until=0
                self.update_mask(); self.changed()
        elif self.options['duration'] and now-self.started>=self.options['duration']*60:
            self.wake('睡眠时间已到，已醒来')
        if self.phase=='sleeping': self.update_mask()
        self.pet.state.position_x=float(self.pet.x()); self.pet.update()

    def wake(self,message='已醒来'):
        active=self.target is not None
        self.target=None; self.phase='idle'; self.watch.stop(); self.animation.stop()
        self.message=message; self.image=None; self.rect=None; self.pet.clearMask()
        self.icon_images={};self.glyph_regions={}
        set_input_passthrough(int(self.pet.winId()),False)
        if self.pet.preferences.auto_snap: self.watch.start()
        self.pet.state.position_x=float(self.pet.x()); self.pet.state.next_action=time.monotonic()+3
        self.pet.update()
        if active: self.changed()

    def pose_rect(self):
        amount=self.options['breath']/100
        pulse=math.sin((time.monotonic()-self.started)*math.tau/4.2)
        if self.side in GEOMETRIES:
            return QRectF(*sprite_rect((self.pet.width(),self.pet.height()),GEOMETRIES[self.side],pulse,amount))
        height=self.pet.height()*.88*(1+amount*.009*pulse)
        width=self.pet.width()*.94
        return QRectF((self.pet.width()-width)/2,self.pet.height()*.98-height,width,height)

    def pose_pixmap(self,side,elapsed):
        if side not in NEW_POSES:return self.pixmaps[side]
        if side not in self.frames:
            self.frames[side]={kind:[QPixmap(str(ASSET_ROOT/side/f'{kind}-{i:02}.png')) for i in range(16)] for kind in ('open','blink')}
        # Two brief, unevenly spaced blinks. Motion has its own slower clock.
        beat=elapsed%9.7
        kind='blink' if 3.2<beat<3.34 or 8.05<beat<8.18 else 'open'
        return self.frames[side][kind][int(elapsed/6.4*16)%16]

    def paint(self,painter):
        if not self.target: return False
        if self.phase!='sleeping': return False
        layer=QImage(self.pet.size(),QImage.Format.Format_ARGB32_Premultiplied); layer.fill(0)
        draw=QPainter(layer); draw.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        draw.drawPixmap(self.pose_rect(),self.pose_pixmap(self.side,time.monotonic()-self.started),QRectF(0,0,256,256))
        draw.end()
        painter.save();painter.setClipRegion(self.pet.mask())
        painter.drawImage(0,0,layer);painter.restore();return True

    def cleanup(self):
        self.closed=True
        self.wake('')
        self.watch.stop()
        if self.worker:
            self.worker.wait()
