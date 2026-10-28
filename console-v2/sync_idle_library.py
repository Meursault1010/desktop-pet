"""Publish existing approved sleep assets and the shared idle taxonomy locally."""
import json
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent


def publish():
    folder = ROOT/'assets/actions'
    config = json.loads((folder/'idle-states.json').read_text(encoding='utf-8'))
    entries = json.loads((folder/'catalog.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT/'assets/sleep/transitions/manifest.json').read_text(encoding='utf-8'))
    playback = manifest.get('playback', {})
    settle_seconds = playback.get('settle', manifest['settle']['seconds'])
    wake_seconds = playback.get('wake', manifest['wake']['seconds'])
    wake_hold = playback.get('wake_hold', 0.)
    settle_count = manifest['settle']['count']
    wake_count = manifest['wake']['count']
    settle_durations = [settle_seconds*1000/settle_count]*settle_count
    wake_motion = max(.001, wake_seconds-wake_hold)
    wake_durations = ([wake_motion*1000/(wake_count-1)]*(wake_count-1)
                      +[wake_hold*1000])
    sources = {
        'sleep': ('睡觉 · 熟睡呼吸', [ROOT/'assets/sleep'/f'{i:02}.png' for i in range(96)], [50]*96),
        'sleep-enter': ('闭眼入睡', [ROOT/'assets/sleep/transitions'/f'settle-{i:03}.png' for i in range(settle_count)], settle_durations),
        'sleep-wake': ('睁眼唤醒', [ROOT/'assets/sleep/transitions'/f'wake-{i:03}.png' for i in range(wake_count)], wake_durations),
    }
    for key, (name, paths, durations) in sources.items():
        target = folder/key
        target.mkdir(exist_ok=True)
        atlas = Image.new('RGBA', (1024, ((len(paths)+3)//4)*256))
        for i, path in enumerate(paths):
            image = Image.open(path).convert('RGBA')
            image.thumbnail((256, 247), Image.Resampling.LANCZOS)
            frame = Image.new('RGBA', (256, 256))
            frame.alpha_composite(image, ((256-image.width)//2, 252-image.height))
            frame.save(target/f'{i+1:02}.png')
            atlas.alpha_composite(frame, ((i%4)*256, (i//4)*256))
            if i == (len(paths)-1 if key == 'sleep-wake' else 0):
                frame.save(target/'poster.png')
        atlas.save(target/'atlas.png')
        entry = next((entry for entry in entries if entry['id'] == key), None)
        if entry is None:
            entry = {'id': key}
            entries.append(entry)
        entry.update(name=name, category='睡觉待机', origin='existing', frames=len(paths), columns=4,
                     cell=256, durations=durations, atlas=f'actions/{key}/atlas.png',
                     poster=f'actions/{key}/poster.png', sources=[str(path.relative_to(ROOT)) for path in paths],
                     review='已认可睡姿与入睡、唤醒预览 · 同一母版', authored_motion=True,
                     scale_calibrated=True, scale_profile='approved-sleep-master-fixed-canvas',
                     tempo_profile='轻微呼吸' if key == 'sleep' else '缓慢闭眼落头' if key == 'sleep-enter' else '逐渐睁眼抬头')
    for state in config['states']:
        for key in state['actions']:
            entry = next(entry for entry in entries if entry['id'] == key)
            entry.update(idle_state=state['id'], idle_role=state['roles'].get(key, '日常动作'),
                         idle_automatic=key in state['automatic'], category=state['name']+'待机')
    public = ROOT/'frontend/public/actions'
    for key in sources:
        (public/key).mkdir(exist_ok=True)
        for name in ('atlas.png', 'poster.png'):
            shutil.copyfile(folder/key/name, public/key/name)
    # Ground clips begin standing before lowering. Their library covers must
    # show the resting pose, rather than three indistinguishable stand cards.
    for key, index in {'sit-neat': 3, 'sit-relaxed': 3, 'sit-swing': 3,
                       'prone-chin': 3, 'prone-rest': 4}.items():
        entry = next(entry for entry in entries if entry['id'] == key)
        with Image.open(folder/key/'atlas.png') as atlas:
            x, y = index%entry['columns']*256, index//entry['columns']*256
            cover = atlas.crop((x, y, x+256, y+256))
            cover.save(folder/key/'poster.png')
            cover.save(public/key/'poster.png')
    for output in (folder/'catalog.json', public/'catalog.json'):
        output.write_text(json.dumps(entries, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    shutil.copyfile(folder/'idle-states.json', public/'idle-states.json')
    # The approved dense sleep frames replace the old sleep drawing. Retire
    # its old optical-flow strips/anchors so previews cannot show stale hair.
    motion_path = ROOT/'assets/action-motion/manifest.json'
    motion = json.loads(motion_path.read_text(encoding='utf-8'))
    motion['pairs'] = {key: value for key, value in motion['pairs'].items() if not key.startswith('sleep:')}
    motion['source_sha256'].pop('sleep', None)
    motion_path.write_text(json.dumps(motion, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    alignment_path = folder/'frame-alignment.json'
    alignment = json.loads(alignment_path.read_text(encoding='utf-8'))
    alignment.get('actions', {}).pop('sleep', None)
    alignment['transitions'] = {key: value for key, value in alignment.get('transitions', {}).items() if not key.startswith('sleep:')}
    alignment_path.write_text(json.dumps(alignment, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'Published {len(entries)} actions with four idle states; reused approved sleep assets.')


if __name__ == '__main__':
    publish()
