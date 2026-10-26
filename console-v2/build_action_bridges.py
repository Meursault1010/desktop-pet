"""Insert one authored in-between into stretch, affection and curious.

The shipped keyframes already carry the reviewed scale calibration, so this
pass only adds the generated mid-pose and repacks each clip; it never rescales
the existing drawings. Originals stay in action-work/<clip>-bridge/original.

After insertion, --finalize-calibration records the repacked clips as the new
calibration baseline (identity transform). That keeps the scale report, hashes
and web mirror honest without applying the reviewed scale a second time.
"""
import argparse
import io
import json
import os
import shutil
import time

from PIL import Image

from build_action_library import ROOT, extract
from calibrate_action_scale import digest

COLUMNS = 4
BRIDGES = {
    'stretch': dict(
        height=239.5, floor=247.5, center=123.5,
        durations=[240, 360, 270, 270, 600, 340, 240],
        review='已审查：姿态 2→3 之间补入身体初倾、双臂仍在头顶的中帧，流程连续'),
    'affection': dict(
        height=227.5, floor=247.5, center=132.75,
        durations=[180, 220, 230, 230, 520, 340, 300],
        review='已审查：姿态 2→3 之间补入双手离开下巴、于胸前将合未合的中帧'),
    'curious': dict(
        height=225.0, floor=246.5, center=124.5,
        durations=[180, 240, 225, 225, 550, 360, 280],
        review='已审查：姿态 2→3 之间补入放大镜抬至胸前、另一手仍在颊边的中帧'),
}
INSERT_AFTER = 2


def atomic_write(path, payload):
    for attempt in range(5):
        temporary = path.with_name(f'{path.name}.{os.getpid()}.{attempt}.tmp')
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, path)
            return
        except OSError:
            temporary.unlink(missing_ok=True)
            if attempt == 4:
                raise
            time.sleep(.35*(attempt+1))


def save_image(image, path, **options):
    buffer = io.BytesIO()
    image.save(buffer, format={'png':'PNG','jpg':'JPEG','gif':'GIF'}[path.suffix[1:].lower()],
               **options)
    atomic_write(path, buffer.getvalue())


def bridge_frame(work, spec):
    # The generator emits a near-opaque alpha channel; flatten it so the
    # chroma keyer runs instead of treating the green sheet as a cutout.
    subject = extract(Image.open(work/'raw.png').convert('RGB').convert('RGBA'), True)
    alpha = subject.getchannel('A').point(lambda value: 255 if value > 32 else 0)
    left, top, right, bottom = alpha.getbbox()
    sprite = subject.crop((left, top, right, bottom))
    factor = spec['height']/sprite.height
    sprite = sprite.resize((max(1, round(sprite.width*factor)), round(spec['height'])),
                           Image.Resampling.LANCZOS)
    frame = Image.new('RGBA', (256, 256))
    frame.alpha_composite(sprite, (round(spec['center']-sprite.width/2),
                                   round(spec['floor']-sprite.height)))
    return frame


def main():
    catalog_path = ROOT/'assets/actions/catalog.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    qa = ROOT/'qa/actions'
    qa.mkdir(parents=True, exist_ok=True)
    for key, spec in BRIDGES.items():
        work = ROOT/f'action-work/{key}-bridge'
        target = ROOT/'assets/actions'/key
        previous = next(action for action in catalog if action['id'] == key)
        original = [Image.open(work/'original'/f'{index:02d}.png').convert('RGBA')
                    for index in range(1, previous['frames']+1)]
        if len(original) != 6 or INSERT_AFTER+1 >= len(original):
            raise ValueError(f'{key}: unexpected shipped frame count')
        frames = [*original[:INSERT_AFTER+1], bridge_frame(work, spec),
                  *original[INSERT_AFTER+1:]]
        durations = spec['durations']
        if len(durations) != len(frames):
            raise ValueError(f'{key}: durations do not match frames')
        target.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(frames):
            save_image(frame, target/f'{index+1:02d}.png')
        rows = (len(frames)+COLUMNS-1)//COLUMNS
        atlas = Image.new('RGBA', (256*COLUMNS, 256*rows))
        for index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (index % COLUMNS*256, index//COLUMNS*256))
        save_image(atlas, target/'atlas.png')
        save_image(frames[0], target/'poster.png')
        sheet = Image.new('RGB', atlas.size, '#48505e')
        sheet.paste(atlas, mask=atlas.getchannel('A'))
        save_image(sheet, qa/f'{key}.jpg')
        previews = []
        for frame in frames:
            background = Image.new('RGB', (256, 256), '#48505e')
            background.paste(frame, mask=frame.getchannel('A'))
            previews.append(background)
        save_image(previews[0], qa/f'{key}.gif', save_all=True,
                   append_images=previews[1:], duration=durations, loop=0)
        entry = {**previous, 'frames': len(frames), 'columns': COLUMNS,
                 'durations': durations,
                 'sources': [*previous.get('sources', []),
                             str((work/'raw.png').relative_to(ROOT))],
                 'review': spec['review']}
        catalog = [entry if action['id'] == key else action for action in catalog]
        print(f'{key}: {len(frames)} frames, {sum(durations)} ms')
    atomic_write(catalog_path,
                 (json.dumps(catalog, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


def finalize_calibration():
    catalog = json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
    report_path = ROOT/'action-work/scale-calibration/report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    originals_root = ROOT/'action-work/scale-calibration/originals/actions'
    for key, spec in BRIDGES.items():
        entry = next(action for action in catalog if action['id'] == key)
        expected = len(spec['durations'])
        if entry['frames'] != expected:
            raise ValueError(f'{key}: expected {expected} bridge frames, found {entry["frames"]}')
        frames = [ROOT/f'assets/actions/{key}/{index+1:02d}.png'
                  for index in range(entry['frames'])]
        target = originals_root/key
        backup = ROOT/f'action-work/{key}-bridge/pre-scale-originals'
        if target.exists() and not backup.exists():
            shutil.copytree(target, backup)
        target.mkdir(parents=True, exist_ok=True)
        for stale in target.glob('*.png'):
            stale.unlink()
        for frame in frames:
            shutil.copy2(frame, target/frame.name)
        record = report['actions/'+key]
        record.update(
            frames=len(frames),
            transform=[1, 0, 0],
            input_hash=digest([target/frame.name for frame in frames]),
            output_hash=digest(frames),
            note='bridge composited after reviewed scale; final frames recorded at identity',
        )
        print(f'{key}: calibration recorded at identity ({len(frames)} frames)')
    atomic_write(report_path,
                 (json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--finalize-calibration', action='store_true',
                        help='record the already-repacked bridge clips at identity scale')
    args = parser.parse_args()
    if args.finalize_calibration:
        finalize_calibration()
    else:
        main()
