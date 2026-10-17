from pathlib import Path
import subprocess,sys
from generate_locomotion import COMMON
root=Path(__file__).resolve().parent
folder=root/'action-work/drag-resist';folder.mkdir(parents=True,exist_ok=True)
prompt=COMMON+'''
Create six directional REACHING TO COVER THE MOUSE GRAB POINT poses. She is being gently dragged by the desktop user and playfully tries her utmost to stop it, eyes looking precisely at the invisible cursor location, both palms reaching together to cover that point. Endearing determined pout, gently furrowed brows, cheeks slightly puffed, lively effort; no anger, fear, crying, injury. Torso counterleans away from the reach, legs dangle and bend softly, hair lags. No cursor or hand of user drawn, no props. Preserve expressive face and delicate original character style. Full body.
Strict consistent character layout: head centered around x256,y135, pelvis around x256,y320, soles no lower than y470. Shoulder around x210 and x300 at y230. Two clearly drawn bent arms connected to shoulders, elbows and five-finger small hands. BOTH palms gathered CLOSE TOGETHER at the target; do not leave arms outstretched to opposite sides. Hands layered in front of hair/body, no detached arms. Look toward the target with slight matching head tilt. Only modest outfit as reference.
Cell 1 top-left: both hands reaching diagonally UP LEFT, palm cluster centered (135,95). Eyes look upper left. Head tilts left, body counterleans right.
Cell 2 top-middle: both hands reach UP above forehead, palm cluster centered (256,55). Eyes look upward, head tips up a little. Elbows bent beside head, do not cover whole face.
Cell 3 top-right: both hands reach diagonally UP RIGHT, cluster (380,95). Eyes look upper right. Head tilts right, body counterleans left.
Cell 4 bottom-left: both hands reach LEFT at chest height, palm cluster (112,255). Eyes look down left. Soft bent elbows, counterlean right.
Cell 5 bottom-middle: both hands reach DOWN in front of skirt, palm cluster (256,370). Eyes look downward, shoulders raised in effort, head slightly bowed. Both hands cover same point near lap.
Cell 6 bottom-right: both hands reach RIGHT at chest height, palm cluster (400,255). Eyes look down right. Counterlean left.
All six are different believable directed reaches; this is not a walk cycle. No labels, no duplicated poses, no frame lines. Flat pure green background. Keep at least 24px clear around all anatomy in each cell.
'''
(folder/'prompt.txt').write_text(prompt,encoding='utf-8')
if (folder/'raw.png').exists():raise SystemExit('Preserving previous generation')
refs=Path('C:/Users/meursault/Desktop/desktop-pet/图片')
subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py','--provider','gpt','--mode','edit','--quality','high','--size','1536x1024','--prompt',prompt,'--image',str(refs/'参考图.png'),'--image',str(refs/'三视图.png'),'--out',str(folder/'raw.png')],check=True)
