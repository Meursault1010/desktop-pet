"""Offscreen release-path timings; these are not compositor latency measurements."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json,time,tempfile,argparse
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPoint,QPointF,Qt
from PySide6.QtGui import QImage,QPainter,QMouseEvent
from PySide6.QtWidgets import QApplication
from main import PetApplication
from settings_model import SettingsStore
import drop_attachment,edge_attachment
from pet import PetRenderer

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    app=QApplication.instance() or QApplication([]);app.setQuitOnLastWindowClosed(False)
    records=[]
    with tempfile.TemporaryDirectory() as folder:
        controller=PetApplication(app,SettingsStore(Path(folder)/'settings.ini'),enable_tray=False,create_console=False)
        pet=controller.pet;pet.show();pet.presence.reset(True);pet.animator.timer.stop()
        controller.icon_sleep.watch.stop();controller.icon_sleep.refresh=lambda:None
        controller.icon_sleep.icons=[]
        try:
            for cache in ('cold','fresh'):
                pet.wake_icon_sleep();pet.move(300,200)
                pet.snap_preview.surfaces=[];pet.snap_preview.surfaces_at=time.monotonic() if cache=='fresh' else 0
                phases={}
                def timed(name,fn):
                    def call(*a,**kw):
                        start=time.perf_counter()
                        try:return fn(*a,**kw)
                        finally:phases[name]=phases.get(name,0)+(time.perf_counter()-start)*1000
                    return call
                def event(kind,x,y,button,buttons):
                    return QMouseEvent(kind,QPointF(90,90),QPointF(x,y),button,buttons,Qt.KeyboardModifier.NoModifier)
                with patch('snap_preview.SurfaceScanner.start'),patch.object(drop_attachment,'visible_surfaces',timed('native_scan',drop_attachment.visible_surfaces)),patch.object(edge_attachment,'inspect_foreground',timed('foreground',edge_attachment.inspect_foreground)):
                    pet.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress,390,290,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton))
                    pet.mouseMoveEvent(event(QMouseEvent.Type.MouseMove,430,310,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton))
                    start=time.perf_counter()
                    pet.mouseReleaseEvent(event(QMouseEvent.Type.MouseButtonRelease,430,310,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton))
                    phases['release_ms']=(time.perf_counter()-start)*1000
                    # Measure the very next visible frame, including cold atlas decode.
                    PetRenderer.action_atlas.cache_clear()
                    image=QImage(pet.size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0)
                    start=time.perf_counter();painter=QPainter(image);pet.paint_body(painter);painter.end()
                    phases['first_paint_ms']=(time.perf_counter()-start)*1000
                    records.append(dict(cache=cache,phases={k:round(v,3) for k,v in phases.items()}))
        finally:controller.cleanup();pet.deleteLater();controller.deleteLater();app.processEvents()
    result=dict(scenarios=records,note='Offscreen event and paint timings, not end-to-end display latency.')
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':run()
