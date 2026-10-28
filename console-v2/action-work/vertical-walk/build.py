"""Build the vertical walk masters, leg layers and QA previews."""
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
SCALE = max(1, int(os.environ.get('VERTICAL_WALK_SCALE', '1')))
CANVAS = 256 * SCALE
BODY_HEIGHT = 231 * SCALE
BASELINE = 249 * SCALE
CENTER = 128 * SCALE
LIFT = 12.0 * SCALE
OUTWARD = 0.9 * SCALE
TILT = 2.0
BOB = 1.4 * SCALE
BODY_DROP = 3.2 * SCALE
ROLL = 2.4
SWAY = 5.0 * SCALE
STRIDE = 48.0
FRAMES = 75
FRAME_MS = 20
SHADOW = (45, 73, 98)
FONT = 'C:/Windows/Fonts/msyh.ttc'


SESSION = None


def cutout(path):
    """Use an anime matting model; the pale background is too close to the
    white hair for colour keying to be safe."""
    global SESSION
    path = Path(path)
    matte = path.with_name(f'{path.stem}-matte.png')
    if not matte.exists() or matte.stat().st_mtime < path.stat().st_mtime:
        from rembg import new_session, remove
        SESSION = SESSION or new_session('isnet-anime')
        image = Image.open(path).convert('RGB')
        remove(image, session=SESSION, post_process_mask=True).save(matte)
    rgb = np.asarray(Image.open(path).convert('RGB'))
    alpha = np.asarray(Image.open(matte).convert('RGBA'))[:, :, 3]
    rgba = np.dstack([rgb, alpha])
    return Image.fromarray(rgba, 'RGBA')


def normalize(image):
    box = image.getchannel('A').getbbox()
    cut = image.crop(box)
    scale = BODY_HEIGHT / cut.height
    size = (max(1, round(cut.width * scale)), BODY_HEIGHT)
    cut = cut.resize(size, Image.Resampling.LANCZOS)
    frame = Image.new('RGBA', (CANVAS, CANVAS))
    frame.alpha_composite(cut, (CENTER - cut.width // 2, BASELINE - cut.height))
    return frame


def row_runs(mask, y):
    row = mask[y] > 0
    runs, start = [], None
    for x, value in enumerate(row):
        if value and start is None:
            start = x
        elif not value and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, len(row)))
    return runs


