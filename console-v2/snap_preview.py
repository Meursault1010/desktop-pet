"""Input-transparent ghost at the exact prospective manual-drop location."""
import random
import time
from PySide6.QtCore import Qt, QRectF, QTimer, QPoint, QThread, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget
from drop_attachment import icon_candidate
from window_edges import visible_surfaces
from icon_sleep import logical_rect, placement, GEOMETRIES
from icon_pose_geometry import icon_surface, sprite_rect


class SurfaceScanner(QThread):
    completed=Signal(object)

    def __init__(self, excluded, parent=None):
        super().__init__(parent)
        self.excluded=tuple(excluded)

    def run(self):
        try:self.completed.emit(visible_surfaces(self.excluded))
        except Exception:self.completed.emit([])


class SnapPreview(QWidget):
    def __init__(self, pet):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.pet=pet
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.candidate=None
        self.last_probe=0.
        self.point=None
        self.timer=QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh)
        self.surfaces=[]
        self.surfaces_at=0.
        self.surface_scanner=None

    def queue(self,point):
        if not self.pet.preferences.auto_snap:
            self.clear();return
        self.point=QPoint(point)
        if not self.timer.isActive():self.timer.start()
        self.request_surfaces()

    def request_surfaces(self,force=False):
        if ((not force and not self.pet.preferences.auto_snap) or self.surface_scanner is not None
                or time.monotonic()-self.surfaces_at<=.35):
            return
        edge=self.pet.state.edge_attachment
        scanner=SurfaceScanner(edge.excluded() if edge else (), QApplication.instance())
        self.surface_scanner=scanner
        scanner.completed.connect(self.surfaces_ready)
        scanner.finished.connect(scanner.deleteLater)
        scanner.start()

    def surfaces_ready(self,surfaces):
        self.surface_scanner=None
        self.surfaces=surfaces
        self.surfaces_at=time.monotonic()
        if self.point is not None and self.pet.state.drag_feedback:
            self.last_probe=0.
            self.probe(self.point)

    def refresh(self):
        if self.point is not None and self.pet.state.drag_feedback:
            self.probe(self.point)

    def clear(self):
        self.candidate=None
        self.point=None
        self.timer.stop()
        self.hide()

    def shutdown(self):
        self.clear()
        if self.surface_scanner is not None:
            self.surface_scanner.wait()
            self.surface_scanner=None

    def probe(self, point):
        pet=self.pet
        if not pet.preferences.auto_snap:
            self.clear();return
        now=time.monotonic()
        if now-self.last_probe<.07:return
        self.last_probe=now
        self.request_surfaces()
        factor=pet.preferences.size/100
        size=(round(180*factor),round(190*factor))
        dx,dy=pet.state.drag_feedback.body_origin()
        origin=(pet.x()+round((dx-10)*factor),pet.y()+round((dy-25)*factor))
        # Exactly the same clamping that happens when the drag is released.
        area=pet.screen_area()
        origin=(max(area.left(),min(origin[0],area.right()-size[0]+1)),
                max(area.top(),min(origin[1],area.bottom()-size[1]+1)))
        edge=pet.state.edge_attachment
        try:
            surfaces=self.surfaces
            if self.surfaces_at==0 and self.surface_scanner is not None:
                self.candidate=None;self.hide();return
            poses=pet.state.icon_sleep;poses.load_poses()
            target=icon_candidate(pet,point,surfaces,origin,size)
            if target:
                old=self.candidate
                pose=old['pose'] if old and old.get('icon')==target else random.choice(
                    ('sit-front','sit-back','prone-front','prone-back','perch-front','perch-back'))
                icon=next(i for i in poses.icons if i['id']==target)
                rect,screen=logical_rect(icon['rect'])
                support=icon_surface(rect,poses.cache_images.get(target))
                pose,position=placement(support,size,pose,{**poses.options,'offset_x':0,'offset_y':0},
                                        screen.availableGeometry().getRect(),poses.bounds)
                self.candidate=dict(icon=target,pose=pose,position=position)
            else:
                candidate=edge.drop_candidate(surfaces,point,origin,size)
                if candidate is None:
                    self.candidate=None;self.hide();return
                landing=candidate[0]
                self.candidate=dict(pose=landing.pose,position=landing.position)
            self.setGeometry(*(round(v) for v in self.candidate['position']),*size)
            self.show();self.update()
        except (ValueError,OSError,RuntimeError,StopIteration):
            self.clear()

    def paintEvent(self,event):
        if not self.candidate:return
        from edge_geometry import geometry
        from locomotion import frame
        pose=self.candidate['pose']
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(.43)
        if self.candidate.get('icon') and pose not in GEOMETRIES:
            rect=QRectF(self.width()*.03,self.height()*.10,self.width()*.94,self.height()*.88)
            pixmap=self.pet.state.icon_sleep.pixmaps[pose]
        else:
            spec=GEOMETRIES.get(pose) or geometry(pose)
            rect=QRectF(*sprite_rect((self.width(),self.height()),spec,0,0))
            pixmap=(self.pet.state.icon_sleep.pixmaps[pose] if pose in GEOMETRIES
                    else frame(pose,0,0,False,1))
        painter.drawPixmap(rect,pixmap,QRectF(0,0,256,256))
        painter.end()
