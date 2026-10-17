"""Compose actual runtime paint at logical desktop scale; no screenshots."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile,time,math
from unittest.mock import patch
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont,QFontDatabase,QImage,QPainter,QColor
from PySide6.QtWidgets import QApplication
from main import PetApplication
from settings_model import SettingsStore
from edge_geometry import nearest,corner_landing
ROOT=Path(__file__).resolve().parent

def main():
    app=QApplication([]);QFontDatabase.addApplicationFont('C:/Windows/Fonts/msyh.ttc')
    out=ROOT/'qa/locomotion';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        control=PetApplication(app,SettingsStore(Path(folder)/'settings.ini'),enable_tray=False,create_console=False)
        pet=control.pet;pet.show();pet.animator.timer.stop();edge=control.edge_attachment;poses=control.icon_sleep;poses.load_poses()
        rect=(210,140,330,230);area=(0,0,680,540);size=(pet.width(),pet.height())
        cases=[('上沿 · 回头坐坐',(300,-60)),('左侧 · 抓框攀爬',(15,170)),('右侧 · 抓框攀爬',(540,170)),('下沿 · 抓框悬挂',(300,410))]
        images=[]
        for tick in range(32):
            sheet=QImage(1360,1080,QImage.Format.Format_ARGB32_Premultiplied);sheet.fill(QColor('#e8eef7'))
            draw=QPainter(sheet);draw.setFont(QFont('Microsoft YaHei UI',12))
            for index,(label,origin) in enumerate(cases):
                landing=nearest(rect,area,size,poses.bounds,origin)
                if index==0:
                    from edge_geometry import candidates
                    landing=next(l for _,l in candidates(rect,area,size,poses.bounds,origin) if l.pose=='sit-back')
                assert landing.kind==('top','left','right','bottom')[index]
                position=landing.position
                if landing.kind in ('left','right'):
                    p=landing.interval[0]+(landing.interval[1]-landing.interval[0])*(.5+.4*math.sin(tick*math.tau/32))
                    position=(position[0],position[1]+p-landing.parameter)
                draw.save();draw.translate(index%2*680,index//2*540)
                draw.setPen(QColor('#31486b'));draw.drawText(24,35,label)
                draw.fillRect(QRectF(*rect),QColor('#fafcff'));draw.fillRect(QRectF(rect[0],rect[1],rect[2],30),QColor('#bed0eb'))
                draw.drawText(rect[0]+12,rect[1]+21,'应用窗口')
                edge.active=True;edge.phase='resting';edge.side=landing.pose;edge.kind=landing.kind;edge.started=0
                edge.distance=tick*44/24;edge.crawl_target=1;edge.crawl_direction=1
                frame=QImage(pet.size(),QImage.Format.Format_ARGB32_Premultiplied);frame.fill(0)
                painter=QPainter(frame)
                with patch('edge_attachment.time.monotonic',return_value=tick/12):edge.paint(painter)
                painter.end();draw.drawImage(QRectF(*position,*size),frame)
                draw.restore()
            draw.end();path=out/f'contact-{tick:02}.png';sheet.save(str(path));images.append(path)
        control.cleanup()
    print(out)
if __name__=='__main__':main()
