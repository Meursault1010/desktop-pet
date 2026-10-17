"""Generate coherent ground-level actions using the original identity references."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
WORK = ROOT / 'action-work/ground-idle'
GENERATOR = Path('C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py')
SPECS = {
    'sit-neat': ('端坐待机', 'standing; bend knees gracefully; lower to seated; sit neatly knees together legs tucked sideways hands on lap; same seated pose eyes soften; same seated pose head tilts slightly; same seated pose blink closed; same seated pose look at viewer; same seated pose breathe; plant hand to rise; kneel then rise; standing'),
    'sit-relaxed': ('抱膝待机', 'standing; crouch; sit down; sit knees gently hugged feet together; same seated pose chin on knees; same seated pose look left; same seated pose blink; same seated pose look toward viewer; same seated pose small smile; release knees and plant palms; rise from crouch; standing'),
    'sit-swing': ('侧坐晃脚待机', 'standing; bend knees; lower onto floor; sit side saddle supporting body with left palm right hand on skirt; same pose small foot movement; same pose head tilt to viewer; same pose blink; same pose tiny foot movement back; same pose smile; gather knees underneath; rise; standing'),
    'prone-chin': ('托腮趴姿待机', 'standing; crouch palms on floor; lower belly toward floor; lie on belly elbows grounded tiny hands under chin feet bent behind; same prone pose look toward viewer; same prone pose blink; same prone pose feet gently sway; same prone pose curious head tilt; same prone pose smile; palms under shoulders push up; kneel and rise; standing'),
    'prone-rest': ('枕臂趴姿待机', 'standing; crouch palms down; lower to belly; lie on belly head resting on folded forearms feet together; same prone pose sleepy open eyes; same prone pose slow blink; same prone pose cheek on arms; same prone pose eyes open softly; same prone pose ear perk; push torso up with palms; kneel then rise; standing'),
}


def generate(key):
    name, poses = SPECS[key]
    out = WORK/key
    out.mkdir(parents=True, exist_ok=True)
    instructions = '\n'.join(f'{i+1}. {pose.strip()}' for i, pose in enumerate(poses.split(';')))
    prompt = f'''Create a polished animation KEYFRAME sheet for Yuki, the exact character in the two supplied identity references. ONE sheet, EXACTLY 4 columns by 3 rows, 12 equal rectangular cells read left to right then top to bottom. One complete character per cell. No extra characters. Flat pure chroma green #00ff00 background, no floor, no shadows, no labels, no text, no borders, no grid lines.
Identity: small chibi anime girl, long white hair, white cat ears, blue eyes, delicate blue-white-silver dress, blue Mary Jane shoes, snowflake hairclip on viewer RIGHT. Original face, petite short arms, consistent head-to-body proportion throughout. Fully clothed, modest skirt with opaque underskirt during rolling, innocent playful cozy companion. Detailed clean soft anime illustration matching references. Gorgeous expressive face, gentle asymmetry and lively eye contact, no stiff mannequin poses. Natural connected limbs, exactly two arms two legs. Hair follows gravity. Never stretch her body or arms.
Action: {name}. Ordered poses, every cell is a different successive moment:
{instructions}
Camera fixed at a slightly elevated front three-quarter view. Character scale, head size and perspective FIXED in every cell: do not enlarge seated/prone poses to fill the cell. The standing figure should fit within 80 percent of cell height, leave generous margins including in the widest lying poses. All poses must share one imaginary floor at 90 percent cell height, planted hands/hips/feet touch that floor. Keep character center near cell center. Rolling is a real connected body barrel roll with intermediate side/back/belly poses, not a rotated standing cutout. The program supplies horizontal travel. No motion streaks, no props, no furniture, no speech bubbles.'''
    (out/'prompt.txt').write_text(prompt, encoding='utf-8')
    if (out/'raw.png').exists():
        print(f'EXISTS {key}', flush=True)
        return
    subprocess.run([sys.executable, str(GENERATOR), '--provider', 'gpt', '--mode', 'edit',
                    '--quality', 'high', '--size', '1536x1024', '--prompt', prompt,
                    '--image', str(ROOT/'图片/参考图.png'), '--image', str(ROOT/'图片/三视图.png'),
                    '--out', str(out/'raw.png')], check=True)
    print(f'DONE {key}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', choices=SPECS)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(generate, [args.only] if args.only else SPECS))
