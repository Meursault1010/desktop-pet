"""Apply reviewed character-scale measurements, keeping an untouched source copy.

Each clip receives ONE similarity transform, including all frames and semantic
contact points. Never fit each pose separately: that causes size pumping.
Run after rebuilding any art: python calibrate_action_scale.py --apply
Re-running on unchanged output is byte-for-byte idempotent. Changed clips are
backed up as fresh inputs; untouched clips retain their original source.
"""
import argparse
import hashlib
import json
import math
import shutil
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT/'assets'
WORK = ROOT/'action-work/scale-calibration'


def digest(paths):
    value = hashlib.sha256()
    for path in sorted(paths):
        value.update(path.name.encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def bounds(image):
    # Nearly invisible keying dust must not dictate the character's scale.
    return image.getchannel('A').point(lambda value:255 if value>=16 else 0).getbbox()


def transform_for(images, requested, baseline=None):
    boxes = [bounds(image) for image in images]
    left = min(b[0] for b in boxes); top = min(b[1] for b in boxes)
    right = max(b[2] for b in boxes); bottom = max(b[3] for b in boxes)
    # Reserve transparent margins even at the widest authored pose. A clip
    # whose limbs span the canvas cannot be enlarged safely without new art.
    factor = min(requested, 248/(right-left), 248/(bottom-top))
    factor = round(256*factor)/256
    dx = round(128-(left+right)/2*factor)
    dy = round((baseline if baseline is not None else 128+(bottom-top)*factor/2)-bottom*factor)
    if top*factor+dy < 3:
        dy = math.ceil(3-top*factor)
    if bottom*factor+dy > 253:
        dy = math.floor(253-bottom*factor)
    return factor, dx, dy


def apply_image(image, transform, mask=False):
    factor, dx, dy = transform
    if mask:
        # Skirt semantic masks are opaque grayscale files.
        result = Image.new('L', (256, 256), 0)
        resized = image.convert('L').resize((round(256*factor),)*2, Image.Resampling.NEAREST)
        result.paste(resized, (dx,dy))
        return result.convert('RGBA')
    result = Image.new('RGBA', (256,256))
    resized = image.convert('RGBA').resize((round(256*factor),)*2, Image.Resampling.LANCZOS)
    result.alpha_composite(resized, (dx,dy))
    return result


def map_point(point, transform, normalized=True):
    factor, dx, dy = transform
    unit = 256 if normalized else 1
    return [(point[0]*unit*factor+dx)/unit, (point[1]*unit*factor+dy)/unit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        parser.error('Use --apply to publish the reviewed calibration')
    profile = json.loads((ROOT/'scale_calibration.json').read_text(encoding='utf-8'))
    entries = json.loads((ASSETS/'actions/catalog.json').read_text(encoding='utf-8'))
    if set(profile['actions']) != {entry['id'] for entry in entries}:
        raise ValueError('Review new or removed action scales before calibrating')
    WORK.mkdir(parents=True, exist_ok=True)
    report_path = WORK/'report.json'
    previous = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    report = {}

    def calibrate(group, name, paths, head, attached=False, upright_height=None, baseline=None):
        key = f'{group}/{name}'
        before = digest(paths)
        old = previous.get(key)
        unchanged = old and old['output_hash'] == before
        if unchanged and old.get('version') == 2:
            report[key] = old
            return old['transform']
        backup = WORK/'originals'/key
        backup.mkdir(parents=True, exist_ok=True)
        if not unchanged:
            for path in paths:
                shutil.copy2(path, backup/path.name)
        images = [Image.open(backup/path.name).convert('RGBA') for path in paths if path.name != 'skirt.png']
        factor = 97/head/(math.sqrt((180*.94/160)*(190*.88/160)) if attached else 1)
        if upright_height:
            box = bounds(images[0])
            factor = math.sqrt(factor*227/(box[3]-box[1]))
        transform = transform_for(images, factor, baseline)
        for path in paths:
            image = Image.open(backup/path.name)
            apply_image(image, transform, mask=path.name=='skirt.png').save(path)
        report[key] = dict(version=2, head_span=head, requested_scale=round(factor,6),
                           transform=transform, frames=len(images), input_hash=digest([backup/path.name for path in paths]),
                           output_hash=digest(paths))
        return transform

    for entry in entries:
        key = entry['id']; directory = ASSETS/'actions'/key
        paths = [directory/f'{i+1:02}.png' for i in range(entry['frames'])]
        neutral = Image.open(paths[0]).convert('RGBA')
        box = bounds(neutral)
        height = box[3]-box[1] if key not in profile['nonstanding'] else None
        transform = calibrate('actions',key,paths,profile['actions'][key],
                              upright_height=height,baseline=251)
        atlas = Image.new('RGBA',(entry['columns']*256,math.ceil(entry['frames']/entry['columns'])*256))
        for index,path in enumerate(paths):
            atlas.alpha_composite(Image.open(path).convert('RGBA'),(index%entry['columns']*256,index//entry['columns']*256))
        atlas.save(directory/'atlas.png')
        # Ground-idle posters intentionally show the established sitting pose.
        poster = 4 if entry.get('ground_idle') else 0
        shutil.copyfile(paths[poster],directory/'poster.png')
        entry['scale_calibrated'] = True

    # Keep metadata sources alongside the original clips, then always transform
    # from those originals (never apply the scale twice to grip coordinates).
    for group, filename in [('motion','motion-v2/clips.json'),('drag','drag-resist/poses.json'),('icon','icon-interactions/poses.json')]:
        path=ASSETS/filename; backup=WORK/'originals'/f'{group}-metadata.json'
        if not backup.exists():shutil.copy2(path,backup)
        metadata=json.loads(backup.read_text(encoding='utf-8'))
        for key, head in profile[group].items():
            if group=='motion':paths=sorted((ASSETS/'motion-v2'/key).glob('*.png'))
            elif group=='drag':paths=[ASSETS/f'drag-resist/{key}.png']
            else:paths=sorted((ASSETS/'icon-interactions'/key).glob('*.png'))
            transform=calibrate(group,key,paths,head,attached=group=='icon' or group=='motion' and not key.startswith('walk'),
                                baseline=251 if group=='motion' and key.startswith('walk') else None)
            spec=metadata[key]
            for field in ('hand','contact'):
                if field in spec:spec[field]=map_point(spec[field],transform,normalized=field!='hand')
            if group=='motion':
                boxes=[bounds(Image.open(p).convert('RGBA')) for p in paths]
                spec['bounds']=[min(b[0] for b in boxes)/256,min(b[1] for b in boxes)/256,
                                max(b[2] for b in boxes)/256,max(b[3] for b in boxes)/256]
                for field in ('baseline','support_bottom'):
                    if field in spec:spec[field]=spec[field]*transform[0]+transform[2]/256
                spec['stride'] *= transform[0]
        path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    legacy={}
    original_contacts=dict(left=(.76,.48),right=(.24,.48),back=(.76,.49),front=(.50,.48))
    for key,head in profile['legacy'].items():
        transform=calibrate('legacy',key,[ASSETS/f'icon-sleep-v2/{key}.png'],head,attached=True)
        legacy[key]={'contact':map_point(original_contacts[key],transform)}
    (ASSETS/'icon-sleep-v2/poses.json').write_text(json.dumps(legacy,indent=2)+'\n',encoding='utf-8')
    manifest=ASSETS/'actions/catalog.json'
    manifest.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # Save the source/output fingerprint before copying the web mirror, so a
    # transient Windows file lock cannot cause a later run to rescale outputs.
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for source in (ASSETS/'actions').rglob('*'):
        if source.is_file():
            target=ROOT/'frontend/public/actions'/source.relative_to(ASSETS/'actions')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(source.read_bytes())
    print(f'Calibrated {len(report)} clips; original sprites and audit: {WORK}')


if __name__=='__main__':main()
