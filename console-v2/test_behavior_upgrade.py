"""点击分区、专注、关系记忆、回访问候与窗口停靠的独立验收。"""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from companion_awareness import CompanionAwareness
from companion_memory import CompanionMemory
from focus_companion import FocusCompanion
from pet import DesktopPet, PetRenderer
from settings_model import Preferences, SettingsStore
from window_perch import WindowPerch


class BehaviorUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='xiaoju-behavior-')
        self.store = SettingsStore(Path(self.directory.name) / 'settings.ini')
        self.memory = CompanionMemory(self.store)
        self.pet = DesktopPet(Preferences())
        self.pet.controller = SimpleNamespace(memory=self.memory, quick_pending=None)
        self.pet.show()
        self.pet.animator.timer.stop()
        self.app.processEvents()

    def tearDown(self):
        self.pet.snap_preview.shutdown()
        self.pet.close()
        self.pet.deleteLater()
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()
        self.directory.cleanup()

    def test_click_zones_headpat_and_repeated_jelly(self):
        pet = self.pet
        QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 110))
        self.assertEqual(pet.click_zone, 'body')
        self.assertEqual(pet.state.action_player.action['id'], 'smile')
        QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 30))
        self.assertEqual(pet.click_zone, 'shy')
        self.assertEqual(pet.state.action_player.action['id'], 'shy')
        QTest.mouseClick(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 175))
        self.assertEqual(pet.click_zone, 'feet')
        self.assertEqual(pet.state.action_player.action['id'], 'clicked')

        QTest.mousePress(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 30))
        pet.press_started = time.monotonic() - .5
        QTest.mouseRelease(pet, Qt.MouseButton.LeftButton, pos=QPoint(90, 30))
        self.assertEqual(pet.state.action_player.action['id'], 'affection')
        self.assertEqual(pet.state.click_reaction.kind, 'headpat')
        # Click feedback must not wait for the counter file to reach the disk.
        self.assertEqual(self.memory.snapshot()['headpats'], 0)
        pet.flush_memory()
        self.assertEqual(self.memory.snapshot()['headpats'], 1)

        player = pet.state.action_player
        generation, started = player.generation, pet.state.click_reaction.started
        time.sleep(.02)
        pet.play_click_reaction('headpat')
        self.assertGreater(pet.state.click_reaction.started, started)
        self.assertGreater(player.generation, generation)
        self.assertEqual(pet.state.action_player.action['id'], 'affection')
        pet.flush_memory()
        self.assertEqual(self.memory.snapshot()['headpats'], 2)

    def test_focus_hold_break_click_through_and_memory(self):
        pet, memory = self.pet, self.memory
        base = Preferences(focus_click_through=True)
        pet.apply_preferences(base)
        focus = FocusCompanion(pet, lambda: base, memory)
        now = time.monotonic()
        focus.set(True, 'focus', 600, now=now)
        self.assertTrue(focus.active)
        self.assertTrue(pet.preferences.quiet)
        self.assertFalse(base.quiet)
        self.assertEqual(pet.state.action_player.action['id'], 'sit-neat')
        self.assertIn('专注陪伴', pet.status_text())
        self.assertTrue(pet.windowFlags() & Qt.WindowType.WindowTransparentForInput)

        focus.focus_started = now - 125
        focus.set(True, 'break', 300, now=now)
        self.assertEqual(focus.phase, 'break')
        self.assertEqual(pet.state.action_player.action['id'], 'stretch')
        self.assertIn('专注休息', pet.status_text())
        self.assertFalse(pet.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.assertEqual(memory.snapshot()['focus_minutes'], 2)

        focus.set(False, now=now)
        self.assertFalse(focus.active)
        self.assertFalse(pet.preferences.quiet)

    def test_focus_auto_ends_at_saved_deadline(self):
        pet = self.pet
        focus = FocusCompanion(pet, lambda: Preferences(), self.memory)
        now = time.monotonic()
        focus.set(True, 'focus', 1, now=now)
        focus.last_tick = now - .6
        focus.tick(now + 2)
        self.assertFalse(focus.active)
        self.assertFalse(pet.preferences.quiet)

    def test_click_action_atlases_are_pinned_off_the_click_path(self):
        PetRenderer.prewarm_click_atlas('clicked')
        PetRenderer.action_atlas.cache_clear()
        self.assertIs(PetRenderer.action_atlas('clicked'), PetRenderer.click_atlases['clicked'])

    def test_left_click_skips_activation_but_right_click_keeps_the_menu(self):
        import ctypes
        from pet import _NativeMessage
        pet = self.pet
        self.assertFalse(pet.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
        self.assertTrue(pet._skips_activation((0x0201 << 16) | 1))
        self.assertTrue(pet._skips_activation((0x0203 << 16) | 1))
        self.assertFalse(pet._skips_activation((0x0204 << 16) | 1))

    def test_memory_is_content_free_and_reloads(self):
        stamp = 1_760_000_000
        self.memory.record('clicks', 2, now=stamp)
        self.memory.record('headpats', 1, now=stamp)
        self.memory.record('focus_minutes', 3, now=stamp)
        self.memory.record('greetings', 1, now=stamp)
        loaded = CompanionMemory(self.store)
        snapshot = loaded.snapshot(now=stamp)
        self.assertEqual((snapshot['clicks'], snapshot['headpats'],
                          snapshot['focus_minutes'], snapshot['greetings']), (2, 1, 3, 1))
        raw = json.loads((self.store.directory() / 'companion-memory.json').read_text(encoding='utf-8'))
        self.assertEqual(set(raw), {'version', 'first_seen', 'last_interaction', 'days',
                                    'clicks', 'headpats', 'focus_minutes', 'greetings'})
        for day, counts in raw['days'].items():
            self.assertRegex(day, r'^\d{4}-\d{2}-\d{2}$')
            self.assertEqual(set(counts), {'clicks', 'headpats', 'focus_minutes', 'greetings'})
        paused = CompanionMemory(self.store, enabled=False)
        self.assertFalse(paused.record('clicks', now=stamp))
        self.assertEqual(paused.snapshot(now=stamp)['clicks'], 2)
        paused.set_enabled(True)
        self.assertEqual(paused.snapshot(now=stamp)['clicks'], 2)
        self.assertTrue(loaded.clear(now=stamp))
        cleared = CompanionMemory(self.store).snapshot(now=stamp)
        self.assertEqual((cleared['clicks'], cleared['headpats'],
                          cleared['focus_minutes'], cleared['greetings']), (0, 0, 0, 0))

    def test_return_greeting_is_coalesced_and_respects_preferences(self):
        pet, memory = self.pet, self.memory
        pet.state.action_player.stop()
        awareness = CompanionAwareness(pet, memory, idle=lambda: 0)
        awareness.away = True
        awareness.away_since = 90
        awareness.last_check = 0
        awareness.idle = lambda: 1
        self.assertEqual(awareness.tick(200), 'return')
        self.assertEqual(pet.state.action_player.action['id'], 'wave')
        self.assertEqual(memory.snapshot()['greetings'], 1)

        pet.state.action_player.stop()
        awareness.away = True
        awareness.last_check = 0
        self.assertIsNone(awareness.tick(300))
        self.assertIsNone(pet.state.action_player.action)
        self.assertEqual(memory.snapshot()['greetings'], 1)

        pet.apply_preferences(Preferences(greeting=False))
        awareness.away = True
        awareness.last_greeting = -float('inf')
        awareness.last_check = 0
        self.assertIsNone(awareness.tick(4_000))
        self.assertIsNone(pet.state.action_player.action)
        self.assertEqual(memory.snapshot()['greetings'], 1)

    def test_window_perch_rejects_busy_states_and_leaps_to_foreground_top(self):
        pet = self.pet
        edge = SimpleNamespace(active=False, started=None, message='', poses=SimpleNamespace(bounds=None))
        def attach(candidate, autonomous=False):
            edge.active, edge.started = True, 1
            return True
        edge.attach = attach
        edge.release = lambda cooldown=0: (setattr(edge, 'active', False),
                                           setattr(edge, 'started', None))
        perch = WindowPerch(pet, edge)
        pet.apply_preferences(Preferences(paused=True))
        with self.assertRaises(ValueError):
            perch.manual(time.monotonic())
        pet.apply_preferences(Preferences())
        pet.state.action_player.stop()

        landing = SimpleNamespace(kind='top', anchor=(400, 320), position=(400, 340))
        now = time.monotonic()
        surface = SimpleNamespace(title='hidden', fullscreen=False)
        with patch('window_perch.inspect_foreground', return_value=surface):
            with patch('window_perch.logical_surface',
                       return_value=(QRect(0, 0, 800, 600), pet.screen_area(), pet.screen())):
                with patch('window_perch.candidates', return_value=[(None, landing)]):
                    with patch('window_perch.QCursor', SimpleNamespace(pos=lambda: QPoint(0, 0))):
                        self.assertTrue(perch.manual(now))
                        self.assertTrue(perch.leaping)
                        self.assertEqual(pet.state.action_player.action['id'], 'play-climb-up')
                        perch._advance_leap(now + 1)
        self.assertFalse(perch.leaping)
        self.assertTrue(perch.attached)
        perch.cancel(now + 2)
        self.assertFalse(perch.attached)

    def test_perch_leap_falls_if_the_window_disappears_mid_air(self):
        pet = self.pet
        edge = SimpleNamespace(active=False, started=None, message='', poses=SimpleNamespace(bounds=None))
        edge.attach = lambda candidate, autonomous=False: True
        edge.release = lambda cooldown=0: None
        perch = WindowPerch(pet, edge)
        pet.state.action_player.stop()
        landing = SimpleNamespace(kind='top', anchor=(400, 320), position=(400, 340))
        now = time.monotonic()
        surface = SimpleNamespace(title='target', fullscreen=False, handle=4242)
        with patch('window_perch.inspect_foreground', return_value=surface):
            with patch('window_perch.logical_surface',
                       return_value=(QRect(0, 0, 800, 600), pet.screen_area(), pet.screen())):
                with patch('window_perch.candidates', return_value=[(None, landing)]):
                    with patch('window_perch.QCursor', SimpleNamespace(pos=lambda: QPoint(0, 0))):
                        self.assertTrue(perch.manual(now))
        self.assertTrue(perch.leaping)
        with patch('window_perch.inspect_foreground', return_value=None):
            perch._advance_leap(now + .2)
        self.assertFalse(perch.leaping)
        self.assertFalse(perch.active)
        self.assertTrue(pet.state.physics.active)
        self.assertIsNone(pet.state.action_player.action)

    def test_autonomous_window_perch_releases_when_switch_turns_off(self):
        pet = self.pet
        edge = SimpleNamespace(active=True, started=1, message='', poses=SimpleNamespace(bounds=None))
        released = []
        edge.release = lambda cooldown=0: (released.append(cooldown),
                                           setattr(edge, 'active', False),
                                           setattr(edge, 'started', None))
        perch = WindowPerch(pet, edge)
        perch.attached = True
        perch.attached_started = 1
        perch.active = True
        pet.apply_preferences(Preferences(autonomous_windows=False))
        perch.tick(time.monotonic())
        self.assertFalse(perch.attached)
        self.assertTrue(released)

        perch.attached = True
        perch.manual_attached = True
        perch.attached_started = 2
        edge.active, edge.started = True, 2
        perch.tick(time.monotonic())
        self.assertTrue(perch.attached)
        perch.cancel(time.monotonic())


class ToolStatusTempoTests(unittest.TestCase):
    def test_status_speeds_follow_their_semantics(self):
        from pet_backend import STATUS_PERFORMANCES
        self.assertEqual(STATUS_PERFORMANCES['thinking'][3], .8)
        self.assertEqual(STATUS_PERFORMANCES['working'][3], .95)
        self.assertEqual(STATUS_PERFORMANCES['waiting'][3], .7)
        self.assertEqual(STATUS_PERFORMANCES['done'][3], .7)
        self.assertEqual(STATUS_PERFORMANCES['error'][3], .8)
        self.assertFalse(STATUS_PERFORMANCES['done'][2])


if __name__ == '__main__':
    unittest.main(verbosity=2)
