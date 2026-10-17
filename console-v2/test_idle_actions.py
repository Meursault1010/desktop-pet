import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import json
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter
from pet import DesktopPet
from settings_model import Preferences
from action_player import catalog
from idle_actions import IdleActions, IDLE_ACTIONS


class AmbientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bag_covers_all_existing_daily_actions(self):
        scheduler = IdleActions()
        self.assertTrue(set(IDLE_ACTIONS).issubset(catalog()))
        self.assertEqual({scheduler.choose(catalog()) for _ in IDLE_ACTIONS}, set(IDLE_ACTIONS))

    def test_only_lazy_rolls_remain(self):
        root = Path(__file__).resolve().parent
        public = json.loads((root/'frontend/public/actions/catalog.json').read_text(encoding='utf-8'))
        expected = {'lazy-roll-toward', 'lazy-roll-away'}
        self.assertEqual({key for key in catalog() if 'roll' in key}, expected)
        self.assertEqual({a['id'] for a in public if 'roll' in a['id']}, expected)
        for folder in ('assets/actions', 'frontend/public/actions'):
            self.assertFalse(list((root/folder).glob('roll-*')))

    def test_ground_assets_and_web_catalog_match(self):
        root = Path(__file__).resolve().parent
        public = {a['id']: a for a in json.loads((root/'frontend/public/actions/catalog.json').read_text(encoding='utf-8'))}
        for key in ('lazy-roll-toward', 'lazy-roll-away', 'sit-neat', 'sit-relaxed', 'sit-swing', 'prone-chin', 'prone-rest'):
            action = catalog()[key]
            self.assertEqual(action, public[key])
            self.assertEqual(action['frames'], len(action['durations']))
            image = QImage(str(root/'assets'/action['atlas']))
            self.assertEqual(image.width(), 1024)
            self.assertGreaterEqual(image.height(), ((action['frames']+3)//4)*256)
            self.assertEqual((root/'assets'/action['atlas']).read_bytes(),
                             (root/'frontend/public'/action['atlas']).read_bytes())
            if action.get('ground_idle'):
                self.assertGreater(sum(action['durations'][3:-3]), 10000)

    def test_lazy_roll_assets_close_exactly_with_full_colour_and_soft_alpha(self):
        root=Path(__file__).resolve().parent
        self.assertNotIn('roll-front',IDLE_ACTIONS)
        for key in ('lazy-roll-toward','lazy-roll-away'):
            self.assertIn(key,IDLE_ACTIONS)
            action=catalog()[key]
            self.assertFalse(action['pixel_art'])
            self.assertEqual(action['frames'],12)
            self.assertEqual((root/'assets/actions'/key/'01.png').read_bytes(),
                             (root/'assets/actions'/key/'12.png').read_bytes())
            atlas=QImage(str(root/'assets'/action['atlas']))
            self.assertEqual(atlas.size().width(),1024)
            self.assertEqual(atlas.size().height(),768)
            colours=set()
            soft_edge=False
            for y in range(256):
                for x in range(256):
                    colour=atlas.pixelColor(x,y)
                    if colour.alpha()>0:colours.add(colour.rgba())
                    if 0<colour.alpha()<255:soft_edge=True
            self.assertGreater(len(colours),48)
            self.assertTrue(soft_edge)

    def test_lazy_roll_finishes_in_rest_and_can_be_interrupted(self):
        pet=self.make_pet()
        pet.state.ambient.next_at=0
        with patch.object(pet.state.ambient,'choose',return_value='lazy-roll-toward'):
            pet.animator.update_ambient(100)
        player=pet.state.action_player
        duration=sum(player.action['durations'])/1000
        self.assertAlmostEqual(pet.state.ambient.current[3],duration)
        self.assertFalse(pet.movement_allowed())
        player.frame(100+duration+.01)
        pet.animator.update_ambient(100+duration+.01)
        self.assertEqual(player.action['id'],'prone-rest')
        self.assertGreaterEqual(player.frame(100+duration+.01),3)
        pet.preferences=replace(pet.preferences,paused=True)
        pet.animator.update_ambient(101+duration)
        self.assertIsNone(player.action)
        self.assertIsNone(pet.state.ambient.current)

    def make_pet(self):
        pet = DesktopPet(Preferences())
        pet.show()
        pet.animator.timer.stop()
        self.addCleanup(self.dispose_pet, pet)
        return pet

    def dispose_pet(self, pet):
        pet.close()
        pet.deleteLater()
        self.app.sendPostedEvents(None, 0)
        self.app.processEvents()

    def test_interrupted_roll_does_not_spawn_a_seated_action(self):
        for interrupt in ('manual', 'pause', 'drag'):
            pet = self.make_pet()
            player = pet.state.action_player
            player.play('lazy-roll-away', now=100)
            duration = sum(player.action['durations'])/1000
            pet.state.ambient.current = ('lazy-roll-away', 100, float(pet.x()), duration)
            if interrupt == 'manual':
                player.play('read', now=101)
            elif interrupt == 'pause':
                pet.preferences = replace(pet.preferences, paused=True)
            else:
                pet.drag_origin = (0, 0)
            pet.animator.update_ambient(102)
            self.assertIsNone(pet.state.ambient.current)
            self.assertEqual(player.action['id'] if player.action else None,
                             'read' if interrupt == 'manual' else None)

    def test_removed_action_and_transition_lifecycle(self):
        self.assertNotIn('folder-sleep', catalog())
        pet = DesktopPet(Preferences())
        pet.animator.timer.stop()
        canvas = QImage(180, 190, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(canvas)
        try:
            pet.renderer.draw(painter, pet.state)
            pet.state.action_player.play('tea')
            pet.renderer.draw(painter, pet.state)
            self.assertIsNotNone(pet.renderer.transition_image)
            pet.renderer.transition_started -= 1
            pet.renderer.draw(painter, pet.state)
            self.assertIsNone(pet.renderer.transition_image)
            pet.state.action_player.stop()
            pet.renderer.draw(painter, pet.state)
            self.assertIsNotNone(pet.renderer.transition_image)
        finally:
            painter.end()
            self.dispose_pet(pet)

    def test_idle_manual_drag_and_pause_priority(self):
        pet = DesktopPet(Preferences())
        pet.show()
        pet.animator.timer.stop()
        try:
            pet.state.ambient.next_at = 0
            with patch.object(pet.state.ambient, 'choose', return_value='tea'):
                pet.animator.update_ambient(100)
            self.assertEqual(pet.state.action_player.action['id'], 'tea')
            pet.state.action_player.play('read', now=101)
            pet.animator.update_ambient(102)
            self.assertEqual(pet.state.action_player.action['id'], 'read')
            pet.state.action_player.stop()
            pet.state.ambient.next_at = 0
            pet.preferences = replace(pet.preferences, paused=True)
            pet.animator.update_ambient(103)
            self.assertIsNone(pet.state.action_player.action)
        finally:
            self.dispose_pet(pet)


if __name__ == '__main__':
    unittest.main()
