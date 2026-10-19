"""Menu actions must use the existing controller and Electron lifecycle."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from main import PetApplication
from pet_backend import PetService
from settings_model import SettingsStore


class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='yuki-menu-')
        self.controller = PetApplication(self.app, SettingsStore(Path(self.directory.name)/'settings.ini'),
                                         enable_tray=False, create_console=False)
        self.controller.pet.show()
        self.controller.pet.animator.timer.stop()
        self.menu = self.controller.create_menu(self.controller.pet)
        self.actions = {a.objectName(): a for a in self.menu.actions() if a.objectName()}

    def tearDown(self):
        self.menu.close()
        self.menu.deleteLater()
        self.controller.cleanup()
        self.controller.pet.deleteLater()
        self.controller.deleteLater()
        self.app.processEvents()
        self.directory.cleanup()

    def test_shared_settings_and_visibility_refresh(self):
        self.assertNotIn('jump', self.actions)
        self.assertEqual(self.menu.actions()[-1].objectName(), 'exit')
        for key in ('quiet', 'auto_snap'):
            before = getattr(self.controller.preferences, key)
            self.actions[key].trigger()
            self.assertEqual(getattr(self.controller.preferences, key), not before)
            self.assertEqual(getattr(self.controller.store.load(), key), not before)
        self.controller.update_menu(self.menu)
        self.assertFalse(self.actions['pause'].isEnabled())
        self.actions['visibility'].trigger()
        self.controller.update_menu(self.menu)
        self.assertEqual(self.actions['visibility'].text(), '显示宠物')
        self.assertFalse(self.actions['home'].isEnabled())
        self.assertEqual(self.menu.status.text(), self.controller.pet.status_text())

    def test_keyboard_select_and_escape(self):
        self.menu.popup(self.controller.pet.pos())
        self.app.processEvents()
        self.menu.setActiveAction(self.actions['auto_snap'])
        before = self.controller.preferences.auto_snap
        QTest.keyClick(self.menu, Qt.Key.Key_Return)
        self.assertEqual(self.controller.preferences.auto_snap, not before)
        self.menu.popup(self.controller.pet.pos())
        QTest.keyClick(self.menu, Qt.Key.Key_Escape)
        self.assertFalse(self.menu.isVisible())

    def test_stars_are_mouse_transparent_and_stop_when_closed(self):
        header = self.menu.celestial_header
        self.assertTrue(header.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        self.assertEqual(header.focusPolicy(), Qt.FocusPolicy.NoFocus)
        self.menu.popup(self.controller.pet.pos())
        self.app.processEvents()
        header.reveal.start()
        self.assertFalse(header.grab().isNull())
        self.menu.close()
        self.app.processEvents()
        self.assertEqual(header.reveal.state(), header.reveal.State.Stopped)

    def test_electron_exit_stays_routed_to_host(self):
        events = []

        class RecordingService(PetService):
            @staticmethod
            def send(message):
                events.append(message)

        service = RecordingService(self.app, self.controller.store)
        try:
            menu = service.create_menu(service.pet)
            menu.actions()[-1].trigger()
            self.assertEqual(events[-1], {'type': 'event', 'name': 'exit_app'})
            self.assertFalse(service.shutting_down)
            menu.deleteLater()
        finally:
            service.cleanup()
            service.pet.deleteLater()
            service.deleteLater()


if __name__ == '__main__':
    unittest.main()
