from pathlib import Path
from PIL import Image,ImageDraw,PngImagePlugin
import html
BASE=Path(__file__).resolve().parent
source=(BASE/'render_integrated_silver.py').read_text(encoding='utf-8')
exec(source.split('# Overview:')[0])
OUT=BASE/'window-sizes';OUT.mkdir(exist_ok=True)
# Render the expanded layout without modifying any earlier preview.
block=source.split('# Overview:')[1].split('# Character:')[0]
block=block.replace("save_new('Yuki-融洽版-总览.png')",'')
exec(block.split(chr(10),1)[1])
button(1423,114,141,'紧凑窗口','layout')
save_new('Yuki-融洽版-大窗口.png')
# Compact version is a fresh layout at readable type sizes, not a scaled screenshot.
W,H=1120,800
im=Image.new('RGBA',(W*S,H*S),'#E6ECF1');d=ImageDraw.Draw(im)
rr(10,10,1100,780,PAPER,'#B7C7D4',13)
rr(11,11,1098,42,'#EAF0F4',None,12);rr(11,40,1098,14,'#EAF0F4',None,0)
text(29,14,'yuki',26,C['deep'],serif=True);text(95,27,'工作台',11,SUB)
center(558,25,'紧凑窗口 · 静态设计预览',11,SUB)
ln([(992,32),(1002,32)],SUB);rr(1034,27,10,10,None,SUB,0)
ln([(1076,27),(1087,38)],SUB);ln([(1087,27),(1076,38)],SUB)
rule(11,54,1098,'#CCD9E3')
rr(11,55,130,734,'#EEF2F5',None,0)
for i,(t,ic) in enumerate([('总览','grid'),('角色','pet'),('AI 助手','spark'),('工具','tool'),('设置','settings')]):
    y=100+i*59
    if i==0:rr(22,y-9,107,39,C['deep'],None,7)
    icon(ic,35,y+1,'#E0EDF6' if i==0 else SUB,18)
    text(63,y,t,13,'#F0F7FC' if i==0 else SUB,i==0)
rule(31,663,89)
dot(37,690,3,'#3D806F');text(49,680,'本地模型',11,SUB);text(49,704,'已连接',10,SUB)
text(32,754,'冰银工作区',10,SUB)
# Page heading, controls and local tabs.
text(165,77,'总览',23,INK,True)
button(810,76,130,'展开工作台','layout')
button(952,76,133,'自定义布局','settings')
text(165,126,'默认总览',12,INK,True);rule(165,151,55,BLUE)
text(258,126,'我的工作区',12,SUB);icon('plus',354,129,SUB,14)
right(1085,126,'10 月 20 日 · 星期二',11,SUB)
# A shared strip keeps character and task information at the same visual level.
surface(165,173,920,165)
text(185,190,'14:32',47,INK,latin=True)
text(188,259,'星期二 · 本地时间',11,SUB)
ln([(362,199),(362,309)],EDGE)
icon('sun',382,201,BLUE,25);text(418,192,'18°',31,INK,latin=True)
text(383,248,'上海 · 多云',12,SUB);text(383,279,'天气示例',10,SUB)
ln([(536,199),(536,309)],EDGE)
text(558,196,'雪 · 安静待机',15,INK,True)
text(558,230,'正在轻轻呼吸。',12,SUB)
text(558,257,'下一步暂未安排',11,SUB)
button(558,288,118,'隐藏宠物','eye')
button(687,288,153,'移到右下角','corner')
pet(918,190,113,130)
# Activity journal: summaries fit, detailed content is reached by explicit action.
text(165,365,'今日足迹',16,INK,True)
text(165,397,'活跃 3 小时 42 分钟 · 完成 2 次专注',11,SUB)
text(624,370,'查看总结',11,BLUE)
rule(165,432,518)
for y,t,title,detail in [(451,'14:26','编译成功','Yuki 项目'),(507,'11:20','完成专注','25 分钟'),(563,'09:10','开始工作','编辑器')]:
    text(165,y,t,11,SUB,latin=True);dot(227,y+9,2.5,'#6C91AA')
    text(244,y-1,title,13,INK);right(683,y,detail,11,SUB)
    if y<563:rule(244,y+38,439)
text(165,620,'“But thy eternal summer shall not fade.”',15,SUB,serif=True)
text(165,648,'Shakespeare · Sonnet 18',10,SUB,latin=True)
ln([(708,365),(708,671)],EDGE)
text(731,365,'陪伴节奏',16,INK,True)
rr(731,402,354,35,'#E9F1F6',None,6)
for i,(t,sel) in enumerate([('日常',False),('安静',True),('专注',False)]):
    x=735+i*117
    if sel:rr(x,405,111,29,'#FFFFFF','#C7D8E5',4)
    center(x+55,411,t,12,INK if sel else SUB,sel)
