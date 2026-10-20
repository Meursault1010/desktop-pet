"""Approval-only reuse of original crown artwork; no shipping atlas is edited.

Three hand-reviewed frontal head landmark sets are intentionally explicit.
These are NOT a detector or a mapping suitable for side/back poses.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from build_action_inbetweens import premultiply, unpremultiply

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'action-work/character-consistency'


def main():
    reference = np.array(Image.open(ROOT/'assets/living-idle/open.png').convert('RGBA').crop((0, 0, 256, 256)))
    landmarks = np.float32([(110.71, 95.71), (141.99, 95.90), (128, 24)])
    samples = {
        'comb': [(97.98, 83.84), (128.57, 83.96), (113, 15)],
        'wait': [(70.16, 80.59), (99.45, 80.69), (85, 15)],
        'yawn': [(84.14, 79.71), (115.81, 79.60), (100, 11)],
    }
    yy, xx = np.mgrid[:256, :256].astype(np.float32)
    # Only crown, ears, clip and upper side locks. No eye/face/body replacement.
    crown = np.clip((86-yy)/3, 0, 1)
    side = np.clip((np.abs(xx-128)-31)/8, 0, 1)*np.clip((136-yy)/24, 0, 1)
    region = np.maximum(crown, side).astype(np.float32)
    source = premultiply(reference)
    OUTPUT.mkdir(exist_ok=True)
    canvas = Image.new('RGB', (1152, 3*400+32), '#e8eff6')
    draw = ImageDraw.Draw(canvas)
    reports = []
    for row, (key, target_points) in enumerate(samples.items()):
        target = np.array(Image.open(ROOT/f'assets/actions/{key}/06.png').convert('RGBA'))
        transform = cv2.getAffineTransform(landmarks, np.float32(target_points))
        mapped = cv2.warpAffine(source, transform, (256, 256), flags=cv2.INTER_LINEAR)
        strength = cv2.warpAffine(region, transform, (256, 256), flags=cv2.INTER_LINEAR)
        # Only replace the approved region, including its old silhouette so a
        # narrower canonical crown cannot leave the old ears visible behind it.
        result = unpremultiply(premultiply(target)*(1-strength[:, :, None])+mapped*strength[:, :, None])
        result[strength == 0] = target[strength == 0]
        Image.fromarray(result).save(OUTPUT/f'{key}-shared-crown-sample.png')
        for col, (label, raw) in enumerate((('Canonical', reference), (key+': original', target),
                                           (key+': shared crown ONLY', result))):
            x, y = col*384, row*400
            draw.text((x+12, y+8), label, fill='#315273')
            sprite = Image.fromarray(raw).resize((384, 384), Image.Resampling.NEAREST)
            canvas.paste(sprite, (x, y+25), sprite)
        reports.append({'action': key, 'frame': 5, 'head_affine': transform.tolist(),
                        'outside_mask_exact': bool(np.array_equal(result[strength == 0], target[strength == 0])),
                        'scope': 'crown and upper side locks only; not tail/side/back repair',
                        'status': 'approval sample; not shipped'})
    canvas.save(OUTPUT/'shared-crown-review.png')
    (OUTPUT/'shared-crown-review.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
