"""yuki桌面宠物：宠物、控制台和系统托盘共用一个应用。"""
import argparse
from dataclasses import asdict
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from console import ControlWindow
from pet import DesktopPet, make_pet_icon
from settings_model import SettingsStore, normalize, Preferences
from icon_sleep import IconSleep
from edge_attachment import EdgeAttachment
from pet_menu import CompanionMenu
from pet_patrol import Patrol
from pet_music import MusicCompanion
from companion_memory import CompanionMemory
from companion_awareness import CompanionAwareness
from focus_companion import FocusCompanion
from window_perch import WindowPerch


class PetApplication(QObject):
    changed = Signal()

    def __init__(self, app, store=None, enable_tray=True, create_console=True):
        super().__init__(app)
        self.app = app
        self.store = store or SettingsStore()
        self.preferences = self.store.load()
        self.storage_error = False
        self.shutting_down = False
        self.exit_requested = False
        self.exit_animation_started = False
        self.started = False
        self.quick_draft = ''
        self.quick_pending = None
        self.quick_last_text = ''
        self.quick_history = []
        self.quick_tools = {}
        self.saved_position = None
        self.pet = DesktopPet(self.preferences)
        self.pet.controller = self
        self.memory = CompanionMemory(self.store, self.preferences.relationship_memory)
        self.focus = FocusCompanion(self.pet, lambda: self.preferences, self.memory)
        self.awareness = CompanionAwareness(self.pet, self.memory)
        self.pet.awareness = self.awareness
        self.icon_sleep = IconSleep(self.pet, self.store)
        self.edge_attachment = EdgeAttachment(self.pet, self.store, self.icon_sleep)
        # Warm bounds and static pose pixmaps before the first drag, not inside
        # a mouse-move handler. Preview uses these static images directly.
        self.icon_sleep.load_poses()
        from icon_sleep import GEOMETRIES
        from locomotion import frames
        for side in GEOMETRIES:self.icon_sleep.pose_pixmap(side,0)
        for name in ('walk-left','walk-right','climb-left','climb-right','hang'):frames(name)
        self.pet.snap_preview.request_surfaces()
        self.patrol = Patrol(self.pet, self.icon_sleep, self.store)
        self.pet.state.patrol = self.patrol
        self.window_perch = WindowPerch(self.pet, self.edge_attachment)
        self.music = MusicCompanion(self.pet)
        self.pet.state.music = self.music
        self.icon = make_pet_icon()
        self.app.setWindowIcon(self.icon)
        position = self.store.position()
        if position is not None:
            self.pet.move(position)
            self.pet.clamp_to_screen()
        self.pet.state_changed.connect(self.changed)
        self.pet.position_settled.connect(self.save_position)

        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip('yuki · 桌面宠物')
        self.tray_available = enable_tray and QSystemTrayIcon.isSystemTrayAvailable()
        self.window = ControlWindow(self) if create_console else None
        self.tray_menu = self.create_menu(self.window or self.pet)
        self.tray_menu.aboutToShow.connect(self.refresh_menus)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.changed.connect(self.refresh_menus)
        if self.tray_available:
            self.tray.show()

        self.save_timer = QTimer(self)
        self.save_timer.setInterval(10000)
        self.save_timer.timeout.connect(self.save_position)
        self.save_timer.start()
        self.app.aboutToQuit.connect(self.cleanup)
        for screen in self.app.screens():
            self.watch_screen(screen)
        self.app.screenAdded.connect(self.watch_screen)
        self.app.screenRemoved.connect(self.schedule_screen_check)

    def start(self):
        self.pet.present(True)
        self.music.start()
        self.pet.presence_entered.connect(self._entered)
        if not self.pet.presence.active:
            QTimer.singleShot(0, self._entered)

    def _entered(self):
        if self.started:
            return
        self.started = True
        self.open_console()

    def open_console(self):
        if self.window is None:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def set_preference(self, name, value):
        values = asdict(self.preferences)
        if name not in values:
            raise ValueError('Unknown preference: ' + name)
        values[name] = value
        self.preferences = normalize(values)
        self.memory.set_enabled(self.preferences.relationship_memory)
        if name == 'focus_companion' and not value and self.focus.active:
            self.focus.end()
        elif self.focus.active:
            self.focus.sync()
        else:
            self.pet.apply_preferences(self.preferences)
        self.storage_error = not self.store.save(self.preferences)
        self.save_position()
        self.changed.emit()

    def toggle_visibility(self):
        if self.exit_requested or self.exit_animation_started:
            return
        self.pet.present(not self.pet.desired_visible())
        self.changed.emit()

    def toggle_pause(self):
        self.set_preference('paused', not self.preferences.paused)

    def reset_defaults(self):
        self.preferences = Preferences()
        self.memory.set_enabled(self.preferences.relationship_memory)
        if self.focus.active:
            self.focus.sync()
        else:
            self.pet.apply_preferences(self.preferences)
        self.pet.state.jump_started = None
        self.pet.state.message_until = 0
        self.pet.state.walking = False
        self.pet.go_home(primary=True)
        self.storage_error = not self.store.save(self.preferences)
        self.save_position()
        self.changed.emit()

    def create_menu(self, parent):
        menu = CompanionMenu(parent, self.icon)
        menu.quick_chat(self)
        menu.command('translation', '划词翻译', self.toggle_translation, 'translate', checkable=True)
        menu.command('demo_climb', '演示边缘攀爬', self.demo_climb, 'climb')
        menu.command('console', '打开工作台', self.open_console, 'console')
        menu.addSeparator()
        # PetService redirects the last action through Electron's exit handler.
        menu.command('exit', '退出 yuki', self.quit, 'exit')
        self.update_menu(menu)
        menu.aboutToShow.connect(lambda: self.update_menu(menu))
        return menu

    def toggle_translation(self, checked=False):
        self.pet.bubble.say('请在 Electron 中开启划词翻译。', 'error')

    def demo_climb(self):
        try:
            self.patrol.demo_edge()
        except ValueError as error:
            self.pet.bubble.say(str(error), 'error')
            return
        self.pet.bubble.say('去最近的屏幕边缘爬给你看。', 'ambient')
        self.changed.emit()

    def update_menu(self, menu):
        if isinstance(menu, CompanionMenu):
            menu.status.setText(self.pet.status_text())
            menu.routine.setText(self.pet.state.routine.period['name'])
            menu.apply_theme(getattr(self, 'ui_theme', 'mist'))
            menu.update_chat(self)
        for action in menu.actions():
            if action.objectName() == 'translation':
                action.setChecked(getattr(self, 'translation_enabled', False))
            elif action.objectName() == 'visibility':
                action.setText('隐藏宠物' if self.pet.desired_visible() else '显示宠物')
            elif action.objectName() == 'pause':
                action.setText('继续走动' if self.preferences.paused else '暂停走动')
                action.setEnabled(not self.preferences.quiet and self.preferences.random_movement)
            elif action.objectName() in ('quiet', 'auto_snap'):
                action.setChecked(getattr(self.preferences, action.objectName()))
            elif action.objectName() in ('home', 'detach'):
                action.setEnabled(self.pet.desired_visible())

    def refresh_menus(self):
        self.update_menu(self.tray_menu)
        self.tray.setToolTip('yuki · ' + self.pet.status_text())

    def quick_tool_send(self, name, value=None):
        self.quick_tools = {**self.quick_tools, 'error': '请通过 Electron 启动 Yuki 使用快捷工具。'}
        self.changed.emit()

    def quick_chat_send(self, text):
        self.pet.bubble.say('请使用 Electron 版 yuki 连接本地模型聊天。', 'error')
        return False

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_console()

    def watch_screen(self, screen):
        screen.availableGeometryChanged.connect(self.schedule_screen_check)
        screen.geometryChanged.connect(self.schedule_screen_check)
        self.schedule_screen_check()

    def schedule_screen_check(self, *_):
        QTimer.singleShot(0, self.adjust_screen)

    def adjust_screen(self):
        if not self.shutting_down:
            self.pet.wake_icon_sleep()
            self.pet.clamp_to_screen()
            self.save_position()

    def save_position(self):
        if (self.exit_animation_started or self.exit_requested or self.pet.presence.active
                or self.pet.state.physics.active or self.pet.drag_origin is not None):
            return
        position = self.pet.pos()
        if position != self.saved_position:
            success = self.store.save_position(position)
            if success:
                self.saved_position = position
            else:
                self.storage_error = True
                self.changed.emit()

    def cleanup(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        self.save_timer.stop()
        self.focus.save_session()
        self.pet.snap_preview.shutdown()
        self.music.cleanup()
        self.edge_attachment.cleanup()
        self.icon_sleep.cleanup()
        self.pet.animator.timer.stop()
        self.pet.flush_memory()
        self.pet.bubble.timer.stop()
        self.pet.bubble.clear()
        self.store.save(self.preferences)
        self.save_position()
        self.tray.hide()
        self.pet.hide()
        if self.window is not None:
            self.window.hide()

    def begin_exit(self):
        """Start the walk-out and return its remaining duration in seconds."""
        if self.exit_animation_started:
            if self.pet.presence.active:
                return max(0., self.pet.presence.total-self.pet.presence.clock())
            return 0.
        # Persist the last on-screen position before the pet leaves the screen.
        self.save_position()
        self.exit_animation_started = True
        self.save_timer.stop()
        if not self.pet.isVisible():
            return 0.
        was_active = self.pet.presence.active
        was_entering = bool(self.pet.presence.entering) if was_active else False
        self.pet.present(False)
        if was_active and not was_entering:
            return max(0., self.pet.presence.total-self.pet.presence.clock())
        return max(0., self.pet.presence.duration)

    def quit(self):
        if self.exit_requested:
            return
        delay = self.begin_exit()
        self.exit_requested = True
        if delay > 0:
            QTimer.singleShot(round(delay*1000)+50, self.finish_quit)
        else:
            self.finish_quit()

    def finish_quit(self):
        self.cleanup()
        self.app.quit()


def main():
    parser = argparse.ArgumentParser(description='yuki桌面宠物与控制台')
    parser.add_argument('--smoke-test', action='store_true', help='启动后自动退出')
    parser.add_argument('--settings-file', help='指定独立配置文件，适合测试')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setOrganizationName('XiaoJu')
    app.setApplicationName('DesktopPet')
    app.setApplicationDisplayName('yuki · 桌面宠物')
    app.setQuitOnLastWindowClosed(False)
    controller = PetApplication(app, SettingsStore(args.settings_file))
    controller.start()
    if args.smoke_test:
        controller.pet.animator.jump()
        QTimer.singleShot(800, controller.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
