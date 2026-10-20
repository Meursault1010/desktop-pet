"""Generate preview poses only; never touches published assets."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROMPT = '''Create a polished character pose exploration sheet for Yuki, the EXACT same desktop companion in the two attached reference images. Match reference character identity, rendering style, line quality and shading precisely. Ice blue / silvery long hair, white cat ears, blue snowflake hair accessory at the correct side, delicate face, blue off-shoulder dress and matching shoes, same chibi proportions. Do NOT redesign her or introduce a new pixel art style.

ONE image with FOUR equal square cells in a clean 2 by 2 arrangement. Canvas 1536x1536. Each cell has one complete full-body sleeping Yuki, at consistent anatomical scale with comfortable empty margins, on genuine TRANSPARENT background. No text, labels, grid, fake transparency checkerboard, ground, bed, furniture, effects or speech bubbles. This is four different STILL sleep poses, NOT an animation sequence.

CRITICAL PROP CONSISTENCY: Each of the four cells uses the EXACT SAME small plump rounded rectangular pale ice-blue fabric pillow, plain solid color, soft rounded corners, same size, fabric and restrained shading. NO snowflake on the pillow, NO embroidery, NO print, NO pattern, NO buttons, NO piping decoration, NO bow. The character's existing snowflake hairclip and dress details remain unchanged. The cushion is small enough to hug or rest her cheek on naturally, not a huge bed pillow.

TOP LEFT: lying on her side facing the viewer, loosely hugging the plain pillow to her chest with cheek resting on its upper corner, knees softly bent, eyes completely closed, peacefully and deeply asleep. Relaxed small mouth; no exaggerated snoring face.
TOP RIGHT: softly curled up on her side with both hands tucked close to her face on top of the same pillow, cheek resting on pillow, legs comfortably curled, face visible in three-quarter view, deeply asleep.
BOTTOM LEFT: lying on her back in a relaxed natural sleeping position with head supported by the same plain pillow, hands resting loosely on belly, legs relaxed, face visible, eyes closed and serene. Modest skirt, no low camera angle, no exposed underwear.
BOTTOM RIGHT: lying comfortably on her belly, head gently turned toward viewer resting on folded arms over the same plain pillow, legs resting naturally and close together, shoes visible, sleepy rounded relaxed silhouette, closed eyes. No kicked-up legs or energetic pose.

All four: peaceful, cute, sound asleep; hair lies as a stable soft mass following the body, no flying hair, no wind, no large flowing locks extending dramatically across the canvas. Preserve accessory placement, face, outfit and hair volume. Natural connected anatomy, no extra limbs, no stretching. No movement, exaggerated expression, sparkle, zzz or decorative marks: a separate software bubble will be composited later. Do not crop ears, hair or shoes.'''

if __name__ == '__main__':
    (HERE/'variants-prompt.txt').write_text(PROMPT, encoding='utf-8')
    target = HERE/'sleep-variants-raw.png'
    if target.exists():
        raise SystemExit('Preview already exists; refusing overwrite.')
    subprocess.run([
        sys.executable,
        'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
        '--provider','gpt','--mode','edit','--quality','high','--size','1536x1536',
        '--prompt',PROMPT,
        '--image',str(ROOT/'图片/参考图.png'),
        '--image',str(ROOT/'图片/三视图.png'),
        '--out',str(target),
    ], check=True)
