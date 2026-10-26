"""Tauri 专用宠物进程。stdout 只传逐行 JSON，日志写 stderr。"""
import argparse
import base64
from dataclasses import asdict
import json
import sys
import time
import re
import uuid

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from main import PetApplication
from pet import PetRenderer, PetState
from settings_model import SettingsStore, Preferences, LIMITS, ACTIVITIES

STATUS_PERFORMANCES = {
    'thinking': ('curious', '工具状态 · 正在思考', True),
    'working': ('work', '工具状态 · 正在处理', True),
    'waiting': ('wait', '工具状态 · 等你回来', True),
    'done': ('celebrate', '工具状态 · 完成了', False),
    'error': ('sad', '工具状态 · 遇到问题', False),
}
NOTIFICATION_KINDS = ('usb', 'charging', 'download', 'success', 'failure')


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
        self.pet.present(True)
        self.music.start()
        self.reader.start()
        self.events.start()
        self.send({'type': 'ready', 'protocol': 1, 'state': self.snapshot(), 'preview': self.preview})

    def open_console(self):
        self.send({'type': 'event', 'name': 'open_console'})

    def quick_tool_send(self, name, value=None):
        self.send({'type': 'event', 'name': 'quick_tool', 'tool': name, 'value': value})

    def quick_chat_send(self, text):
        if (self.quick_pending or self.exit_requested or not isinstance(text, str)
                or not text.strip() or len(text.encode('utf-16-le'))//2>2000):
            return False
        self.quick_pending = str(uuid.uuid4())
        self.quick_last_text = text.strip()
        self.quick_history.append({'role': 'user', 'text': text.strip()})
        self.quick_history = self.quick_history[-60:]
        self.quick_reply = ''
        self.patrol.suspend()
        self.pet.bubble.say('让我想一想…', 'chat', streaming=True)
        self.send({'type': 'event', 'name': 'quick_chat', 'id': self.quick_pending, 'text': text.strip()})
        pending = self.quick_pending
        QTimer.singleShot(195000, self, lambda: self.speech_update({'id':pending,'phase':'error',
            'text':'这次等得有点久，请检查本地模型服务后再试。'}) if self.quick_pending == pending else None)
        self.changed.emit()
        return True

    def speech_update(self, payload):
        key, phase, text = payload.get('id'), payload.get('phase'), payload.get('text')
        if (set(payload)-{'id','phase','text'} or not isinstance(key,str)
                or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',key)
                or phase not in ('thinking','answer','done','error')
                or not isinstance(text,str) or len(text)>6000):
            raise ValueError('气泡消息无效')
        if self.quick_pending and key != self.quick_pending:
            return
        self.pet.bubble.say(text or '…', 'error' if phase=='error' else 'chat',
                            streaming=phase in ('thinking','answer'))
        self.quick_reply = text if phase in ('answer', 'done', 'error') else ''
        if phase in ('done', 'error') and text:
            self.quick_history.append({'role': 'error' if phase == 'error' else 'assistant', 'text': text})
            self.quick_history = self.quick_history[-60:]
        self.changed.emit()
        if phase in ('done','error') and key == self.quick_pending:
            if phase == 'error':
                self.quick_draft = self.quick_last_text
            self.quick_pending = None
            self.changed.emit()

    def perform_tool_status(self, kind):
        action_id, label, loop = STATUS_PERFORMANCES[kind]
        state = self.pet.state
        player = state.action_player
        now = time.monotonic()
        if (not self.pet.isVisible() or self.pet.preferences.paused or self.pet.preferences.quiet
                or state.sleep.active or state.sleep.transitioning
                or (state.icon_sleep and state.icon_sleep.target)
                or (state.edge_attachment and state.edge_attachment.active)
                or state.physics.active or self.pet.drag_origin is not None
                or self.pet.presence.active or self.focus.active
                or (self.window_perch.attached or self.window_perch.leaping)):
            return
        current = state.status_performance
        replacing = bool(current and player.action is not None
                         and player.started == current.get('started')
                         and player.action['id'] == current.get('action'))
        if player.action is not None and not replacing:
            return
        if now < getattr(self, '_status_performed_at', 0)+.8:
            return
        if kind == getattr(self, '_status_last_kind', None) and now < getattr(self, '_status_ended_at', 0)+1.2:
            return
        if state.patrol:
            state.patrol.suspend()
        if state.music:
            state.music.cancel()
        try:
            player.play(action_id, loop=loop, speed=.85, now=now)
        except ValueError:
            return
        state.status_performance = {'action': action_id, 'label': label,
                                    'started': player.started, 'kind': kind}
        state.walking = False
        state.travel_target = None
        state.travel_position = None
        state.gait_until = 0
        state.jump_started = None
        state.ambient.current = None
        state.ambient.defer(now, self.preferences.activity)
        self._status_performed_at = now
        self._status_last_kind = kind
        if loop:
            generation = player.generation
            QTimer.singleShot((180 if kind == 'waiting' else 120)*1000, self,
                              lambda: self.finish_tool_status(action_id, generation))
        self.pet.update()
        self.pet.state_changed.emit()

    def finish_tool_status(self, action_id, generation):
        if self.shutting_down:
            return
        state = self.pet.state
        player = state.action_player
        if (player.action is None or player.generation != generation
                or player.action['id'] != action_id):
            return
        player.stop()
        state.status_performance = None
        state.ambient.current = None
        state.ambient.defer(time.monotonic(), self.preferences.activity)
        self._status_ended_at = time.monotonic()
        self.pet.state_changed.emit()

    def toggle_translation(self, checked=False):
        self.send({'type': 'event', 'name': 'translation_toggle'})

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
        self.pet.state.routine.update()
        screen = QApplication.screenAt(self.pet.frameGeometry().center()) or QApplication.primaryScreen()
        return {'preferences': asdict(self.preferences), 'status': self.pet.status_text(),
                'visible': self.pet.desired_visible(), 'position': {'x': self.pet.x(), 'y': self.pet.y()},
                'screen': screen.name(), 'storage_error': self.storage_error,
                'icon_sleep': self.icon_sleep.snapshot(),
                'edge_attachment': self.edge_attachment.snapshot(),
                'routine': self.pet.state.routine.snapshot(),
                'patrol': self.patrol.snapshot(),
                'music': self.music.snapshot(),
                'focus': self.focus.snapshot(),
                'memory': self.memory.snapshot(),
                'window_perch': self.window_perch.snapshot(),
                'sleep': self.pet.state.sleep.snapshot(),
                'idle': self.idle_snapshot(),
                'speech': {'active': bool(self.pet.bubble.parts), 'kind': self.pet.bubble.kind,
                           'pages': len(self.pet.bubble.parts), 'pending': bool(self.quick_pending)},
                'revision': self.revision, 'config_path': self.store.settings.fileName()}

    def idle_snapshot(self):
        from idle_states import snapshot
        return snapshot(self.pet.state)

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
            if command == 'set_focus':
                if set(payload)-{'enabled','phase','remaining'} or type(payload.get('enabled')) is not bool:
                    raise ValueError('专注状态无效')
                phase = payload.get('phase', 'focus')
                remaining = payload.get('remaining')
                if phase not in ('focus', 'break'):
                    raise ValueError('专注阶段无效')
                if remaining is not None and (type(remaining) is not int
                                              or not 0 <= remaining <= 86400):
                    raise ValueError('专注时间无效')
                self.focus.set(payload['enabled'], phase, remaining)
            elif command == 'configure_ui':
                if (set(payload)-{'theme','bubble','reduced','translation'} or payload.get('theme') not in ('light','mist','dark') or payload.get('bubble') not in ('light','mist','dark') or type(payload.get('reduced')) is not bool or type(payload.get('translation')) is not bool):
                    raise ValueError('界面设置无效')
                self.ui_theme = payload['theme']
                self.ui_reduced = payload['reduced']
                self.translation_enabled = payload['translation']
                self.pet.bubble.apply_theme(payload['bubble'])
                self.refresh_menus()
            elif command == 'quick_tools_update':
                from pet_quick_tools import validate_snapshot
                self.quick_tools = validate_snapshot(payload)
                self.changed.emit()
            elif command == 'speech_update':
                self.speech_update(payload)
            elif command == 'wake_sleep':
                self.patrol.suspend()
                self.pet.state.sleep.wake(self.pet, '主动交流')
            elif command == 'desktop_event':
                if (set(payload)-{'kind','text'} or not isinstance(payload.get('text'), str)
                        or len(payload['text']) > 180):
                    raise ValueError('桌面事件无效')
                kind = payload['kind']
                if kind in STATUS_PERFORMANCES:
                    self.perform_tool_status(kind)
                elif kind in NOTIFICATION_KINDS:
                    s = self.pet.state
                    now = time.monotonic()
                    if (not s.sleep.transitioning and self.pet.isVisible()
                            and not self.pet.preferences.paused and not self.pet.preferences.quiet
                            and not (s.icon_sleep and s.icon_sleep.target)
                            and not (s.edge_attachment and s.edge_attachment.active)
                            and not s.physics.active and self.pet.drag_origin is None
                            and s.action_player.action is None and not self.pet.presence.active
                            and not self.focus.active
                            and now >= getattr(self, '_desktop_reaction_at', 0)):
                        if s.patrol:
                            s.patrol.suspend()
                        if s.music:
                            s.music.cancel()
                        s.action_player.play('sad' if kind == 'failure' else 'celebrate', speed=.8)
                        s.walking = False
                        s.ambient.current = None
                        s.ambient.next_at = now + 10
                        self._desktop_reaction_at = now + 12
                else:
                    raise ValueError('未知桌面事件')
            elif command == 'set_preference':
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
                if value != self.pet.desired_visible():
                    self.toggle_visibility()
            elif command == 'toggle_visibility':
                self.toggle_visibility()
            elif command == 'toggle_pause':
                self.toggle_pause()
            elif command == 'jump':
                if not self.pet.isVisible():
                    raise ValueError('请先显示宠物')
                self.patrol.suspend()
                self.pet.animator.jump()
            elif command == 'play_action':
                if not self.pet.isVisible():
                    raise ValueError('请先显示宠物')
                self.pet.state.sleep.wake(self.pet, '手动播放动作')
                self.pet.wake_icon_sleep()
                self.pet.state.action_player.play(payload.get('action_id'), payload.get('loop', False), payload.get('speed', 1))
                self.pet.state.jump_started = None
                self.pet.state.walking = False
                self.pet.update()
            elif command == 'stop_action':
                self.pet.wake_icon_sleep()
                self.pet.state.action_player.stop()
                self.pet.update()
            elif command == 'patrol_once':
                self.patrol.start_once()
            elif command == 'stop_patrol':
                self.patrol.stop()
            elif command == 'demo_climb':
                self.patrol.demo_edge()
            elif command == 'go_home':
                self.pet.go_home()
            elif command == 'go_corner':
                self.pet.go_home()
                area = self.pet.screen_area()
                self.pet.state.travel_target = (area.right()-self.pet.width()-30, area.bottom()-self.pet.height()+1)
            elif command == 'refresh_desktop_icons':
                self.icon_sleep.refresh()
            elif command == 'configure_icon_sleep':
                self.icon_sleep.configure(payload)
            elif command == 'start_icon_sleep':
                self.music.cancel()
                self.patrol.suspend()
                self.icon_sleep.start(payload.get('icon_id'))
            elif command == 'stop_icon_sleep':
                self.patrol.suspend()
                self.icon_sleep.wake()
            elif command == 'configure_edge_attachment':
                self.edge_attachment.configure(payload)
            elif command == 'stop_edge_attachment':
                self.edge_attachment.release(cooldown=60)
            elif command == 'perch_window':
                if payload:
                    raise ValueError('参数无效')
                self.window_perch.manual()
            elif command == 'stop_window_perch':
                if payload:
                    raise ValueError('参数无效')
                self.window_perch.release()
            elif command == 'reset_companion_memory':
                if payload:
                    raise ValueError('参数无效')
                self.memory.clear()
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