def leg_analysis(image):
    alpha = np.array(image.getchannel('A')) > 200
    lowest = max(y for y in range(CANVAS) if alpha[y].any())
    candidates = []
    min_width, max_width = 8 * SCALE, 30 * SCALE
    min_gap, max_span = 2 * SCALE, 70 * SCALE
    for y in range(190 * SCALE, lowest + 1):
        runs = [(a, b) for a, b in row_runs(alpha, y) if b - a >= min_width]
        if len(runs) != 2:
            continue
        if any(b - a > max_width for a, b in runs):
            continue
        if runs[1][0] - runs[0][1] < min_gap or runs[1][1] - runs[0][0] > max_span:
            continue
        candidates.append((y, runs))
    if not candidates:
        raise ValueError('无法找到裙摆下的双腿分离线')
    groups = []
    for item in candidates:
        if groups and item[0] - groups[-1][-1][0] <= 4:
            groups[-1].append(item)
        else:
            groups.append([item])
    groups = [group for group in groups if len(group) >= 6]
    if not groups:
        raise ValueError('双腿分离区间过短')
    band = max(groups, key=lambda group: group[-1][0])
    initial_cut, runs = band[0]
    split_x = (sum(runs[0]) / 2 + sum(runs[1]) / 2) / 2
    lower = alpha.copy()
    lower[:initial_cut] = False
    masks = [lower.copy(), lower.copy()]
    masks[0][:, round(split_x):] = False
    masks[1][:, :round(split_x)] = False
    rgba = np.array(image)
    sock_top = None
    for y in range(initial_cut, min(CANVAS, initial_cut + 32 * SCALE)):
        sock_scores, skin_scores = [], []
        for mask in masks:
            xs = np.where(mask[y])[0]
            if len(xs) < 3:
                continue
            pixels = rgba[y, xs, :3].astype(int)
            skin_scores.append(((pixels[:, 0] > pixels[:, 1] + 3)
                                & (pixels[:, 0] > pixels[:, 2] + 5)).mean())
            sock_scores.append(((pixels[:, 2] >= pixels[:, 0] - 3)
                                & (pixels.min(axis=1) > 228)).mean())
        if sock_scores and sum(sock_scores) / len(sock_scores) >= .5:
            if not skin_scores or sum(skin_scores) / len(skin_scores) < .2:
                sock_top = y
                break
    # Split at the sock top so the thigh stays in the body and the sock rolls
    # up and down beneath it. The body's permanent downward bias covers the
    # moving leg's cut edge.
    cut_y = sock_top if sock_top is not None else initial_cut
    # Close-stance masters can merge above the shoes, leaving only the shoe
    # split visible. Keep at least a 28 px lower-leg span for the rig.
    cut_y = min(cut_y, BASELINE - 28 * SCALE)
    lower = alpha.copy()
    lower[:cut_y] = False
    masks = [lower.copy(), lower.copy()]
    masks[0][:, round(split_x):] = False
    masks[1][:, :round(split_x)] = False
    legs = []
    for index, mask in enumerate(masks):
        ys, xs = np.where(mask)
        if len(xs) < 20:
            raise ValueError('脚部图层为空')
        legs.append(dict(box=(int(xs.min()), int(ys.min()),
                              int(xs.max() + 1), int(ys.max() + 1)),
                         area=int(len(xs)),
                         center=[float(xs.mean()), float(ys.mean())]))
    return cut_y, split_x, legs, masks


def make_layers(image, cut_y, masks):
    rgba = np.array(image)
    body = rgba.copy()
    body[cut_y:, :, 3] = 0
    layers = []
    for mask in masks:
        leg = np.zeros_like(rgba)
        leg[mask] = rgba[mask]
        ys, xs = np.where(mask)
        bottom = int(ys.max())
        sole = xs[ys >= bottom - 1]
        layers.append(dict(image=Image.fromarray(leg, 'RGBA'),
                           foot_x=float(sole.mean()), bottom=bottom,
                           pivot=(float(sole.mean()), float(cut_y))))
    return Image.fromarray(body, 'RGBA'), layers


def pose(t, energy=1.):
    result = []
    for index in range(2):
        p = (t + (0. if index == 0 else .5)) % 1.
        if p < .5:
            result.append((0., 0., 0., 0.))
            continue
        u = (p - .5) / .5
        lift = (1 - math.cos(math.pi * u) ** 6) * energy
        side = -1. if index == 0 else 1.
        wave = math.sin(math.pi * u)
        # A rigid lower-leg rock around the sock top keeps the swing from
        # reading as a shoe sliding straight up and down. PIL rotates
        # counter-clockwise, so the outward sign is the leg side.
        result.append((side * TILT * wave * energy,
                       side * OUTWARD * wave * wave * energy,
                       -LIFT * lift, lift))
    return result


