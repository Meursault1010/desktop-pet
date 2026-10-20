"""Offline, reversible reuse of reviewed crown artwork. No runtime filtering.

Proposals are staged first. --apply requires an explicit reviewed profile,
checks every source hash, and retains exact originals for repeatable rebuilds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw

from audit_head_landmarks import propose
from build_action_inbetweens import premultiply, unpremultiply, gray

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'action-work/character-consistency'
BACKUP = WORK/'originals'
STAGE = WORK/'staged'
PROFILE = WORK/'reviewed-profile.json'
OVERRIDES = WORK/'landmark-overrides.json'
# These poses have genuine perspective/occlusion or authored ear compression.
# They require their own view-specific artwork, not a frontal crown graft.
PRESERVE = {'sleep', 'reading-pose-2', 'lazy-roll-toward', 'lazy-roll-away',
            'impact-left', 'impact-right', 'impact-ceiling', 'throw-flight', 'impact-floor'}
PRESERVE_FRAMES = {'wait': {1, 2}, 'work': {0, 1, 2, 3, 4, 5},
                   'stretch': {3}, 'sad': {1, 2, 3, 4}}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original(relative):
    backup = BACKUP/relative
    return backup if backup.exists() else ROOT/'assets'/relative


def correction(target, transform, reference):
    yy, xx = np.mgrid[:256, :256].astype(np.float32)
    region = np.maximum(np.clip((86-yy)/3, 0, 1),
                        np.clip((np.abs(xx-128)-31)/8, 0, 1)*np.clip((136-yy)/24, 0, 1))
    # A finite head-local mask is essential: a half-plane erases raised arms
    # and the feet behind a prone head. The lower locks remain pose-specific.
    region *= (np.clip((xx-50)/5, 0, 1)*np.clip((206-xx)/5, 0, 1)
               *np.clip((yy-8)/5, 0, 1))
    strength = cv2.warpAffine(region, transform, (256, 256), flags=cv2.INTER_LINEAR)
    mapped = cv2.warpAffine(premultiply(reference), transform, (256, 256), flags=cv2.INTER_LINEAR)
    inverse = cv2.invertAffineTransform(transform)
    local_x = inverse[0, 0]*xx+inverse[0, 1]*yy+inverse[0, 2]
    local_y = inverse[1, 0]*xx+inverse[1, 1]*yy+inverse[1, 2]
    r, g, b, a = [target[:, :, i].astype(np.float32) for i in range(4)]
    face_core = ((local_x-128)/34)**2+((local_y-106)/32)**2 < 1
    skin = ((r > 210) & (g > 170) & (b > 165) & (r-b > 4)
            & (r-g > 2) & (a > 30) & (local_y > 60) & ~face_core).astype('uint8')
    # Include the original ink around fingers/face; never graft a crown over
    # a hand. Pink inner ears are above this protected face/hand region.
    protected = cv2.dilate(skin, np.ones((3, 3), np.uint8)) > 0
    strength[protected] = 0
    # Register the shared artwork to the existing fringe/ear contour. Keep
    # the authored alpha EXACT: replacing a whole head silhouette can leave
    # old fringe tips or cut holes around raised hands. This is texture reuse,
    # not a whole-head replacement or a runtime optical-flow filter.
    source = unpremultiply(mapped)
    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow.setFinestScale(0)
    field = flow.calc(gray(target), gray(source), None)
    field = cv2.GaussianBlur(field, (13, 13), 3)
    warped = unpremultiply(cv2.remap(mapped, xx+field[:, :, 0], yy+field[:, :, 1],
                                   cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT))
    # Warm skin, dark facial features and white highlights remain authored.
    # The finite head mask excludes all lower hair, clothing and props.
    cool_hair = (b-r > 0) & (b-g > 0)
    weight = strength*np.minimum(target[:, :, 3], warped[:, :, 3])/255*cool_hair
    result = target.copy()
    result[:, :, :3] = np.rint(target[:, :, :3]*(1-weight[:, :, None])+
                              warped[:, :, :3]*weight[:, :, None]).astype('uint8')
    result[weight == 0] = target[weight == 0]
    assert np.array_equal(result[:, :, 3], target[:, :, 3])
    return result, weight


def stage():
    audit = json.loads((ROOT.parent/'.electron-build/character-consistency/head-audit/proposals.json').read_text())
    reference = np.array(Image.open(ROOT/'assets/living-idle/open.png').convert('RGBA').crop((0, 0, 256, 256)))
    base = propose(reference)
    base_points = np.float32(base['eyes']+[base['crown']])
    overrides = json.loads(OVERRIDES.read_text(encoding='utf-8')) if OVERRIDES.exists() else {}
    records = []
    for item in audit:
        ref = item['ref']
        key, frame = ref.split(':')
        points = item.get('eyes', [])+[item['crown']] if 'crown' in item else []
        if ref in overrides:
            points = overrides[ref]['points']
        record = dict(ref=ref, aliases=item['aliases'], sha256=item['sha256'], status='preserve')
        if key in PRESERVE or int(frame) in PRESERVE_FRAMES.get(key, set()):
            record['reason'] = 'view-specific hair or authored occlusion/deformation'
        elif not points or (ref not in overrides and
                            (abs(item['angle']) > 32 or not 52 <= item['depth'] <= 89)):
            record['reason'] = 'landmarks require individual review'
        else:
            matrix = cv2.getAffineTransform(base_points, np.float32(points))
            scales = np.linalg.svd(matrix[:, :2], compute_uv=False)
            if min(scales) < .72 or max(scales) > 1.4:
                record['reason'] = 'unsafe frontal head fit'
            else:
                record.update(status='proposed', transform=matrix.tolist())
                if ref in overrides:
                    record['landmark_review'] = overrides[ref]['reason']
                relative = Path(f'actions/{key}/{int(frame)+1:02d}.png')
                path = original(relative)
                if digest(path) != item['sha256']:
                    raise ValueError(f'Changed source: {ref}')
                target = np.array(Image.open(path).convert('RGBA'))
                result, mask = correction(target, matrix, reference)
                out = STAGE/relative
                out.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(result).save(out)
                record['outside_mask_exact'] = bool(np.array_equal(result[mask == 0], target[mask == 0]))
                record['alpha_exact'] = bool(np.array_equal(result[:, :, 3], target[:, :, 3]))
                record['staged_sha256'] = digest(out)
        records.append(record)
    profile = dict(version=2, approved=False, reference_sha256=digest(ROOT/'assets/living-idle/open.png'),
                   method='shared-crown-texture-local-registration-original-alpha', records=records)
    PROFILE.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    review(profile)
    print(f"Staged {sum(r['status'] == 'proposed' for r in records)} unique poses; profile unapproved")


def review(profile):
    records = [r for r in profile['records'] if 'transform' in r]
    for page in range(0, len(records), 24):
        sheet = Image.new('RGB', (1536, 6*214), '#e8eff6')
        draw = ImageDraw.Draw(sheet)
        for i, item in enumerate(records[page:page+24]):
            key, frame = item['ref'].split(':')
            relative = Path(f'actions/{key}/{int(frame)+1:02d}.png')
            x, y = i % 4*384, i//4*214
            draw.text((x+3, y+3), f"{page+i}: {item['ref']} original / shared", fill='#315273')
            for dx, path in ((0, original(relative)), (192, STAGE/relative)):
                sprite = Image.open(path).convert('RGBA').resize((192, 192), Image.Resampling.LANCZOS)
                sheet.paste(sprite, (x+dx, y+21), sprite)
        sheet.save(WORK/f'staged-review-{page//24+1}.jpg', quality=95)


def apply(profile):
    if not profile.get('approved'):
        raise ValueError('Stage and visually approve profile before applying')
    if digest(ROOT/'assets/living-idle/open.png') != profile['reference_sha256']:
        raise ValueError('Canonical source changed')
    writes, actions = [], set()
    for record in profile['records']:
        if record['status'] != 'approved':
            continue
        key, frame = record['ref'].split(':')
        staged = STAGE/f'actions/{key}/{int(frame)+1:02d}.png'
        if digest(staged) != record['staged_sha256']:
            raise ValueError(f'Staged image changed after review: {record["ref"]}')
        for ref in [record['ref']]+record['aliases']:
            name, index = ref.split(':')
            relative = Path(f'actions/{name}/{int(index)+1:02d}.png')
            if digest(original(relative)) != record['sha256']:
                raise ValueError(f'Original changed: {ref}')
            writes.append((relative, staged))
            actions.add(name)
    # Validate all inputs before any mutation. Keep original atlases/posters as
    # well, so the accepted version is reversible and rebuilding is idempotent.
    for relative, staged in writes:
        backup = BACKUP/relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        target = ROOT/'assets'/relative
        if not backup.exists():
            shutil.copy2(target, backup)
        shutil.copy2(staged, target)
    catalog = json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
    for action in catalog:
        if action['id'] not in actions:
            continue
        relative = Path('actions')/action['id']
        folder = ROOT/'assets'/relative
        for name in ('atlas.png', 'poster.png'):
            backup = BACKUP/relative/name
            if (folder/name).exists() and not backup.exists():
                shutil.copy2(folder/name, backup)
        atlas = Image.new('RGBA', (action['columns']*256,
                                ((action['frames']+action['columns']-1)//action['columns'])*256))
        for index in range(action['frames']):
            with Image.open(folder/f'{index+1:02d}.png') as frame:
                atlas.paste(frame, (index % action['columns']*256, index//action['columns']*256))
        atlas.save(folder/'atlas.png', optimize=True)
        shutil.copy2(folder/'01.png', folder/'poster.png')
    (WORK/'applied.json').write_text(json.dumps(dict(frames=len(writes), actions=sorted(actions)), indent=2), encoding='utf-8')
    print(f'Applied {len(writes)} frames across {len(actions)} actions. Rebuild inbetweens and alignment next.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        apply(json.loads(PROFILE.read_text(encoding='utf-8')))
    else:
        stage()
