"""Real Shell glyph + four poses, including deliberately crowded neighbors."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor,QFont,QFontDatabase,QImage,QPainter
from PySide6.QtWidgets import QApplication
from desktop_icons import scan_desktop
from main import PetApplication
from settings_model import SettingsStore

if __name__=='__main__':
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    sample=scan_desktop();source=next(i for i in sample['icons'] if i['folder'])
    glyph=scan_desktop(source['id'])['image']
    sheet=QImage(1200,760,QImage.Format.Format_ARGB32_Premultiplied);sheet.fill(QColor('#1e293b'))
    draw=QPainter(sheet);draw.setFont(QFont('Microsoft YaHei UI',10))
    with tempfile.TemporaryDirectory(prefix='natural-sleep-qa-') as directory:
        controller=PetApplication(app,SettingsStore(Path(directory)/'qa.ini'),enable_tray=False,create_console=False)
        pet=controller.pet;pet.show();pet.animator.timer.stop();sleep=controller.icon_sleep
        for index,side in enumerate(('left','right','back','front')):
            icon=dict(id='target',name='Folder',folder=True,rect=dict(x=400,y=300,width=50,height=50))
            sleep.icons=[icon]
            def coordinates(rect):
                return (rect['x'],rect['y'],rect['width'],rect['height']),app.primaryScreen()
            with patch.object(sleep,'refresh'),patch('icon_sleep.logical_rect',side_effect=coordinates):
                sleep.configure({'direction':side});sleep.start('target');sleep.started-=2;sleep.tick()
                sleep.image=glyph;sleep.icon_images={'target':glyph}
                sleep.icons.extend([dict(id='neighbor',name='Other file',folder=False,rect=dict(x=350,y=370,width=40,height=40))])
                sleep.icon_images['neighbor']=glyph;sleep.update_mask()
                frame=QImage(pet.size(),QImage.Format.Format_ARGB32_Premultiplied);frame.fill(0)
                painter=QPainter(frame);sleep.paint(painter);painter.end()
                draw.save();draw.translate((index%2)*600,(index//2)*380)
                shift=QPointF(-100,-190)
                # Draw native icons FIRST and then the masked pet; this verifies
                # masks actually expose them instead of overlaying copied icons.
                draw.drawImage(QRectF(300,110,50,50),glyph)
                draw.drawImage(QRectF(250,180,40,40),glyph)
                draw.setPen(QColor('#e2e8f0'));draw.drawText(290,177,'Folder');draw.drawText(240,237,'Other file')
                draw.drawImage(QPointF(pet.x(),pet.y())+shift,frame)
                draw.drawText(30,35,f'{side} / hair above target; skirt below target')
                draw.restore();sleep.wake()
        controller.cleanup()
    draw.end();output=Path(__file__).parent/'qa/icon-sleep-v2/composite.png'
    output.parent.mkdir(parents=True,exist_ok=True);sheet.save(str(output));print(output)
