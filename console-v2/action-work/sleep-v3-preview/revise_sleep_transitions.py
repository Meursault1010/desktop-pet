"""Correct rejected transition art, preserving the approved master identity."""
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROMPT = '''EDIT the attached image into a 3-column x 2-row sprite pose sheet. The attached image is the APPROVED CHARACTER MASTER. Copy her EXACT drawing style, crisp blue contour, face, eyes, snowy-white cat ears, intricate snowflake hairclip on ONE temple, dangling snowflake earring, white-blue long hair, detailed snowflake lace on blue dress, blue Mary Jane shoes, and small chibi proportions. It must look like the SAME ARTIST drew the same character a moment later. DO NOT use watercolor, paint smears, rough brushwork, 3D, doll style or reduce costume details. Preserve the reference's clean illustrated anime sprite style and fine crisp detail. Ears are fluffy white CAT ears, never round or human ears replacing them. Keep ALL accessories in EVERY pose. Exactly one hairclip.

Canvas 1536x1024, SIX equal 512x512 cells. One fully visible character and one plain pale-blue pillow per cell. Transparent background, no checkerboard, no texture or vignette. No text or labels, borders, props or bubbles. Wide empty margins; no character touches cell edges. Same head size and fixed pillow position in all cells. Nose always faces screen RIGHT, feet to LEFT, consistent side/three-quarter view. Pillow always plain pale ice-blue with NO PATTERN. Hair, ears and dress detail stay stable; only body posture and eyelids change.

TOP row = falling asleep, three stages left to right:
1. Sitting sleepily with legs softly tucked to her left, hugging the pillow on the right, eyelids half closed. Preserve the exact face, blue dress details and snowflake accessories of attached character.
2. Leaning down onto the pillow on the right, supporting herself gently on a forearm, eyelids almost closed, knees gently tucked. Small grounded movement.
3. The EXACT curled side-lying asleep pose in the attached image. Copy it faithfully, eyes completely closed, same cheeks, hands, shoes, hair and plain pillow. Do not redesign her.

BOTTOM row = waking slowly, three stages left to right:
4. EXACT same curled body pose, hands, pillow, hair and all details as cell 3, but eyes open a tiny sleepy slit. No body movement yet.
5. Lifting her head a SMALL distance above the pillow while still lying curled. Eyes half open. One hand on pillow, hair barely moves. Keep same head shape and snowflake accessories.
6. Sleepily seated again, same position as cell 1, gentle open blue eyes, loosely hugging the plain pillow. No waving or big gestures.

Preserve modest anatomy and EXACT outfit details. No missing accessories, no head or hand cropping, no extra limbs, no floating, no wind, no exaggerated motion. The frames must be a coherent gentle sequence with strong identity preservation, not six separate redesigns.'''

if __name__ == '__main__':
    target = HERE/'sleep-transitions-v2-raw.png'
    if target.exists():
        raise SystemExit('Output exists; refusing overwrite.')
    (HERE/'sleep-transitions-v2-prompt.txt').write_text(PROMPT, encoding='utf-8')
    result = subprocess.run([sys.executable,
        'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
        '--provider', 'gpt', '--mode', 'edit', '--quality', 'high', '--size', '1536x1024',
        '--prompt', PROMPT, '--image', str(HERE/'selected-right-02-reference.png'),
        '--out', str(target)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        (HERE/'sleep-transitions-v2-error.txt').write_text(result.stderr, encoding='utf-8')
        print('\n'.join(x for x in result.stderr.splitlines() if 'RuntimeError:' in x or 'HTTP Error' in x))
        raise SystemExit(result.returncode)
    print('Saved revised sleep transition sheet for review.')
