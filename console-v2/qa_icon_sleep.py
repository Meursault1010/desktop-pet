"""Visual QA composites using a real Shell icon, isolated from user settings."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication
from desktop_icons import scan_desktop
from main import PetApplication
from settings_model import SettingsStore

if __name__=='__main__':
    app=QApplication([]); app.setQuitOnLastWindowClosed(False)
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    sample=scan_desktop(); icon=next(i for i in sample['icons'] if i['name']=='desktop-pet')
    image=scan_desktop(icon['id'])['image']
    canvas=QImage(900,350,QImage.Format.Format_ARGB32_Premultiplied);canvas.fill(QColor('#303b4c'))
    painter=QPainter(canvas);painter.setFont(QFont('Microsoft YaHei UI',10))
    with tempfile.TemporaryDirectory(prefix='xiaoju-sleep-qa-') as directory:
        controller=PetApplication(app,SettingsStore(Path(directory)/'test.ini'),enable_tray=False,create_console=False)
        controller.pet.show();controller.pet.animator.timer.stop();sleep=controller.icon_sleep
        for index,side in enumerate(('left','back','right')):
            fake=dict(id='qa',name='文件夹',rect=dict(x=400,y=300,width=50,height=50),folder=True)
            sleep.icons=[fake]
            with patch.object(sleep,'refresh'),patch('icon_sleep.logical_rect',return_value=((400,300,50,50),app.primaryScreen())):
                sleep.configure({'direction':side});sleep.start('qa',instant=True);sleep.started-=2
                sleep.exposed=True;sleep.image=image;sleep.update_mask()
                pet=QImage(controller.pet.size(),QImage.Format.Format_ARGB32_Premultiplied);pet.fill(0)
                draw=QPainter(pet)
                sleep.paint(draw);draw.end()
                shift=QPointF(index*300+150-425,220-325)
                painter.drawImage(QRectF(index*300+125,195,50,50),image)
                painter.drawImage(QPointF(controller.pet.x(),controller.pet.y())+shift,pet)
                painter.setPen(QColor('#e4e8ef'));painter.drawText(QRectF(index*300,15,300,30),0x84,{'left':'左后方','back':'正后方','right':'右后方'}[side])
                painter.drawText(QRectF(index*300+110,248,80,30),0x84,'文件夹')
                sleep.wake()
        controller.cleanup()
    painter.end();out=Path(__file__).parent/'qa/icon-sleep';out.mkdir(parents=True,exist_ok=True)
    canvas.save(str(out/'layout.png'));print(out/'layout.png')