def render(body, layers, t, shadows=True):
    frame = Image.new('RGBA', (CANVAS, CANVAS))
    moves = pose(t)
    if shadows:
        shadow = Image.new('RGBA', frame.size)
        draw = ImageDraw.Draw(shadow)
        for index, (layer, move) in enumerate(zip(layers, moves)):
            angle, dx, _, lift = move
            width = (28. - 5. * lift) * SCALE
            height = (4.3 - .7 * lift) * SCALE
            alpha = int((27 if index == 0 else 24) * (1. - .45 * lift))
            cx = layer['foot_x'] + dx * .75
            draw.ellipse((cx - width / 2, BASELINE - height - 1.2 * SCALE,
                          cx + width / 2, BASELINE - 1.2 * SCALE),
                         fill=SHADOW + (alpha,))
        frame.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(1.3 * SCALE)))
    for layer, move in zip(layers, moves):
        angle, dx, dy, _ = move
        if angle:
            leg = layer['image'].rotate(
                angle, resample=Image.Resampling.BICUBIC,
                center=layer['pivot'], fillcolor=(0, 0, 0, 0))
        else:
            leg = layer['image']
        frame.alpha_composite(leg, (round(dx), round(dy)))
    bob = BODY_DROP - BOB * (1 - math.cos(4 * math.pi * t))
    planted = [1. - move[3] for move in moves]
    total = sum(planted)
    shift = (planted[1] - planted[0]) / total if total else 0.
    sway = SWAY * shift
    angle = -ROLL * shift
    turned = body.rotate(angle, resample=Image.Resampling.BICUBIC,
                         center=(CENTER, 205 * SCALE), fillcolor=(0, 0, 0, 0))
    frame.alpha_composite(turned, (round(sway), round(bob)))
    return frame


def label(draw, xy, text, size=18, fill='#dfe8f2'):
    draw.text(xy, text, font=ImageFont.truetype(FONT, size), fill=fill)


def contact_sheet(rendered, output, dark=True):
    columns = 8
    cell = 256
    top = 42
    background = '#243444' if dark else '#eef4fa'
    text = '#dfe8f2' if dark else '#243444'
    sheet = Image.new('RGB', (cell * columns, top * 2 + cell * 2), background)
    draw = ImageDraw.Draw(sheet)
    for row, (name, frames) in enumerate(rendered.items()):
        label(draw, (12, row * (top + cell) + 10),
              '向上走 · 背身' if name == 'up' else '向下走 · 正身', 20, text)
        y = row * (top + cell) + top
        for column, frame in enumerate(frames):
            tile = Image.new('RGBA', (cell, cell),
                             background if not dark else '#1d2b38')
            tile.alpha_composite(frame)
            sheet.paste(tile.convert('RGB'), (column * cell, y))
            label(draw, (column * cell + 8, y + 6), f'{column}/8', 13, '#9fb3c8')
    sheet.save(output)


def preview_gif(rendered, output):
    width, height = 660, 344
    frames = []
    for index in range(FRAMES):
        t = index / FRAMES
        canvas = Image.new('RGB', (width, height), '#2a3b4d')
        draw = ImageDraw.Draw(canvas)
        for column, (name, label_text) in enumerate(
                (('up', '向上 · 背身'), ('down', '向下 · 正身'))):
            x0 = 20 + column * 320
            draw.rounded_rectangle((x0, 42, x0 + 300, 330), radius=18,
                                   fill='#344a60', outline='#48627b')
            draw.line((x0 + 150, 294, x0 + 150, 76), fill='#5f7f9c', width=2)
            arrow = [(x0 + 150, 68), (x0 + 143, 82), (x0 + 157, 82)]
            draw.polygon(arrow, fill='#8fb5d1')
            label(draw, (x0 + 18, 12), label_text, 20, '#eef5fb')
            frame = render(*rendered[name], t)
            canvas.paste(frame.convert('RGB'), (x0 + 22, 60), frame)
        frames.append(canvas)
    frames[0].save(output, save_all=True, append_images=frames[1:],
                   duration=FRAME_MS, loop=0, optimize=True)


