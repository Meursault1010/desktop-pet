---
name: Yuki Workbench
description: 蓝白银的安静桌面工作室，雪与轻量工具共同陪伴。
colors:
  light-canvas: "#e6ecf1"
  light-panel: "#fcfdfe"
  light-sidebar: "#eef2f5"
  light-text: "#243c50"
  light-muted: "#53697a"
  light-line: "#d2dfe8"
  light-blue: "#276e94"
  light-blue-soft: "#e7f0f7"
  light-soft: "#f1f6f9"
  light-hover: "#e6eff5"
  light-deep: "#163d57"
  light-on-deep: "#fff"
  mist-canvas: "#ced8e1"
  mist-panel: "#e8eef3"
  mist-sidebar: "#dae4ed"
  mist-text: "#263d50"
  mist-muted: "#4c6477"
  mist-line: "#b8cbda"
  mist-blue: "#245f86"
  mist-blue-soft: "#cfdfeb"
  mist-soft: "#dde8f0"
  mist-hover: "#d3e1ec"
  mist-deep: "#234861"
  mist-on-deep: "#fff"
  dark-canvas: "#0a111b"
  dark-panel: "#121c29"
  dark-sidebar: "#101925"
  dark-text: "#e1eaf3"
  dark-muted: "#a6b8c9"
  dark-line: "#34485d"
  dark-blue: "#a7cce8"
  dark-blue-soft: "#203347"
  dark-soft: "#192838"
  dark-hover: "#24394c"
  dark-deep: "#c4ddef"
  dark-on-deep: "#10283c"
typography:
  headline:
    fontFamily: "'Segoe UI Variable','Microsoft YaHei UI','Microsoft YaHei',sans-serif"
    fontSize: "26px"
    lineHeight: 1.4
    letterSpacing: "-.025em"
  title:
    fontFamily: "'Segoe UI Variable','Microsoft YaHei UI','Microsoft YaHei',sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.6
  body:
    fontFamily: "'Segoe UI Variable','Microsoft YaHei UI','Microsoft YaHei',sans-serif"
    fontSize: "13px"
    lineHeight: 1.65
  label:
    fontFamily: "'Segoe UI Variable','Microsoft YaHei UI','Microsoft YaHei',sans-serif"
    fontSize: "12px"
  poem:
    fontFamily: "Georgia, serif"
    fontSize: "16px"
    lineHeight: 1.7
  wordmark:
    fontFamily: "Georgia, serif"
    fontSize: "28px"
  time:
    fontFamily: "'Segoe UI Variable','Microsoft YaHei UI','Microsoft YaHei',sans-serif"
    fontSize: "48px"
    fontWeight: 300
    lineHeight: 1.2
    letterSpacing: "-.04em"
rounded:
  control: "6px"
  navigation: "7px"
  theme: "8px"
  menu: "9px"
  companion: "10px"
  dialog: "12px"
spacing:
  control-y: "8px"
  control-x: "13px"
  form-y: "9px"
  form-x: "11px"
  grid: "22px"
  content-y: "24px"
  content-x: "30px"
components:
  button-primary:
    backgroundColor: "{colors.mist-deep}"
    textColor: "{colors.mist-on-deep}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.mist-blue}"
    textColor: "{colors.mist-on-deep}"
  button-secondary:
    backgroundColor: "{colors.mist-panel}"
    textColor: "{colors.mist-text}"
    rounded: "{rounded.control}"
    padding: "8px 13px"
  input:
    backgroundColor: "{colors.mist-panel}"
    textColor: "{colors.mist-text}"
    rounded: "{rounded.control}"
    padding: "9px 11px"
  nav-active:
    backgroundColor: "{colors.mist-deep}"
    textColor: "{colors.mist-on-deep}"
    rounded: "{rounded.navigation}"
    padding: "9px 15px"
  companion-strip:
    backgroundColor: "{colors.mist-soft}"
    textColor: "{colors.mist-text}"
    rounded: "{rounded.companion}"
    padding: "12px 20px 18px"
---

# Design System: Yuki Workbench

## Overview

**Creative North Star: "静夜工作室 / Quiet orbit"**

Yuki 的工作台是一间安静、精密而有生命的桌面工作室。蓝、白、银建立清楚的层级，雪的原有角色形象带来亲近感。未来感来自低饱和的冷色、细线和留白里的稀疏星尘，英文诗句只在小范围提供文学气息。

