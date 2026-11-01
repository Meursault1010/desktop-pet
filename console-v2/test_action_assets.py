"""Guard the shared climb/top-rest pose against the left-calf alpha hole."""
import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from repair_top_rest_leg import enclosed_hole

ROOT = Path(__file__).resolve().parent
POSES = (('play-top-rest', 0), ('play-top-rest', 1),
         ('play-climb-up', 9), ('play-climb-down', 0))
AFFECTED_BRIDGES = ('play-climb-up_8--play-climb-up_9.png',
                    'play-climb-up_9--play-climb-up_0.png',
                    'play-climb-down_0--play-climb-down_1.png',
                    'play-climb-down_5--play-climb-down_0.png')


def hole_area(frame):
    return int(enclosed_hole(np.array(frame.convert('RGBA'))[:, :, 3]).sum())


def hole_span(frame):
    """Widest row of any enclosed alpha hole."""
    hole = enclosed_hole(np.array(frame.convert('RGBA'))[:, :, 3])
    return max((int(row.sum()) for row in hole), default=0)


def frame(action, index):
    atlas = Image.open(ROOT/'assets/actions'/action/'atlas.png').convert('RGBA')
    return atlas.crop((index % 4*256, index//4*256,
                       (index % 4+1)*256, (index//4+1)*256))


class InPlaceStompTests(unittest.TestCase):
    def test_angry_frames_keep_their_visible_center(self):
        for path in (ROOT/'assets/actions/angry/atlas.png',
                     ROOT/'frontend/public/actions/angry/atlas.webp'):
            atlas = Image.open(path).convert('RGBA')
            centers = []
            for index in range(16):
                cell = atlas.crop((index % 4*256, index//4*256,
                                   (index % 4+1)*256, (index//4+1)*256))
                ys, xs = np.where(np.array(cell)[..., 3] > 8)
                centers.append(float(xs.mean()))
            self.assertLess(max(centers)-min(centers), 8, path.name)


class ShyInPlaceTests(unittest.TestCase):
    def test_shy_frames_keep_their_visible_center_and_ground_line(self):
        entry = next(entry for entry in
                     json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                     if entry['id'] == 'shy')
        frames = entry['frames']
        self.assertGreaterEqual(frames, 30)
        for path in (ROOT/'assets/actions/shy/atlas.png',
                     ROOT/'frontend/public/actions/shy/atlas.webp'):
            atlas = Image.open(path).convert('RGBA')
            centres, floors = [], []
            for index in range(frames):
                cell = atlas.crop((index % 4*256, index//4*256,
                                   (index % 4+1)*256, (index//4+1)*256))
                ys, xs = np.where(np.array(cell)[..., 3] > 8)
                centres.append(float(xs.mean()))
                floors.append(int(ys.max()))
            self.assertLess(max(centres)-min(centres), 8, path.name)
            self.assertLess(max(floors)-min(floors), 4, path.name)


class WorkInPlaceTests(unittest.TestCase):
    def test_work_frames_stay_on_one_seated_spot(self):
        """The clip is baked-locked, so the pixels themselves must hold still."""
        entry = next(entry for entry in
                     json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                     if entry['id'] == 'work')
        self.assertTrue(entry.get('body_locked'))
        for path in (ROOT/'assets/actions/work/atlas.png',
                     ROOT/'frontend/public/actions/work/atlas.webp'):
            atlas = Image.open(path).convert('RGBA')
            heads, floors, rests = [], [], []
            for index in range(entry['frames']):
                cell = np.array(atlas.crop((index % 4*256, index//4*256,
                                            (index % 4+1)*256, (index//4+1)*256)))
                ys, xs = np.where(cell[..., 3] >= 32)
                top, floor = int(ys.min()), int(ys.max())
                head = (ys >= top) & (ys <= top + 60)
                lap = (ys >= floor - 70) & (ys <= floor - 30)
                heads.append(float(xs[head].mean()))
                floors.append(floor)
                rests.append(float(xs[head].mean()) - float(xs[lap].mean()))
            self.assertLess(max(heads)-min(heads), 2.0, path.name)
            self.assertEqual(len(set(floors)), 1, path.name)
            self.assertLess(max(rests)-min(rests), 3.0, path.name)


class PlayLeanInPlaceTests(unittest.TestCase):
    def test_she_leans_without_stepping_across_the_desk(self):
        """The four authored poses were drawn 108px apart; the bake must cancel it."""
        entry = next(entry for entry in
                    json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                    if entry['id'] == 'play-lean')
        self.assertTrue(entry.get('body_locked'))
        for path in (ROOT/'assets/actions/play-lean/atlas.png',
                     ROOT/'frontend/public/actions/play-lean/atlas.webp'):
            atlas = Image.open(path).convert('RGBA')
            feet, floors = [], []
            for index in range(entry['frames']):
                cell = np.array(atlas.crop((index % 4*256, index//4*256,
                                            (index % 4+1)*256, (index//4+1)*256)))
                ys, xs = np.where(cell[..., 3] >= 32)
                floor = int(ys.max())
                contact = ys >= floor - 9
                weight = cell[..., 3][ys[contact], xs[contact]]
                feet.append(float((xs[contact]*weight).sum()/weight.sum()))
                floors.append(floor)
            self.assertLess(max(feet)-min(feet), 2.0, f'{path.name}: {feet}')
            self.assertEqual(set(floors), {250}, path.name)


class CelebrateInPlaceTests(unittest.TestCase):
    def test_the_bounce_never_walks_her_across_the_desk(self):
        """The seven key poses were drawn 64px apart; the bake must cancel that."""
        entry = next(entry for entry in
                     json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                     if entry['id'] == 'celebrate')
        self.assertTrue(entry.get('body_locked'))
        for path in (ROOT/'assets/actions/celebrate/atlas.png',
                     ROOT/'frontend/public/actions/celebrate/atlas.webp'):
            atlas = Image.open(path).convert('RGBA')
            feet, floors, widths = [], [], []
            for index in range(entry['frames']):
                cell = np.array(atlas.crop((index % 4*256, index//4*256,
                                            (index % 4+1)*256, (index//4+1)*256)))
                ys, xs = np.where(cell[..., 3] >= 32)
                floor = int(ys.max())
                band = ys >= floor - 9
                weight = cell[..., 3][ys[band], xs[band]]
                feet.append(float((xs[band]*weight).sum()/weight.sum()))
                floors.append(floor)
                widths.append(int(xs.max()) - int(xs.min()))
            self.assertLess(max(feet)-min(feet), 2.0, f'{path.name}: {feet}')
            # The hop is real motion: the floor line has to keep moving.
            self.assertGreater(len(set(floors)), 1, path.name)
            self.assertLess(max(widths)-min(widths), 20, path.name)


class DanceRestIdleStyleTests(unittest.TestCase):
    """`dance-rest` was ten separate drawings of one rest; it now shares the idle's weight."""

    BAND = (104, 158, 92, 166)      # rows, cols: the closed-eye plate of frame 10
    FEATHER = 10

    @staticmethod
    def line_weight(cell):
        a = cell.astype(np.float32) / 255
        alpha = a[..., 3]
        solid = alpha > 0.78
        lum = (a[..., :3] * alpha[..., None] + 0.95 * (1 - alpha[..., None])).mean(2)
        gy, gx = np.gradient(lum)
        return float(np.sqrt(gy ** 2 + gx ** 2)[solid].mean() * 255)

    def test_every_frame_sits_in_the_idle_line_weight_band(self):
        for path in (ROOT/'assets/actions/dance-rest/atlas.png',
                     ROOT/'frontend/public/actions/dance-rest/atlas.webp'):
            atlas = Image.open(path).convert('RGBA')
            for index in range(10):
                cell = np.array(atlas.crop((index % 5*256, index//5*256,
                                            (index % 5+1)*256, (index//5+1)*256)))
                weight = self.line_weight(cell)
                self.assertGreater(weight, 14.6, f'{path.name} frame {index+1}: {weight}')
                self.assertLess(weight, 16.6, f'{path.name} frame {index+1}: {weight}')

    def test_the_rest_hold_shares_one_body_and_keeps_only_its_blink(self):
        folder = ROOT/'assets/actions/dance-rest'
        base = np.array(Image.open(folder/'08.png').convert('RGBA'))
        hold = np.array(Image.open(folder/'09.png').convert('RGBA'))
        blink = np.array(Image.open(folder/'10.png').convert('RGBA'))
        self.assertTrue((base == hold).all(),
                        'the two 650ms holds must be one drawing, not two redraws')
        r0, r1, c0, c1 = self.BAND
        margin = self.FEATHER
        outside = np.ones(base.shape[:2], bool)
        outside[r0-margin:r1+margin, c0-margin:c1+margin] = False
        difference = np.abs(base.astype(np.int16) - blink.astype(np.int16)).mean(2)
        self.assertLess(difference[outside].mean(), 1.0,
                        'everything outside the eye plate must be the shared body')
        self.assertGreater(difference[r0:r1, c0:c1].mean(), 4.0,
                           'frame 10 has to keep its own closed eyes')


class TeaStableHoldsTests(unittest.TestCase):
    """The six tea key poses are six independent redraws of one character.

    Two frames of the *same* pose still differed on 43% of their pixels — every
    outline moved — and that flicker, not the missing in-betweens, is what made
    the clip look rough. The holds therefore share one base body outright, and a
    closed-eye beat may only differ inside the eye/mouth band.
    """

    EYE_BAND = (72, 124, 84, 173)      # rows, cols: the band paste plus its feather

    def test_holds_share_pixels_and_adjacent_frames_stay_calm(self):
        entry = next(e for e in
                     json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                     if e['id'] == 'tea')
        self.assertEqual(entry['frames'], entry['keyframes'])
        cells = []
        for path in (ROOT/'assets/actions/tea/atlas.png',
                     ROOT/'frontend/public/actions/tea/atlas.webp'):
            atlas = np.array(Image.open(path).convert('RGBA'))
            held = [atlas[i//4*256:(i//4+1)*256, i%4*256:(i%4+1)*256]
                    for i in range(entry['frames'])]
            band = np.zeros((256, 256), bool)
            y0, y1, x0, x1 = self.EYE_BAND
            band[y0:y1, x0:x1] = True
            for index in (1, 3, 4):          # sip, blink, eyes open again
                a, b = held[index], held[index+1]
                gap = np.abs(a[:, :, :3].astype(int) - b[:, :, :3].astype(int)).mean(2)
                solid = (a[:, :, 3] >= 32) | (b[:, :, 3] >= 32)
                self.assertLess(float(gap[~band & solid].mean()), 0.5,
                                f'{path.name}: hold {index+1}->{index+2} moved outside the band')
            for index in range(entry['frames']):
                nxt = held[(index + 1) % entry['frames']]
                gap = np.abs(held[index][:, :, :3].astype(int)
                             - nxt[:, :, :3].astype(int)).mean(2)
                solid = (held[index][:, :, 3] >= 32) | (nxt[:, :, 3] >= 32)
                self.assertLess(float(gap[solid].mean()), 15.0,
                                f'{path.name}: {index+1}->{index+2} still boils')
            cells.append([c.tobytes() for c in held])
        self.assertEqual(len(set(cells[0])), 4, 'expected four unique frames')
        self.assertEqual(cells[0], cells[1], 'runtime atlas and workbench atlas diverged')


class WaveInPlaceTests(unittest.TestCase):
    ARM_BOX = (78, 158, 30, 118)          # rows, cols: where the arm is allowed to change
    STATIC = 216                          # the flow only works above this, the legs never move

    def test_wave_frames_stay_on_one_spot(self):
        """The batch drew one stance at three canvas positions; the lock is in the pixels."""
        entry = next(e for e in
                     json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                     if e['id'] == 'wave')
        self.assertTrue(entry.get('body_locked'))
        self.assertEqual(entry['keyframes'], 8)
        self.assertGreater(entry['frames'], entry['keyframes'])
        for path in (ROOT/'assets/actions/wave/atlas.png',
                     ROOT/'frontend/public/actions/wave/atlas.webp'):
            atlas = np.array(Image.open(path).convert('RGBA'))
            cells = [atlas[i//4*256:(i//4+1)*256, i%4*256:(i%4+1)*256]
                     for i in range(entry['frames'])]
            feet, hips, floors = [], [], []
            for cell in cells:
                alpha = cell[:, :, 3]
                ys, xs = np.where(alpha >= 32)
                floor = int(ys.max())
                band = ys >= floor - 9
                feet.append(float((xs[band]*alpha[ys[band], xs[band]]).sum()
                                  / alpha[ys[band], xs[band]].sum()))
                hips.append(float(xs[(ys >= floor-95) & (ys <= floor-55)].mean()))
                floors.append(floor)
            self.assertEqual(len(set(floors)), 1, path.name)
            self.assertLess(max(feet)-min(feet), 1.5, f'{path.name}: feet slide')
            self.assertLess(max(hips)-min(hips), 2.5, f'{path.name}: hips slide')
            self.assertAlmostEqual(sum(feet)/len(feet), 126.7, delta=1.0, msg=path.name)
            # the warp must not creep into the legs: skirt, legs and shoes are one image
            below = [c[self.STATIC:].tobytes() for c in cells]
            self.assertEqual(len(set(below)), 1, f'{path.name}: the flow moved the legs')
            # locking must not flatten the gesture: the arm still has to move frame to frame
            r0, r1, c0, c1 = self.ARM_BOX
            arms, whole = [], []
            for index in range(entry['frames'] - 1):
                a, b = cells[index], cells[index + 1]
                solid = (a[:, :, 3] >= 32) | (b[:, :, 3] >= 32)
                gap = np.abs(a[:, :, :3].astype(int) - b[:, :, :3].astype(int))
                whole.append(float(gap[solid].mean()))
                arms.append(float(gap[r0:r1, c0:c1][solid[r0:r1, c0:c1]].mean()))
            self.assertGreater(max(arms), 20.0,
                               f'{path.name}: arm never moves, no wave left {arms}')
            self.assertLess(max(whole), 23.0, f'{path.name}: {whole}')
            self.assertEqual(cells[0].tobytes(), cells[-1].tobytes(),
                             f'{path.name}: the loop would flash')

    def test_wave_leg_channel_stays_open(self):
        """The pale strip the extraction left between the legs used to bridge and flicker."""
        entry = next(e for e in
                     json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
                     if e['id'] == 'wave')
        for index in range(1, entry['frames'] + 1):
            path = ROOT/'assets/actions/wave'/f'{index:02d}.png'
            alpha = np.array(Image.open(path).convert('RGBA'))[:, :, 3]
            floor = int(np.where(alpha >= 32)[0].max())
            bridged = 0
            for row in range(floor - 34, floor):
                on = alpha[row, 112:142] >= 32
                kept = np.where(on)[0]
                if len(kept) and on[kept.min():kept.max()+1].all():
                    bridged += 1
            self.assertEqual(bridged, 0, f'{path.name}: {bridged} rows bridge the legs')


class TopRestLegTests(unittest.TestCase):
    def test_shared_top_rest_pose_has_a_filled_left_calf(self):
        # The space between the calves is keyed out on purpose; a lost calf fill
        # is a wide hole, the slot between the legs is at most eight pixels.
        for action, index in POSES:
            with self.subTest(action=action, frame=index):
                self.assertLessEqual(hole_span(frame(action, index)), 12)

    def test_climb_bridges_keep_the_left_calf(self):
        for name in AFFECTED_BRIDGES:
            path = ROOT/'assets/action-motion'/name
            strip = Image.open(path).convert('RGBA')
            for index in range(25):
                cell = strip.crop((index % 5*256, index//5*256,
                                   (index % 5+1)*256, (index//5+1)*256))
                with self.subTest(file=path.name, frame=index):
                    self.assertLess(hole_area(cell), 200)


if __name__ == '__main__':
    unittest.main()
