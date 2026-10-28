"""Bake approved eye expressions on one stable sleep drawing, without online calls.

The generated key sheet varies its pillow/hair between cells. Reuse the approved
sleep master for those regions and transplant only the approved eye expressions.
Small smooth deformation lowers/lifts the head; the pillow remains pixel exact.
"""
import json
import math
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'action-work/sleep-v3-preview'
sys.path.insert(0, str(WORK))
from prepare_sleep_master import cutout

SIZE = (340, 328)
FPS = 60
SETTLE_SECONDS = 1.6
WAKE_SECONDS = 1.0
# Runtime playback can breathe slower than the baked 60 fps motion without
# regenerating the approved frame sequence.
PLAYBACK = {'settle': 2.1, 'wake': 1.5, 'wake_hold': .25}


def smooth(t):
    t = np.clip(t, 0., 1.)
    return t*t*t*(t*(t*6-15)+10)


def premul(image):
    raw = np.array(image).astype('float32')
    raw[:, :, :3] *= raw[:, :, 3:4]/255
    return raw


def unpremul(raw):
    raw = raw.copy()
    raw[:, :, :3] = np.divide(raw[:, :, :3]*255, raw[:, :, 3:4],
                              out=np.zeros_like(raw[:, :, :3]), where=raw[:, :, 3:4] > 0)
    return Image.fromarray(np.rint(np.clip(raw, 0, 255)).astype('uint8'))


