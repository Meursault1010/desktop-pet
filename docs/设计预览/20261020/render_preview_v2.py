from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math, random
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
OUT = BASE / 'refero-v2'
OUT.mkdir(exist_ok=True)
# Reuse only drawing primitives, never execute or replace historical previews.
old = (BASE / 'render_preview.py').read_text(encoding='utf-8')
exec(old.split('# A restrained desktop shell:')[0])
W,H = 1800,1160
im = Image.new('RGBA',(W*S,H*S),'#080f1a'); d=ImageDraw.Draw(im)
WHITE='#E8EFF8'; TEXT='#C1CEDD'; MUTED='#A6B5C8'; FAINT='#899BB3'; BLUE='#9DCBEE'; LINE='#2D3D53'
def txt_right(x,y,t,n=13,c=MUTED):
    f=font(n); b=d.textbbox((0,0),t,font=f);text(x-(b[2]-b[0])/S,y,t,n,c)
def tag(x,y,t,w=None,c=BLUE):
    w=w or len(t)*12+22
    box(x,y,w,25,'#203348',None,5);text(x+10,y+4,t,11,c)
def rule(x,y,w,c=LINE):line([(x,y),(x+w,y)],c)
def play_button(x,y):
    box(x,y,35,35,'#9DCBEE',None,17);icon('play',x+9,y+8,'#142638',18)
def small_arrow(x,y,c=BLUE):
    line([(x,y+7),(x+12,y+7),(x+12,y)],c,1.2);line([(x+6,y+1),(x+12,y),(x+11,y+6)],c,1.2)
def save(name):
    im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(OUT/name)

# Desktop window shell.
box(20,20,1760,1120,'#0B1220','#354258',15)
box(21,21,1758,56,'#101A29',None,14)
box(21,61,1758,16,'#101A29',None,0)
rule(21,77,1758,'#233146')
icon('spark',46,37,BLUE,23);text(80,30,'yuki',25,WHITE,True,True)
text(139,39,'/  工作台',12,MUTED)
text(780,40,'静态设计预览 · 示例数据',12,'#A6B5C8')
line([(1651,48),(1663,48)],MUTED)
box(1695,42,11,11,None,MUTED,0)
line([(1740,43),(1751,54)],MUTED);line([(1751,43),(1740,54)],MUTED)
# Quiet navigation spine.
line([(216,78),(216,1139)],'#243146')
text(48,112,'WORKSPACE',10,FAINT,latin=True)
for i,(t,ic) in enumerate([('总览','grid'),('角色','person'),('AI 助手','spark'),('工具','tools'),('设置','settings')]):
    y=157+i*57
    if i==0:
        box(35,y-8,166,43,'#1C2C40',None,7)
        box(35,y+4,3,18,BLUE,None,1)
    icon(ic,52,y+2,BLUE if i==0 else MUTED,19)
    text(87,y-1,t,15,WHITE if i==0 else MUTED,bold=i==0)
text(48,530,'我的页面',11,FAINT)
icon('layout',51,570,MUTED,17);text(85,566,'我的工作区',13,MUTED)
icon('plus',51,614,FAINT,17);text(85,610,'新建页面',13,FAINT)
rule(47,927,140,'#27364A')
dot(54,958,3,'#A9D0CB');text(68,948,'本地模型已连接',12,TEXT)
text(48,989,'外观主题',11,FAINT)
for i,(c,title) in enumerate([('#DCE5EE','雪白'),('#8DA4BA','银雾'),('#1E3651','星夜')]):
    x=57+i*51;dot(x,1027,7,c)
    if i==2:d.ellipse(((x-10)*S,1017*S,(x+10)*S,1037*S),outline=BLUE,width=S)
    text(x-12,1050,title,10,FAINT)
text(48,1101,'YUKI  /  DESKTOP COMPANION',9,FAINT,latin=True)
# Header and workspace tabs.
text(250,111,'总览',28,WHITE,True)
text(251,156,'此刻、今日，以及她的小小日常。',14,MUTED)
box(1590,117,154,37,'#172639','#35465D',7)
icon('layout',1604,126,TEXT,17);text(1631,125,'自定义布局',13,TEXT)
text(251,207,'默认总览',13,WHITE,True);rule(250,234,59,BLUE)
text(348,207,'我的工作区',13,MUTED);icon('plus',458,209,MUTED,15)
txt_right(1744,207,'2026 年 10 月 20 日  ·  星期二',12,FAINT)
# Main character area: no repeated card headers, breathing room around the object.
box(248,255,1006,392,'#111E2E','#2B3B50',12)
# Sparse stars with no glow, trails, or noise behind data.
random.seed(19)
for _ in range(33):
    x=random.uniform(760,1230);y=random.uniform(278,620)
    dot(x,y,random.choice([.5,.7,1]),random.choice(['#36506A','#405E79','#58758E']))
