"""Generate one rest keyframe per API call, with identity and prior-pose references."""
from pathlib import Path
import subprocess,sys,argparse
from PIL import Image
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'output/dance-rest-20261023'
SKILL=Path('C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py')
DESCRIPTIONS={
2:'延续站立姿势，双脚保持稳定，双手轻搭胸前，肩膀略抬起，嘴唇微张，轻轻吸气。轻微疲惫但开心。',
3:'与第02帧站位一致，呼气时肩膀放松，双手缓缓放低到腰前，头轻低，眼皮稍放松，温柔微笑。保持站立高度。',
4:'双脚原落点不变，膝盖自然弯曲，骨盆向后下方移动，上身略前倾，双手移向膝盖前。头顶比站立低100像素，人物不缩小。',
5:'从上一帧继续降低重心至低蹲，膝盖进一步弯曲，一只手向身体侧后方的地面伸下，另一手轻搭膝旁。头顶比站立低230像素，双脚仍接地，人物大小不变。',
6:'从低蹲自然坐到地面，侧后方一只手掌触地短暂支撑，手肘微弯，臀部轻轻落地，双膝弯曲，双脚留身前。裙摆自然铺开完整遮盖腿根。头顶比站立低330像素。',
7:'保持第06帧臀部接地点不变，坐直，支撑地面的手收回，两腿在身前舒适屈膝靠拢，双手轻放膝盖上，呼气，安心满足。头顶比站立低330像素。',
8:'保持第07帧坐姿与臀部双脚位置，双手放松搭膝上，肩膀垂下，头微偏，半睁眼，轻微微笑，平稳休息基准姿势。头顶比站立低330像素。',
9:'严格保持提供的第08帧基准坐姿，臀部双脚双手裙摆不动，仅轻微吸气，胸口与肩膀上移约3像素，头部稳定。绝不能重新设计坐姿、头发、衣裙或脸。',
10:'严格保持提供的第08帧基准坐姿，臀部双脚双手裙摆头发不动，仅眼睛自然闭合眨眼，肩膀呼气放松约2像素，轻微微笑。不要低头。只修改眼皮。'}
FIXED='''以第一张参考图（三视图）中的雪Yuki为唯一角色，第二张参考是上一帧，保持相同角色头部、手脚大小与画风。严格保持身份、蓝眼睛、白色猫耳长发、雪花发饰、露肩蓝白裙、白袜蓝鞋、娇小比例与细腻线条。生成桌宠单张完整关键帧，只画一个人物，不要三视图、拼图或分格。
固定1024x1024正交画布，人物大小与第二张参考完全相同，头部与手脚大小不因坐下改变。地面接触线固定y=924，身体中心x=512，站立时头顶y约80。坐下使头部自然下降，不能自动填满画布或将坐姿放大。所有头发双手双脚完整在画布内，四周有留白。面向观众略带四分之三角度。轻柔、疲惫而满足，符合重心和接地。
为了后期可靠抠图，背景严格使用均匀纯绿色#00ff00，无地面、无阴影、无渐变、无棋盘格。最终程序将背景转成全透明。'''
NEG='''不要椅子桌子背景或支撑物，不要汗滴、痛苦、晕倒，不要悬空或穿地，不要脚底滑动与突然换位，不要肢体融合、重复肢体、多指、反折关节，不要裙摆穿模或暴露内衣，不要头发与手臂融合，不要缩放人物、镜头移动、半透明、动作残影、改变服装或身份，不要文字水印。'''
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--start',type=int,default=2);parser.add_argument('--end',type=int,default=10);parser.add_argument('--provider',default='gpt');parser.add_argument('--independent',action='store_true');parser.add_argument('--skip-existing',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    first=OUT/'01-reference.png'
    if not first.exists():
        with Image.open(ROOT/'assets/actions/music-waltz/atlas.png') as atlas:
            atlas.crop((0,0,256,256)).resize((1024,1024),Image.Resampling.LANCZOS).save(first)
    for index in range(args.start,args.end+1):
        path=OUT/f'{index:02d}-raw.png'
        if path.exists() and args.skip_existing:print('Already generated',index,flush=True);continue
        prior=OUT/('08-raw.png' if index>=9 else f'{index-1:02d}-raw.png')
        if index==2 or args.independent:prior=first
        prompt=FIXED+'\n当前帧：'+DESCRIPTIONS[index]+'\n反向约束：'+NEG
        (OUT/f'{index:02d}-prompt.txt').write_text(prompt,encoding='utf-8')
        cmd=[sys.executable,str(SKILL),'--provider',args.provider,'--mode','edit','--size','1024x1024','--quality','low',
             '--image',str(ROOT/'图片/三视图.png'),'--image',str(prior),'--prompt',prompt,'--out',str(path)]
        guide=OUT/f'{index:02d}-pose-guide.png'
        if guide.exists():
            cmd[cmd.index('--prompt'):cmd.index('--prompt')]=['--image',str(guide)]
            cmd[cmd.index('--prompt')+1]+='\nCRITICAL: Second reference defines exact face, blue eyes, saturated blue dress and illustration style. Third reference defines ONLY the body pose. Copy that pose with the second reference character. Keep full outfit and white socks, no redesign. Frame 03 MUST remain STANDING with both straight legs, NOT sitting. For other frames follow their own specified pose. The phrase about frame03 applies ONLY when current frame is03. '
        (OUT/f'{index:02d}-prompt.txt').write_text(cmd[cmd.index('--prompt')+1],encoding='utf-8')
        print('Generating frame',index,flush=True)
        result=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace')
        if result.returncode:raise RuntimeError('Image generation failed: '+result.stderr[-1500:])
        print('Saved frame',index,flush=True)
if __name__=='__main__':main()
