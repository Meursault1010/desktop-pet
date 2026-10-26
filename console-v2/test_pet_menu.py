"""Menu actions must use the existing controller and Electron lifecycle."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import json
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

    def test_compact_menu_exposes_only_authorized_commands(self):
        self.assertEqual(set(self.actions), {'translation', 'demo_climb', 'console', 'exit'})
        self.assertEqual(self.menu.width(), 328)
        self.assertEqual(self.menu.actions()[-1].objectName(), 'exit')
        self.controller.update_menu(self.menu)
        self.assertEqual(self.menu.status.text(), self.controller.pet.status_text())
        self.assertTrue(self.menu.chat_input.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled))
        for theme in ('light', 'mist', 'dark'):
            self.menu.apply_theme(theme)
            self.assertFalse(self.menu.grab().isNull())

    def test_demo_climb_entry_starts_visible_exploration(self):
        self.actions['demo_climb'].trigger()
        self.assertTrue(self.controller.patrol.demo)
        self.assertTrue(self.controller.patrol.exploring)

    def test_keyboard_escape_and_inline_reply(self):
        self.controller.quick_reply = '雪在这里。'
        self.controller.update_menu(self.menu)
        self.assertEqual(self.menu.chat_reply.toPlainText(), 'yuki\n雪在这里。')
        self.menu.popup(self.controller.pet.pos())
        self.app.processEvents()
        QTest.keyClick(self.menu, Qt.Key.Key_Escape)
        self.assertFalse(self.menu.isVisible())

    def test_history_scroll_and_literal_markup(self):
        self.controller.quick_history = [{'role':'user','text':'问题'}, {'role':'assistant','text':'<b>原文</b>\n'+'长回复。'*800}]
        self.controller.update_menu(self.menu)
        self.menu.popup(self.controller.pet.pos())
        self.app.processEvents()
        self.assertIn('<b>原文</b>',self.menu.chat_reply.toPlainText())
        self.assertIn('长回复。'*800,self.menu.chat_reply.toPlainText())
        scroll=self.menu.chat_reply.verticalScrollBar()
        self.assertGreater(scroll.maximum(),0)
        scroll.setValue(0)
        self.controller.quick_history.append({'role':'assistant','text':'新回复'})
        self.controller.update_menu(self.menu)
        self.assertEqual(scroll.value(),0)
        self.assertEqual(self.menu.composer.height(),300)

    def test_native_tools_use_shared_controller(self):
        sent=[]
        # Connect signal directly to inspect the action contract without external services.
        pane=self.menu.tool_panes[2]
        pane.request.connect(lambda name,value:sent.append((name,value)))
        state={'ready':True,'clipboard':[],'clipboardPaused':False,'todos':[{'id':'t1','text':'写总结','due':''}], 'todoCount':1,'focus':None,'error':''}
        self.controller.quick_tools=state
        pane.refresh(state)
        pane.entry.setText('休息一下')
        pane.due.setCurrentIndex(1)
        pane.add_todo()
        self.assertEqual(sent[-1],('todo-add',{'text':'休息一下','minutes':30}))
        pane.items.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(sent[-1],('todo-done','t1'))
        pane.refresh({**state,'todos':[],'todoCount':0})
        self.assertFalse(pane.empty.isHidden())

    def test_short_menu_scrolls_tools_and_recovers_height(self):
        self.menu.fit_available_height(440)
        self.menu.tabs.setCurrentIndex(3)
        self.menu.show()
        self.app.processEvents()
        self.menu.fit_available_height(440)
        self.app.processEvents()
        area=self.menu.pages.widget(3)
        self.assertGreater(area.verticalScrollBar().maximum(),0)
        area.verticalScrollBar().setValue(area.verticalScrollBar().maximum())
        self.assertGreater(area.verticalScrollBar().value(),0)
        self.menu.fit_available_height(900)
        self.assertEqual(self.menu.composer.height(),300)

    def test_focus_is_temporary_and_preserves_saved_preferences(self):
        service = PetService(self.app, self.controller.store)
        try:
            before = service.preferences.quiet
            service.receive(json.dumps({'id':'focus-1','name':'set_focus','payload':{'enabled':True}}))
            self.assertTrue(service.pet.preferences.quiet)
            self.assertEqual(service.preferences.quiet, before)
            self.assertEqual(service.store.load().quiet, before)
            service.set_preference('size', 100)
            self.assertTrue(service.pet.preferences.quiet)
            service.receive(json.dumps({'id':'focus-2','name':'set_focus','payload':{'enabled':False}}))
            self.assertEqual(service.pet.preferences.quiet, before)
        finally:
            service.cleanup()
            service.pet.deleteLater()
            service.deleteLater()

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
