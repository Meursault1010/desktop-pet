"""Offline visual QA; synthetic surfaces only, no personal desktop capture."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtCore import QPoint
from unittest.mock import patch
from test_drop_attachment import DropTests
from drag_feedback import DragFeedback

DropTests.setUpClass()
case=DropTests();case.setUp()
out=Path(__file__).parent/'qa/drag-preview';out.mkdir(parents=True,exist_ok=True)
try:
    image=QImage(900,600,QImage.Format.Format_ARGB32_Premultiplied);image.fill('#eef5ff')
    p=QPainter(image)
    p.fillRect(200,220,400,300,QColor('#ffffff'))
    p.setPen(QColor('#9ab9d1'));p.drawRect(200,220,400,300)
    p.fillRect(400,350,40,40,QColor('#a3c7ea'))
    pet=case.pet;pet.state.drag_feedback=DragFeedback((90,110))
    pet.setFixedSize(420,440);pet.move(210,210)
    with patch('snap_preview.visible_surfaces',return_value=[]):pet.snap_preview.probe(QPoint(420,370))
    ghost=pet.snap_preview.grab().toImage()
    p.drawImage(pet.snap_preview.pos(),ghost)
    p.drawImage(pet.pos(),pet.state.drag_feedback.image(3));p.end()
    image.save(str(out/'icon-preview.png'))
    sheet=QImage(1260,880,QImage.Format.Format_ARGB32_Premultiplied);sheet.fill('#24334a')
    p=QPainter(sheet)
    for index,target in enumerate(((45,55),(90,40),(135,55),(35,110),(90,160),(145,110))):
        p.drawImage(QPoint((index%3)*420,(index//3)*440),DragFeedback(target).image(2))
    p.end();sheet.save(str(out/'shy-drag.png'))
finally:case.tearDown()
