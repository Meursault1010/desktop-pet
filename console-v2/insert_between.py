"""Turn a generated 4-cell pose strip into insertable 256px in-betweens.

Keeps the character scale/baseline of the key poses, corrects only the global
colour offset (no contrast stretch, which washed the art out), then matches the
key poses' edge strength and semi-transparent edge share so the joins read as
one drawing.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from skimage.color import lab2rgb, rgb2lab

ROOT = Path(__file__).resolve().parent


_SESSION = None


def cut(image, tolerance=55):
    """White hair on a white background needs the anime matting model."""
    global _SESSION
    from rembg import new_session, remove
    if _SESSION is None:
        _SESSION = new_session('isnet-anime')
    out = remove(image.convert('RGB'), session=_SESSION, post_process_mask=True).convert('RGBA')
    ys, xs = np.where(np.asarray(out)[:, :, 3] > 24)
    return out.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def fit(frame, height, base, centre=128):
    scaled = frame.resize((max(1, round(frame.width * height / frame.height)), height), Image.LANCZOS)
    out = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    alpha = np.asarray(scaled)[:, :, 3]
    ys, xs = np.where(alpha > 40)
    out.alpha_composite(scaled, (round(centre - (xs.min() + xs.max()) / 2), base - height + 1))
    return out


def edges(frame):
    a = np.asarray(frame).astype(np.float32) / 255
    alpha = a[:, :, 3]
    lum = (a[:, :, :3] * alpha[..., None] + 0.95 * (1 - alpha[..., None])).mean(2)
    gy, gx = np.gradient(lum)
    solid = alpha > 0.78
    return float(np.sqrt(gy ** 2 + gx ** 2)[solid].mean() * 255)


def aa_share(frame):
    a = np.asarray(frame)[:, :, 3]
    return float(((a > 20) & (a < 235)).sum() / max(1, (a > 40).sum()))


def tone_offset(frame, reference):
    """Move the frame's mean Lab onto the reference; leave its contrast alone."""
    src = np.asarray(frame).astype(np.float32) / 255
    ref = np.asarray(reference).astype(np.float32) / 255
    sm, rm = src[:, :, 3] > 0.4, ref[:, :, 3] > 0.4
    slab, rlab = rgb2lab(src[:, :, :3]), rgb2lab(ref[:, :, :3])
    delta = rlab[rm].mean(0) - slab[sm].mean(0)
    out = np.clip(lab2rgb(slab + delta), 0, 1)
    return Image.fromarray(np.rint(np.dstack([out, src[:, :, 3]]) * 255).astype(np.uint8))


def match_sharpness(frame, target, limit=180):
    best, percent = None, 0
    for value in range(0, limit + 1, 10):
        sharp = frame if value == 0 else frame.filter(ImageFilter.UnsharpMask(radius=1.0, percent=value, threshold=2))
        score = abs(edges(sharp) - target)
        if best is None or score < best[0]:
            best, percent = (score, sharp), value
        if edges(sharp) > target:
            break
    return best[1], percent


def match_aa(frame, target):
    a = np.asarray(frame).astype(np.float32) / 255
    alpha = a[:, :, 3]
    for factor in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8):
        curve = np.clip((alpha - 0.5) * factor + 0.5, 0, 1)
        if aa_share(Image.fromarray(np.rint(np.dstack([a[:, :, :3], curve]) * 255).astype(np.uint8))) <= target:
            return Image.fromarray(np.rint(np.dstack([a[:, :, :3], curve]) * 255).astype(np.uint8)), factor
    return frame, 1.0


def main():
    strip_path, key_a, key_b, outdir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    cells = [c for c in sys.argv[5:] if not c.startswith('--')]
    ramp = next((c[7:] for c in sys.argv[5:] if c.startswith('--ramp=')), None)
    strip = Image.open(strip_path)
    key_a, key_b = Image.open(key_a).convert('RGBA'), Image.open(key_b).convert('RGBA')
    def box(frame):
        alpha = np.asarray(frame)[:, :, 3]
        ys, xs = np.where(alpha > 40)
        return ys.min(), ys.max(), xs.min(), xs.max()
    a_top, a_base, a_left, a_right = box(key_a)
    b_top, b_base, b_left, b_right = box(key_b)
    height, base = int(a_base - a_top + 1), int(a_base)
    centre_a, centre_b = (a_left + a_right) / 2, (b_left + b_right) / 2
    height_b, centre_b_floor, base_b = int(b_base - b_top + 1), centre_b, int(b_base)
    if ramp:
        steps = [float(v) / 100 for v in ramp.split(',')]
    target_edge = (edges(key_a) + edges(key_b)) / 2
    target_aa = (aa_share(key_a) + aa_share(key_b)) / 2
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    report = {'height': height, 'base': base, 'edge_target': round(target_edge, 2),
              'aa_target': round(target_aa, 4), 'frames': []}
    width = strip.width // 4
    for index, cell in enumerate(cells):
        bx = (int(cell) - 1) * width
        piece = cut(strip.crop((bx, 0, bx + width, strip.height)))
        step = steps[index] if ramp else 0.0
        local_h = round(height + (height_b - height) * step)
        local_centre = round(centre_a + (centre_b_floor - centre_a) * step)
        local_base = round(base + (base_b - base) * step)
        placed = fit(piece, local_h, local_base, local_centre)
        toned = tone_offset(placed, key_a)
        sharp, percent = match_sharpness(toned, target_edge)
        final, factor = match_aa(sharp, target_aa)
        name = f'{index + 1:02d}.png'
        final.save(out / name)
        report['frames'].append({'cell': int(cell), 'file': name, 'unsharp': percent,
                                 'aa': factor, 'edge': round(edges(final), 2),
                                 'aa_share': round(aa_share(final), 4)})
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
