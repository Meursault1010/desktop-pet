"""Per-frame alignment stabilizes artwork placement without changing poses."""
import json
import unittest
from pathlib import Path
from PIL import Image

from build_frame_alignment import ASSETS, build
from frame_alignment import offset_for, profile


class FrameAlignmentTests(unittest.TestCase):
    def test_profile_covers_generated_action_sequences_and_matches_visible_bounds(self):
        generated = {entry['id']:entry for entry in
                     json.loads((ASSETS/'catalog.json').read_text(encoding='utf-8'))
                     if entry.get('origin') == 'generated' and entry['frames'] > 1
                     and not entry.get('ground_idle') and not entry.get('lazy_roll')
                     and not entry.get('physics_only') and entry['id'] not in {'leap', 'dragged'}}
        measured = build()['actions']
        shipped = profile()
        self.assertEqual(set(shipped), set(generated))
        self.assertEqual(shipped, measured)
        for action_id, entry in generated.items():
            offsets = shipped[action_id]['offsets']
            self.assertEqual(len(offsets), entry['frames'])
            boxes = []
            for index in range(entry['frames']):
                image = Image.open(ASSETS/action_id/f'{index+1:02d}.png').convert('RGBA')
                box = image.getchannel('A').point(lambda value:255 if value >= 32 else 0).getbbox()
                boxes.append(box)
                dx, dy = offsets[index]
                self.assertAlmostEqual((box[0]+box[2])/2+dx, shipped[action_id]['anchor_x'])
                if shipped[action_id].get('preserve_vertical'):
                    self.assertEqual(dy, 0.)
                else:
                    self.assertAlmostEqual(box[3]+dy, shipped[action_id]['floor_y'])
                self.assertGreaterEqual(box[0]+dx, 0)
                self.assertLessEqual(box[2]+dx, 256)
                self.assertGreaterEqual(box[1]+dy, 0)
                self.assertLessEqual(box[3]+dy, 256)

    def test_frame_offsets_ease_between_poses_and_ignore_world_motion_clips(self):
        from unittest.mock import patch
        start = offset_for(('wait',0),('wait',1),0)
        end = offset_for(('wait',0),('wait',1),1)
        self.assertNotEqual(start, end)
        with patch('frame_alignment._data', return_value={'actions':profile()}):
            middle = offset_for(('wait',0),('wait',1),.5)
            self.assertAlmostEqual(middle[0], (start[0]+end[0])/2)
            self.assertAlmostEqual(middle[1], (start[1]+end[1])/2)
        self.assertEqual(offset_for(('leap',0),('leap',1),.5),(0.,0.))
        self.assertEqual(offset_for(('lazy-roll-toward',0),('lazy-roll-toward',1),.5),(0.,0.))

    def test_warp_subframes_keep_the_same_anchor_and_exact_endpoints(self):
        from frame_alignment import _data
        payload = _data()
        self.assertEqual(payload['transitions'], build()['transitions'])
        motion = ASSETS.parent/'action-motion'
        manifest = json.loads((motion/'manifest.json').read_text(encoding='utf-8'))['pairs']
        self.assertGreater(len(payload['transitions']), 100)
        for pair, offsets in payload['transitions'].items():
            before, after = [(name, int(index)) for name, index in
                             (ref.rsplit(':', 1) for ref in pair.split('>'))]
            self.assertEqual(offsets[0], list(offset_for(before)))
            self.assertEqual(offsets[-1], list(offset_for(after)))
            entry = manifest[pair]
            with Image.open(motion/entry['file']) as strip:
                for index in range(len(offsets)):
                    t = index/(len(offsets)-1)
                    dx, dy = offset_for(before, after, t)
                    self.assertAlmostEqual(dx, offsets[index][0])
                    self.assertAlmostEqual(dy, offsets[index][1])
                    if index not in (0, len(offsets)//2, len(offsets)-1):
                        continue
                    x, y = index % entry['columns']*256, index//entry['columns']*256
                    box = strip.crop((x,y,x+256,y+256)).getchannel('A').point(
                        lambda value:255 if value >= 32 else 0).getbbox()
                    start, end = profile()[before[0]], profile()[after[0]]
                    anchor_x = start['anchor_x']+(end['anchor_x']-start['anchor_x'])*t
                    self.assertAlmostEqual((box[0]+box[2])/2+dx, anchor_x, places=2)
                    if not start['preserve_vertical'] and not end['preserve_vertical']:
                        floor_y = start['floor_y']+(end['floor_y']-start['floor_y'])*t
                        self.assertAlmostEqual(box[3]+dy, floor_y, places=2)
            i = len(offsets)//2
            midway = (i+.5)/(len(offsets)-1)
            dx, dy = offset_for(before, after, midway)
            self.assertAlmostEqual(dx, (offsets[i][0]+offsets[i+1][0])/2)
            self.assertAlmostEqual(dy, (offsets[i][1]+offsets[i+1][1])/2)


if __name__ == '__main__':
    unittest.main()