def expression(master, raw, index, source_lids):
    source = cutout(raw.crop((index % 3*512, index//3*512,
                             index % 3*512+512, index//3*512+512)))
    # Eye-line anchors, not face bounding boxes: do not drag the hair/pillow
    # along with the generated face or let its head-size differences leak in.
    a, b = np.array(source_lids, dtype='float32')
    d = b-a
    src = np.array([a, b, a+[-d[1], d[0]]], dtype='float32')
    a, b = np.array([(411, 239), (459, 273)], dtype='float32')
    d = b-a
    dst = np.array([a, b, a+[-d[1], d[0]]], dtype='float32')
    transform = cv2.getAffineTransform(src, dst)
    warped = cv2.warpAffine(premul(source), transform, master.size,
                            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    yy, xx = np.mgrid[:master.height, :master.width].astype('float32')
    mask = np.zeros((master.height, master.width), dtype='float32')
    for cx, cy, rx, ry in [(412, 249, 27, 19), (460, 280, 11, 14)]:
        u = (xx-cx)*.82+(yy-cy)*.57
        v = -(xx-cx)*.57+(yy-cy)*.82
        radius = np.sqrt((u/rx)**2+(v/ry)**2)
        mask = np.maximum(mask, 1-smooth((radius-.72)/.28))
    mask *= (warped[:, :, 3] > 250)
    base = premul(master)
    return unpremul(base*(1-mask[:, :, None])+warped*mask[:, :, None])


class EyeMorph:
    def __init__(self, first, last):
        # Only a small face patch changes. Its textures travel together under
        # bidirectional flow, rather than overlaying two different eyelids.
        self.first, self.last = first, last
        self.box = (378, 213, 481, 305)
        self.a = premul(first.crop(self.box))
        self.b = premul(last.crop(self.box))
        def gray(raw):
            return cv2.cvtColor(np.uint8(np.clip(raw[:, :, :3], 0, 255)), cv2.COLOR_RGB2GRAY)
        flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        flow.setFinestScale(0)
        self.ab = cv2.GaussianBlur(flow.calc(gray(self.a), gray(self.b), None), (0, 0), 1.8)
        self.ba = cv2.GaussianBlur(flow.calc(gray(self.b), gray(self.a), None), (0, 0), 1.8)
        self.yy, self.xx = np.mgrid[:self.a.shape[0], :self.a.shape[1]].astype('float32')
        # The patch border must remain identical to the canonical drawing.
        edge = np.minimum.reduce([self.xx, self.yy,
                                  self.xx.shape[1]-1-self.xx, self.xx.shape[0]-1-self.yy])
        weight = smooth(edge/10)[:, :, None]
        self.ab *= weight
        self.ba *= weight

    def warp(self, raw, field, amount):
        mx, my = self.xx.copy(), self.yy.copy()
        for _ in range(8):
            sampled = cv2.remap(field, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            mx = mx*.25+(self.xx-amount*sampled[:, :, 0])*.75
            my = my*.25+(self.yy-amount*sampled[:, :, 1])*.75
        return cv2.remap(raw, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def frame(self, t):
        if t <= 0:
            return self.first.copy()
        if t >= 1:
            return self.last.copy()
        raw = self.warp(self.a, self.ab, t)*(1-t)+self.warp(self.b, self.ba, 1-t)*t
        result = self.first.copy()
        result.paste(unpremul(raw), self.box[:2])
        return result


def head_lift(image, amount):
    if amount <= 0:
        return image
    h, w = image.height, image.width
    yy, xx = np.mgrid[:h, :w].astype('float32')
    head = np.exp(-((xx-430)/115)**2-((yy-180)/145)**2)
    # Zero deformation below the cheek: no pillow or lower hair movement.
    head *= 1-smooth((yy-275)/40)
    dx = -1.8*amount*head
    dy = -7*amount*head
    return unpremul(cv2.remap(premul(image), xx-dx, yy-dy, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT))


def main():
    cv2.setNumThreads(1)
    master = Image.open(WORK/'sleep-right-02-master.png').convert('RGBA')
    raw = Image.open(WORK/'sleep-transitions-v2-raw.png')
    half = expression(master, raw, 0, [(288, 222), (345, 239)])
    opened = expression(master, raw, 5, [(280, 190), (335, 211)])
    closing = EyeMorph(half, master)
    opening = EyeMorph(master, half)
    alert = EyeMorph(half, opened)
    folder = ROOT/'assets/sleep/transitions'
    folder.mkdir(parents=True, exist_ok=True)
    sequences = {}
    for name, seconds in [('settle', SETTLE_SECONDS), ('wake', WAKE_SECONDS)]:
        frames = []
        for i in range(round(seconds*FPS)+1):
            t = i/(seconds*FPS)
            if name == 'settle':
                # Hold the sleepy look briefly, then slowly close and settle.
                image = closing.frame(float(smooth((t-.12)/.70)))
                lift = .75*(1-float(smooth(t)))
            else:
                if t < .6:
                    image = opening.frame(float(smooth(t/.6)))
                else:
                    image = alert.frame(float(smooth((t-.6)/.4)))
                lift = float(smooth(t))
            image = head_lift(image, lift).resize(SIZE, Image.Resampling.LANCZOS)
            image.save(folder/f'{name}-{i:03}.png')
            frames.append(image)
        sequences[name] = frames
    manifest = {'version': 1, 'fps': FPS, 'size': list(SIZE),
                'settle': {'count': len(sequences['settle']), 'seconds': SETTLE_SECONDS},
                'wake': {'count': len(sequences['wake']), 'seconds': WAKE_SECONDS},
                'playback': PLAYBACK,
                'source': 'Approved sleep-transitions-v2 eyes on sleep-right-02-master',
                'pillow': 'Unpatterned master; fixed throughout all sequences'}
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    # Deliver an honest 30 fps viewing copy; production PNGs are sampled at 60.
    preview = []
    order = (sequences['settle']+[sequences['settle'][-1]]*90+sequences['wake'])
    for index, im in enumerate(order[::2]):
        canvas = Image.new('RGB', (480, 420), '#eff4fc')
        ImageDraw.Draw(canvas).text((25, 18), 'YUKI / settle - sleep - wake', fill='#384d74')
        canvas.paste(im, (70, 65), im)
        preview.append(canvas)
    preview[0].save(WORK/'sleep-transitions-applied.gif', save_all=True,
                    append_images=preview[1:], duration=33, loop=0, disposal=2)
    sheet = Image.new('RGB', (340*4, 368*2), '#eff4fc')
    draw = ImageDraw.Draw(sheet)
    for row, name in enumerate(('settle', 'wake')):
        frames = sequences[name]
        for col, t in enumerate((0, .35, .7, 1)):
            im = frames[round(t*(len(frames)-1))]
            sheet.paste(im, (col*340, row*368+30), im)
            draw.text((col*340+10, row*368+8), f'{name} {t:.2f}', fill='#384d74')
    sheet.save(WORK/'sleep-transitions-applied.jpg')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
