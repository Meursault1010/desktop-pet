"""Continuous up/down walk rig, route selection and draw integration."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
import unittest

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

import vertical_walk_rig as v
from locomotion import vertical_walk, walk_stride, walking_name, gait_advance, walking_speed
from pet import DesktopPet
from settings_model import Preferences


class VerticalWalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_assets_are_full_canvases_split_at_the_sock_top(self):
        data, bodies, legs = v.rig()
        for key in ('up', 'down'):
            spec = data[key]
            body = bodies[key]
            self.assertEqual((body.width(), body.height()), (256, 256))
            self.assertGreater(body.toImage().pixelColor(128, 80).alpha(), 0)
            cut = int(spec['cut_y'])
            for x in range(0, 256, 4):
                self.assertEqual(body.toImage().pixelColor(x, min(255, cut + 4)).alpha(), 0)
            for index, leg in enumerate(legs[key]):
                self.assertEqual((leg.width(), leg.height()), (256, 256))
                image = leg.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                top = min(y for y in range(256)
                          if any(image.pixelColor(x, y).alpha() for x in range(256)))
                self.assertGreaterEqual(top, cut - 1)
                self.assertLess(top, 250)
                self.assertAlmostEqual(spec['pivots'][index][1], cut, delta=1)

    def test_only_down_dominant_travel_uses_the_front_back_rigs(self):
        self.assertEqual(walking_name(1, (0., -1.)), 'walk-up')
        self.assertEqual(walking_name(-1, (0., 1.)), 'walk-down')
        self.assertEqual(walking_name(1, (.2, -.9)), 'walk-up')
        self.assertEqual(walking_name(1, (1., 0.)), 'walk-right')
        self.assertEqual(walking_name(-1, (1., 0.)), 'walk-left')
        self.assertEqual(walking_name(1, (.8, -.6)), 'walk-right')
        self.assertTrue(vertical_walk('walk-up'))
        self.assertFalse(vertical_walk('walk-right'))
        self.assertEqual(walk_stride('walk-up'), 48.)

    def test_gait_is_continuous_and_keeps_one_foot_planted(self):
        for name in v.NAMES:
            stride = walk_stride(name)
            data = v.rig()[0][v.direction(name)]
            for phase in (0., .5, 1.):
                a = v.sample(name, (phase - 1e-6) * stride)
                b = v.sample(name, (phase + 1e-6) * stride)
                for before, after in zip(a[0], b[0]):
                    self.assertLess(max(abs(x - y) for x, y in zip(before, after)), .01)
                self.assertLess(abs(a[1] - b[1]), .001)
                self.assertLess(abs(a[2] - b[2]), .001)
                self.assertLess(abs(a[3] - b[3]), .001)
            for tick in range(240):
                moves, _, _, _, soles = v.sample(name, tick / 240 * stride)
                self.assertTrue(any(move[3] == 0. for move in moves))
                for index, (_, dx, dy, lift) in enumerate(moves):
                    if lift == 0:
                        self.assertEqual(dx, 0.)
                        self.assertLessEqual(abs(dy), v.FOOT_TRAVEL + 1e-6)
                        self.assertLessEqual(abs(soles[index][1] - data['baseline']),
                                             v.FOOT_TRAVEL + 1e-6)
                if tick in (60, 180):
                    planted = [i for i, move in enumerate(moves) if move[3] == 0][0]
                    self.assertAlmostEqual(moves[planted][2], 0., places=6)
                    lifted = [i for i, move in enumerate(moves) if move[3] > 0][0]
                    self.assertLess(soles[lifted][1], data['baseline'] - 10)
                    side = -1. if lifted == 0 else 1.
                    self.assertGreater(side * moves[lifted][1], .4)

    def test_translation_follows_the_swing_leg(self):
        base = walking_speed(60) * .05
        for name in v.NAMES:
            stride = walk_stride(name)
            slow = gait_advance(0., name, 60, .05, 1.)[0]
            mid = gait_advance(stride * .25, name, 60, .05, 1.)[0]
            self.assertLess(slow, base * .85)
            self.assertGreater(mid, base * 1.15)
            # The step rhythm keeps the authored average walking speed.
            total = sum(gait_advance(stride * i / 240, name, 60, .05, 1.)[0]
                        for i in range(240))
            self.assertAlmostEqual(total / 240, base, delta=base * .02)
        right = gait_advance(0., 'walk-right', 60, .05, 1.)[0]
        right_quarter = gait_advance(walk_stride('walk-right') * .25,
                                     'walk-right', 60, .05, 1.)[0]
        self.assertAlmostEqual(right, right_quarter)

    def test_stance_foot_moves_back_while_swing_foot_returns_front(self):
        for name in v.NAMES:
            sign = 1. if v.direction(name) == 'up' else -1.
            stride = walk_stride(name)
            start = v.sample(name, 0.)[0]
            half = v.sample(name, stride * .5)[0]
            # Stance starts in front (-A) and ends behind (+A); the other foot
            # hands over at the opposite end of the stride.
            self.assertAlmostEqual(start[0][2], -v.FOOT_TRAVEL * sign, places=6)
            self.assertAlmostEqual(half[0][2], v.FOOT_TRAVEL * sign, places=6)
            self.assertAlmostEqual(half[1][2], -v.FOOT_TRAVEL * sign, places=6)
            self.assertAlmostEqual(v.sample(name, stride * .25)[0][0][2], 0., places=6)

    def test_center_of_gravity_follows_the_planted_foot(self):
        for name in v.NAMES:
            data = v.rig()[0][v.direction(name)]
            feet = data['feet']
            center = sum(feet) / len(feet)
            for phase in (.25, .75):
                moves, _, sway, roll, soles = v.sample(name, phase * 48)
                planted = next(index for index, move in enumerate(moves)
                               if move[3] == 0.)
                self.assertEqual(moves[planted][1], 0.)
                self.assertAlmostEqual(soles[planted][1], data['baseline'])
                # The body travels over the supporting foot, and the torso
                # tips in the same direction instead of leaning over the swing.
                self.assertGreater(sway * (feet[planted] - center), 0.)
                self.assertGreater(abs(sway), 2.5)
                self.assertGreater(sway * roll, 0.)
            for phase in (0., .5):
                _, _, sway, roll, _ = v.sample(name, phase * 48)
                self.assertAlmostEqual(sway, 0., places=6)
                self.assertAlmostEqual(roll, 0., places=6)

    def test_energy_zero_returns_to_the_authored_stance(self):
        for name in v.NAMES:
            data = v.rig()[0][v.direction(name)]
            for phase in (0., .25, .5, .75):
                moves, bob, sway, roll, soles = v.sample(name, phase * 48, energy=0.)
                self.assertEqual(bob, 0.)
                self.assertEqual(sway, 0.)
                self.assertEqual(roll, 0.)
                for index, move in enumerate(moves):
                    self.assertEqual(move, (0., 0., 0., 0.))
                    self.assertEqual(soles[index], (data['feet'][index], data['baseline']))

    def test_paint_produces_grounded_artwork_in_both_directions(self):
        for name in v.NAMES:
            for phase in (0., .125, .25, .5, .75):
                image = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
                image.fill(Qt.GlobalColor.transparent)
                painter = QPainter(image)
                v.paint(painter, QRectF(0, 0, 256, 256), name, phase * 48)
                painter.end()
                rows = [y for y in range(256)
                        if any(image.pixelColor(x, y).alpha() > 0 for x in range(256))]
                self.assertTrue(rows)
                # The stance foot rolls back by FOOT_TRAVEL source pixels but
                # must stay inside the 256px cell.
                self.assertLessEqual(max(rows), 250 + v.FOOT_TRAVEL)
                self.assertGreater(min(rows), 10)
                self.assertGreater(image.pixelColor(128, 100).alpha(), 0)

    def test_back_walk_never_crossfades_with_front_facing_poses(self):
        from motion_transition import handover_duration
        self.assertEqual(handover_duration(('idle',), ('walk', 'walk-up'), None, None), 0.)
        self.assertEqual(handover_duration(('walk', 'walk-down'),
                                           ('walk', 'walk-up'), None, None), 0.)
        self.assertEqual(handover_duration(('walk', 'walk-up'),
                                           ('action', 'sit-neat', 1.), None, None), 0.)
        self.assertNotEqual(handover_duration(('idle',), ('walk', 'walk-down'), None, None), 0.)

    def test_route_heading_selects_the_rig_and_draws_through_the_renderer(self):
        pet = DesktopPet(Preferences(random_movement=False))
        pet.animator.timer.stop()
        pet.move(200, 200)
        try:
            pet.advance_to((200, 120), .016, 65)
            self.assertEqual(pet.state.gait_name, 'walk-up')
            for _ in range(30):
                pet.advance_to((200, 120), .016, 65)
            self.assertEqual(pet.state.gait_name, 'walk-up')
            pet.state.travel_position = None
            pet.advance_to((200, 300), .016, 65)
            self.assertEqual(pet.state.gait_name, 'walk-down')
            pet.state.travel_position = None
            pet.advance_to((320, pet.y()), .016, 65)
            self.assertEqual(pet.state.gait_name, 'walk-right')
            pet.state.gait_name = 'walk-down'
            pet.state.gait_clock = 12.
            pet.state.gait_until = time.monotonic() + 5
            pet.state.gait_energy = 1.
            pet.state.gait_energy_at = time.monotonic()
            image = QImage(360, 380, QImage.Format.Format_RGBA32FPx4_Premultiplied)
            image.setDevicePixelRatio(2.)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            pet.renderer.draw_pose(painter, pet.state)
            painter.end()
            self.assertGreater(image.pixelColor(180, 180).alpha(), 0)
        finally:
            pet.hide()
            pet.deleteLater()


if __name__ == '__main__':
    unittest.main()