for x,y in [(1163,303),(825,371),(1180,570)]:
    line([(x-3,y),(x+3,y)],'#7597B3');line([(x,y-3),(x,y+3)],'#7597B3')
text(281,282,'YUKI  /  COMPANION',11,FAINT,latin=True)
tag(1102,279,'桌面可见',118,'#C3D7E8')
text(280,328,'雪，此刻在身边。',30,WHITE,True)
dot(285,396,3,BLUE);text(299,382,'安静待机',17,BLUE)
text(281,424,'正轻轻呼吸，陪你做自己的事。',14,TEXT)
text(281,459,'下一步',11,FAINT);text(338,457,'暂未安排',13,MUTED)
button(281,503,133,'隐藏宠物',False,'eye');button(426,503,146,'移到右下角',False,'corner')
text(281,577,'“But thy eternal summer shall not fade.”',17,'#AFBED0',italic=True)
text(281,607,'SHAKESPEARE  /  SONNET 18',9,FAINT,latin=True)
# Keep original artwork intact and in its natural aspect ratio.
pet_src=Image.open(ROOT/'console-v2/frontend/public/pet-preview.png').convert('RGBA')
pet_src=pet_src.crop(pet_src.getbbox())
pet=pet_src.copy();pet.thumbnail((round(277*S),round(307*S)),Image.Resampling.LANCZOS)
px=1007*S-pet.width//2; py=324*S
# An understated contact ellipse, separate from the character.
d.ellipse((899*S,617*S,1119*S,629*S),fill='#0C1623',outline='#25384C',width=S)
im.alpha_composite(pet,(px,py))
# Clock/weather: a different composition, not another dashboard header.
box(1278,255,466,182,'#121E2D','#29394D',12)
text(1305,274,'本地时间',11,FAINT)
text(1302,298,'14:32',57,WHITE,latin=True)
text(1307,380,'星期二  /  20 OCT 2026',11,MUTED)
line([(1542,287),(1542,408)],'#304056')
icon('sun',1567,291,BLUE,29)
text(1608,286,'18°',35,WHITE,latin=True)
text(1569,338,'多云 · 体感 17°',12,TEXT)
text(1569,380,'上海 · 14:25 更新',10,FAINT)
# Companionship and independent health notification.
box(1278,453,466,194,'#121E2D','#29394D',12)
text(1305,475,'陪伴节奏',15,WHITE,True)
box(1304,511,414,35,'#0B1523',None,6)
for x,t,sel in [(1308,'日常',False),(1445,'安静',True),(1582,'专注',False)]:
    if sel:box(x,514,132,29,'#2B4057',None,4)
    text(x+51,519,t,12,WHITE if sel else MUTED)
text(1306,561,'健康提醒',12,TEXT);text(1390,561,'每 50 分钟休息一下',11,FAINT);toggle(1683,563,True)
rule(1305,595,413,'#29394D')
icon('play',1306,613,BLUE,15);text(1331,608,'开始 25 分钟专注',12,BLUE)
# Activity: actual example records rather than invented chart decoration.
box(248,670,1006,297,'#101B2A','#29394D',12)
text(280,695,'今日足迹',17,WHITE,True)
text(280,727,'把忙碌的一天，留成可以回望的片段。',12,MUTED)
text(1113,699,'生成今日总结',12,BLUE);small_arrow(1214,700)
# Compact typographic summary with no nested cards.
text(281,768,'3',33,WHITE,latin=True);text(302,784,'小时',12,MUTED);text(338,768,'42',33,WHITE,latin=True);text(383,784,'分',12,MUTED)
text(281,820,'今日活跃时长',11,FAINT)
line([(465,776),(465,845)],'#2D3D53')
text(496,768,'2',33,WHITE,latin=True);text(524,784,'次专注',12,MUTED)
text(497,820,'为自己留出的时间',11,FAINT)
rule(280,863,942,'#29394D')
# Semantic timeline with labelled sample records.
for x,t,h,detail in [(287,'09:10','开始工作','编辑器 · Yuki 项目'),(603,'11:20','专注完成','25 分钟 · 工作时段'),(920,'14:26','任务完成','编译成功 · 素材下载完成')]:
    dot(x,891,3,BLUE);text(x+14,880,t,11,FAINT,latin=True)
    text(x+14,902,h,13,TEXT);text(x+14,931,detail,11,MUTED)