def main():
    normalized = {}
    metadata = {}
    all_layers = {}
    for name in ('up', 'down'):
        image = normalize(cutout(ROOT / 'raw' / f'{name}-master.png'))
        image.save(ROOT / 'normalized' / f'{name}.png')
        normalized[name] = image
        cut_y, split_x, legs, masks = leg_analysis(image)
        body, layers = make_layers(image, cut_y, masks)
        all_layers[name] = dict(body=body, layers=layers)
        body.save(ROOT / 'normalized' / f'{name}-body.png')
        for index, layer in enumerate(layers):
            layer['image'].save(ROOT / 'normalized' / f'{name}-leg-{index}.png')
        metadata[name] = dict(cut_y=cut_y, split_x=split_x, legs=legs,
                              feet=[round(layer['foot_x'], 2) for layer in layers],
                              pivots=[[round(v, 2) for v in layer['pivot']]
                                      for layer in layers],
                              baseline=BASELINE, body_height=BODY_HEIGHT,
                              stride=STRIDE * SCALE, source_scale=SCALE,
                              lift=LIFT, outward=OUTWARD, tilt=TILT,
                              bob=BOB, body_drop=BODY_DROP, roll=ROLL,
                              sway=SWAY, frames=FRAMES, frame_ms=FRAME_MS,
                              method='sock-cut-body-drop-rig-v2')
        print(name, 'cut_y', cut_y, 'split_x', round(split_x, 2),
              'feet', [round(layer['foot_x'], 1) for layer in layers])
        overlay = image.copy()
        draw = ImageDraw.Draw(overlay)
        draw.line((0, cut_y, CANVAS, cut_y), fill='#ff3366', width=1)
        draw.line((round(split_x), cut_y, round(split_x), CANVAS),
                  fill='#ff3366', width=1)
        colors = [(0, 229, 255), (255, 212, 0)]
        for index, leg in enumerate(legs):
            x0, y0, x1, y1 = leg['box']
            draw.rectangle((x0, y0, x1 - 1, y1 - 1),
                           outline=colors[index % len(colors)])
            tint = Image.new('RGBA', image.size, colors[index % len(colors)] + (90,))
            tint.putalpha(Image.fromarray((masks[index] * 90).astype(np.uint8)))
            overlay.alpha_composite(tint)
        for x in range(0, CANVAS, 16):
            draw.line((x, 0, x, CANVAS), fill=(255, 255, 255, 28))
        for y in range(0, CANVAS, 16):
            draw.line((0, y, CANVAS, y), fill=(255, 255, 255, 28))
        overlay.resize((CANVAS * 3, CANVAS * 3), Image.Resampling.NEAREST).save(
            ROOT / 'qa' / f'{name}-grid.png')
        contact = Image.new('RGB', (CANVAS * 2, CANVAS * 2 + 30), '#263747')
        cdraw = ImageDraw.Draw(contact)
        label(cdraw, (12, 6), 'UP · back view' if name == 'up' else 'DOWN · front view')
        contact.paste(image.resize((CANVAS * 2, CANVAS * 2), Image.Resampling.NEAREST)
                      .convert('RGB'), (0, 30))
        contact.save(ROOT / 'qa' / f'{name}-normalized.png')

    rendered = {}
    for name in ('up', 'down'):
        frames = [render(all_layers[name]['body'], all_layers[name]['layers'],
                         index / FRAMES) for index in range(FRAMES)]
        rendered[name] = frames
        folder = ROOT / 'preview' / f'walk-{name}'
        folder.mkdir(parents=True, exist_ok=True)
        for index, frame in enumerate(frames):
            frame.save(folder / f'{index:02}.png')
        rendered[name] = frames
    contact_sheet({name: [frames[i] for i in range(0, FRAMES, FRAMES // 8)]
                   for name, frames in rendered.items()},
                  ROOT / 'qa' / 'contact-dark.png', dark=True)
    contact_sheet({name: [frames[i] for i in range(0, FRAMES, FRAMES // 8)]
                   for name, frames in rendered.items()},
                  ROOT / 'qa' / 'contact-light.png', dark=False)
    preview_gif({name: (all_layers[name]['body'], all_layers[name]['layers'])
                 for name in ('up', 'down')},
                ROOT / 'preview' / 'vertical-walk.gif')
    (ROOT / 'layers.json').write_text(json.dumps(metadata, ensure_ascii=False,
                                                 indent=2) + '\n',
                                      encoding='utf-8')


if __name__ == '__main__':
    main()
