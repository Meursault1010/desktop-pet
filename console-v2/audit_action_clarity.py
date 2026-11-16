"""Read-only quality audit for every registered action frame.

Writes metrics and contact sheets outside the runtime asset directories. The
sharpness values are relative screening signals; they are not an image-quality
score and must be confirmed visually before rebuilding any frame.
"""
import argparse
import html
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets' / 'actions'
PUBLIC = ROOT / 'frontend' / 'public' / 'actions'
DISPLAY_CELL = 320  # 160 logical px on the 2x pet-render canvas.
SHEET_COLUMNS = 5
SHEET_CELL = 196


def frame_source(action, index, atlas):
    folder = ASSETS / action['id']
    frame = folder / f'{index + 1:02d}.png'
    if frame.exists():
        return Image.open(frame).convert('RGBA'), str(frame.relative_to(ROOT))
    cell = int(action.get('cell', 256))
    columns = int(action.get('columns', 4))
    box = ((index % columns) * cell, (index // columns) * cell,
           (index % columns + 1) * cell, (index // columns + 1) * cell)
    return atlas.crop(box).convert('RGBA'), str((folder / 'atlas.png').relative_to(ROOT))


def render_preview(image):
    return image.resize((DISPLAY_CELL, DISPLAY_CELL), Image.Resampling.LANCZOS)


def sharpness_metrics(image):
    """Measure high-frequency detail on the same 320px render target."""
    rendered = render_preview(image)
    rgba = np.asarray(rendered, dtype=np.float32)
    alpha = rgba[:, :, 3] / 255.0
    # A neutral matte makes semitransparent edge pixels comparable between frames.
    background = np.full((DISPLAY_CELL, DISPLAY_CELL, 3), 224, dtype=np.float32)
    rgb = rgba[:, :, :3] * alpha[:, :, None] + background * (1 - alpha[:, :, None])
    gray = rgb[:, :, 0] * .2126 + rgb[:, :, 1] * .7152 + rgb[:, :, 2] * .0722
    mask = alpha > .65
    mask[:2] = False; mask[-2:] = False; mask[:, :2] = False; mask[:, -2:] = False
    if not np.any(mask):
        return rendered, {'laplacian_variance': 0.0, 'gradient_energy': 0.0, 'edge_pixel_ratio': 0.0}
    laplacian = np.zeros_like(gray)
    laplacian[1:-1, 1:-1] = (4 * gray[1:-1, 1:-1] - gray[:-2, 1:-1]
                              - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:])
    dx = np.zeros_like(gray); dy = np.zeros_like(gray)
    dx[:, 1:-1] = (gray[:, 2:] - gray[:, :-2]) * .5
    dy[1:-1, :] = (gray[2:, :] - gray[:-2, :]) * .5
    gradient = np.hypot(dx, dy)
    return rendered, {
        'laplacian_variance': round(float(np.var(laplacian[mask])), 4),
        'gradient_energy': round(float(np.mean(gradient[mask])), 4),
        'edge_pixel_ratio': round(float(np.mean(gradient[mask] >= 24)), 6),
    }


def atlas_checks(action, index, frame, atlas, webp):
    cell = int(action.get('cell', 256)); columns = int(action.get('columns', 4))
    box = ((index % columns) * cell, (index // columns) * cell,
           (index % columns + 1) * cell, (index // columns + 1) * cell)
    atlas_cell = atlas.crop(box).convert('RGBA')
    atlas_exact = visible_pixels_equal(atlas_cell, frame)
    webp_exact = visible_pixels_equal(webp.crop(box).convert('RGBA'), frame) if webp else None
    return atlas_exact, webp_exact


def visible_pixels_equal(left, right):
    a, b = np.asarray(left), np.asarray(right)
    visible = (a[:, :, 3] > 0) | (b[:, :, 3] > 0)
    return bool(np.array_equal(a[:, :, 3], b[:, :, 3])
                and np.array_equal(a[:, :, :3][visible], b[:, :, :3][visible]))


def robust_outlier(score, values):
    median = float(np.median(values)) if values else 0.0
    mad = float(np.median(np.abs(np.asarray(values) - median))) if values else 0.0
    relative = score / median if median > 0 else 1.0
    robust_z = .6745 * (score - median) / mad if mad > 1e-8 else 0.0
    return relative, robust_z


def make_sheet(action, previews, rows, output):
    columns = min(SHEET_COLUMNS, max(1, len(previews)))
    cell_w, cell_h = SHEET_CELL, SHEET_CELL + 22
    sheet = Image.new('RGB', (columns * cell_w,
                              math.ceil(len(previews) / columns) * cell_h), '#dce4eb')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (preview, row) in enumerate(zip(previews, rows)):
        x, y = (index % columns) * cell_w, (index // columns) * cell_h
        # Keep the render's aspect and put all frame pixels on a stable matte.
        preview.thumbnail((cell_w, cell_w), Image.Resampling.LANCZOS)
        tile = Image.new('RGB', (cell_w, cell_w), '#e0e4e8')
        tile.paste(preview.convert('RGB'), ((cell_w-preview.width)//2, (cell_w-preview.height)//2))
        sheet.paste(tile, (x, y))
        label = f"{index + 1:03d}  L{row['laplacian_variance']:.0f}  G{row['gradient_energy']:.1f}"
        draw.text((x + 4, y + cell_w + 3), label, fill='#172c3b', font=font)
    target = output / 'sheets' / f"{action['id']}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, quality=92, subsampling=0)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / '.qoder' / 'action-clarity-report')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
    actions = []
    all_frames = 0
    for action in catalog:
        rows, previews = [], []
        expected = int(action['frames'])
        action_dir = ASSETS / action['id']
        with Image.open(action_dir / 'atlas.png') as source_atlas:
            atlas = source_atlas.convert('RGBA')
        public_path = PUBLIC / action['id'] / 'atlas.webp'
        if public_path.exists():
            with Image.open(public_path) as source_webp:
                webp = source_webp.convert('RGBA')
        else:
            webp = None
        for index in range(expected):
            frame, source = frame_source(action, index, atlas)
            bbox = frame.getchannel('A').point(lambda value: 255 if value >= 16 else 0).getbbox()
            preview, metrics = sharpness_metrics(frame)
            atlas_exact, webp_exact = atlas_checks(action, index, frame, atlas, webp)
            touches_edge = bool(bbox and (bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= frame.width or bbox[3] >= frame.height))
            row = {
                'frame': index + 1, 'source': source,
                'source_size': [frame.width, frame.height],
                'alpha_bbox': list(bbox) if bbox else None,
                'alpha_occupancy': round(float(np.mean(np.asarray(frame.getchannel('A')) >= 16)), 6),
                'touches_cell_edge': touches_edge,
                'atlas_exact': atlas_exact, 'public_webp_exact': webp_exact,
                **metrics,
            }
            rows.append(row); previews.append(preview)
        values = [row['laplacian_variance'] for row in rows]
        for row in rows:
            row['relative_sharpness'] = round(robust_outlier(row['laplacian_variance'], values)[0], 4)
            row['robust_z'] = round(robust_outlier(row['laplacian_variance'], values)[1], 3)
            row['review_candidate'] = row['relative_sharpness'] < .70 and row['robust_z'] < -2.0
        sheet = make_sheet(action, previews, rows, output)
        sharpness = [row['laplacian_variance'] for row in rows]
        actions.append({
            'id': action['id'], 'name': action.get('name', action['id']),
            'frames': expected, 'cell': int(action.get('cell', 256)),
            'display_scale': round(DISPLAY_CELL / int(action.get('cell', 256)), 4),
            'sharpness_median': round(float(np.median(sharpness)), 4),
            'sharpness_min': round(min(sharpness), 4),
            'sharpness_max': round(max(sharpness), 4),
            'outlier_frames': [row['frame'] for row in rows if row['review_candidate']],
            'atlas_mismatches': [row['frame'] for row in rows if not row['atlas_exact']],
            'webp_mismatches': [row['frame'] for row in rows if row['public_webp_exact'] is False],
            'edge_touch_frames': [row['frame'] for row in rows if row['touches_cell_edge']],
            'sheet': str(sheet.relative_to(output)), 'frame_metrics': rows,
        })
        all_frames += expected

    report = {
        'read_only': True,
        'registered_actions': len(actions), 'frames_checked': all_frames,
        'render_cell_px': DISPLAY_CELL,
        'render_note': 'Sharpness metrics are relative within each clip; outliers require visual review.',
        'actions': actions,
    }
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '<!doctype html><meta charset="utf-8"><title>Yuki action clarity audit</title>',
        '<style>body{font:14px Segoe UI, sans-serif;max-width:1200px;margin:32px auto;color:#1c2e3b}'
        'table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ccd5dc;text-align:left}'
        'img{width:180px;height:180px;object-fit:contain;background:#dce4eb}a{color:#245f86}</style>',
        f'<h1>Yuki 动作逐帧清晰度审查</h1><p>{len(actions)} 个动作 · {all_frames} 帧 · 输出画布 {DISPLAY_CELL}px</p>',
        '<p>清晰度数值仅用于同一动作内筛查，离群帧需结合接触表人工判断。此报告不会修改正式素材。</p>',
        '<table><thead><tr><th>动作</th><th>帧数</th><th>清晰度范围</th><th>建议复核帧</th><th>图表</th></tr></thead><tbody>',
    ]
    for action in actions:
        outliers = ', '.join(map(str, action['outlier_frames'])) or '—'
        sheet = html.escape(action['sheet'])
        lines.append(f"<tr><td>{html.escape(action['name'])} ({html.escape(action['id'])})</td>"
                     f"<td>{action['frames']}</td><td>{action['sharpness_min']:.1f}–{action['sharpness_max']:.1f}</td>"
                     f"<td>{outliers}</td><td><a href='{sheet}'><img src='{sheet}' loading='lazy'></a></td></tr>")
    lines.append('</tbody></table>')
    (output / 'index.html').write_text('\n'.join(lines), encoding='utf-8')
    print(f"Audited {len(actions)} actions / {all_frames} frames. Report: {output / 'index.html'}")
    print('Atlas mismatches:', sum(len(a['atlas_mismatches']) for a in actions))
    print('Public WebP mismatches:', sum(len(a['webp_mismatches']) for a in actions))
    print('Candidate clarity outliers:', sum(len(a['outlier_frames']) for a in actions))


if __name__ == '__main__':
    main()
