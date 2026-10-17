"""从现有矢量角色导出预览和 Windows 图标，保持角色一致。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication
from pet import PetRenderer, PetState

app = QApplication([])
root = Path(__file__).parent
image = QImage(720, 760, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
painter = QPainter(image)
painter.scale(4, 4)
PetRenderer().draw(painter, PetState())
painter.end()
public = root / 'frontend/public'
public.mkdir(parents=True, exist_ok=True)
assert image.save(str(public / 'pet-preview.png'))
icons = root / 'frontend/src-tauri/icons'
icons.mkdir(parents=True, exist_ok=True)
icon = QImage(256, 256, QImage.Format.Format_ARGB32)
icon.fill(Qt.GlobalColor.transparent)
painter = QPainter(icon)
painter.drawImage(7, 0, image.scaled(242, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
painter.end()
assert icon.save(str(icons / 'icon.ico'))
assert icon.save(str(icons / 'icon.png'))
print('Preview and icons exported.')
