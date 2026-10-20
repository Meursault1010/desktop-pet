"""离屏验收：独立临时配置，不触碰用户偏好，也不显示真实托盘。"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from main import PetApplication
from settings_model import Preferences, SettingsStore, normalize


class ConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        # Windows 的 offscreen 插件不枚举系统字体，显式加载用于截图验收。
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
            cls.app.setFont(QFont('Microsoft YaHei UI', 9))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='xiaoju-test-')
        self.path = Path(self.directory.name) / 'settings.ini'
        self.controller = PetApplication(self.app, SettingsStore(self.path), enable_tray=False)
        self.controller.pet.state.patrol = None  # Legacy movement controls are tested independently.
        self.controller.start()
        self.controller.pet.advance_presence(time.monotonic()+2)
        self.controller.pet.animator.timer.stop()
        self.app.processEvents()
        self.sleep_patch = patch('pet_sleep.sleep_time', return_value=False)
        self.sleep_patch.start()
        self.controller.pet.state.sleep.phase = 'awake'
        from datetime import datetime
        from daily_routine import current_period
        self.controller.pet.state.routine.period = current_period(datetime(2026, 1, 1, 10))
        self.controller.pet.state.ambient.set_period(self.controller.pet.state.routine.period)
        self.routine_patch = patch.object(self.controller.pet.state.routine, 'update', return_value=False)
        self.routine_patch.start()

    def tearDown(self):
        self.sleep_patch.stop()
        self.routine_patch.stop()
        self.controller.cleanup()
        self.controller.window.deleteLater()
        self.controller.pet.deleteLater()
        self.controller.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_controls_and_shared_menu(self):
        controller = self.controller
        window, pet = controller.window, controller.pet
        QTest.mouseClick(window.visibility_button, Qt.MouseButton.LeftButton)
        pet.advance_presence(time.monotonic()+2)
        self.assertFalse(pet.isVisible())
        self.assertFalse(pet.animator.timer.isActive())
        self.assertFalse(window.jump_button.isEnabled())
        visibility = next(a for a in controller.tray_menu.actions()
                          if a.objectName() == 'visibility')
        self.assertEqual(visibility.text(), '显示宠物')
        visibility.trigger()
        pet.advance_presence(time.monotonic()+2)
        self.assertTrue(pet.isVisible())
        QTest.mouseClick(window.pause_button, Qt.MouseButton.LeftButton)
        self.assertTrue(controller.preferences.paused)
        self.assertEqual(pet.status_text(), '已暂停')
        pause = next(a for a in controller.tray_menu.actions() if a.objectName() == 'pause')
        self.assertEqual(pause.text(), '继续走动')
        QTest.mouseClick(window.jump_button, Qt.MouseButton.LeftButton)
        self.assertIsNotNone(pet.state.jump_started)
        self.assertTrue(controller.preferences.paused)
        pet.state.jump_started = time.monotonic() - 1
        pet.animator.tick()
        self.assertEqual(pet.status_text(), '已暂停')
        pause.trigger()
        self.assertFalse(controller.preferences.paused)

    def test_settings_immediate_and_persistent(self):
        window, pet = self.controller.window, self.controller.pet
        window.sliders['size'][0].setValue(150)
        window.sliders['opacity'][0].setValue(65)
        window.sliders['speed'][0].setValue(85)
        window.activity.setCurrentText('活跃')
        window.checks['always_on_top'].setChecked(False)
        window.checks['random_movement'].setChecked(False)
        window.checks['greeting'].setChecked(False)
        self.assertEqual(pet.width(), 270)
        self.assertAlmostEqual(pet.windowOpacity(), .65, delta=.01)
        self.assertFalse(pet.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.assertTrue(pet.isVisible())
        self.assertEqual(pet.preferences.speed, 85)
        self.assertEqual(pet.preferences.activity, '活跃')
        pet.animator.jump()
        self.assertEqual(pet.state.message_until, 0)
        loaded = SettingsStore(self.path).load()
        self.assertEqual(loaded, self.controller.preferences)
        self.assertFalse(loaded.random_movement)
        self.assertFalse(loaded.greeting)

    def test_quiet_mode_restores_preferences_across_restart(self):
        controller = self.controller
        controller.set_preference('random_movement', False)
        controller.set_preference('greeting', True)
        controller.window.checks['quiet'].setChecked(True)
        self.assertFalse(controller.pet.movement_allowed())
        controller.pet.animator.jump()
        self.assertEqual(controller.pet.state.message_until, 0)
        self.assertFalse(controller.window.checks['greeting'].isEnabled())
        self.assertFalse(controller.window.checks['random_movement'].isEnabled())
        controller.preferences = SettingsStore(self.path).load()
        controller.set_preference('quiet', False)
        self.assertFalse(controller.preferences.random_movement)
        self.assertTrue(controller.preferences.greeting)
        controller.pet.animator.jump()
        self.assertGreater(controller.pet.state.message_until, time.monotonic())

    def test_movement_speed_and_stop_conditions(self):
        controller, pet = self.controller, self.controller.pet
        area = pet.screen_area()
        pet.move(area.left() + 50, area.top() + 100)
        pet.state.position_x = float(pet.x())
        controller.set_preference('speed', 100)
        pet.state.direction = 1
        pet.state.walking = True
        pet.state.next_action = float('inf')
        now = time.monotonic()
        pet.state.last_tick = now - .1
        before = pet.state.position_x
        with patch('pet.time.monotonic', return_value=now):
            pet.animator.tick()
        self.assertAlmostEqual(pet.state.position_x - before, 10, places=4)
        controller.set_preference('paused', True)
        before = pet.pos()
        pet.state.walking = True
        pet.animator.tick()
        self.assertEqual(pet.pos(), before)
        self.assertFalse(pet.state.walking)
        controller.set_preference('paused', False)
        controller.set_preference('random_movement', False)
        pet.state.walking = True
        pet.animator.tick()
        self.assertEqual(pet.pos(), before)
        self.assertFalse(pet.state.walking)

    def test_activity_frequency_changes_behavior(self):
        pet = self.controller.pet
        for activity, expected, interval in (
                ('少动', False, (14, 22)), ('默认', False, (10, 18)), ('活跃', True, (1, 2.5))):
            self.controller.set_preference('activity', activity)
            pet.state.next_action = 0
            with patch('pet.random.random', return_value=.2), \
                    patch('pet.random.uniform', return_value=3) as uniform:
                pet.animator.tick()
            self.assertEqual(pet.state.walking, expected)
            uniform.assert_called_once_with(*interval)

    def test_mouse_click_drag_and_boundaries(self):
        pet = self.controller.pet
        self.controller.set_preference('paused', True)
        QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 110))
        self.assertTrue(pet.click_timer.isActive())
        pet.click_timer.stop()
        pet.click_timer.timeout.emit()
        self.assertEqual(pet.state.action_player.action['id'], 'shy')
        self.assertIsNone(pet.state.jump_started)
        old = pet.pos()
        QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 110))
        QTest.mouseMove(pet, QPoint(45, 75))
        QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(45, 75))
        self.assertNotEqual(pet.pos(), old)
        self.assertIsNone(pet.state.jump_started)
        pet.move(-100000, -100000)
        pet.clamp_to_screen()
        self.assertTrue(pet.screen_area().contains(pet.geometry()))
        self.controller.window.home_button.click()
        for _ in range(200):
            pet.state.last_tick-=.1;pet.animator.tick()
            if pet.state.travel_target is None:break
        self.assertEqual(pet.geometry().bottom(), pet.screen_area().bottom())
        self.controller.save_position()
        self.assertEqual(SettingsStore(self.path).position(), pet.pos())

    def test_real_restart_restores_position_and_preferences(self):
        controller = self.controller
        controller.set_preference('paused', True)
        controller.set_preference('size', 125)
        controller.pet.move(110, 130)
        controller.pet.clamp_to_screen()
        expected = controller.pet.pos()
        controller.cleanup()
        restored = PetApplication(self.app, SettingsStore(self.path), enable_tray=False)
        try:
            restored.start()
            self.assertEqual(restored.pet.pos(), expected)
            self.assertEqual(restored.preferences.size, 125)
            self.assertTrue(restored.preferences.paused)
        finally:
            restored.cleanup()
            restored.window.deleteLater()
            restored.pet.deleteLater()
            restored.deleteLater()

    def test_reset_confirmation_and_safe_close(self):
        controller = self.controller
        controller.set_preference('speed', 120)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            controller.window.confirm_reset()
        self.assertEqual(controller.preferences.speed, 120)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            controller.window.confirm_reset()
        self.assertEqual(controller.preferences, Preferences())
        self.assertEqual(controller.pet.geometry().bottom(), controller.pet.screen_area().bottom())
        controller.tray_available = True
        controller.window.close()
        self.assertFalse(controller.window.isVisible())
        self.assertTrue(controller.pet.isVisible())
        self.assertFalse(controller.shutting_down)
        controller.open_console()
        controller.tray_available = False
        controller.window.close()
        self.assertTrue(controller.window.isMinimized())
        self.assertTrue(controller.pet.isVisible())
        controller.cleanup()
        self.assertFalse(controller.pet.animator.timer.isActive())
        self.assertFalse(controller.save_timer.isActive())
        self.assertFalse(controller.window.isVisible())
        self.assertFalse(controller.pet.isVisible())

    def test_corrupt_settings_and_screen_recovery(self):
        preferences = normalize({'size': 'invalid', 'speed': -10, 'opacity': 0,
                                 'activity': '未知', 'quiet': 'false', 'greeting': 'false'})
        self.assertEqual(preferences.size, 100)
        self.assertEqual(preferences.speed, 10)
        self.assertEqual(preferences.opacity, 30)
        self.assertEqual(preferences.activity, '默认')
        self.assertFalse(preferences.quiet)
        self.assertFalse(preferences.greeting)
        self.controller.pet.move(100000, 100000)
        self.controller.adjust_screen()
        self.assertTrue(self.controller.pet.screen_area().contains(self.controller.pet.geometry()))

    def test_console_layout_snapshot(self):
        window = self.controller.window
        window.resize(620, 900)
        self.app.processEvents()
        folder = Path(__file__).parent / 'qa'
        folder.mkdir(exist_ok=True)
        self.assertTrue(window.grab().save(str(folder / 'console.png')))
        self.assertTrue(self.controller.pet.grab().save(str(folder / 'pet.png')))
        for button in window.findChildren(QPushButton):
            self.assertGreaterEqual(button.width(), button.sizeHint().width())


if __name__ == '__main__':
    unittest.main(verbosity=2)
