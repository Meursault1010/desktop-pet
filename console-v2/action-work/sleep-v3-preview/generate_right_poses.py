"""Two right-facing sleep stills; review only, no published asset changes."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PROMPT='''Create a character pose exploration sheet for Yuki, the EXACT same desktop companion in the two attached references. Match character identity, fine line quality, colors, shading and original rendering style precisely: silvery ice-blue long hair, fluffy white cat ears, blue snowflake hair accessory on her original anatomical side, delicate face, blue off-shoulder dress and matching shoes, original chibi proportions. Do NOT redesign or introduce coarse pixelation.

ONE 1536x1024 image, TWO equal cells side by side. Each cell contains ONE complete full-body sleeping Yuki. Genuine transparent background, no checkerboard. No lettering, labels, dividers, speech bubbles, bed, scenery or ground. Leave ample empty margin around every ear, strand of hair and shoe, same anatomical scale in both cells.

Both poses must be a real RIGHT-FACING side / three-quarter view. The head is at the RIGHT end of the horizontal body and the feet extend to the LEFT, with her nose and face directed toward SCREEN RIGHT (viewer right). The right-facing direction must be instantly clear. Not a front-facing character with a tilted head. Do not horizontally mirror the asymmetric hair accessory or dress details: construct the correct opposite-side view from the turnaround. Keep the snowflake accessory on its actual anatomical side; it may be partially hidden on the far side.

Use exactly ONE identical small soft plump rounded-rectangular pale ice-blue fabric pillow in each pose. Absolutely plain, no pattern, no snowflake embroidery, no print, no bow, no buttons, no decorative piping. Same color, proportions and cushion volume in both cells. Keep snowflake details on character hair accessory and dress.

LEFT CELL, right-facing SIDE CUDDLE: lying peacefully on her side, nose facing right, cheek resting on the top corner of the plain pillow which she loosely hugs against her chest. Head at screen right, softly bent knees and shoes at screen left. Eyes completely closed, serene deeply asleep expression, relaxed hands, modest skirt.

RIGHT CELL, right-facing CURLED SLEEP: lying on her side, head at screen right, body gently curled with knees softly tucked toward torso on screen left, cheek supported by the same pillow, both hands comfortably near her cheek on the pillow. Nose clearly points right, closed eyes, peaceful sound sleep, natural anatomy.

Hair rests as a calm stable mass following the body, no wind or dramatic flowing strands. Both are comfortably horizontal lying poses, not sitting, standing, kneeling or hovering. No exaggerated snoring expression, movement, extra limbs, sparkle, motion lines or zzz. A software bubble will be added later. Character fully contained in each cell, no clipping or overlapping cells.'''

if __name__=='__main__':
    revised='--revise' in sys.argv
    prompt=PROMPT
    if revised:
        prompt=prompt.replace('Genuine transparent background, no checkerboard.', 'Perfectly flat uniform solid pale blue #e9effa background. No texture, gradient, shadow or checkerboard. This is a still presentation preview, not a production cutout.')
        prompt+='\nSTRICT CORRECTION: EXACTLY ONE snowflake hairclip TOTAL on each character, at her anatomical LEFT temple as in the original front reference (viewer RIGHT in a frontal view). No second hairclip on the opposite temple or behind the ears. No duplicate clips. Two normal snowflake earrings remain as in the reference. EACH complete character including hair, ears, shoes AND pillow must be contained within the central 65 percent of its own cell width: cell one x=100..650, cell two x=870..1420, with NO body crossing x=768. Keep the entire character smaller to ensure wide empty padding. Uniform flat backdrop without any lighting effects. Both noses clearly point screen right.'
    (HERE/('right-poses-v2-prompt.txt' if revised else 'right-poses-prompt.txt')).write_text(prompt,encoding='utf-8')
    target=HERE/('sleep-right-v2-raw.png' if revised else 'sleep-right-raw.png')
    if target.exists():raise SystemExit('Output exists; refusing overwrite.')
    args=[sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
          '--provider','gpt','--mode','edit','--quality','high','--size','1536x1024','--prompt',prompt,
          '--image',str(ROOT/'图片/参考图.png'),'--image',str(ROOT/'图片/三视图.png'),'--out',str(target)]
    result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        (HERE/'right-generation-error.txt').write_text(result.stderr,encoding='utf-8')
        print('\n'.join(line for line in result.stderr.splitlines() if 'RuntimeError:' in line or 'HTTP Error' in line))
        raise SystemExit(result.returncode)
    print('Saved right-facing sleep preview image.')
