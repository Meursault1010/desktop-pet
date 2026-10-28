"""Self-closing vertical walking check on the real animator/renderer path."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import statistics
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from pet import DesktopPet
from settings_model import Preferences

OUT = Path(__file__).resolve().parent / 'qa/vertical-live'


def main():
    app = QApplication([])
    pet = DesktopPet(Preferences(random_movement=False, auto_snap=False))
    pet.state.sleep.awake_until = float('inf')
    pet.state.ambient.next_at = float('inf')
    area = app.primaryScreen().availableGeometry()
    x, y = area.left() + 120, area.top() + area.height() // 2
    pet.move(x, y)
    # Alternate down/up so both rigs run back to back through the real timer.
    segments = [110, -110, 95, -95]
    frames, intervals, modes, positions = [], [], [], []
    state = dict(ticks=0, last=time.perf_counter(), segment=0, pause_until=0.,
                 start=time.monotonic(), finished=False)
    OUT.mkdir(parents=True, exist_ok=True)
    pet.state.travel_position = None
    pet.state.travel_target = (x, y + segments[0])
    state['segment'] = 1

    def finish():
        if state['finished']:
            return
        state['finished'] = True
        metrics = dict(frames=len(frames), ticks=state['ticks'],
                       median_ms=round(statistics.median(intervals), 2),
                       modes=modes, positions=positions[-80:])
        (OUT / 'metrics.json').write_text(json.dumps(metrics, indent=2, ensure_ascii=False),
                                          encoding='utf-8')
        if frames:
            frames[0].save(OUT / 'vertical-live.gif', save_all=True,
                           append_images=frames[1:], duration=50, loop=0, optimize=True)
        print(json.dumps({k: metrics[k] for k in ('frames', 'ticks', 'median_ms', 'modes')},
                         ensure_ascii=False), flush=True)
        pet.hide()
        pet.close()
        app.quit()

    def inspect():
        now = time.perf_counter()
        intervals.append((now - state['last']) * 1000)
        state['last'] = now
        state['ticks'] += 1
        stamp = round(time.monotonic() - state['start'], 3)
        mode = pet.state.gait_name
        energy = round(pet.state.current_gait_energy(time.monotonic()), 2)
        if not modes or modes[-1][1] != mode:
            modes.append([stamp, mode])
        if state['ticks'] % 4 == 0:
            positions.append([stamp, mode, pet.x(), pet.y(), energy])
            q = pet.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            image = Image.frombytes('RGBA', (q.width(), q.height()), bytes(q.constBits()))
            canvas = Image.new('RGB', (320, 300), '#cfd9e2')
            canvas.paste(image, (70, 50), image)
            frames.append(canvas)
        if pet.state.travel_target is None:
            if not state['pause_until']:
                state['pause_until'] = time.monotonic() + .18
            elif time.monotonic() >= state['pause_until']:
                if state['segment'] >= len(segments):
                    finish()
                    return
                pet.state.travel_position = None
                pet.state.travel_target = (x, y + segments[state['segment']])
                state['segment'] += 1
                state['pause_until'] = 0.
        if time.monotonic() - state['start'] > 12:
            finish()

    timer = QTimer()
    timer.timeout.connect(inspect)
    timer.start(16)
    pet.show()
    app.exec()


if __name__ == '__main__':
    main()
