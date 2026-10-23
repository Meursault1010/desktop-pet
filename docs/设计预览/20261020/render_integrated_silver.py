from pathlib import Path
from PIL import Image, ImageDraw, PngImagePlugin
BASE=Path(__file__).resolve().parent
# Reuse drawing primitives and the neutral window shell, preserving prior concepts.
exec((BASE/'render_silver_pages.py').read_text(encoding='utf-8').split('# Role screen:')[0])
OUT=BASE/'integrated-silver'
OUT.mkdir(exist_ok=True)
SOFT='#F1F6F9'; EDGE='#D2DFE8'; INK=C['ink']; SUB=C['secondary']; BLUE=C['blue']; PAPER=C['paper']
def surface(x,y,w,h):rr(x,y,w,h,SOFT,EDGE,11)
def named(x,y,t,sub=None):
    text(x,y,t,17,INK,True)
    if sub:text(x,y+34,sub,12,SUB)
def small_pet(x,y,w,h):pet(x,y,w,h)
def state_row(x,y,t,v,w=420):
    text(x,y,t,12,SUB);right(x+w,y,v,12,INK)
def save_new(name):
    meta=PngImagePlugin.PngInfo();meta.add_text('Description','Yuki integrated silver UI concept. Shared neutral surfaces, original character artwork, illustrative data. Static design preview; production UI unchanged.')
    p=OUT/name;im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS).save(p,pnginfo=meta);print(p)
def model_status(x,y):
    dot(x+3,y+10,3,'#3D806F');text(x+16,y,'本地模型已连接',12,SUB)

# Overview: the character participates in a shared 'now' region alongside clock and weather.
page(0,'总览','时间、工作与陪伴，都留在同一片安静的空间里。',['默认总览','我的工作区'])
icon('plus',414,194,SUB,14)
button(1580,114,164,'自定义工作区','layout')
# One shared light surface: no isolated portrait or contrasting character stage.
surface(216,242,1528,247)
text(246,263,'此刻',14,INK,True)
text(242,302,'14:32',67,INK,latin=True)
text(247,402,'10 月 20 日 · 星期二',12,SUB)
ln([(478,306),(478,435)],EDGE)
icon('sun',513,324,BLUE,33);text(562,307,'18°',43,INK,latin=True)
text(514,375,'上海 · 多云',13,SUB);text(514,408,'天气示例 · 更新于 14:25',10,SUB)
ln([(814,306),(814,435)],EDGE)
text(852,311,'雪 · 安静待机',18,INK,True)
text(853,353,'正在轻轻呼吸，陪你做自己的事。',13,SUB)
text(853,387,'下一步暂未安排',11,SUB)
# Small character shares the surface with contextual text, original artwork unmodified.
small_pet(1434,281,178,182)
button(853,424,130,'隐藏宠物','eye');button(995,424,168,'移到右下角','corner')
# Activity is on the common page rather than an equally prominent tile grid.
named(218,530,'今日足迹','活跃 3 小时 42 分钟，完成 2 段专注。')
text(975,536,'生成今日总结',12,BLUE);icon('arrow',1086,537,BLUE,17)
rule(218,613,893)
for y,when,title,detail in [(648,'14:26','编译成功','Yuki 项目 · 任务结果'),(732,'11:20','完成一段专注','25 分钟 · 时间管理'),(816,'09:10','开始今天的工作','编辑器 · 活动记录')]:
    text(220,y,when,12,SUB,latin=True)
    dot(304,y+10,3,'#6C91AA');text(325,y-3,title,15,INK)
    right(1110,y+2,detail,11,SUB)
    if y<816:rule(325,y+55,786)
text(219,901,'“But thy eternal summer shall not fade.”',18,SUB,serif=True)
text(220,934,'William Shakespeare · Sonnet 18',10,SUB,latin=True)
# Companion modes are conventional functional controls, no character picture here.
ln([(1150,530),(1150,967)],EDGE)
named(1185,530,'陪伴节奏')
rr(1184,578,560,40,'#EAF1F6',None,6)
for i,(t,sel) in enumerate([('日常',False),('安静',True),('专注',False)]):
    x=1188+i*185
    if sel:rr(x,581,181,34,'#FFFFFF','#C5D7E3',5)
    center(x+90,589,t,12,INK if sel else SUB,sel)
text(1185,642,'安静陪伴，保留到期待办和重要提醒。',12,SUB)
text(1185,689,'健康提醒',13,INK);toggle(1708,690,True)
text(1185,723,'每 50 分钟提醒休息与眺望。',12,SUB)
rule(1185,772,559)
icon('music',1187,800,BLUE,21);text(1221,795,'Clair de lune',17,INK,latin=True)
text(1223,829,'Claude Debussy',11,SUB,latin=True)
icon('prev',1560,803,SUB,18);rr(1610,791,37,37,'#E0EBF3',None,19);icon('pause',1619,800,BLUE,19);icon('next',1676,803,SUB,18)
rr(1186,873,556,2,'#D4DFE7',None,1);rr(1186,873,202,2,'#5D87A3',None,1)
text(1185,886,'01:48',10,SUB,latin=True);right(1744,886,'04:57',10,SUB)
# All system items sit on a shared low-contrast baseline.
rule(216,975,1528)
for i,(t,v) in enumerate([('CPU','12%'),('内存','14.6 / 32 GB'),('电源','86% · 已接通'),('U 盘','未连接'),('开机自启','已开启')]):
    x=219+i*251
    text(x,996,t,11,SUB);text(x,1027,v,14,INK,latin=i<2)
