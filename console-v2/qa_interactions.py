"""Render runtime paint/mask/geometry at actual scale against real Shell art."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QRectF,QPointF
from PySide6.QtGui import QColor,QFont,QFontDatabase,QImage,QPainter
from PySide6.QtWidgets import QApplication
from main import PetApplication
from settings_model import SettingsStore
from desktop_icons import scan_desktop
from icon_sleep import NEW_POSES,GEOMETRIES
from edge_attachment import edge_placement
from icon_pose_geometry import sprite_rect

ROOT=Path(__file__).resolve().parent
def main():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    listing=scan_desktop();source=next((i for i in listing['icons'] if i['folder']),listing['icons'][0])
    glyph=scan_desktop(source['id'])['image']
    out=ROOT/'qa/interactions';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        controller=PetApplication(app,SettingsStore(Path(folder)/'settings.ini'),enable_tray=False,create_console=False)
        pet=controller.pet;pet.show();pet.animator.timer.stop();poses=controller.icon_sleep
        sheet=QImage(960,680,QImage.Format.Format_ARGB32_Premultiplied);sheet.fill(QColor('#202b40'))
        painter=QPainter(sheet);painter.setFont(QFont('Microsoft YaHei UI',10))
        for index,side in enumerate(NEW_POSES):
            icon=dict(id='qa',name=source['name'],folder=True,rect=dict(x=500,y=400,width=50,height=50))
            poses.icons=[icon]
            with patch.object(poses,'refresh'),patch('icon_sleep.logical_rect',return_value=((500,400,50,50),app.primaryScreen())):
                poses.configure({'direction':side});poses.start('qa');poses.started-=2;poses.tick();poses.image=glyph;poses.align();poses.update_mask()
                frame=QImage(pet.size(),QImage.Format.Format_ARGB32_Premultiplied);frame.fill(0)
                draw=QPainter(frame);poses.paint(draw);draw.end()
                painter.save();painter.translate(index%3*320,index//3*340)
                painter.setPen(QColor('#e5efff'));painter.drawText(15,25,NEW_POSES[side]['name'])
                # Contact at (160,210) for all panels; icon under current pose.
                shift=QPointF(-340,-190)
                painter.drawImage(QRectF(160,210,50,50),glyph)
                painter.drawText(142,280,source['name'])
                painter.drawImage(QPointF(pet.x(),pet.y())+shift,frame)
                painter.restore();poses.wake('')
        painter.end();sheet.save(str(out/'icon-contact.png'))
        poses.load_poses()
        # Window top, near-screen-top side fallback, fullscreen corner.
        sheet=QImage(1200,760,QImage.Format.Format_ARGB32_Premultiplied);sheet.fill(QColor('#e7edf6'))
        painter=QPainter(sheet);painter.setFont(QFont('Microsoft YaHei UI',10))
        cases=[((80,200,440,150),(0,0,600,380),False,'窗口上沿'),((680,6,400,340),(600,0,600,380),False,'窗口靠近屏幕顶部'),((0,380,600,380),(0,380,600,380),True,'全屏右下角'),((600,380,600,380),(600,380,600,380),True,'全屏左下角')]
        for index,(rect,area,full,label) in enumerate(cases):
            painter.fillRect(QRectF(*rect),QColor('#ffffff'));painter.fillRect(QRectF(rect[0],rect[1],rect[2],24),QColor('#c8d8ee'))
            painter.setPen(QColor('#334d70'));painter.drawText(rect[0]+12,rect[1]+18,label)
            side,(x,y),kind=edge_placement(rect,area,(180,190),poses.bounds,'left' if index==3 else 'right',full)
            sx,sy,w,h=sprite_rect((180,190),GEOMETRIES[side])
            painter.drawPixmap(QRectF(x+sx,y+sy,w,h),poses.pose_pixmap(side,2),QRectF(0,0,256,256))
        painter.end();sheet.save(str(out/'window-contact.png'))
        controller.cleanup()
    print(out)

if __name__=='__main__':main()
