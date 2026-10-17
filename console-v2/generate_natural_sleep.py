"""Reference-preserving generation through the user-selected shengtu gateway."""
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'action-work/icon-sleep-v2'
PROMPT='''Use case: identity-preserve. Asset type: desktop pet transparent sprite poses.
Input image 1 is the character identity reference; input image 2 is the front/side/back turnaround, use it to preserve the BACK of the hair and dress accurately.
Create ONE sprite sheet, EXACTLY FOUR equal square cells in a 2 by 2 grid, 1536x1536. Each cell contains ONE isolated FULL BODY of the SAME original white-haired catgirl. Genuine transparent background, no checkerboard, no colored backdrop, no floor shadow. Each body fits inside its own cell with 12 percent padding, same scale and baseline.
Preserve the reference's chibi pixel-anime style, long white wavy hair, white cat ears, blue snowflake hairclip on her anatomical left side, delicate snowflake earrings, ice-blue off-shoulder snowflake dress and blue shoes. Do not redesign her. Eyes CLOSED asleep wherever the face is visible.
All poses: seated naturally on an invisible floor, weight in the hips, knees loosely bent and feet resting on floor, hands relaxed in lap, shoulders relaxed, upper BACK leaning slightly backward against an imaginary upright support at shoulder-blade height. Chin relaxed downwards. This is natural upright seated dozing, NOT lying down, not standing, not kneeling in prayer, not hugging a prop. The BACK, never the forehead/face, is the contact with the unseen support. Do NOT draw the support.
TOP LEFT: TRUE LEFT-FACING side profile. Nose points viewer LEFT, feet extend gently LEFT. Back and shoulder blade on the RIGHT side of the silhouette are supported, torso inclines subtly RIGHT. Closed eye visible. Not a frontal pose with tilted head.
TOP RIGHT: TRUE RIGHT-FACING side profile. Nose and feet point viewer RIGHT. Back and shoulder blade on the LEFT side are supported, torso inclines subtly LEFT. Preserve accessory asymmetry, not an exact horizontal mirror.
BOTTOM LEFT: rear three-quarter view, almost FULL BACK facing the viewer. Show the long back hair and rear of the dress from the turnaround, NOT a face drawn on back of head. Seated bottom, folded relaxed legs visible beside skirt, head gently bowed left and slightly back, upper back supported just to viewer RIGHT. Peaceful asleep, not standing.
BOTTOM RIGHT: FRONT view facing viewer, seated, closed eyes, hands resting naturally on skirt, slightly reclined upper back with rounded relaxed shoulders resting on an unseen upright support BEHIND the shoulder blades. Whole body visible, dress and feet in front.
No icons, folders, books, pillows, beds, chairs, screens, furniture, props, lettering, grid lines, watermarks, glow or lighting changes. Only the four character cutouts, no cut-off ears/hair/shoes.'''

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'raw.png').exists(): raise SystemExit('Output already exists; preserve it.')
    # Prompt source is preserved in this script, and copied with the artwork.
    refs=Path('C:/Users/meursault/Desktop/desktop-pet/图片')
    subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py',
                    '--provider','gpt','--mode','edit','--quality','high','--size','1536x1536',
                    '--prompt',PROMPT,'--image',str(refs/'参考图.png'),'--image',str(refs/'三视图.png'),
                    '--out',str(OUT/'raw.png')],check=True)
