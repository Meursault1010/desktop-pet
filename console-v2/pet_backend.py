"""Tauri 专用宠物进程。stdout 只传逐行 JSON，日志写 stderr。"""
import argparse
import base64
from dataclasses import asdict
import json
import sys
import time

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from main import PetApplication
from pet import PetRenderer, PetState
from settings_model import SettingsStore, Preferences, LIMITS, ACTIVITIES


class InputReader(QThread):
    message = Signal(str)
    closed = Signal()

    def run(self):
        try:
            for line in sys.stdin:
                if len(line) <= 65536:
                    self.message.emit(line)
        finally:
            self.closed.emit()


class PetService(PetApplication):
    def __init__(self, app, store):
        super().__init__(app, store, enable_tray=False, create_console=False)
        self.revision = 0
        self.previous = None
        self.started_at = time.monotonic()
        self.reader = InputReader(self)
        self.reader.message.connect(self.receive)
        self.reader.closed.connect(self.quit)
        self.changed.connect(self.publish)
        self.events = QTimer(self)
        self.events.setInterval(500)
        self.events.timeout.connect(self.publish)
        self.preview = self.make_preview()

    def start(self):
        self.pet.show()
        self.reader.start()
        self.events.start()
        self.send({'type': 'ready', 'protocol': 1, 'state': self.snapshot(), 'preview': self.preview})

    def open_console(self):
        self.send({'type': 'event', 'name': 'open_console'})

    def create_menu(self, parent):
        menu = super().create_menu(parent)
        action = menu.actions()[-1]
        action.triggered.disconnect()
        action.triggered.connect(lambda: self.send({'type': 'event', 'name': 'exit_app'}))
        return menu

    @staticmethod
    def send(message):
        try:
            sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(',', ':')) + '\n')
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            QApplication.quit()

    def snapshot(self):
        screen = QApplication.screenAt(self.pet.frameGeometry().center()) or QApplication.primaryScreen()
        return {'preferences': asdict(self.preferences), 'status': self.pet.status_text(),
                'visible': self.pet.isVisible(), 'position': {'x': self.pet.x(), 'y': self.pet.y()},
                'screen': screen.name(), 'storage_error': self.storage_error,
                'icon_sleep': self.icon_sleep.snapshot(),
                'edge_attachment': self.edge_attachment.snapshot(),
                'revision': self.revision, 'config_path': self.store.settings.fileName()}

    def publish(self):
        if self.shutting_down:
            return
        state = self.snapshot()
        comparable = {k: v for k, v in state.items() if k != 'revision'}
        if comparable != self.previous:
            self.previous = comparable
            self.revision += 1
            state['revision'] = self.revision
            self.send({'type': 'event', 'name': 'state_changed', 'state': state})

    @staticmethod
    def make_preview():
        image = QImage(360, 380, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.scale(2, 2)
        PetRenderer().draw(painter, PetState())
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(bytes(data)).decode('ascii')

    def receive(self, line):
        request_id = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError('请求必须是对象')
            request_id = request.get('id')
            if not isinstance(request_id, str):
                raise ValueError('请求缺少编号')
            command = request.get('name')
            payload = request.get('payload') or {}
            if not isinstance(payload, dict):
                raise ValueError('参数格式不正确')
            if command == 'set_preference':
                key, value = payload.get('key'), payload.get('value')
                defaults = asdict(Preferences())
                if key not in defaults:
                    raise ValueError('未知设置')
                if key in LIMITS:
                    low, high = LIMITS[key]
                    if type(value) is not int or not low <= value <= high:
                        raise ValueError(f'数值应在 {low}～{high} 之间')
                elif key == 'activity':
                    if value not in ACTIVITIES:
                        raise ValueError('未知活动频率')
                elif type(value) is not bool:
                    raise ValueError('开关值必须为布尔类型')
                self.set_preference(key, value)
            elif command == 'set_visible':
                value = payload.get('visible')
                if type(value) is not bool:
                    raise ValueError('显示状态必须是布尔类型')
                if value != self.pet.isVisible():
                    self.toggle_visibility()
            elif command == 'toggle_visibility':
                self.toggle_visibility()
            elif command == 'toggle_pause':
                self.toggle_pause()
            elif command == 'jump':
                if not self.pet.isVisible():
                    raise ValueError('请先显示宠物')
                self.pet.animator.jump()
            elif command == 'play_action':
                if not self.pet.isVisible():
                    raise ValueError('请先显示宠物')
                self.pet.wake_icon_sleep()
                self.pet.state.action_player.play(payload.get('action_id'), payload.get('loop', False), payload.get('speed', 1))
                self.pet.state.jump_started = None
                self.pet.state.walking = False
                self.pet.update()
            elif command == 'stop_action':
                self.pet.wake_icon_sleep()
                self.pet.state.action_player.stop()
                self.pet.update()
            elif command == 'go_home':
                self.pet.go_home()
            elif command == 'refresh_desktop_icons':
                self.icon_sleep.refresh()
            elif command == 'configure_icon_sleep':
                self.icon_sleep.configure(payload)
            elif command == 'start_icon_sleep':
                self.icon_sleep.start(payload.get('icon_id'))
            elif command == 'stop_icon_sleep':
                self.icon_sleep.wake()
            elif command == 'configure_edge_attachment':
                self.edge_attachment.configure(payload)
            elif command == 'stop_edge_attachment':
                self.edge_attachment.release(cooldown=60)
            elif command == 'reset_defaults':
                self.reset_defaults()
            elif command not in ('get_state', 'shutdown'):
                raise ValueError('不支持的操作')
            self.publish()
            response = {'type': 'response', 'id': request_id, 'ok': True, 'state': self.snapshot()}
            if command == 'get_state':
                response['preview'] = self.preview
            self.send(response)
            if command == 'shutdown':
                QTimer.singleShot(0, self.quit)
        except (ValueError, TypeError, KeyError) as error:
            self.send({'type': 'response', 'id': request_id, 'ok': False, 'error': str(error)})
        except Exception as error:
            print(str(error), file=sys.stderr, flush=True)
            self.send({'type': 'response', 'id': request_id, 'ok': False, 'error': '操作失败，请重试'})

    def cleanup(self):
        if hasattr(self, 'events'):
            self.events.stop()
        super().cleanup()


def main():
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--settings-file')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setOrganizationName('XiaoJu')
    app.setApplicationName('DesktopPet')
    app.setQuitOnLastWindowClosed(False)
    service = PetService(app, SettingsStore(args.settings_file))
    service.start()
    result = app.exec()
    # stdin 读取线程等待父进程关闭管道；退出不等待下一条输入。
    service.reader.requestInterruption()
    return result, service


if __name__ == '__main__':
    import os
    exit_code, _service = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