当前实现以操作效率为先：五项主导航、清楚的子页、可调整的总览区块与简短原生右键菜单共用一套颜色语义。动效说明状态、位置和响应；专注、隐藏及减少动态设置约束环境动画。本文记录 2026-10-20 的源码和验收截图，不把规划中的能力视为已实现。

**Key Characteristics:**

- 蓝白银三主题共用语义，默认银雾。
- 界面使用紧凑中文无衬线字体，品牌与少量诗句使用 Georgia。
- 内容以对齐和细分隔线组织，角色与主要操作获得有限的容器强调。
- 稀疏星尘与短促状态反馈服从阅读、专注和减少动态设置。

## Colors

### Primary

冰蓝动作色对应每个主题的 blue；deep 承担主要按钮和选中导航，on-deep 保证深色表面上的文字层级。前置令牌按 light、mist、dark 分组，分别对应「雪白」「银雾」「星夜」；银雾是初始默认。组件令牌展示默认银雾值，运行时始终通过 CSS 语义变量切换整套颜色。

### Neutral

canvas 是窗口外层，panel 是主要内容面，sidebar 是侧栏和标题栏，soft 是角色条、表单或局部选择面的浅层底色。text 承担正文，muted 承担说明，line 承担边界。hover 是交互表面，blue-soft 是选择文本和低强调状态底色。实际错误色继承 workbench.css 的 danger，不能以正常蓝色伪装错误。

**The Shared Theme Rule.** 三主题共享相同信息结构与状态语义；切换主题改变光线，不改变功能。

原生右键菜单在 pet_menu.py 使用同角色的 Qt 调色值，以适应原生绘制；它们不是逐字复制 Web 颜色。菜单的银雾表面、文字、边界与强调值分别以该文件 apply_theme 为准。

## Typography

功能文字使用 Segoe UI Variable、Microsoft YaHei UI、Microsoft YaHei 的无衬线回退栈。页面标题为 headline，节标题为 title；区块标题通常较节标题再小一级（14px），业务正文采用 body。辅助说明通常为 11px，底部状态为 10px。该密度服务于桌面窗口，不能继续缩小关键正文。

Georgia 斜体只承担 yuki 字标、总览诗句和聊天空态的少量表达性文字。诗句来源署名使用较小的无衬线字体。时钟使用轻字重与等宽数字；专注计时采用更大的数字（70px），并非通用营销 display 字阶。

**The Quiet Voice Rule.** 文学文字留在陪伴语境，功能名称、状态、错误和操作继续用直接的中文。

## Layout

桌面 Electron 为主场景：初始窗口 1180×820，最小 880×640；展开操作按当前显示器工作区设置边界，保留四周余量，并可返回紧凑窗口。根壳层为 46px 标题栏与 144px 主导航，内容独立滚动，最大壳宽为 1920px。默认内容内边距见前置令牌；宽屏从 1500px 起扩为 166px 侧栏及 32px/46px 内容边距。1150px 以下侧栏收为 126px；950px 以下总览改两列；700px 以下保留浏览器单列与可展开导航路径，不把该路径当原生桌面的默认布局。

总览采用三列可配置网格，基础间距为 grid；默认布局另用 26px 列距与 20px 行距。Yuki、时间、天气与当前状态共用一条横向区域。事件记录、陪伴节奏与系统状态在其后分层，不把所有信息做成同等权重卡片。角色和参数、剪贴板列表与详情、聊天与上下文各使用适合任务的分区。

用户页面最多 12 个、每页最多 20 个区块；区块跨 1–3 列、高度 180–640px。编辑有完成、取消及 Escape 回滚；拖动重排、菜单前后移动和右下指针尺寸调整都有实现。它是当前网格工作区，不宣称已实现任意独立浮窗或完整 Adobe 停靠系统。

## Elevation & Depth

主体是扁平的冷色层次与细分隔线，普通内容段落和区块无卡片阴影。角色条使用 soft 底色、细线和轻圆角；菜单浮层使用柔和阴影（0 12px 35px #06162525），对话框遮罩使用低透明深蓝与 3px 模糊。深度用于说明浮层关系，不在每个区域叠加强光或玻璃。

**The Flat Workspace Rule.** 通过对齐、留白、明度和细线建立秩序；浮层才需要脱离平面。

## Shapes

控件和输入采用小圆角，主导航略柔和；角色条、浮层和对话框逐级放大圆角。普通内容区保持平直的底部分隔，不套多层圆角盒。开关的胶囊和圆形 thumb 只表达开关状态；线性 SVG 图标保持简洁，不能以字符图案替代。星尘是留白里的小点，角色素材完整呈现，不裁掉服装、足部或既有身份细节。

