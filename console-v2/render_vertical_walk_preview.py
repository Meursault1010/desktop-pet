"""Render evenly sampled vertical-walk rig frames for visual QA."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from PIL import Image
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from vertical_walk_rig import paint, rig

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'


def render_frame(name, clock):
    image = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(248, 248, 248, 255))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    # Use a full 256px QA canvas so foot phase differences remain visible.
    paint(painter, QRectF(0, 0, 256, 256), name, clock, energy=1.0, shadows=True)
    painter.end()
    return image


def main():
    app = QApplication.instance() or QApplication([])
    stride = rig()[0]['up']['stride']
    frames = []
    for i in range(8):
        image = render_frame('walk-up', i * stride / 8.0)
        path = OUT / f'.vertical-walk-frame-{i}.png'
        image.save(str(path))
        frames.append(Image.open(path).convert('RGB'))

    contact = Image.new('RGB', (1024, 512), (248, 248, 248))
    for i, frame in enumerate(frames):
        contact.paste(frame, ((i % 4) * 256, (i // 4) * 256))
    contact.save(OUT / 'yuki-up-even-gait-contact.png')
    frames[0].save(OUT / 'yuki-up-even-gait-preview.gif', save_all=True,
                   append_images=frames[1:], duration=120, loop=0)
    for path in OUT.glob('.vertical-walk-frame-*.png'):
        path.unlink()
    app.quit()


if __name__ == '__main__':
    main()
