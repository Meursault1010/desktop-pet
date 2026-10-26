"""Rebuild corrected cells without reordering or retiming the approved dance."""
import hashlib
import json
from PIL import Image
import numpy as np
from build_dance_25d import SOURCE, BRIDGES, OUT, clean_cell
from dance_artwork_repair import repair_cell, HEIGHT, TOP, SKIN_PATCHES
from build_dance_footwork import main as install, ASSETS


def main():
    report_path = OUT/'build-report.json'
    report = json.loads(report_path.read_text(encoding='utf-8'))
    atlas = Image.new('RGBA', (report['columns']*256,
                              (len(report['order'])+report['columns']-1)//report['columns']*256))
    for index, check in enumerate(report['frame_checks']):
        path = SOURCE/'consistent-keys'/check['source']
        if not path.exists():
            path = BRIDGES/check['source']
        with Image.open(path) as source:
            cell = repair_cell(clean_cell(np.array(source.convert('RGBA'))), check['source'])
        atlas.paste(cell, (index%report['columns']*256, index//report['columns']*256))
        check['cell_sha256'] = hashlib.sha256(cell.tobytes()).hexdigest()
    report['artwork_repair'] = dict(version=1, visible_height=HEIGHT, top=TOP,
                                    skin_sources=list(SKIN_PATCHES), isotropic_scale=True)
    report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    atlas.save(OUT/'atlas.png')
    atlas.crop((0, 0, 256, 256)).save(OUT/'poster.png')
    atlas.crop((0, 0, 256, 256)).save(ASSETS/'poster.png')
    install(source=OUT)
    # The installer rebuilds foot contacts and both atlas mirrors from the same
    # drawings, so registration cannot leave a stale support-foot track behind.


if __name__ == '__main__':
    main()
