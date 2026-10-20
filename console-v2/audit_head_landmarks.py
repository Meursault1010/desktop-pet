"""Propose head landmarks for offline review, never for runtime inference."""
import hashlib
import itertools
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent/'.electron-build/character-consistency/head-audit'


def propose(rgba):
    r, g, b, alpha = [rgba[:, :, i].astype(np.float32) for i in range(4)]
    skin = ((r > 210) & (g > 170) & (b > 165) & (r-b >= -2) & (r-g >= -1) & (alpha > 100)).astype('uint8')
    skin = cv2.morphologyEx(skin, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, labels, stats, centers = cv2.connectedComponentsWithStats(skin)
    faces = [(s[4], i, s, center) for i, (s, center) in enumerate(zip(stats, centers))
             if i and s[4] > 140 and s[2] > 20 and s[1] < 165 and s[2] < 110 and s[3] < 130]
    if not faces:
        return {'reason': 'no face'}
    pairs = []
    for _, label, bounds, _ in faces:
        # Try all skin contours: bright crown highlights must not displace the
        # smaller actual face. Closed eyelids use a separate conservative pass.
        contour = cv2.findNonZero((labels == label).astype('uint8'))
        hull = np.zeros(skin.shape, 'uint8')
        cv2.fillConvexPoly(hull, cv2.convexHull(contour), 1)
        hull = cv2.dilate(hull, np.ones((5, 5), np.uint8))
        for relaxed in (False, True):
            ink = ((r < 150) & (g < 150) & (b < 200)) if relaxed else ((r < 140) & (b-r > 28) & (b > 95))
            dark = (ink & (alpha > 100) & (hull > 0)).astype('uint8')
            _, _, eye_stats, eye_centers = cv2.connectedComponentsWithStats(dark)
            eyes = [(s, c) for s, c in zip(eye_stats[1:], eye_centers[1:])
                    if s[4] >= 7 and 4 <= s[2] <= 23 and s[3] <= 20]
            for (sa, ca), (sb, cb) in itertools.combinations(eyes, 2):
                left, right = sorted((ca, cb), key=lambda c: c[0])
                distance = np.linalg.norm(right-left)
                eye_y = (left[1]+right[1])/2
                if (22 < distance < 48 and abs(right[1]-left[1]) < distance*.65
                        and bounds[1]+bounds[3]*.13 <= eye_y <= bounds[1]+bounds[3]*.50):
                    score = float(sa[4]+sb[4])-abs(right[1]-left[1])*2-(75 if relaxed else 0)
                    pairs.append((score, left, right, bounds, relaxed))
    if not pairs:
        return {'reason': 'no reliable eye pair'}
    _, left, right, bounds, relaxed = max(pairs, key=lambda p: p[0])
    x, y, w, h, _ = [int(v) for v in bounds]
    eye_mid = (left+right)/2
    angle = float(np.degrees(np.arctan2(*(right-left)[::-1])))
    # Crown is a measurement along the head's local up direction. Restrict
    # the ray to the scalp, not raised hands or hair trailing to the sides.
    across = (right-left)/np.linalg.norm(right-left)
    up = np.array([across[1], -across[0]])
    points = []
    for step in range(25, 105):
        pos = eye_mid+up*step
        px, py = np.rint(pos).astype(int)
        if 1 <= px < 255 and 1 <= py < 255 and alpha[py, px] > 80:
            points.append((step, pos))
    if not points:
        return {'reason': 'no crown', 'face': [x, y, w, h]}
    depth, crown = max(points, key=lambda p: p[0])
    return {'eyes': [left.tolist(), right.tolist()], 'crown': crown.tolist(),
            'angle': round(angle, 2), 'face': [x, y, w, h], 'depth': depth,
            'closed_eye_candidate': relaxed,
            'reason': 'proposal; review required'}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))
    records, seen = [], {}
    for action in catalog:
        for index in range(action['frames']):
            path = ROOT/f"assets/actions/{action['id']}/{index+1:02d}.png"
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in seen:
                seen[digest]['aliases'].append(f"{action['id']}:{index}")
                continue
            rgba = np.array(Image.open(path).convert('RGBA'))
            record = dict(ref=f"{action['id']}:{index}", aliases=[], sha256=digest, **propose(rgba))
            records.append(record)
            seen[digest] = record
    (OUTPUT/'proposals.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    for page in range(0, len(records), 48):
        group = records[page:page+48]
        sheet = Image.new('RGB', (8*192, 6*214), '#e8eff6')
        draw = ImageDraw.Draw(sheet)
        for i, record in enumerate(group):
            action_id, index = record['ref'].split(':')
            sprite = Image.open(ROOT/f'assets/actions/{action_id}/{int(index)+1:02d}.png').convert('RGBA')
            x, y = i % 8*192, i//8*214
            sprite = sprite.resize((192, 192), Image.Resampling.LANCZOS)
            sheet.paste(sprite, (x, y+21), sprite)
            draw.text((x+2, y+3), f"{page+i}: {record['ref']}", fill='#315273')
            for point in record.get('eyes', [])+[record['crown']] if 'crown' in record else []:
                px, py = point
                cx, cy = x+px*.75, y+21+py*.75
                draw.ellipse((cx-2, cy-2, cx+2, cy+2), fill='#d62855')
        sheet.save(OUTPUT/f'heads-{page//48+1}.jpg', quality=95)
    print(f'{len(records)} unique poses; {sum("eyes" in r for r in records)} landmark proposals')


if __name__ == '__main__':
    main()
