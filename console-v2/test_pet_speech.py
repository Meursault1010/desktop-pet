"""Bubble lifecycle, paging, quiet mode, menu submission and backend routing."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import time
import unittest
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pet import DesktopPet
from pet_speech import pages
from pet_backend import PetService
from settings_model import SettingsStore


class SpeechTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.pet = DesktopPet()
        self.pet.show()
        self.pet.animator.timer.stop()
        self.bubble = self.pet.bubble
        self.bubble.timer.stop()

    def tearDown(self):
        self.pet.close()
        self.pet.deleteLater()
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()

    def test_pages_preserve_text_and_bound_length(self):
        text = '一段话。'*200
        result = pages(text)
        self.assertEqual(''.join(result), text)
        self.assertTrue(all(0<len(part)<=120 for part in result))

    def test_plain_text_stream_progress_and_readable_pages(self):
        self.bubble.say('<b>你好</b>', streaming=True)
        self.bubble.shown_chars=5
        self.bubble.say('<b>你好</b>。今天好吗？', streaming=True)
        self.assertEqual(self.bubble.shown_chars, 5)
        self.assertEqual(self.bubble.copy.textFormat(), Qt.TextFormat.PlainText)
        self.bubble.say('一'*260)
        self.assertEqual(len(self.bubble.parts),3)
        self.bubble.shown_chars=120
        self.bubble.page_age=20
        self.bubble.tick()
        self.assertEqual(self.bubble.index,1)

    def test_follows_pet_within_screen_and_does_not_capture_pointer(self):
        self.bubble.say('我在这里。')
        self.bubble.tick()
        self.assertTrue(self.bubble.isVisible())
        self.assertTrue(self.pet.screen_area().contains(self.bubble.geometry()))
        self.assertTrue(self.bubble.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.assertTrue(self.bubble.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)

    def test_quiet_suppresses_monologue_but_allows_chat(self):
        self.pet.apply_preferences(replace(self.pet.preferences, quiet=True))
        self.bubble.say('自言自语', 'ambient');self.bubble.tick()
        self.assertFalse(self.bubble.parts)
        self.bubble.say('聊天回复', 'chat');self.bubble.tick()
        self.assertTrue(self.bubble.isVisible())

    def test_drag_flight_presence_and_hidden_suspend_bubble(self):
        self.bubble.say('你好');self.bubble.tick()
        self.pet.start_throw((300,-200));self.bubble.tick()
        self.assertFalse(self.bubble.isVisible())
        self.pet.state.physics.cancel()
        self.pet.present(False);self.bubble.tick()
        self.assertFalse(self.bubble.isVisible())
        self.pet.hide();self.bubble.tick()
        self.assertFalse(self.bubble.isVisible())

    def test_monologue_is_low_frequency_and_chat_has_priority(self):
        self.bubble.next_ambient=0
        self.bubble.tick()
        self.assertEqual(self.bubble.kind,'ambient')
        self.assertGreater(self.bubble.next_ambient,time.monotonic()+80)
        self.bubble.say('与你聊天',streaming=True)
        self.bubble.next_ambient=0;self.bubble.tick()
        self.assertEqual(self.bubble.text,'与你聊天')


class QuickInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_popup_accepts_chinese_ime_composition_before_sending(self):
        from PySide6.QtGui import QInputMethodEvent
        with tempfile.TemporaryDirectory() as folder:
            service = PetService(self.app, SettingsStore(Path(folder)/'settings.ini'))
            menu = service.create_menu(service.pet)
            try:
                menu.popup(service.pet.pos())
                self.app.processEvents()
                edit = menu.chat_input
                self.assertTrue(menu.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled))
                self.assertTrue(edit.hasFocus())
                self.app.sendEvent(edit, QInputMethodEvent('ni hao', []))
                self.assertEqual(edit.text(), '')
                self.assertIsNone(service.quick_pending)
                commit = QInputMethodEvent()
                commit.setCommitString('你好，雪')
                self.app.sendEvent(edit, commit)
                self.assertEqual(edit.text(), '你好，雪')
                self.assertEqual(service.quick_draft, '你好，雪')
                self.assertIsNone(service.quick_pending)
            finally:
                menu.close()
                menu.deleteLater(); service.cleanup(); service.pet.deleteLater(); service.deleteLater()
                self.app.sendPostedEvents(None, 0); self.app.processEvents()

    def test_enter_routes_native_input_and_matching_response_unlocks(self):
        events=[]
        class RecordingService(PetService):
            @staticmethod
            def send(message): events.append(message)
        with tempfile.TemporaryDirectory() as folder:
            service=RecordingService(self.app, SettingsStore(Path(folder)/'settings.ini'))
            menu=service.create_menu(service.pet)
            try:
                service.pet.show()
                menu.chat_input.setText('今天好吗？')
                menu.popup(service.pet.pos())
                menu.chat_input.setFocus()
                QTest.keyClick(menu.chat_input, Qt.Key.Key_Return)
                event=next(e for e in events if e.get('name')=='quick_chat')
                self.assertEqual(event['text'],'今天好吗？')
                self.assertEqual(service.quick_pending,event['id'])
                self.assertFalse(service.quick_chat_send('再发一次'))
                service.speech_update({'id':'wrong','phase':'done','text':'旧回复'})
                self.assertEqual(service.quick_pending,event['id'])
                service.speech_update({'id':event['id'],'phase':'done','text':'今天想喝茶。'})
                self.assertIsNone(service.quick_pending)
                self.assertEqual(service.pet.bubble.text,'今天想喝茶。')
                self.assertEqual(menu.chat_input.text(),'')
                self.assertEqual(menu.actions()[-1].objectName(),'exit')
                self.assertTrue(service.quick_chat_send('这句话保留以便重试'))
                service.speech_update({'id':service.quick_pending,'phase':'error','text':'本地服务离线'})
                self.assertEqual(service.quick_draft,'这句话保留以便重试')
                self.assertIsNone(service.quick_pending)
                with self.assertRaises(ValueError):
                    service.speech_update({'id':'bad','phase':'done','text':'x'*6001})
            finally:
                menu.deleteLater();service.cleanup();service.pet.deleteLater();service.deleteLater()
                self.app.sendPostedEvents(None,0);self.app.processEvents()


if __name__ == '__main__': unittest.main()
