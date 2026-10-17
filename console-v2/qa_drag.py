import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor,QPen
from drag_feedback import DragFeedback
app=QApplication([]);root=Path(__file__).resolve().parent;folder=root/'qa/drag';folder.mkdir(exist_ok=True)
targets=[(45,55),(90,40),(135,55),(35,110),(90,160),(145,110)]
sheet=QImage(1260,880,QImage.Format.Format_ARGB32_Premultiplied);sheet.fill(QColor('#202b40'));p=QPainter(sheet)
for i,target in enumerate(targets):
 f=DragFeedback(target);im=f.image(0);im.save(str(folder/f'pose-{i}.png'))
 x=i%3*420;y=i//3*440;p.drawImage(x,y,im);p.setPen(QPen(QColor('#faac66'),2));p.drawEllipse(x+206,y+216,8,8)
 p.drawText(x+10,y+20,f'{f.name} — grab {target}')
p.end();sheet.save(str(folder/'runtime-review.png'))
for tick in range(32):
 im=QImage(1260,880,QImage.Format.Format_ARGB32_Premultiplied);im.fill(QColor('#202b40'));p=QPainter(im)
 for i,target in enumerate(targets):
  f=DragFeedback(target);p.drawImage(i%3*420,i//3*440,f.image(tick%16));p.setPen(QPen(QColor('#faac66'),2));p.drawEllipse(i%3*420+206,i//3*440+216,8,8)
 p.end();im.save(str(folder/f'review-{tick:02}.png'))
print('Saved six actual runtime reaches with fixed pointer markers.')