## Components

### Buttons and Inputs

主要操作用 deep/on-deep，次要操作用 panel/text 与 line 边界；按钮最小高度 36px，按下位移 1px。输入采用细线、panel 底色和明确标签，placeholder 只是补充。聚焦为 2px blue 轮廓与 3px 偏移；禁用保留可辨识性并停止可执行动作。

### Navigation and Tabs

总览、角色、AI 助手、工具、设置共五项。选中主导航使用深色实体面；子页与总览页面使用下划线、文字字重及 aria-selected 表达状态。二级标签保留可横向滚动的路径。

### Companion Strip and Workspace Blocks

原角色预览与时间天气、真实当前状态整合显示；仅提供显示/隐藏和移角等就近动作。编辑时区块标题成为拖动入口、出现设置菜单和尺寸柄；正常状态收起编辑 chrome。未连接、无数据、保存失败、空记录均给出可理解文本，不制造数值。

### Motion

常规页面与子页进入使用 page-reveal：透明度 .75 到 1，垂直 3px 到 0，基础时长 180ms，舒缓模式为 320ms；缓动为 cubic-bezier(.16,1,.3,1)。区块位置变化采用 320ms FLIP，避免重排后失去位置感。标签下划线、导航图标和开关 thumb 使用 240ms 反馈，主题颜色过渡 300ms。星尘周期 24s，仅在背景留白轻移；角色预览 7s、1px 的微动。媒体电平只在播放状态表达活动，不是媒体控制。

用户减少动态与系统 prefers-reduced-motion 优先，关闭动画及过渡；专注或隐藏暂停环境动画，粒子可单独关闭。舒缓节奏只改变界面过渡，不改变桌宠动作速度。原生菜单的星光 reveal 为 900ms，并读取原生系统动画和减少动态设置。

### Native Menu

Qt 右键菜单聚合简短角色状态、快速聊天、翻译开关、打开工作台和退出。采用同主题家族、Georgia 斜体字标、细分隔线、小圆角输入及微弱星光；输入支持中文合成期间 Enter 不发送。聊天与工作台共用当前选中的本地/云端模型连接，原生菜单不是独立模型配置页。

## Do's and Don'ts

### Do:

- Do 使用当前主题的语义变量，保持文字、表面、边界和动作层级。
- Do 保留原角色比例、现有素材和清楚的实时状态来源。
- Do 给表单提供可见标签、键盘焦点、错误反馈与禁用状态。
- Do 在缩放、重排和页面切换时保持上下文，并尊重减少动态。

### Don't:

- Don’t 用大面积强光、彩色粒子球或星座连线替代稀疏星尘。
- Don’t 将有限事件摘要写成全天使用监测，或用虚构状态填补缺失数据。
- Don’t 把一个已安装造型描述成可用换装库，也不要宣称 Live2D 已配置。
- Don’t 用装饰性英文抢占功能文案，或让环境动态穿过正文与控件。




### 原生右键快捷页 · 2026-10-23

保留 328px 宽的 Qt 原生菜单和三主题，顶部只显示角色状态与稀疏星光。固定高度快捷区采用「对话、剪贴板、时间、待办」四个文字页签，避免菜单因回复增长跳动。底部保留翻译、工作台和保存退出。

- 对话：本次运行最近 60 条快捷对话/收到的回复，可用滚轮回看全文。纯文字显示，流式更新只在读者接近底部时自动跟随；不新增对话磁盘存档。
- 剪贴板：复用现有最近十条记录；短预览、悬停查看预览全文、双击或按钮复制原始完整内容，支持暂停记录。剪贴板不会自动发送给模型。
- 时间：共享工作台的专注/休息计时，仅显示剩余时间、开始/暂停、重置。时长与完整设置留在工作台。
- 待办：共享工作台记录，显示优先到期的五项未完成事项，支持勾选完成、添加及不提醒/30分钟/1小时提醒。输入在状态确认新增后清空，错误时保留草稿。
- 菜单关闭时停止本地刷新计时器；仅工具页可见时刷新快照。中文 IME、Esc 收起和宿主退出路由继续使用原生实现。

原生快捷页在屏幕可用高度不足时自动收紧内容区，工具页使用纵向滚动容器，页签与底部操作保留在外层。聊天记录仍在独立对话区滚动；工作台主体原有纵向滚动继续保留。