line([(371,891),(584,891)],'#31445B');line([(687,891),(901,891)],'#31445B')
# Music object, with record detail and a small playback graph that is a progress bar only.
box(1278,670,466,297,'#121E2D','#29394D',12)
text(1305,695,'正在播放',14,WHITE,True)
tag(1622,692,'音乐互动',96)
box(1305,738,78,78,'#1A2E43','#3F5870',7)
for rr in [27,19,10]:
    d.ellipse(((1344-rr)*S,(777-rr)*S,(1344+rr)*S,(777+rr)*S),outline='#607F9B',width=S)
dot(1344,777,3,'#9DCBEE')
text(1404,739,'Clair de lune',22,WHITE,latin=True)
text(1406,778,'Claude Debussy',13,MUTED,latin=True)
box(1305,845,412,3,'#2B3C51',None,1);box(1305,845,150,3,BLUE,None,1);dot(1455,846,3,WHITE)
text(1305,860,'01:48',10,FAINT,latin=True);txt_right(1718,860,'04:57',10,FAINT)
icon('prev',1433,914,MUTED,19);box(1489,896,45,45,'#25405A',None,23);icon('pause',1500,908,WHITE,22);icon('next',1573,914,MUTED,19)
text(1305,917,'系统媒体',11,FAINT)
# Device status is a low-priority quiet strip, not equal-weight hero cards.
box(248,990,1496,87,'#101A28','#29394D',10)
text(276,1007,'后台与设备',12,TEXT)
text(276,1043,'运行平稳',11,FAINT)
for x,title,value in [(449,'CPU','12%'),(595,'内存','14.6 / 32 GB'),(832,'电源','86% · 已接通'),(1085,'U 盘','未连接'),(1271,'开机自启','已开启')]:
    line([(x-23,1010),(x-23,1057)],'#29394D')
    text(x,1007,title,11,FAINT);text(x,1035,value,14,TEXT,latin=title=='CPU')
icon('check',1483,1008,'#A9D0CB',15);text(1506,1005,'编译成功',12,TEXT)
text(1485,1036,'下载完成 · 项目素材.zip',11,MUTED)
text(250,1100,'星夜  /  蓝 · 白 · 银',10,FAINT)
txt_right(1744,1100,'视觉方案 v2  ·  静态设计预览，全部数据为示例',11,FAINT)
save('Yuki-总览-Refero-v2.png')

# Save a separate compact right-click menu concept at its intended density.
W,H=1040,760
im=Image.new('RGBA',(W*S,H*S),'#0B1220');d=ImageDraw.Draw(im)
text(50,38,'Yuki',25,WHITE,True,True);text(118,49,'/  桌面快捷面板',13,MUTED)
text(51,91,'状态轻一点，对话近一点。',14,MUTED)
random.seed(21)
for _ in range(22):dot(random.uniform(52,980),random.uniform(142,671),.7,'#3A526C')
pet=pet_src.copy();pet.thumbnail((265*S,335*S),Image.Resampling.LANCZOS)
im.alpha_composite(pet,(round(229*S-pet.width/2),265*S))
# 360 x 367, compact menu driven by its content.
box(470,204,390,369,'#121E2D','#3B5068',12)
dot(495,232,3,BLUE);text(509,220,'雪 · 安静待机',13,WHITE)
text(495,251,'正轻轻呼吸，陪你做自己的事。',11,MUTED)
rule(494,286,342,'#2C3E54')
box(493,302,344,93,'#0B1523','#3B516B',7)
text(508,318,'想对雪说些什么？',13,FAINT)
text(509,368,'Enter 发送',10,FAINT)
box(797,358,27,25,'#A9CFEA',None,5)
line([(804,370),(816,370),(812,366)],'#1E3347',1.4)
icon('spark',495,418,MUTED,18);text(524,414,'划线翻译',13,TEXT);toggle(802,417,False)
icon('layout',495,463,MUTED,18);text(524,459,'打开工作台',13,TEXT)
txt_right(834,461,'Ctrl + Alt + Y',10,FAINT)
rule(494,501,342,'#2C3E54')
icon('exit',495,526,MUTED,18);text(524,522,'保存并退出',13,TEXT)
text(52,700,'静态设计预览 · 角色沿用现有素材 · 所有数据为示例',11,FAINT)
save('Yuki-右键快捷面板-Refero-v2.png')
print(OUT/'Yuki-总览-Refero-v2.png')
print(OUT/'Yuki-右键快捷面板-Refero-v2.png')

