"""Calibration integrity across actions, motion and attachment coordinates."""
import json
import unittest
from pathlib import Path
from PIL import Image
from calibrate_action_scale import apply_image, map_point, digest

ROOT=Path(__file__).resolve().parent


class ScaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads((ROOT/'action-work/scale-calibration/report.json').read_text(encoding='utf-8'))
        cls.entries=json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))

    def test_every_runtime_clip_has_one_reviewed_scale(self):
        profile=json.loads((ROOT/'scale_calibration.json').read_text(encoding='utf-8'))
        for group in ('actions','motion','drag','icon','legacy'):
            self.assertEqual({key.split('/')[1] for key in self.report if key.startswith(group+'/')},set(profile[group]))
        self.assertTrue(all(entry.get('scale_calibrated') for entry in self.entries))

    def test_identical_uniform_transform_for_all_frames_and_web_mirror(self):
        for entry in self.entries:
            key=entry['id']; directory=ROOT/'assets/actions'/key
            paths=[directory/f'{index+1:02}.png' for index in range(entry['frames'])]
            record=self.report['actions/'+key]
            self.assertEqual(digest(paths),record['output_hash'])
            atlas=Image.open(directory/'atlas.png').convert('RGBA')
            for index,path in enumerate(paths):
                original=ROOT/'action-work/scale-calibration/originals/actions'/key/path.name
                image=Image.open(path).convert('RGBA')
                box=image.getchannel('A').point(lambda value:255 if value>=16 else 0).getbbox()
                self.assertTrue(box[0]>=1 and box[1]>=1 and box[2]<=255 and box[3]<=255,(key,index,box))
                self.assertEqual(image.tobytes(),apply_image(Image.open(original),record['transform']).tobytes())
                cell=atlas.crop((index%entry['columns']*256,index//entry['columns']*256,
                                 (index%entry['columns']+1)*256,(index//entry['columns']+1)*256))
                self.assertEqual(image.tobytes(),cell.tobytes())
                self.assertEqual(path.read_bytes(),(ROOT/'frontend/public/actions'/key/path.name).read_bytes())

    def test_support_coordinates_follow_the_art_and_masks_remain_binary(self):
        for group,filename in [('motion','motion-v2/clips.json'),('drag','drag-resist/poses.json'),('icon','icon-interactions/poses.json')]:
            original=json.loads((ROOT/f'action-work/scale-calibration/originals/{group}-metadata.json').read_text(encoding='utf-8'))
            current=json.loads((ROOT/'assets'/filename).read_text(encoding='utf-8'))
            for key,old in original.items():
                transform=self.report[f'{group}/{key}']['transform']
                for field in ('hand','contact'):
                    if field in old:self.assertEqual(current[key][field],map_point(old[field],transform,normalized=field!='hand'))
                if group=='icon':
                    mask=Image.open(ROOT/f'assets/icon-interactions/{key}/skirt.png').convert('L')
                    self.assertLessEqual(len(set(mask.tobytes())),2)

    def test_neutral_standing_height_is_close_to_default_and_lazy_roll_closes(self):
        profile=json.loads((ROOT/'scale_calibration.json').read_text(encoding='utf-8'))
        for entry in self.entries:
            if entry['id'] in profile['nonstanding']:continue
            image=Image.open(ROOT/f"assets/actions/{entry['id']}/01.png")
            box=image.getchannel('A').point(lambda value:255 if value>=16 else 0).getbbox()
            self.assertLessEqual(abs((box[3]-box[1])-227),19,entry['id'])
        for key in ('lazy-roll-toward','lazy-roll-away'):
            directory=ROOT/'assets/actions'/key
            self.assertEqual((directory/'01.png').read_bytes(),(directory/'12.png').read_bytes())


if __name__=='__main__':unittest.main()
