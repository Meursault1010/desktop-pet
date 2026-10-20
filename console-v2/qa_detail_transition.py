"""Review-only alternative to hard source switching; never writes shipped assets."""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from build_action_inbetweens import gray, premultiply, unpremultiply

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent / '.electron-build/character-consistency'


def coherent_frames(a, b, count=25):
    flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    flow.setFinestScale(0)
    flow.setGradientDescentIterations(64)
    flow.setVariationalRefinementIterations(30)
    ab = flow.calc(gray(a), gray(b), None)
    ba = flow.calc(gray(b), gray(a), None)
    # Subpixel linework must travel with the surrounding hair mass. A local
    # flow spike should not pull a single strand, eye or snowflake apart.
    ab = cv2.GaussianBlur(ab, (0, 0), 2.0)
    ba = cv2.GaussianBlur(ba, (0, 0), 2.0)
    yy, xx = np.mgrid[:256, :256].astype(np.float32)

    def inverse_warp(image, field, amount):
        mx, my = xx.copy(), yy.copy()
        for _ in range(12):
            sampled = cv2.remap(field, mx, my, cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)
            mx = mx*.25+(xx-amount*sampled[:, :, 0])*.75
            my = my*.25+(yy-amount*sampled[:, :, 1])*.75
        return cv2.remap(image, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    pa, pb = premultiply(a), premultiply(b)
    result = [a]
    for i in range(1, count-1):
        t = i/(count-1)
        left = inverse_warp(pa, ab, t)
        right = inverse_warp(pb, ba, 1-t)
        # Both textures change gradually in aligned coordinates, instead of
        # replacing all hair/face details on a single middle frame.
        result.append(unpremultiply(left*(1-t)+right*t))
    return result+[b]


def main():
    cv2.setNumThreads(1)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    actions = {a['id']: a for a in json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8'))}
    manifest = json.loads((ROOT/'assets/action-motion/manifest.json').read_text())['pairs']
    report = []
    for name, first, last in [('wait', 0, 1), ('comb', 0, 1), ('yawn', 2, 3), ('sit-neat', 1, 2)]:
        atlas = Image.open(ROOT/'assets'/actions[name]['atlas']).convert('RGBA')
        columns = actions[name]['columns']
        def crop(index):
            x, y = index % columns*256, index//columns*256
            return np.array(atlas.crop((x, y, x+256, y+256)))
        a, b = crop(first), crop(last)
        frames = coherent_frames(a, b)
        entry = manifest[f'{name}:{first}>{name}:{last}']
        old = Image.open(ROOT/'assets/action-motion'/entry['file']).convert('RGBA')
        current = [np.array(old.crop((i % entry['columns']*256, i//entry['columns']*256,
                    i % entry['columns']*256+256, i//entry['columns']*256+256))) for i in range(25)]
        def metric(sequence):
            p = [premultiply(frame) for frame in sequence]
            return round(max(float(np.abs(x-y).mean()) for x, y in zip(p, p[1:])), 4)
        report.append({'action': name, 'pair': [first, last], 'whole_canvas_step_current': metric(current),
                       'whole_canvas_step_candidate': metric(frames)})
        paired = []
        for left, right in zip(current, frames):
            canvas = Image.new('RGB', (540, 290), '#e8eff6')
            d = ImageDraw.Draw(canvas)
            d.text((16, 8), f'{name}: current', fill='#315273')
            d.text((286, 8), 'Candidate (not applied)', fill='#315273')
            for x, raw in [(7, left), (277, right)]:
                sprite = Image.fromarray(raw)
                canvas.paste(sprite, (x, 30), sprite)
            paired.append(canvas)
        # A slow diagnostic preview exposes defects; not proposed clip timing.
        sequence = [paired[0]]*10+paired+[paired[-1]]*10+list(reversed(paired))
        sequence[0].save(OUTPUT/f'{name}-detail-review.gif', save_all=True,
                         append_images=sequence[1:], duration=45, loop=0)
        sheet = Image.new('RGB', (1280, 600), '#e8eff6')
        d = ImageDraw.Draw(sheet)
        for row, sequence in enumerate((current, frames)):
            d.text((8, row*300+5), 'Current' if row == 0 else 'Candidate', fill='#315273')
            for col, i in enumerate((0, 10, 12, 15, 24)):
                sprite = Image.fromarray(sequence[i])
                sheet.paste(sprite, (col*256, row*300+30), sprite)
        sheet.save(OUTPUT/f'{name}-detail-review.png')
    (OUTPUT/'transition-review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
