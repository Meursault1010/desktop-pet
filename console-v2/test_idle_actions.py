import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
import json
import random
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
import numpy as np
from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QPixmap
from pet import DesktopPet
from settings_model import Preferences
from action_player import ActionPlayer, catalog
from action_life_motion import ActionLifeMotion
from idle_actions import IdleActions, IDLE_ACTIONS
from idle_animation import MOTION_SECONDS
from daily_routine import schedule
from types import SimpleNamespace


class AmbientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bag_covers_all_existing_daily_actions(self):
        scheduler = IdleActions()
        self.assertTrue(set(IDLE_ACTIONS).issubset(catalog()))
        self.assertEqual({scheduler.choose(catalog()) for _ in IDLE_ACTIONS}, set(IDLE_ACTIONS))

    def test_reading_stays_like_an_idle_instead_of_a_short_gesture(self):
        player = ActionPlayer()
        with patch('action_player.random', random.Random(4)):
            duration = IdleActions().play(player, 'read', 100)
        self.assertGreaterEqual(duration, 17)
        self.assertLessEqual(duration, 40)
        self.assertEqual(player.action['id'], 'read')
        self.assertIsNotNone(player.frame(100+duration*.5))
        self.assertIsNone(player.frame(100+duration+.01))
        self.assertTrue(catalog()['read'].get('reading_idle'))
        self.assertGreater(catalog()['read']['idle_life']['bob'], 0)

    def test_reading_breathing_keeps_the_book_and_feet_in_place(self):
        root = Path(__file__).resolve().parent
        action = catalog()['read']
        atlas = QPixmap(str(root/'assets'/action['atlas']))
        motion = ActionLifeMotion()
        centroids, floors = [], []
        for elapsed in (.4, 1.35, 2.3):
            source = QRect((5 % action['columns'])*256, (5 // action['columns'])*256, 256, 256)
            image = motion.render(atlas, source, 'read', elapsed, 256, **action['idle_life'])
            image = image.convertToFormat(QImage.Format.Format_RGBA8888)
            alpha = np.frombuffer(bytes(image.constBits()), dtype=np.uint8).reshape(256, 256, 4)[:, :, 3]
            rows = np.flatnonzero(alpha.max(axis=1) > 32)
            floors.append(int(rows[-1]))
            band = alpha[max(0, rows[-1]-12):rows[-1]+1]
            centroids.append(float(np.flatnonzero(band.any(axis=0)).mean()))
        self.assertEqual(len(set(floors)), 1)
        self.assertLess(max(centroids)-min(centroids), 1.5)

    def test_held_reading_poses_breathe_like_the_base_idle(self):
        root = Path(__file__).resolve().parent
        motion = ActionLifeMotion()
        for key in ('reading-pose-1', 'reading-pose-2', 'reading-pose-3'):
            action = catalog()[key]
            life = action['idle_life']
            self.assertGreater(life['bob'], 0, key)
            self.assertGreater(life['lean'], 0, key)
            self.assertEqual(life['period'], MOTION_SECONDS, key)
            atlas = QPixmap(str(root/'assets'/action['atlas']))
            shots = []
            for elapsed in (.0, life['period']*.25, life['period']*.5, life['period']*.75):
                image = motion.render(atlas, QRect(0, 0, 256, 256), key, elapsed, 256, **life)
                image = image.convertToFormat(QImage.Format.Format_RGBA8888)
                shots.append(np.frombuffer(bytes(image.constBits()), dtype=np.uint8).reshape(256, 256, 4))
            alpha = shots[0][:, :, 3]
            rows = np.flatnonzero(alpha.max(axis=1) > 32)
            heads = [int(np.flatnonzero((shot[:, :, 3] > 200).max(axis=1))[0]) for shot in shots]
            floors = [int(np.flatnonzero((shot[:, :, 3] > 32).max(axis=1))[-1]) for shot in shots]
            self.assertEqual(len(set(floors)), 1, key)
            # The head lifts a couple of pixels and comes back; anything that
            # moves the whole figure reads as floating rather than breathing.
            self.assertGreaterEqual(max(heads)-min(heads), 2, key)
            self.assertLessEqual(max(heads)-min(heads), 4, key)
            waist = rows[0] + int((rows[-1]-rows[0])*.74)
            for shot in shots[1:]:
                moved = np.abs(shot[waist:].astype(int) - shots[0][waist:].astype(int)).max(axis=2)
                self.assertLess(int((moved > 4).sum()), 24, key)

    def test_period_favourites_do_not_crowd_out_other_actions(self):
        for period in schedule():
            scheduler = IdleActions()
            scheduler.set_period(period)
            expected = (set(period.get('only', IDLE_ACTIONS)) | set(period['preferred'])) & set(IDLE_ACTIONS)
            choices = [scheduler.choose(catalog()) for _ in expected]
            self.assertEqual(set(choices), expected)
            self.assertEqual(len(choices), len(set(choices)))

    def test_time_of_day_preference_moves_favourites_earlier(self):
        scheduler = IdleActions()
        period = schedule()[2]
        scheduler.set_period(period)
        with patch('idle_actions.random.random', return_value=.5):
            first = scheduler.choose(catalog())
        self.assertIn(first, period['preferred'])

    def test_blocked_ticks_do_not_keep_rescheduling_and_resume_is_prompt(self):
        pet = self.make_pet()
        state = pet.state
        state.routine.period = schedule()[2]
        state.ambient.set_period(state.routine.period)
        state.patrol = SimpleNamespace(active=True, exploring=False, cancel=lambda *args, **kwargs: None)
        with patch.object(state.routine, 'update', return_value=False):
            pet.animator.update_ambient(100)
            deadline = state.ambient.next_at
            for now in range(101, 161):
                pet.animator.update_ambient(now)
                self.assertEqual(state.ambient.next_at, deadline)
            state.patrol.active = False
            pet.animator.update_ambient(161)
            self.assertTrue(164 <= state.ambient.next_at <= 167)
            self.assertIsNone(state.action_player.action)
            with patch.object(state.ambient, 'choose', return_value='tea'):
                pet.animator.update_ambient(168)
            self.assertEqual(state.action_player.action['id'], 'tea')
        state.patrol = None

    def test_new_standing_vignettes_are_complete_automatic_actions(self):
        root = Path(__file__).resolve().parent
        public = {a['id']: a for a in json.loads((root/'frontend/public/actions/catalog.json').read_text(encoding='utf-8'))}
        vignettes = {'hum', 'hair-tuck', 'sneeze', 'gaze-far', 'listen',
                     'warm-hands', 'curtsy', 'wave', 'star-wish'}
        for key in vignettes:
            action = catalog()[key]
            self.assertIn(key, IDLE_ACTIONS)
            self.assertEqual(action['idle_state'], 'stand')
            self.assertTrue(action['idle_automatic'])
            self.assertTrue(action['scale_calibrated'])
            self.assertFalse(action.get('ground_idle'))
            self.assertTrue(action.get('smoothed'), key)
            self.assertGreater(action['frames'], action['keyframes'], key)
            self.assertTrue(2200 <= sum(action['durations']) <= 3200, key)
            self.assertEqual(public[key]['idle_role'], action['idle_role'])
            with Image.open(root/'assets'/action['atlas']) as atlas:
                for index in range(action['frames']):
                    x, y = index%action['columns']*256, index//action['columns']*256
                    box = atlas.crop((x, y, x+256, y+256)).getchannel('A')\
                        .point(lambda value: 255 if value >= 16 else 0).getbbox()
                    self.assertIsNotNone(box)
                    self.assertTrue(box[0] >= 1 and box[1] >= 1 and box[2] <= 255 and box[3] <= 255, (key, index))
                    if index == 0:
                        self.assertLessEqual(abs((box[3]-box[1])-227), 3, key)
                        self.assertTrue(245 <= box[3] <= 253, key)
            with Image.open(root/'assets'/action['atlas']) as atlas, \
                    Image.open(root/'frontend/public'/public[key]['atlas']) as mirror:
                self.assertEqual(atlas.size, mirror.size)
                self.assertEqual(atlas.convert('RGBA').tobytes(), mirror.convert('RGBA').tobytes())

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
            self.assertEqual({**action, 'atlas': action['atlas'].removesuffix('.png') + '.webp',
                              'poster': action['poster'].removesuffix('.png') + '.webp'}, public[key])
            self.assertEqual(action['frames'], len(action['durations']))
            image = QImage(str(root/'assets'/action['atlas']))
            self.assertEqual(image.width(), 1024)
            self.assertGreaterEqual(image.height(), ((action['frames']+3)//4)*256)
            with Image.open(root/'assets'/action['atlas']) as source, \
                    Image.open(root/'frontend/public'/public[key]['atlas']) as mirror:
                self.assertEqual(source.size, mirror.size)
                self.assertEqual(source.convert('RGBA').tobytes(), mirror.convert('RGBA').tobytes())
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

    def test_lazy_roll_moves_across_axis_and_finishes_at_its_target(self):
        pet = self.make_pet()
        pet.move(100,200)
        player = pet.state.action_player
        player.play('lazy-roll-toward', now=100)
        total = sum(player.action['durations'])/1000
        origin_x,origin_y = pet.x(),pet.y()
        self.assertTrue(pet.animator.advance_roll(100))
        target = pet.state.roll_path[3]
        self.assertLess(target,origin_y-40)
        self.assertTrue(pet.animator.advance_roll(100+total*.65))
        self.assertLess(pet.y(),origin_y-20)
        self.assertEqual(pet.x(),origin_x)
        player.frame(100+total+1)
        self.assertFalse(pet.animator.advance_roll(100+total+1))
        self.assertEqual(pet.y(),round(target))
        self.assertIsNone(pet.state.roll_path)

    def test_front_and_reverse_roll_travel_in_opposite_directions(self):
        for key,direction in (('lazy-roll-toward',-1),('lazy-roll-away',1)):
            pet=self.make_pet()
            pet.move(300,200)
            pet.state.action_player.play(key,now=100)
            pet.animator.advance_roll(100)
            target=pet.state.roll_path[3]
            self.assertGreater((target-pet.y())*direction,40)
            self.assertEqual(pet.x(),300)

    def test_roll_window_holds_during_side_lying_frames(self):
        for key, stationary in (('lazy-roll-toward', (0, 8, 9, 10, 11)),
                                ('lazy-roll-away', (0, 1, 2, 10, 11))):
            pet = self.make_pet()
            pet.move(300, 200)
            player = pet.state.action_player
            player.play(key, now=100)
            elapsed = 0
            moving_slots = 0
            for frame, duration in zip(player.frame_order, player.action['durations']):
                positions = []
                for fraction in (.05, .5, .95):
                    pet.animator.advance_roll(100+(elapsed+duration*fraction)/1000)
                    positions.append((pet.x(), pet.y()))
                if frame >= 12 or frame in stationary:
                    self.assertEqual(len(set(positions)), 1, (key, frame, positions))
                elif len(set(positions)) > 1:
                    moving_slots += 1
                elapsed += duration
            self.assertGreater(moving_slots, 4)

    def test_roll_near_edge_never_reverses_its_bound_direction(self):
        for key,direction in (('lazy-roll-toward',-1),('lazy-roll-away',1)):
            pet=self.make_pet()
            area=pet.screen_area()
            boundary=area.top() if direction < 0 else area.bottom()-pet.height()+1
            for room in (0, 12):
                origin=boundary-direction*room
                pet.move(300,origin)
                pet.state.roll_path=None
                pet.state.action_player.play(key,now=100)
                pet.animator.advance_roll(100)
                target=pet.state.roll_path[3]
                self.assertGreaterEqual((target-origin)*direction,0)
                self.assertLessEqual(abs(target-origin),room)

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
            # Dissimilar poses must show one opaque character, never a long
            # dissolve. Same-orientation swaps may settle for at most 120 ms.
            self.assertLessEqual(pet.renderer.transition_duration,.12)
            pet.renderer.transition_started -= 1
            pet.renderer.draw(painter, pet.state)
            self.assertIsNone(pet.renderer.transition_image)
            pet.state.action_player.stop()
            pet.renderer.draw(painter, pet.state)
            self.assertLessEqual(pet.renderer.transition_duration,.12)
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