## 2026-10-24 工作台与右键菜单视觉升级（已实现）

本轮沿用蓝白银、银雾/雪白/星夜与现有五栏目结构。任务型界面优先阅读和操作，不把研究站的大标题、滚动演出直接迁移进工作台。

- 最终覆盖层仍为 `console-v2/frontend/src/workbench-v2.css`。页面标题改为26–30px，时钟40–56px，面板14px、控件8px圆角；主区域留白和总览区块间距收紧。主陪伴区用实色表面，去除两层装饰光晕。区块标题13px，取消过度字距；隐藏与归位操作使用可辨识浅底。
- 原生菜单 `console-v2/pet_menu.py` 与工作台的主文字/辅助文字/表面/强调色同步；四标签改为浅底选中，清除原生标签底线，补按钮焦点/按下状态。图标按主题重绘，避免星夜仍用浅色主题固定图标。菜单仍328px，快捷面板仍308×300px基准，小屏滚动机制不变。
- 未改事件处理、IPC、持久化、角色动作、素材或业务能力；总览仍只有默认页面，区块编辑继续保留。页面切换移除装饰进入动画，原有操作反馈及减少动态选项继续生效。
- 构建通过；五尺寸75个页面/子页检查无横向溢出或页面控制台错误，三主题与主题弹层Esc焦点恢复、主题刷新保留、窗口紧凑/展开恢复断言通过。菜单与输入相关unittest报告16项OK。前端测试68/69通过，既有动作数量测试将47写死而HEAD目录已为54，与本次样式无关，未更改动作资产或放宽测试。
- 菜单测试进程在断言全部通过后以0xC0000409异常退出；HEAD原菜单复跑同样16项OK和相同退出码，属既有测试退出问题，未将其记为完整进程通过。
- 真实Windows输入法候选窗、多显示器与125%/150% DPI未进行本轮人工复验；截图以隔离的Electron预览和Qt离屏实例取得，不等同于正式运行实例。


### 2026-10-24 用户确认的工作台字体规范（覆盖上述旧字阶）

中文使用微软雅黑 UI（Microsoft YaHei UI，缺失时微软雅黑回退），英文与数字优先 Segoe UI Variable；保留系统字体回退，不下载外部字体。正文14px/400、页面标题28px/600、区块标题14px/600、辅助说明12px/400；小窗口不再把辅助信息降至9–11px。时钟与专注计时保留现有响应式尺寸，字重300，启用 lining-nums tabular-nums。yuki字标与诗句保留衬线斜体，代码和原文内容仍保留专用等宽字体。

实现集中在workbench-v2.css的字体变量、既有字号声明与末尾字体规范区；保持布局、主题、原生菜单及业务逻辑不变。生产构建通过；五种窗口尺寸75个页面/子页检查无横向溢出和页面控制台错误，三主题截图及主题/窗口状态断言通过。浏览器核对实际计算样式：标题28/600、区块14/600、正文14/400、辅助12/400、计时300与tabular-nums。


### 2026-10-24 歌词展示规范（用户最新要求）

工作台所有原诗句/装饰引用位置统一使用现有lyricPool歌词库，歌词正文使用衬线斜体。覆盖标题栏、页脚、总览今日足迹空态及引文、未播放媒体提示、AI助手空态、角色音乐页；歌手、歌名、专辑和年份维持正体，普通状态及实际媒体歌手信息不受影响。使用lyric-quote类统一样式，保留旧poem类仅用于兼容现有布局，不代表仍展示诗歌。歌词选取及窗口恢复刷新机制保持不变；不替换用户聊天内容和业务说明。

2026-10-24 模式说明：总览与工具时间管理复用Rhythm组件，为日常、安静、专注按钮提供原生title悬停说明及aria-description辅助描述；说明对应真实切换行为，悬停不触发模式切换。生产构建及隔离Electron渲染属性检查通过。

### 2026-10-24 音乐功能收敛（用户最新要求）

移除总览音乐播放器区块、区块库入口，以及角色页的播放控制、进度条、同步歌词与桌面浮窗入口。旧布局过滤 media 区块；默认总览为陪伴、足迹、节奏、电脑状态四块，电脑状态占满最后一行，避免遗留空白。角色首个子页命名为“随音乐舞动”，保留原声音检测、舞动开关、音量节奏与状态，不改动桌宠舞动逻辑。标题栏、足迹、页脚等静态歌词装饰继续保留。
