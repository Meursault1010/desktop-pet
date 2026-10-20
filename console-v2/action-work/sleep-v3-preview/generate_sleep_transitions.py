"""Generate approved-scope sleep transitions for review, without shipping changes."""
from pathlib import Path
import subprocess
import sys
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROMPT = '''Create an animation key-pose sheet for the exact Yuki desktop companion shown in the references. Reference one is the APPROVED curled-up RIGHT-FACING sleeping pose and its plain pillow: preserve this specific design, proportions, hairstyle, outfit, facial features, snowflake accessory and art style. Other references show the same character's identity and turnaround. Fine clean blue linework, delicate soft shading, silver ice-blue hair, fluffy white cat ears, one snowflake hairclip on the correct anatomical side, blue off-shoulder dress, original small chibi body. Do not make a different character or coarsen the pixel texture.

One 1536x1024 RGBA sprite sheet, FOUR columns and TWO rows, EIGHT equally sized cells of 384x512. Genuine transparent background, NOT a painted checkerboard. Each cell contains exactly one complete full-body Yuki and exactly one identical PLAIN pale ice-blue plump rounded pillow. NO labels, numbers, borders, lettering, speech bubbles, zzz, effects, scenery, ground or other props. All eight characters must fit fully inside their own cells with wide margin. No overlap. Ears, hair, skirt and shoes must never be cropped. Consistent anatomical scale (same HEAD SIZE) in all cells, common support baseline, consistent right-facing three-quarter perspective. Do not stretch or resize the character between cells. Nose faces screen RIGHT. Body is naturally horizontal when lying, head on RIGHT, feet on LEFT. Hair is a quiet cohesive mass, never windy or fanned out further than the approved reference.

TOP ROW: four subtle sequential FALLING ASLEEP key poses, read left to right.
1. Drowsy seated Yuki in a right-facing three-quarter view, knees gently bent to her left, hugging the plain pillow close, eyelids half lowered, quiet relaxed expression. Pillow is at screen right, ready to rest her cheek.
2. Slowly leaning down to her right on her forearm, keeping the same pillow at her right, sleepy eyelids almost closed, knees softly tucking, a modest natural resting movement.
3. Nearly lying in the approved curled pose, cheek just touching the same pillow, hands settling near cheek, eyes completely closed. No big hair displacement.
4. Exact approved curled-up right-facing sleeping pose, cheek on pillow, softly bent knees toward torso, hands relaxed at cheek/pillow, deeply asleep. Match reference one as closely as possible.

BOTTOM ROW: four restrained sequential AWAKENING key poses, read left to right. No panic or large gesture.
5. The EXACT same body, head, hands, pillow and hair placement as cell 4, but eyes open a tiny slit, sleepy and confused. The body has not yet moved. Do not sit up immediately.
6. Head lifted just a little from the pillow, one hand still resting there, eyes half open and heavy, tiny calm ear movement, knees still curled. Minimal amplitude.
7. Slowly propping upper body up on a forearm, same pillow on the right, same shoes and bent knees on the left, sleepy gentle expression, no dramatic hair swinging.
8. Drowsy seated right-facing Yuki again, matching cell 1's body scale and seated position, now with gently open eyes. One hand loosely hugs the pillow, other relaxed; no raised arm or waving.

Make adjacent poses anatomically plausible stages of a single slow movement. Keep each intermediate motion small and grounded. Pillow stays the SAME SHAPE, solid pale ice-blue fabric, no embroidery or pattern anywhere on pillow. Keep her snowflake hair accessory and dress motifs as in the references, never copy those onto the pillow. Exactly one hairclip, no duplicated ornaments. Natural joined arms, legs and neck, no extra fingers or limbs, no flying, jumping, rolling, flinging hair, big snoring mouth, deformed face, ghosting, blur, photorealism or redesign.'''

if __name__ == '__main__':
    selected = HERE/'selected-right-02-reference.png'
    Image.open(HERE/'sleep-right-v2-raw.png').crop((815, 200, 1420, 785)).save(selected)
    target = HERE/'sleep-transitions-raw.png'
    if target.exists():
        raise SystemExit('Output exists; refusing overwrite.')
    (HERE/'sleep-transitions-prompt.txt').write_text(PROMPT, encoding='utf-8')
    args = [sys.executable, 'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
            '--provider', 'gpt', '--mode', 'edit', '--quality', 'high', '--size', '1536x1024',
            '--prompt', PROMPT, '--image', str(selected),
            '--image', str(ROOT/'图片/参考图.png'), '--image', str(ROOT/'图片/三视图.png'),
            '--out', str(target)]
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        (HERE/'sleep-transitions-error.txt').write_text(result.stderr, encoding='utf-8')
        print('\n'.join(line for line in result.stderr.splitlines() if 'RuntimeError:' in line or 'HTTP Error' in line))
        raise SystemExit(result.returncode)
    print('Saved sleep transition key-pose sheet for review.')