icon('check',1490,1001,'#347A67',17);text(1517,998,'下载完成',12,INK);text(1491,1029,'项目素材.zip · 示例',11,SUB)
save_new('Yuki-融洽版-总览.png')

# Character: neutral preview shares the page, no theatrical background.
page(1,'角色','浏览动作，调整外观，了解雪的日常。',['音乐互动','动作','外观','行为逻辑'],1)
button(1597,114,147,'在桌面演示','play',True)
text(219,257,'动作分类',12,SUB)
for i,t in enumerate(['全部动作','站立待机','坐下待机','趴着待机','睡眠','移动与舞蹈','拖拽与物理','附着与互动','情绪与事件','出现与离开']):
    y=302+i*45
    if i==1:rr(216,y-8,174,36,'#E5EFF6',None,6)
    text(233,y,t,13,INK if i==1 else SUB,i==1)
ln([(413,242),(413,1044)],EDGE)
# Preview region has the same tone as controls and thumbnails.
surface(444,242,810,545)
text(472,266,'安静等待',17,INK,True);right(1225,270,'站立待机',11,SUB)
pet(728,332,240,290)
# A subtle grounding mark beneath feet, no spotlight or glow.
d.ellipse((795*S,623*S,901*S,630*S),fill='#DCE7EE')
pet(728,332,240,290)
rule(472,698,753,EDGE)
text(472,734,'预览播放',11,SUB)
icon('prev',756,734,SUB,18);rr(808,723,36,36,'#DDE9F2',None,18);icon('pause',816,731,BLUE,20);icon('next',878,734,SUB,18)
right(1224,734,'00:01 / 00:03',11,SUB)
text(446,823,'站立待机',16,INK,True);field(1002,815,252,'搜索动作')
for i,(a,t) in enumerate([('wait','等待'),('comb','梳头'),('dress','整理衣服'),('stretch','伸懒腰'),('yawn','打哈欠')]):
    x=444+i*164
    rr(x,870,152,174,'#F3F7FA','#9AB9CF' if i==0 else '#D6E1E9',8)
    asset(x+26,883,100,117,a);text(x+14,1018,t,12,INK if i==0 else SUB,i==0)
ln([(1291,242),(1291,1044)],EDGE)
named(1325,256,'动作信息')
text(1325,313,'安静等待',23,INK,True);text(1325,359,'轻微呼吸与放松的小幅动作。',13,SUB)
rule(1325,409,419)
for y,t,v in [(440,'姿态归属','站立'),(494,'触发方式','自然待机 / 手动预览'),(548,'表现方式','动作帧与程序呼吸'),(602,'播放策略','活动后自然停留')]:state_row(1325,y,t,v,419)
rule(1325,657,419)
named(1325,689,'自然衔接')
text(1325,736,'站立 → 安静等待 → 自然停留',13,SUB)
text(1325,792,'只播放一个预览，缩略图保持静止。',12,SUB)
text(1325,824,'预览不会打断桌面上的雪。',12,SUB)
rule(1325,922,419)
text(1325,950,'角色沿用原有素材，保持自然比例。',12,SUB)
text(1325,991,'演示结束后恢复原有行为。',12,SUB)
save_new('Yuki-融洽版-角色动作.png')

# Assistant: no separate character showcase; Yuki appears as the speaking identity.
page(2,'AI 助手','把想说的话、想做的事，慢慢说给雪听。',['本地模型','云端 API'])
button(1608,114,136,'连接设置','settings')
text(219,256,'对话',15,INK,True);icon('plus',462,259,BLUE,18)
rule(218,297,266)
for i,(t,m) in enumerate([('截图文字与翻译','今天 14:32'),('今天的工作安排','今天 10:16'),('与雪聊聊天','昨天 20:41')]):
    y=333+i*91
    if i==0:rr(211,y-13,282,76,'#E7F0F6',None,7)
    text(232,y,t,13,INK,i==0);text(232,y+30,m,11,SUB)
text(232,989,'会话保留在本机。',11,SUB)
ln([(522,242),(522,1044)],EDGE)
model_status(558,255);text(777,255,'Qwen · 本地服务',12,SUB)
right(1744,255,'图片处理：本地 OCR',11,SUB)
rule(558,297,1186)
center(1150,325,'今天 14:32',11,SUB)
rr(1088,377,598,108,'#E9F1F6',None,11)
text(1112,394,'雪，帮我识别这张截图里的英文，再翻译成中文。',15,INK)
rr(1112,441,185,25,'#DCE9F2',None,5);text(1124,447,'截图.png · 已提取文字',10,SUB)
# Compact original character and name: no dedicated rail or large portrait.
rr(599,536,68,73,'#F0F5F8',None,9)
small_pet(606,542,54,62)
text(687,545,'雪',16,INK,True);text(687,575,'本地回答',11,SUB)
text(688,629,'我读到了这句话：',14,SUB)
text(687,676,'“Take a moment to rest your eyes.”',26,INK,latin=True)
text(688,732,'中文是：“让眼睛休息一会儿。”',17,INK)
text(688,785,'先看看远处，让眼睛放松一下，再慢慢继续。',14,SUB)
icon('check',687,843,BLUE,15);text(713,840,'由本地 OCR 提取文字 · 回答完成',11,SUB)
# Conversation read width remains bounded, composer spans useful space.
rr(591,920,1117,124,'#F1F6F9','#B1C8D9',10)
text(613,940,'继续和雪聊聊…',15,SUB)
icon('plus',613,1001,SUB,18);text(642,999,'图片或文档',12,SUB)
text(1273,1004,'Enter 发送 / Shift + Enter 换行',10,SUB)
button(1594,990,93,'发送',primary=True)
save_new('Yuki-融洽版-AI助手.png')