text(731,459,'健康提醒',12,INK);toggle(1049,460,True)
text(731,487,'每 50 分钟，休息与眺望。',11,SUB)
rule(731,526,354)
icon('music',732,549,BLUE,19);text(761,543,'Clair de lune',15,INK,latin=True)
text(762,571,'Claude Debussy',11,SUB,latin=True)
rr(1047,545,36,36,'#DFEBF4',None,18);icon('pause',1055,553,BLUE,20)
rr(731,613,354,2,'#D3DFE8',None,1);rr(731,613,129,2,'#5D87A3',None,1)
text(731,627,'01:48',10,SUB,latin=True);right(1085,627,'04:57',10,SUB)
# Compact device strip: all values remain text, no excessive graph ornament.
rule(165,691,920)
for i,(t,v) in enumerate([('CPU','12%'),('内存','14.6 / 32 GB'),('电源','86% · 已接通'),('U 盘','未连接'),('开机自启','已开启')]):
    x=165+i*184;text(x,706,t,10,SUB);text(x,731,v,12,INK,latin=i<2)
text(165,767,'窗口可拖动缩放 · 切换时保留会话与布局',10,SUB)
right(1085,767,'静态预览 · 示例数据',10,SUB)
save_new('Yuki-融洽版-小窗口.png')
# Local review prototype: navigation changes presentation size, with no application writes.
html_source='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Yuki · 窗口尺寸预览</title><style>
*{box-sizing:border-box}body{margin:0;background:#dce5ed;color:#243c50;font-family:"Microsoft YaHei",sans-serif}header{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:12px;padding:16px 24px;background:#f8fbfd;border-bottom:1px solid #b9ccd9}strong{font-size:16px;margin-right:14px}button{padding:9px 17px;border:1px solid #b4cbdc;background:#fff;color:#284e69;border-radius:7px;cursor:pointer}button[aria-pressed="true"]{background:#173d57;color:white;border-color:#173d57}span{font-size:12px;color:#53697a;margin-left:auto}main{padding:24px;display:flex;justify-content:center;align-items:flex-start;min-height:calc(100vh - 70px)}.frame{position:relative;width:min(1120px,100%);transition:width 260ms ease}img{width:100%;height:auto;display:block}.hotspot{position:absolute;opacity:0;padding:0;min-height:0}.hotspot:focus-visible{opacity:1;background:#cce4f5;color:#173d57;outline:2px solid #286f98}.note{font-size:12px;text-align:center;padding:0 24px 22px;color:#53697a}@media(prefers-reduced-motion:reduce){.frame{transition:none}}@media(max-width:700px){header{flex-wrap:wrap}span{width:100%;margin:0}main{padding:10px}}
</style><header><strong>Yuki 窗口尺寸预览</strong><button id="small" aria-pressed="true">紧凑窗口</button><button id="large" aria-pressed="false">大窗口</button><span>静态设计交互演示 · 不连接正式程序</span></header><main><div class="frame" id="frame"><img id="preview" src="Yuki-融洽版-小窗口.png" alt="Yuki 紧凑窗口设计预览"><button class="hotspot" id="switch" aria-label="切换到大窗口" title="展开工作台"></button></div></main><p class="note">可点顶部尺寸按钮，也可点图中“展开工作台 / 紧凑窗口”。图片内其他控件仅为视觉示意。</p><script>
const state={small:true};function show(small){state.small=small;document.querySelector('#small').setAttribute('aria-pressed',String(small));document.querySelector('#large').setAttribute('aria-pressed',String(!small));const f=document.querySelector('#frame');f.style.width=small?'min(1120px,100%)':'min(1800px,100%)';const p=document.querySelector('#preview');p.src=small?'Yuki-融洽版-小窗口.png':'Yuki-融洽版-大窗口.png';p.alt=small?'Yuki 紧凑窗口设计预览':'Yuki 大窗口设计预览';const b=document.querySelector('#switch');b.style.left=(small?810/1120*100:1423/1800*100)+'%';b.style.top=(small?76/800*100:114/1160*100)+'%';b.style.width=(small?130/1120*100:141/1800*100)+'%';b.style.height=(small?38/800*100:38/1160*100)+'%';b.setAttribute('aria-label',small?'切换到大窗口':'切换到紧凑窗口');b.title=small?'展开工作台':'紧凑窗口'}document.querySelector('#small').onclick=()=>show(true);document.querySelector('#large').onclick=()=>show(false);document.querySelector('#switch').onclick=()=>show(!state.small);show(true);
</script></html>'''
(OUT/'Yuki-大小窗口切换预览.html').write_text(html_source,encoding='utf-8')
(OUT/'窗口切换设计说明.md').write_text('''# Yuki 工作台窗口切换预览

当前仅为待确认的视觉与交互预览，不修改 Electron 正式入口。

- 大窗口图：1800 × 1160 预览画布，代表宽屏布局，并不强制系统全屏。
- 紧凑窗口图：1120 × 800 预览画布，包含窗口边界；设计正文重新排版而非缩小截图。
- 右上角“展开工作台”与“紧凑窗口”互相切换；系统最大化、还原与全屏仍属不同窗口行为。
- 正式开发时，两种尺寸共用同一窗口、同一会话和计时状态；记住各自 bounds 与布局断点。
- 切换保存当前栏目、草稿、附件、播放和计时状态，不创建第二个业务会话。
- 更窄尺寸允许主区滚动、次要摘要折叠，保持正文与按钮的可读尺寸。
- 本地 HTML 只演示预览图尺寸切换，图片内其他控件不执行业务操作。
''',encoding='utf-8')
print(OUT/'Yuki-大小窗口切换预览.html')

