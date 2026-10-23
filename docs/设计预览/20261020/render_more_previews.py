from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import random, math
BASE=Path(__file__).resolve().parent
exec((BASE/'render_preview.py').read_text(encoding='utf-8').split('# A restrained desktop shell:')[0])
ROOT=BASE.parents[2]
OUT=BASE/'refero-v2'
OUT.mkdir(exist_ok=True)
W,H=1800,1160
WHITE='#E8EFF8';TEXT='#C1CEDD';MUTED='#A6B5C8';FAINT='#899BB3';BLUE='#9DCBEE';LINE='#2D3D53'
BG='#0B1220';SURF='#121E2D';ELEV='#1A293D';INPUT='#0D1726'

def rule(x,y,w,c=LINE):line([(x,y),(x+w,y)],c)
def right(x,y,t,n=13,c=MUTED):
    f=font(n);b=d.textbbox((0,0),t,font=f);text(x-(b[2]-b[0])/S,y,t,n,c)
def tag(x,y,t,w=90,c=BLUE):
    box(x,y,w,25,'#203348',None,5);text(x+10,y+4,t,11,c)
def btn(x,y,w,t,primary=False,ic=None):button(x,y,w,t,primary,ic)
def avatar(x,y,w,h,asset='pet-preview.png',alpha=255):
    p=Image.open(ROOT/'console-v2/frontend/public'/asset).convert('RGBA')
    p=p.crop(p.getbbox());p.thumbnail((round(w*S),round(h*S)),Image.Resampling.LANCZOS)
    if alpha<255:p.putalpha(p.getchannel('A').point(lambda a:a*alpha//255))
    im.alpha_composite(p,(round((x+w/2)*S-p.width/2),round((y+h)*S-p.height)))
def frame(x,y,w,h,title=None,fill=SURF):
    box(x,y,w,h,fill,LINE,12)
    if title:text(x+25,y+21,title,16,WHITE,True)
def row_icon(x,y,ic,t,selected=False,w=182):
    if selected:box(x-11,y-8,w,38,'#203349',None,6)
    icon(ic,x,y+1,BLUE if selected else MUTED,17);text(x+29,y-2,t,13,WHITE if selected else MUTED,bold=selected)
def tabs(items,selected=0):
    x=251
    for i,t in enumerate(items):
        text(x,207,t,13,WHITE if i==selected else MUTED,bold=i==selected)
        tw=d.textlength(t,font=font(13))/S
        if i==selected:rule(x,234,tw,BLUE)
        x+=tw+40

def shell(section,title,subtitle):
    global im,d
    im=Image.new('RGBA',(W*S,H*S),'#080F1A');d=ImageDraw.Draw(im)
    box(20,20,1760,1120,BG,'#354258',15)
    box(21,21,1758,56,'#101A29',None,14);box(21,61,1758,16,'#101A29',None,0);rule(21,77,1758,'#233146')
    icon('spark',46,37,BLUE,23);text(80,30,'yuki',25,WHITE,True,True);text(139,39,'/  工作台',12,MUTED)
    text(780,40,'静态设计预览 · 示例数据',12,MUTED)
    line([(1651,48),(1663,48)],MUTED);box(1695,42,11,11,None,MUTED,0)
    line([(1740,43),(1751,54)],MUTED);line([(1751,43),(1740,54)],MUTED)
    line([(216,78),(216,1139)],'#243146')
    text(48,112,'工作空间',11,FAINT)
    for i,(t,ic) in enumerate([('总览','grid'),('角色','person'),('AI 助手','spark'),('工具','tools'),('设置','settings')]):
        y=157+i*57;sel=i==section
        if sel:box(35,y-8,166,43,'#1C2C40',None,7)
        icon(ic,52,y+2,BLUE if sel else MUTED,19);text(87,y-1,t,15,WHITE if sel else MUTED,bold=sel)
    text(48,530,'我的页面',11,FAINT);row_icon(51,570,'layout','我的工作区',False,145);row_icon(51,614,'plus','新建页面',False,145)
    rule(47,927,140,'#27364A');dot(54,958,3,'#A9D0CB');text(68,948,'本地模型已连接',12,TEXT)
    text(48,989,'外观主题',11,FAINT)
    for i,(c,t) in enumerate([('#DCE5EE','雪白'),('#8DA4BA','银雾'),('#1E3651','星夜')]):
        x=57+i*51;dot(x,1027,7,c)
        if i==2:d.ellipse(((x-10)*S,1017*S,(x+10)*S,1037*S),outline=BLUE,width=S)
        text(x-12,1050,t,10,FAINT)
    text(48,1101,'Yuki Desktop Companion',10,FAINT,latin=True)
    text(250,111,title,28,WHITE,True);text(251,156,subtitle,14,MUTED)
    text(250,1100,'星夜  /  蓝 · 白 · 银',10,FAINT)
    right(1744,1100,'静态设计预览 · 全部内容为示例 · 待确认后开发',11,FAINT)

def save(name):
    path=OUT/name;im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(path);print(path)

# 1. Character: catalog, stage and inspector with distinct roles.
shell(1,'角色','每一种小动作，都有自己的时刻。')
tabs(['音乐互动','动作','外观','行为逻辑'],1)
box(1578,117,166,37,ELEV,LINE,7);icon('eye',1592,126,TEXT,17);text(1620,125,'仅在舞台预览',12,TEXT)
# Category rail.
text(250,264,'动作分类',12,FAINT)
cats=['全部动作','出现与离开','站立待机','坐下待机','趴着待机','睡眠','移动与舞蹈','拖拽与物理','附着与互动','情绪与事件']
for i,t in enumerate(cats):
    y=309+i*45
    if i==2:box(248,y-8,190,36,'#1D3045',None,6)
    text(264,y-1,t,13,WHITE if i==2 else MUTED,bold=i==2)
    if i==2:dot(416,y+9,2,BLUE)
rule(262,792,158)
text(264,814,'待机姿态',11,FAINT)
text(264,848,'站立  /  坐下',12,MUTED);text(264,882,'趴着  /  睡觉',12,MUTED)
text(264,1013,'预览不会打断',11,FAINT);text(264,1036,'桌面上雪的活动。',11,FAINT)
# Stage.
frame(462,255,838,537)
text(489,278,'安静等待',18,WHITE,True);tag(1184,276,'站立待机',90)
random.seed(21)
for _ in range(32):dot(random.uniform(500,1265),random.uniform(325,716),random.choice([.6,.8,1]),random.choice(['#344C65','#47647F']))
line([(670,716),(1093,716)],'#2D435A')
avatar(689,342,384,368,'pet-preview.png')
text(488,748,'舞台预览',11,FAINT)
icon('prev',806,750,MUTED,18);box(861,737,36,36,'#284159',None,18);icon('pause',869,745,WHITE,19);icon('next',932,750,MUTED,18)
right(1272,749,'00:01 / 00:03',11,FAINT)
# Inspector as aligned rows rather than repeated cards.
frame(1324,255,420,817,'动作信息')
text(1351,317,'安静等待',23,WHITE,True);text(1351,356,'轻微呼吸与放松的小幅动作。',13,MUTED)
rule(1350,402,368)
for y,t,v in [(426,'姿态归属','站立'),(473,'触发方式','自然待机 / 手动预览'),(520,'表现方式','动作帧 + 呼吸'),(567,'播放策略','自然停留，避免重复')]:
    text(1351,y,t,12,FAINT);right(1717,y,v,12,TEXT)
rule(1350,615,368)
text(1351,640,'衔接',14,WHITE,True);text(1351,678,'站立待机 → 安静等待 → 自然停留',12,MUTED)
text(1351,724,'同一时间只播放一个预览，',12,FAINT);text(1351,750,'缩略图保持静止。',12,FAINT)
btn(1351,818,366,'在桌面演示',True,'play')
text(1351,881,'演示结束后恢复原有行为。',12,MUTED)
rule(1350,970,368);icon('check',1351,996,'#A9D0CB',17);text(1379,993,'原有角色素材，未重新绘制',12,MUTED)
# Library below stage.
text(464,819,'站立待机',16,WHITE,True)
box(1051,813,249,32,INPUT,LINE,6);text(1064,820,'搜索动作名称',12,FAINT)
for i,(asset,title) in enumerate([('wait','等待'),('comb','梳头'),('dress','整理衣服'),('stretch','伸懒腰'),('yawn','打哈欠')]):
    x=462+i*170
    box(x,868,158,176,'#111D2C',BLUE if i==0 else LINE,8)
    avatar(x+19,883,120,120,f'actions/{asset}/poster.png')
    text(x+14,1017,title,12,WHITE if i==0 else MUTED)
save('Yuki-角色动作-Refero-v2.png')

# 2. Assistant: calm message reading and useful context, no stars under text.
shell(2,'AI 助手','把想说的话、想做的事，交给雪。')
tabs(['本地模型','云端 API'],0)
btn(1614,117,130,'连接设置',False,'settings')
frame(248,255,253,817,fill='#101B2A')
btn(266,275,216,'新建对话',False,'plus')
text(271,346,'今天',11,FAINT)
for y,title,sub,sel in [(388,'一张截图里的文字','14:32 · 文字识别',True),(470,'今天的工作安排','10:16 · 日常对话',False),(552,'一句英文的翻译','09:08 · 翻译',False)]:
    if sel:box(261,y-11,227,70,'#203348',None,6)
    text(276,y,title,13,WHITE if sel else TEXT);text(276,y+27,sub,10,FAINT)
text(271,663,'昨天',11,FAINT);text(276,705,'与雪聊聊天',13,TEXT);text(276,734,'20:41 · 日常对话',10,FAINT)
rule(270,970,207);text(273,992,'会话保留在本机。',11,MUTED);text(273,1018,'清理会话不会删除长期记忆。',10,FAINT)
# Main chat, open canvas.
dot(535,277,3,'#A9D0CB');text(549,266,'Qwen · 本地服务',13,TEXT);right(1374,266,'连接正常',11,MUTED)
rule(527,306,853)
text(539,336,'今天 14:32',11,FAINT)
box(841,378,522,119,'#203348',None,10)
text(863,397,'雪，帮我识别这张截图里的英文，',15,WHITE);text(863,426,'再翻译成中文。',15,WHITE)
box(864,459,183,25,'#14273B',None,4);icon('files',874,464,MUTED,15);text(877,463,'截图.png  ·  已提取文字',10,TEXT)
# An authored minimal avatar icon for identity; real character stays in context panel.
box(538,550,31,31,'#1D334A',None,7);icon('spark',545,557,BLUE,18);text(583,550,'雪',14,WHITE,True)
tag(622,551,'OCR 文字识别',111)
text(584,597,'识别到的原文：',13,MUTED)
text(584,633,'“Take a moment to rest your eyes.”',20,WHITE,latin=True)
text(584,685,'中文是：“让眼睛休息一会儿。”',16,TEXT)
text(584,733,'这句话是在温柔地提醒你暂停一下，',14,MUTED)
text(584,762,'看看远处，再慢慢继续。',14,MUTED)
text(584,812,'图片由本地 OCR 提取文字，再交给模型回答。',11,FAINT)
icon('check',584,853,MUTED,14);text(607,850,'回答完成',10,FAINT)
# Fixed composer.
box(527,924,853,148,'#111F30','#3B536C',10)
text(548,944,'继续和雪聊聊…',15,FAINT)
icon('plus',548,1024,MUTED,19);text(579,1023,'图片或文档',12,MUTED)
text(982,1030,'Enter 发送 / Shift + Enter 换行',10,FAINT)
btn(1260,1017,99,'发送',True)
# Context rail.
frame(1404,255,340,817)
text(1430,280,'和雪在一起',15,WHITE,True)
random.seed(41)
for _ in range(14):dot(random.uniform(1445,1700),random.uniform(320,512),.7,'#405E79')
avatar(1487,327,171,197)
text(1431,559,'“Let me not to the marriage',15,MUTED,italic=True)
text(1431,584,'of true minds admit impediments.”',14,MUTED,italic=True)
text(1431,615,'Shakespeare · Sonnet 116',10,FAINT,latin=True)
rule(1430,662,288)
text(1431,687,'当前对话',13,WHITE,True)
for y,t,v in [(730,'模型来源','本地'),(775,'附件处理','本地 OCR / 文档解析'),(820,'云端发送','未启用')]:
    text(1431,y,t,11,FAINT);right(1717,y,v,11,TEXT)
rule(1430,875,288)
text(1431,900,'人设与长期记忆',13,TEXT);icon('chevron',1696,901,MUTED,16)
text(1431,937,'你可以查看雪记住了什么。',11,MUTED)
text(1431,1017,'不会自动将本地会话切换到云端。',10,FAINT)
save('Yuki-AI助手-Refero-v2.png')

# 3. Tools: the running timer is the task, with a list of concrete reminders.
shell(3,'工具','安排时间，留住灵感，再给自己一点余地。')
tabs(['时间管理','剪贴板','待办事项'],0)
btn(1578,117,166,'提醒与通知',False,'settings')
frame(248,255,967,546)
text(281,283,'专注中',17,WHITE,True);right(1181,287,'今日第 2 段专注',12,MUTED)
# The timer is a functional readout, no decorative dial.
text(518,361,'18:42',110,WHITE,latin=True)
text(577,501,'这段时间，交给眼前这一件事。',15,MUTED)
box(486,562,476,44,INPUT,None,7);icon('check',502,576,BLUE,16);text(531,573,'正在专注：整理 Yuki 的界面设计',14,TEXT)
btn(562,653,151,'暂停',True,'pause');btn(728,653,151,'结束专注',False)
rule(281,741,902)
text(281,760,'25 分钟专注',12,TEXT);text(507,760,'5 分钟短休',12,MUTED);text(730,760,'完成 4 轮后长休',12,MUTED)
right(1181,760,'调整时长',12,BLUE)
# A task list, not another timer card.
frame(1239,255,505,546,'接下来')
text(1266,316,'今天，给重要的事留位置。',13,MUTED)
for i,(title,when,sel) in enumerate([('整理 Yuki 的界面设计','进行中',True),('休息，喝一点水','本轮专注结束后',False),('检查动作衔接','16:00 提醒',False),('备份项目文件','18:30 提醒',False)]):
    y=376+i*89
    if sel:box(1258,y-11,467,74,'#203348',None,6)
    box(1271,y+3,15,15,None,BLUE if sel else '#657E98',3)
    if sel:dot(1278.5,y+10.5,3,BLUE)
    text(1304,y,title,14,WHITE if sel else TEXT);text(1304,y+30,when,11,BLUE if sel else FAINT)
btn(1267,736,449,'添加待办',False,'plus')
# History rows show factual example records rather than random activity charts.
frame(248,825,967,247,'今天的专注')
right(1181,850,'查看记录',12,BLUE)
for i,(when,task,duration,state) in enumerate([('10:30 – 10:55','梳理工作台页面','25 分钟','已完成'),('14:26 – 14:32','整理 Yuki 的界面设计','进行中','专注中')]):
    y=901+i*75
    if i:rule(279,y-16,904)
    text(281,y,when,13,TEXT);text(492,y,task,13,TEXT);text(918,y,duration,12,MUTED)
    tag(1090,y-1,state,93,'#A9D0CB' if not i else BLUE)
    text(493,y+29,'时间管理',10,FAINT)
frame(1239,825,505,247,'专注时的陪伴')
text(1266,889,'减少闲聊和主动散步',14,TEXT);toggle(1683,892,True)
text(1266,924,'保留到期待办与重要系统提醒。',12,MUTED)
rule(1265,969,451)
text(1266,993,'健康提醒',12,TEXT);right(1716,993,'与休息时间合并',12,MUTED)
text(1266,1029,'不让两个提醒同时打断你。',11,FAINT)
save('Yuki-工具时间管理-Refero-v2.png')

# 4. Settings: a readable vertical form and a live visual sample.
shell(4,'设置','让工作台与雪，都更适合你的习惯。')
# Local settings navigation.
text(251,211,'偏好设置',12,FAINT);right(1744,211,'视觉方案 · 设置状态仅作示意',11,FAINT)
for i,t in enumerate(['通用','主题与动态','通知','快捷键','人设与长期记忆','隐私与数据','诊断与版本']):
    y=278+i*54
    if i==1:box(248,y-9,201,39,'#1D3045',None,6)
    text(266,y,t,13,WHITE if i==1 else MUTED,bold=i==1)
# Open aligned form.
text(487,270,'主题与动态',21,WHITE,True)
text(488,311,'蓝白银的三种明暗，保留同样的秩序。',13,MUTED)
for i,(title,col,canvas,fg,sel) in enumerate([('雪白','#F5F7FA','#FFFFFF','#253B4E',False),('银雾','#D9E2EC','#E8EDF2','#354C60',False),('星夜','#0B1220','#1A293D','#E8EFF8',True)]):
    x=487+i*213
    box(x,366,193,141,col,BLUE if sel else '#42546A',8,2 if sel else 1)
    box(x+10,379,36,116,'#122036' if sel else '#CCD7E1',None,3)
    for yy in [391,414,437]:box(x+18,yy,20,4,'#8297AB',None,1)
    box(x+57,379,124,57,canvas,None,3);box(x+57,449,73,46,canvas,None,3);box(x+139,449,42,46,canvas,None,3)
    text(x+1,522,title,13,WHITE if sel else MUTED)
    if sel:icon('check',x+166,526,BLUE,17)
rule(486,578,619)
# Settings rows each has a text group and a control aligned right.
for y,t,desc,on in [(609,'跟随系统主题','随系统在雪白与星夜之间切换。',False),(699,'星辰背景','稀疏、缓慢，仅出现在预览与留白区域。',True),(789,'减少动态效果','关闭环境粒子与非必要过渡。',False)]:
    text(488,y,t,14,TEXT);text(488,y+31,desc,11,MUTED);toggle(1068,y+8,on);rule(487,y+70,618,'#26364A')
text(488,883,'界面密度',14,TEXT);text(488,915,'调整间距，不缩小文字与操作区域。',11,MUTED)
box(866,877,239,37,INPUT,LINE,6);box(986,881,115,29,'#294058',None,4)
text(904,886,'紧凑',12,MUTED);text(1025,886,'舒展',12,WHITE)
rule(487,959,618)
text(488,985,'界面缩放',14,TEXT);text(488,1016,'按显示器尺寸选择舒适的阅读大小。',11,MUTED)
box(986,982,119,36,ELEV,LINE,6);text(1006,990,'100%',13,TEXT,latin=True);icon('chevron',1079,993,MUTED,14)
# Preview zone.
frame(1140,255,604,817)
text(1168,282,'效果预览',15,WHITE,True);tag(1640,280,'星夜',76)
random.seed(72)
for _ in range(28):dot(random.uniform(1182,1700),random.uniform(340,779),random.choice([.5,.8,1]),'#4A6A86')
box(1270,371,344,70,'#DFEDF8',None,18);text(1293,389,'陪你把今天慢慢过完。',16,'#2D4B64')
# small speech tail
p=[(1436*S,438*S),(1450*S,453*S),(1460*S,438*S)];d.polygon(p,fill='#DFEDF8')
avatar(1315,479,259,289)
text(1257,830,'“So long as men can breathe”',17,MUTED,italic=True)
text(1321,862,'Shakespeare · Sonnet 18',10,FAINT,latin=True)
rule(1168,919,548)
text(1168,946,'星辰会缓慢移动，静态图展示疏密与层次。',12,MUTED)
text(1168,981,'开启“减少动态效果”时，保留安静的纯色背景。',11,FAINT)
save('Yuki-设置主题动态-Refero-v2.png')

# 5. Layout editing state: affordances appear only during intentional editing.
shell(0,'我的工作区','正在编辑布局，调整只影响当前页面。')
text(251,207,'默认总览',13,MUTED);text(348,207,'我的工作区',13,WHITE,True);rule(348,234,65,BLUE);icon('plus',462,209,MUTED,15)
btn(1501,117,105,'取消',False);btn(1620,117,124,'完成布局',True)
tag(1325,124,'布局编辑中',126)
# Editing targets, handle region separated from content.
def edit_panel(x,y,w,h,title,selected=False):
    box(x,y,w,h,SURF,BLUE if selected else LINE,10,1.5 if selected else 1)
    handle(x+18,y+22);text(x+36,y+12,title,13,WHITE)
    text(x+w-37,y+9,'···',18,MUTED,latin=True);rule(x+1,y+43,w-2,'#30445B')
    if selected:
        for xx,yy in [(x,y),(x+w,y),(x,y+h),(x+w,y+h)]:box(xx-3,yy-3,6,6,'#A8CFEA',None,1)
        line([(x+w-20,y+h-7),(x+w-7,y+h-20)],BLUE)
        line([(x+w-13,y+h-7),(x+w-7,y+h-13)],BLUE)
edit_panel(248,255,686,418,'雪的此刻',True)
text(276,332,'雪，在这里。',25,WHITE,True);dot(281,393,3,BLUE);text(294,381,'安静待机',14,BLUE)
text(277,423,'正轻轻呼吸，陪你做自己的事。',12,MUTED)
btn(276,493,129,'隐藏宠物',False,'eye');btn(417,493,145,'移到右下角',False,'corner')
avatar(649,330,239,276)
text(277,610,'“But thy eternal summer shall not fade.”',14,MUTED,italic=True)
edit_panel(954,255,384,418,'时间与天气')
text(980,332,'14:32',58,WHITE,latin=True);text(984,416,'10 月 20 日 · 星期二',12,MUTED)
rule(982,468,327);icon('sun',984,506,BLUE,29);text(1034,493,'18°',36,WHITE,latin=True);text(1038,544,'上海 · 多云',12,MUTED)
text(984,616,'地点与天气为示例。',11,FAINT)
edit_panel(248,697,1090,364,'今日足迹')
text(276,770,'从今天开始，到此刻。',21,WHITE,True);right(1308,777,'生成今日总结',12,BLUE)
text(277,814,'今天活跃 3 小时 42 分钟，完成了 2 段专注。',13,MUTED)
rule(277,868,1031)
for x,t,h,detail in [(285,'09:10','开始工作','编辑器 · Yuki 项目'),(636,'11:20','专注完成','25 分钟 · 工作时段'),(987,'14:26','任务完成','编译成功 · 素材下载完成')]:
    dot(x,910,3,BLUE);text(x+14,897,t,11,FAINT,latin=True);text(x+14,932,h,14,TEXT);text(x+14,969,detail,11,MUTED)
# Temporary block library drawer.
frame(1362,255,382,806,fill='#172437')
text(1389,279,'添加区块',18,WHITE,True)
line([(1707,284),(1718,295)],MUTED);line([(1718,284),(1707,295)],MUTED)
text(1389,320,'按需组合自己的桌面工作区。',12,MUTED)
box(1388,361,330,36,INPUT,LINE,6);text(1401,370,'搜索区块',12,FAINT)
for i,(title,desc,ic,added) in enumerate([('雪的此刻','当前状态与快捷操作','person',True),('时间与天气','本地时钟与天气摘要','sun',True),('陪伴节奏','安静、日常与健康提醒','moon',False),('正在播放','系统媒体与播放控制','play',False),('专注计时','与时间管理共享计时状态','check',False),('剪贴板','最近 10 条文本','layout',False)]):
    y=432+i*87
    icon(ic,1391,y+8,MUTED,20);text(1426,y,title,14,TEXT);text(1426,y+29,desc,10,FAINT)
    icon('check' if added else 'plus',1694,y+10,FAINT if added else BLUE,18)
    if i<5:rule(1388,y+66,329,'#2A3C52')
rule(1388,973,330)
text(1389,995,'移除区块只改变布局，',11,MUTED);text(1389,1020,'不会删除聊天、待办或历史数据。',11,MUTED)
# a helpful non-technical edit-status line.
text(248,1080,'拖动标题栏移动 · 拖动选中区块右下角调整大小',11,MUTED)
right(1338,1080,'恢复默认布局',11,BLUE)
save('Yuki-自定义布局编辑态-Refero-v2.png')

