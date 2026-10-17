"""Draw actual articulated gait and grip keyframes using approved identity refs."""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parent
COMMON='''Use the two supplied character identity references to draw the EXACT same white-haired catgirl: white cat ears, long soft white hair, blue eyes, asymmetric snowflake hairclip on her anatomical left, snowflake earrings, layered ice-blue offshoulder modest dress with belt, white socks, blue Mary Jane shoes. Preserve original cute chibi proportions, pixel-anime delicate outlines, readable expressive face. No redesign, no tail. Small lively person, not a stiff doll. Outfit intact and modest, no underwear visible.
Output EXACTLY SIX full-body cutouts, one per cell, in a STRICT 3 column x 2 row sprite sheet, 1536x1024, six 512x512 cells. Reading order 1-6. Same head size and body proportions in ALL cells. Minimum 30px blank margin in every cell, no cropped limbs/hair/ears. Perfect flat #00FF00 green background, including gaps inside limbs. NO gradients, shadows, labels, checkerboard, floor, stairs, furniture, drawn frame, lines, platform, objects or props. Only the character. Neutral uniform lighting. Hair has no green tint. Clear believable hand, elbow, knee and ankle articulation. Six distinct animation keyframes, not six copies.
'''
def prompt(kind):
    if kind.startswith('walk'):
        direction='RIGHT' if kind.endswith('right') else 'LEFT'
        return COMMON+f'''
Create SIX consecutive evenly spaced phases of a natural WALK CYCLE travelling towards viewer {direction}. All six characters face the SAME direction {direction}. Three-quarter view, chest slightly turned towards viewer, face gently glances towards us without twisting the neck unnaturally. Keep her head center approximately (256,150), hips around (256,325), and the supporting sole ground baseline EXACTLY y=462 in EVERY 512x512 cell. The original character is not walking on tiptoes. One foot is planted each phase, the other has a bent knee or lifts. Arms swing opposite legs. Long hair and skirt lag softly. Keep common camera, drawing style, scale and alignment. Show both shoes distinctly. No whole-character translation in the sheet.
Frame 1: left foot forward heel contact, right foot back at toe-off, opposite arm swing.
Frame 2: weight on left foot, right knee bends and lifts to pass, body lowers slightly.
Frame 3: left support leg nearly straight, right foot swings forward just above ground, arms pass relaxed.
Frame 4: right foot forward heel contact, left foot back at toe-off, arm swing reversed.
Frame 5: weight on right foot, left knee bends and lifts to pass, body lowers slightly.
Frame 6: right support leg nearly straight, left foot swings forward just above ground, arms pass relaxed. The next implied phase returns naturally to Frame 1.
Do not draw running, jumping, standing still with identical feet, or skating. The leg silhouettes and arm swing must change clearly from phase to phase. Gentle cheerful focused expression, open eyes.'''
    return COMMON+'''
Six GRIPPING and HANGING key poses. The frame/ledge is INVISIBLE and must NOT be drawn. Her fingers visibly curl around its imaginary edge; weight and tension must look physically believable. Threequarter face can look towards viewer. No sad tears, no panic, an endearing playful determined face.
Cell1 TOP LEFT: climbing a VERTICAL edge at canvas x=355, BODY LEFT of that edge. Two hands at x=355: one high y=118, one lower y=222; both grip the invisible rail. Knees bent, shoes braced at that same vertical rail x=355 at y=330 and y=425. Slightly rear threequarter torso, face turned gently back to us, hair falls left, no hair across hands. Like a tiny person climbing the LEFT OUTSIDE edge of a real browser window. Full body within cell.
Cell2 TOP MIDDLE: next climbing phase, SAME rail x=355 and same character scale as cell1. Swap upper/lower supporting hand and opposite bent knee, hips shift upward slightly. Hands still at (355,118) and (355,222), shoes braced at x=355 at y=330 and y=425. Show distinct limb articulation and opposite arm/leg loading, not identical pose.
Cell3 TOP RIGHT: climbing a VERTICAL edge at x=157, BODY RIGHT of edge. Two hands at (157,118) and (157,222) curl around the invisible rail. Knees bent, shoes braced on same rail x=157 at y=330 and y=425. Threequarter body, face glances at viewer. Preserve clip on correct anatomical side, do not merely mirror cell1. Like climbing RIGHT OUTSIDE of browser window.
Cell4 BOTTOM LEFT: next climbing phase for cell3, SAME x=157 rail. Swap upper/lower supporting hand and opposite bent knee, hips shift upward slightly. Same hand and shoe contact coordinates. Distinct opposing arm/leg articulation.
Cell5 BOTTOM MIDDLE: HANGING by BOTH HANDS below invisible horizontal ledge y=82. Both fingers curl around top of ledge at x=206 and x=306, y=82. Arms stretched up, elbows slightly soft. Her head is BELOW hands, face around y=198, torso below it, skirt drapes naturally downward, knees softly bent, feet hang down around y=430. Little body swings a little LEFT, head tilts toward viewer, mouth tiny and playfully nervous. Hair obeys gravity and does not replace or cover the fingers. Full body. No chin on ledge, not seated, not standing, no levitation.
Cell6 BOTTOM RIGHT: next HANGING swing phase, BOTH HANDS stay exactly at x=206 and x=306,y=82. Torso, hair and legs swing gently RIGHT, knees at slightly different height, one shoe kicks a little. Arms still attached to those fixed grip points. Same head size, clear little swaying suspended body. Expressive cute determined look. No falling away or released hands.
'''
if __name__=='__main__':
    kind=sys.argv[1];folder=ROOT/'action-work/locomotion'/kind;folder.mkdir(parents=True,exist_ok=True)
    text=prompt(kind);(folder/'prompt.txt').write_text(text,encoding='utf-8')
    if (folder/'raw.png').exists():raise SystemExit('Preserving prior generation')
    refs=Path('C:/Users/meursault/Desktop/desktop-pet/图片')
    subprocess.run([sys.executable,'C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py','--provider','gpt','--mode','edit','--quality','high','--size','1536x1024','--prompt',text,'--image',str(refs/'参考图.png'),'--image',str(refs/'三视图.png'),'--out',str(folder/'raw.png')],check=True)
