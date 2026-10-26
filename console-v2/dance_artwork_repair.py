"""Conservative offline repairs to the authored dance, before page export.

Coordinates refer to the original 256px padded cells. Only the two damaged
skin regions are painted; the face, costume, fingers and other poses stay intact.
"""
import cv2
import numpy as np
from PIL import Image, ImageDraw


HEIGHT = 213
TOP = 20
SKIN_PATCHES = {
    'mixed-pose-19.png': [(55, 81), (63, 81), (66, 83), (66, 91),
                          (57, 92), (54, 86)],
    'keyed-turn-03.png': [(69, 90), (74, 90), (75, 97), (79, 103),
                          (83, 108), (83, 115), (77, 115), (74, 107),
                          (73, 101), (70, 96)],
}


def repair_cell(cell, source):
    cell = cell.convert('RGBA')
    if source in SKIN_PATCHES:
        # Supersampled mask avoids a hard polygon edge on the pale skin.
        mask = Image.new('L', (1024, 1024))
        ImageDraw.Draw(mask).polygon([(x*4, y*4) for x, y in SKIN_PATCHES[source]], fill=255)
        mask = mask.resize(cell.size, Image.Resampling.LANCZOS)
        if source == 'keyed-turn-03.png':
            # The forearm has a fully enclosed cutout. Follow its actual
            # contour, including the half-transparent dark matte at the rim.
            alpha = np.array(cell)[:, :, 3]
            flooded = np.pad(np.uint8(alpha > 80), 1)
            cv2.floodFill(flooded, None, (0, 0), 1)
            holes = np.uint8(flooded[1:-1, 1:-1] == 0)
            roi = np.zeros_like(holes)
            roi[85:120, 65:87] = 1
            holes *= roi
            mask = Image.fromarray(cv2.dilate(holes, np.ones((3, 3), np.uint8))*255)
        patch = Image.new('RGBA', cell.size, (253, 245, 245, 255))
        cell = Image.composite(patch, cell, mask)

    # Remove only detached alpha noise, retaining the soft edge of the main
    # character. Register the visible figure, rather than the padded canvas.
    pixels = np.array(cell)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        np.uint8(pixels[:, :, 3] > 24))
    if count < 2:
        raise ValueError('Empty dance drawing: ' + source)
    main = 1 + stats[1:, cv2.CC_STAT_AREA].argmax()
    keep = cv2.dilate(np.uint8(labels == main), np.ones((3, 3), np.uint8)) > 0
    pixels[~keep] = 0
    cell = Image.fromarray(pixels)
    bbox = cell.getchannel('A').point(lambda a: 255 if a > 24 else 0).getbbox()
    cropped = cell.crop(bbox)
    width = round(cropped.width * HEIGHT / cropped.height)
    cropped = cropped.resize((width, HEIGHT), Image.Resampling.LANCZOS)
    # A very faint ear-tip pixel can fall below the visibility threshold after
    # resampling. Measure the result too, so every actual silhouette is 213px.
    for _ in range(3):
        visible = cropped.getchannel('A').point(lambda a: 255 if a > 24 else 0).getbbox()
        if visible[1] == 0 and visible[3] == HEIGHT:
            break
        cropped = cropped.crop(visible)
        width = round(cropped.width * HEIGHT / cropped.height)
        cropped = cropped.resize((width, HEIGHT), Image.Resampling.LANCZOS)
    result = Image.new('RGBA', (256, 256))
    result.alpha_composite(cropped, ((256-width)//2, TOP))
    return result
