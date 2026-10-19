"""Measure uncached runtime frames and mouse handlers, without desktop capture."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import json,statistics,time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QPointF,Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from drag_feedback import DragFeedback, warm_assets
from test_drop_attachment import DropTests

DropTests.setUpClass()
started=time.perf_counter();warm_assets()
startup_preload_ms=(time.perf_counter()-started)*1000
frames=[]
for target in ((45,55),(90,40),(135,55),(35,110),(90,160),(145,110)):
    feedback=DragFeedback(target)
    for index in range(32):
        started=time.perf_counter();feedback.image(index)
        frames.append((time.perf_counter()-started)*1000)
case=DropTests();case.setUp()
try:
    pet=case.pet;pet.move(200,200)
    def event(kind,x,y,button,buttons):
        return QMouseEvent(kind,QPointF(45,55),QPointF(x,y),button,buttons,Qt.KeyboardModifier.NoModifier)
    pet.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress,245,255,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton))
    samples=[]
    with patch('snap_preview.SurfaceScanner.start'),patch('snap_preview.visible_surfaces') as scan:
        for index in range(120):
            started=time.perf_counter()
            pet.mouseMoveEvent(event(QMouseEvent.Type.MouseMove,270+index,280,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton))
            samples.append((time.perf_counter()-started)*1000)
        assert scan.call_count==0
    def stats(data):return dict(median_ms=round(statistics.median(data),3),p95_ms=round(sorted(data)[int(len(data)*.95)],3),max_ms=round(max(data),3))
    result=dict(startup_preload_ms=round(startup_preload_ms,3),uncached_frames=stats(frames),
                first_drag_move_ms=round(samples[0],3),mouse_moves=stats(samples),
                native_scans_in_mouse_handler=0,
                note='Offscreen handler timings; not end-to-end display latency.')
    print(json.dumps(result))
    out=Path(__file__).parent/'qa/drag-preview/performance.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
finally:case.tearDown()
