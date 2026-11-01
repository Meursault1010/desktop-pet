# Yuki 跳跃动作 · 重做提示词（详细版）

> **本轮驳回判据（先看这一条）**：出现下列任何一项，该帧直接判废，不要修——
> ① 双臂向两侧张开成"大"字／星形跳；② 双脚左右分开或一前一后；③ 离地超过 24px；
> ④ 头发整体甩动、飘起或向一侧倒；⑤ 腿是伸直的（没有屈膝收脚）；⑥ 脸、线宽、裙花纹和待机母版不一致。

## 走哪条路线


**AI 帧生成 + 主帧派生链**，不用程序绑骨（2026-10-29 用户已就梳头明确否掉绑骨："算了，你还是给我使用帧生成吧，不要绑定了"）。管线与 `console-v2/action-work/comb-gen/README.md` 同源：

1. `ref/idle-anchor-256.png` = 待机母版第 1 格，画风/比例/落位基准。
2. `ref/master-white.png` = 该格放大到 1024 铺纯白底，作为 IMAGE 1 编辑对象。
3. **先只出主帧（顶点 b04）一张**，过审后才派生其余相位。
4. 派生帧一律以**主帧**为 IMAGE 1，提示词只写"这一拍比主帧高多少/低多少、腿放开多少、手降到哪里"，不再重复画风。
5. 后处理：`comb-gen/proc.py` 的 `cut/metrics/place`（rembg `isnet-anime` → 去白边 → 共用主帧缩放 → 按裙摆带中心对 x=123、脚底 250）→ 逐帧 UnsharpMask **只作用 RGB、保留 alpha** → 关键拍之间一律硬切。
6. 离批检测：两帧 alpha>16 交集腐蚀 3 圈，只比内部 RGB 均值；同批 7–13，20+ 判离批。

### 主帧提示词（b04 顶点，实际使用原文）

IMAGE 1 = `ref/master-white.png`，IMAGE 2 = `ref/idle-anchor-256.png`，`1024x1024`。

```text
EDIT IMAGE 1 (the white-background sprite) into ONE key pose of a tiny in-place hop. Keep IMAGE 1's face, eye shape, eye size, hair silhouette, hair volume, hairclip, earrings, dress cut, skirt snowflake pattern, line weight, palette and anti-aliasing EXACTLY as drawn — redraw only the two arms, the two legs/feet and the eyelids/mouth. Same camera, same scale, same center, full body, nothing cropped, flat pure white background, no shadow, no props.

Pose (apex of a small cute bunny hop): she is airborne just 18 px above her ground line. Both knees bend together and symmetrically and tuck straight up under the skirt, so only about 10 px of white socks and the two small light-blue round-toe shoes show below the hem, both feet together on the body center line, toes pointing down. Both forearms are folded upward in front of her upper chest with the elbows tucked down at her sides; her two small rounded hands sit side by side about 12 px either side of the body center, just below the collarbone and clearly below the chin, knuckles forward, like little cat paws. Upper arms stay vertical, the off-shoulder puff sleeves stay exactly as in IMAGE 1. Head tilts about 3 degrees toward the viewer's LEFT. Eyes softly closed in a gentle upward happy curve (contented ^ ^ closed lashes, thin dark-navy lash line, no thick black lashes), eyebrows relaxed, mouth a very small open smile, cheeks slightly raised. Her long white hair stays rooted and hangs straight down along both sides of her body in the same silhouette as IMAGE 1 — the hair does NOT swing, does NOT float upward, does NOT fan out. Skirt hem may lift only 2 px.

Hard proportions to keep from IMAGE 1: total sprite height about 227 px in a 256 cell, ear tips y=24, chin y=119, head-with-hair 93 px (42%), skirt hem y=221 (88% of height), hair width 150 px, face width 46 px, skirt width 86 px, one shoe 12 px wide, body centered at x=128.

Style: soft Japanese cel-shaded chibi anime, low-saturation pastel ice-blue palette, very thin blue-gray line art (#8FA9C6 at 35-55% opacity, never thick black outlines), cool lavender-blue two-tone shadows (no gray or black shadows), flat cel fills with only very light gradients, clean digital illustration with no grain, no noise, no 3D render, no plastic gloss, no airbrush, no bloom. Medium-soft anti-aliasing, no white fringe, no jagged edges.

Do NOT: spread the arms outward or raise them above the shoulders, make a star jump or a V, split the legs apart, kick the legs straight down, draw a deep squat, add motion lines, dust, sparkles, sweat drop, shadow on the ground, background, text or a second character, change the face, the eye shape, the dress pattern or the hairclip side (it stays on the viewer's RIGHT).
```

主帧实测（已归一化到 256）：`h=227`、`feet=250`、`cx=123`，构图与落位全对；但与待机锚点的内部 RGB 差落在"离批"区间（20+），也就是说 AI 帧和待机不是同一张画。**这一条由下一节的合成法解决，不需要用户接受画风跳变。**

### 派生帧的调用方式

### 画风统一：锚点身体 + 只贴 AI 的手和脚（2026-10-29 确认做法）

AI 不肯照抄裙子——两轮提示词收紧（明确禁止围裙蕾丝、方扣腰带、长吊坠耳坠、抬高的裙长）之后，生成的帧仍然每次都重画整套服装。所以反过来做：

- **底 = 待机锚点本身**（顶点帧用 `ref/closed-anchor-256.png`，因为它已经带正确的闭眼眼皮）；头、发、发夹、耳坠、袖、 bodice、腰带蝴蝶结、裙花纹、裙长、鞋全部用锚点真实像素。
- **只从 AI 帧取两块**，羽化 2.2px 贴回：前臂+爪（约 `x99–147, y131–170`）、裙下收起来的脚（约 `x104–142, y214–252`）。
- 脚本：`action-work/leap-v4/`（`proc.cut/metrics/place` 复用 `comb-gen/proc.py` → `frames/leap-master-c1.png` → 合成 `frames/master-unified.png`）。

离批检测（内部 RGB 差，同批 7–13 / 离批 20+）：

| 帧 | vs 睁眼锚点 | vs 闭眼锚点 |
| --- | --- | --- |
| AI 帧原样 | 24.0 | 21.5 |
| **锚点身体 + AI 手脚** | **8.4** | **5.0** |
| 下限参照（睁眼锚点 vs 闭眼锚点） | 3.4 | — |

合成帧已落进同批区间。剩余差异（不能宣称完全一致）：前臂与手仍是 AI 画的、线宽比锚点略软；胸口那块羽化带会盖住锚点原本的腰带上方，每拍都要单独检查接缝；深色壁纸下要看镂空和光晕。

派生其余相位时沿用同一套：每拍都以锚点为 IMAGE 1 生成，再只把该拍的手臂/脚合成回锚点身体。

### 抬手帧的裙↔发接缝：失败模式总结（2026-10-30 实测）

上面那条"矩形贴块"路线在抬手帧上失败了。放大到 8× 逐区比对（`action-work/leap-v4/qa-hair/`）定位到四类缺陷，共同根因只有一个：**贴块边界走的是坐标，不是部件**。AI 帧和锚点在同一个坐标上画的并不是同一个东西，所以任何直边蒙版都会把两套轮廓硬拼在一起。

| 缺陷 | 位置 | 实测 | 现象 |
| --- | --- | --- | --- |
| A 胸口块横切垂臂 | `x99/x147` 边界，`y131–170` | 锚点的上臂在这 40 行里全程占 `x80–103` 和 `x142–169`，正好压在蒙版左右边上；羽化带 1180px 里 **532px（45%）两源不一致** | 框外的锚点手臂继续垂到大腿，框内换成 AI 抬到胸前的前臂， elbow 处对不上 → 画面像四条胳膊；前臂下缘在 `y170` 被齐口切断，落在腰带上方 |
| B 收脚块把裙摆下沿整体搬低 | 块顶 `y214` | 锚点裙摆蕾丝 `y≈224` 收口（w39→35），AI 到 `y≈230` 才收口；`y222` 锚点 w54 / AI w83（宽 29px）；羽化带 1042px 里 **550px（53%）不一致** | 两层扇贝花边 + 中间一块没有花边的浅色补丁，`x104/x142` 处出现台阶 |
| C 发↔裙层序被拆成两套 | 两侧发梢 `y195–230` | AI 长发比锚点宽 7–15px、低 8–16px（`y214`：锚点 79–171 / AI 72–175） | 裙和发留锚点、身体按 AI 摆，"发在裙前"的相对关系两边都不像，发梢悬在裙面上 |
| D 抠图残影 | 鞋子左右下沿 | rembg 没吃净的发间浅灰背景随块贴入 | 灰斑 |

离批指标（Δ8.4/5.0）只测躯干内部，**看不见边界上的接缝**——它奖励矩形贴块，正好和观感相反。以后判定合成质量，必须单独看蒙版羽化带两侧的源间不一致率，而不是只看内部差值。

**规则**：贴块边界只能走"同一部件在两个源里都连续"的地方。跨层区域（发压裙、裙压腿、臂压 bodice）不允许用矩形蒙版。

**改法（下一步采用）**：

1. 蒙版跟着**部件自身的 alpha 轮廓**走，不按坐标框：按颜色从 AI 帧里分割出手套白 + 鞋蓝，向外扩 1px 做羽化。
2. 让出来的洞**只用锚点自己的像素补**（inpaint 锚点，不引入 AI），风格不会漂。
3. 收脚改成**层序**问题而不是贴块问题：先把 AI 的鞋贴在锚点裙摆**下面一层**，再用锚点原样的裙摆蕾丝盖回去。这样裙摆底线一个像素都不动，B 类缺陷从根上消失。
4. 胸口同理：先抹掉锚点的垂臂（用锚点 bodice/裙/发补），再把 AI 的前臂按轮廓贴上去，让上臂→前臂的转折落在锚点自己的袖口上。

### 结论：合成路线也救不回来，改成「约束式改图」（2026-10-30）

上面四步都实现了（`render_v4.py` / `fill2.py` / `variants.py`），结果：

- **收脚（第 3 步）成功**：鞋藏在裙摆下层 + 锚点蕾丝盖回，双层花边、灰斑、台阶全部消失，裙摆底线一像素没动。
- **手臂（第 1/2/4 步）失败**，且是结构性的：锚点前臂原来占的那条带子横跨**发与裙的层界线**，而 AI 帧在同一位置的发/裙边界被它自己挪过，任何填充（cv2 NS、biharmonic、AI 同坐标像素、按蕾丝边对齐的 AI 片）都会把这条线抹成一片糊斑。实测三种抹除方案（只抹手 / 抹到肘下 / 抹到袖口）全部在髋部留下奶油色团块，因为洞的上边界就是手臂本身，inpaint 必然沿手臂继续画下去。

**真正的解法是别让它重画身体**：把提示词从"生成一个跳起来的姿势"改成"**只改手臂，其余像素不许动**"，并明确写出"手臂原来的位置要露出后面的裙褶、蕾丝边和发，不要补洞、不要发明新褶子"。同样的模型这次照做了——腰带、金扣、扇贝蕾丝、裙花纹、耳坠全部保留，最佳对齐下内部差 12.0（同批区间 7–13），**完全不需要贴块**。在这张上再叠一条"只收脚"的约束，得到顶点帧（脚底 232 = 离地 19px）。

所以流程改成：

| 步骤 | 做法 |
| --- | --- |
| 1 | 锚点 1024 白底当 IMAGE 1，提示词只写"肘弯、两手到胸前"，把整套服装和头发列进 UNCHANGED，并写出"旧手臂位置露出后面的裙和发" |
| 2 | 用第 1 步的输出当 IMAGE 1，提示词只写"屈膝、双脚收到裙下、离地约 7% 身高" |
| 3 | 归一化按**头宽**定标（姿态无关），x 按裙摆带中心对 123，y 按**头顶**对齐再叠加该拍的离地位移 |
| 4 | 每拍只过内部差 + 目视 9× 胸口/裙摆，不做贴块也不做羽化 |

归一化不能用"人物总高"定标：收脚会让总高变短，按总高定标会把顶点帧整体放大。




```bash
# 主帧过审后，逐拍派生：IMAGE 1 一律用主帧，提示词只写本拍与主帧的差异
console-v2/.venv/Scripts/python.exe \
  C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py \
  --provider gpt --mode edit --quality high --size 1024x1024 \
  --prompt "<与主帧的唯一差异，见 §C 各拍的『相对主帧的差』一行> + <B 通用负向>" \
  --image console-v2/action-work/leap-v4/frames/leap-master.png \
  --out console-v2/action-work/leap-v4/gen/b0X.png
```

下面 §A 的完整通用块只在**主帧那一轮**用；派生轮不再重复，避免模型每轮重新理解一遍画风。


---

## 0. 与上一版提示词的差异（旧版为什么会画成星形跳）

旧版提示词（`console-v2/action-work/leap/prompt.txt`，2026-10-17）的动作描述只有一句：

```text
Action is 跳跃. Six consecutive KEY POSES ...: bend knees, push off, airborne arms spread, land softly, stand.
```

问题逐条对应到现在的失败现象：

| 旧措辞 | 实际画出来 | 新措辞 |
| --- | --- | --- |
| `airborne arms spread` | 双臂水平大张成星形，是"欢呼"不是"跳" | `both forearms folded up in front of her chest, elbows stay tucked at her sides, arms never extend outward or upward away from the body` |
| 没有幅度数值 | 离地 38px、下蹲压到 190px 高 | 每拍写死像素：离地 ≤18px、下蹲 9px |
| 没有脚的关系描述 | 空中双腿左右分开 | `both knees bend together, both feet tuck straight up under the skirt, feet stay together and never split apart` |
| 没有头发约束 | 长发向两侧炸开飘起 | `her long hair stays hanging straight down along her body, rooted, no swing` |
| 没有朝向约束 | 出现半侧身／背身 | `hips and shoulders square to camera in every frame, never a back view` |
| 没有表情约束 | 第 2 拍出现半闭眼的另一张脸 | `eyes softly closed in a happy curve only on beats 3–5, otherwise the exact idle eye shape` |
| 六格共用一张图 | 逐格漂脸漂线宽 | 一帧一张，上一拍只当姿势参考 |

---

## 1. 快速使用：通用提示词 + 每拍提示词

拼接顺序：**A 通用 → 本拍 Pose → B 通用负向**，中间用换行分隔。六拍共用 A 和 B，只替换本拍。

### A. 通用提示词（每拍都放最前面）

```text
Master style and character lock for every frame: single full-body 2D chibi anime sprite of Yuki, front view (hips and shoulders square to camera, never a back or side view), fixed camera, same scale and framing as the reference idle sprite, centered at x≈128 in a 256×256 cell, nothing cropped, clean flat white background for later cutout. Yuki has long straight white hair (#F4F6FB highlights, #D9DDEF midtones, #C9D3EA shadows, #BFD6F2 cool tips), large round deep-blue eyes (#2E4F86 / #1E3A6E with #8CC8F0 highlights and dark navy upper lash lines, never pure black), white cat ears with pale pink inner ears, a light-blue off-shoulder dress (#9BD1F0 base, #7FB9DE shadows, #EAF7FF lace and highlights), a thin blue waist belt, a fine pale-blue snowflake pattern on the skirt, white socks, small light-blue round-toe shoes (#9BC5E8), a translucent pale-blue snowflake hairclip on the viewer's RIGHT side of her bangs, and a pair of snowflake earrings. Proportions identical to the idle master: total height about 227 px, ear tips y≈24, hair top y≈26, chin y≈119, head-with-hair about 93 px (42%), skirt hem y≈221 (88% of height), only about 26 px of socks and shoes below the hem, feet baseline y≈250, hair width about 150 px, face width about 46 px, skirt width about 86 px, one shoe about 12 px wide. Soft Japanese cel-shaded anime style matching the idle sprite exactly: very thin blue-gray line art (#8FA9C6 at about 35–55% opacity, never thick black outlines), cool lavender-blue two-tone shadows (no gray or black shadows), low-saturation pastel ice-blue palette, flat cel fills with only very light gradients in the hair, dress folds and under the chin, clean digital illustration texture with no grain, no noise, no paper texture, no 3D specular, no plastic gloss, no airbrush blur, no bloom and no chromatic aberration. Anti-aliasing: medium-soft, about 0.6–1.2 px semi-transparent edge transition at 256, hair tips fading over 1–2 px and 2–5 alpha levels; generate at 1024 or 2048 and downscale with premultiplied-alpha Lanczos; no jagged edges, no white fringe or halo, no black rim, no over-sharpened contour and no blurry edge. JUMP LOCK (this is a tiny in-place hop, not a leap): the action is a small cute bunny hop. The character's horizontal center stays at x≈128 in every frame with zero lateral translation; the only motion is vertical. Maximum clearance between the shoe soles and the y≈250 ground line is 18 px; the body sinks at most 9 px below the idle height of 227 px. ARMS RULE: both forearms fold upward in front of her chest with the elbows staying tucked down at her sides; her two small rounded hands sit close together at upper-chest / collarbone height, about 12 px either side of the body center; upper arms stay vertical, sleeves unchanged; the arms NEVER spread outward, NEVER raise above the shoulders, NEVER form a star or a V, and the hands never cover the face, the chin or the hairclip. LEG RULE: both knees bend together and symmetrically; both feet tuck straight up under the skirt on the body center line; the feet never split apart, never kick forward or backward, never one-leg-bent-one-leg-straight. HAIR RULE: her long hair stays rooted and hangs straight down along both sides of her body in the same silhouette as the idle master; the hair does NOT swing, does NOT float upward, does NOT fan out, does not drift sideways; only the skirt hem and the two side tips may settle by 1–2 px. EXPRESSION RULE: a small happy hop — on the airborne beats her eyes are softly closed in a gentle upward curve (a contented ^ ^ blink), eyebrows relaxed, mouth a tiny closed smile or a very small open smile; on the ground beats her eyes are the exact idle eye shape and size. Never change the face shape, the eye shape or the eye size. No motion lines, no speed streaks, no dust cloud, no sparkles, no impact ring, no sweat drop, no shadow on the ground.
```

### B. 通用负向提示词（每拍都放最后）

```text
arms spread wide, arms out to the sides, star jump, jumping jack, T-pose arms, hands above shoulders, hands raised over the head, one arm up one arm down, arms crossed, stiff straight arms, reaching hands, hands covering face, hands covering eyes, hands in front of the mouth, hands touching the chin, extra fingers, missing fingers, deformed hands, broken wrist; legs apart, legs split, one leg forward one leg back, kicking legs, straight stiff legs, legs splayed, frog legs, feet crossed, huge jump, high leap, airborne above 24 px, floating far above the ground, deep squat, body compressed below 214 px, knees bent outward, knock-kneed; hair swinging, hair floating upward, hair fanned out, wind-blown hair, hair spread sideways, detached hair lock, hair bundle in front of the chest, hairclip moved, hairclip hidden, hairclip on viewer left, missing earrings; back view, side view, turned body, three-quarter turn, looking away, cropped head, cropped feet, character off center, lateral drift, root translation, zoom, camera rotation, perspective change, low angle, high angle; different character, different face, different eye shape, different eye size, different eye color, half-closed bored eyes on the ground beats, angry eyebrows, open shouting mouth, teeth, tongue, 3-head or 4-head proportion, short skirt, long legs, large feet, outfit change, extra accessories, tail, bow, wings; ground shadow, cast shadow, drop shadow, contact shadow, motion blur, speed lines, action streaks, dust puff, impact star, sparkles, sweat drop, exclamation mark, onomatopoeia, text, watermark, logo, UI, frame border, grid, checkerboard, background scene, floor, wall, multiple characters, duplicate character; thick black outlines, hard 1px black rim, white halo, white fringe, jagged edges, pixel art, over-sharpened edges, blurry edges, airbrush, soft painting, 3D render, glossy plastic, metallic shine, strong specular, realistic shading, grain, noise, paper texture, jpeg artifacts, bloom, lens flare, chromatic aberration.
```

### C. 每拍的详细提示词（6 拍关键帧）

#### b01 · 起势：手开始抬，脚未离地

```text
Pose: the neutral idle standing pose, feet planted on the y≈250 baseline, total height 227 px, ear tips at y≈24. The only change from idle: both forearms have just begun to fold upward, her hands at waist-front height about (112,164) and (134,164), elbows still at her sides. Head upright, eyes open in the exact idle eye shape, looking at the viewer, calm soft mouth. Knees straight, skirt and hair in the idle silhouette. Nothing else moves.
```

中文重点：这一拍几乎等于待机，只有双手开始往起收；不要提前下蹲，不要离地。

#### b02 · 蓄力：屈膝下沉 9px，双手收到胸前

```text
Pose: a small anticipation crouch. Her whole body above the waist has lowered by exactly 9 px (ear tips now y≈33, total height 227→218 px), while both shoe soles stay flat on the y≈250 baseline and the body center stays at x≈128. Both knees bend together, symmetrically, so the visible socks and shoes below the hem shorten; the skirt bulges outward by only about 3% at the hem. Both forearms are folded up in front of her chest, elbows tucked down at her sides, her two small rounded hands close together at upper-chest height about (112,146) and (134,146), just below the collarbone and clearly below the chin. Eyes softly closed in a gentle curve, mouth a tiny determined-but-cute closed smile. Hair hangs straight down in the idle silhouette, no swing. Feet are NOT off the ground yet.
```

中文重点：压低只有 9px，是"微微一蹲"不是深蹲；脚掌还贴着地；手已经收到胸口两侧。

#### b03 · 蹬地离地：脚底离地 6px，身体刚开始伸展

```text
Pose: the instant after push-off. Both shoe soles have just left the ground, clearance 6 px (soles at y≈244), and both feet are still tucked together directly under her on the center line. Body height returning toward 227 px, ear tips about y≈27. Both hands stay folded at her chest, elbows at her sides. Eyes closed in a happy curve, tiny open smile. The skirt hem has lifted by 1–2 px and the hair is still hanging straight down with no swing. Symmetric pose, both legs identical, no leg split.
```

中文重点：刚离地，只有 6px；两脚并拢收在裙子正下方，不要伸腿。

#### b04 · 顶点：离地 18px，收脚到裙下，歪头 3°

```text
Pose: the apex of the tiny hop. Both soles at y≈232, i.e. 18 px of clearance under the feet, the maximum of the whole action. Both knees are tucked up so only the rounded toes of her two small blue shoes peek out from under the skirt hem, about 10 px of leg visible below the hem instead of the usual 26 px, both feet together on the center line. Total body height 227 px (legs are not stretched). Her head tilts about 3° toward the viewer's LEFT, eyes closed in a soft happy curve, a small open smile, cheeks slightly raised. Both hands still folded in front of her chest at (112,146)/(134,146), elbows down at her sides. Hair hangs straight down, same silhouette as idle, no fan-out and no upward float; the skirt is very slightly narrower and lifted at the hem by 2 px. Body center still exactly x≈128.
```

中文重点：这是最"小兔子"的一帧——收脚、闭眼、微微歪头、手在胸口；离地封顶 18px。

#### b05 · 下落：脚底回到离地 11px，脚开始伸

```text
Pose: descending. Sole clearance is back down to 11 px (soles at y≈239), the knees beginning to un-tuck so about 16 px of socks and shoes show below the hem, both feet still together under her on the center line. Head tilt reduced to about 1.5°, eyes still closed in a happy curve, mouth back to a small closed smile. Both hands still folded at her chest. Hair still hanging straight down with no swing; the skirt hem lifts by about 3 px as she drops. Body center x≈128.
```

中文重点：正在落回来，膝盖逐渐放开；不要画成第二次起跳。

#### b06 · 落地缓冲：脚掌回 250，再压 7px

```text
Pose: she has landed. Both soles are flat on the y≈250 baseline again, and the body absorbs the landing by sinking 7 px (ear tips y≈31, total height about 220 px), both knees bent together symmetrically. The skirt hem spreads outward by only about 5% and drops 3 px; the hair still hangs straight down in the idle silhouette. Both hands are starting to lower from her chest toward her sides, now at about (110,156)/(136,156). Eyes half closed, a small relieved smile, head upright. No bounce higher than the ground line, no second hop.
```

中文重点：落地只压 7px，比蓄力更浅；裙摆轻微外扩；手开始往下放。

#### b07 · 收势：回到待机（与 b01 同构图，手放回身侧）

```text
Pose: back to the neutral idle standing pose, total height 227 px, ear tips y≈24, soles on the y≈250 baseline, body center x≈128. Both arms lowered, hands almost back at her sides (about (108,172)/(138,172)), one last 2 px settle of the skirt hem. Eyes open in the exact idle eye shape, looking at the viewer, a small satisfied smile. This frame must match the idle reference closely enough to blend back into the standing idle with no pop.
```

中文重点：收势帧要能无缝接回待机；这一帧如果和待机明显不同就是失败的。

---

## 2. 参考图使用顺序（很重要）

1. **画风 / 身份 / 比例 / 配色唯一母版**：`console-v2/assets/living-idle/open.png` 左上第一格 256×256，放大到 1024。它负责脸、眼型、发量、裙花纹、线宽和配色。
2. **姿势参考**：上一拍**已通过**的帧，只负责"这一拍手臂和腿收到哪里"。第一拍（b01）没有上一拍，只喂母版。
3. **三视图** `console-v2/assets/reference/yuki-turnaround.png` 只用于生成后的身份核对，**不作为画风参考**，也不要和待机帧混成"画风基准"。

画面里出现"另一张脸"、线变粗、裙花纹变样、角色变窄或变宽——直接判废重出，不要拿去修下一拍。

---

## 3. 幅度硬数值（灰模已实测，出图必须落在这套数上）

| 拍 | 脚底 y | 离地 | 头顶 y | 身高 | 手位（左/右） | 歪头 | 眼 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| b01 起势 | 250 | 0 | 24 | 227 | (112,164)/(134,164) | 0° | open |
| b02 蓄力 | 250 | 0 | 33 | 218 | (112,146)/(134,146) | 0° | closed |
| b03 蹬地 | 244 | 6 | 27 | ~225 | (112,146)/(134,146) | 1° | closed |
| b04 顶点 | **232** | **18** | 24 | 227 | (112,146)/(134,146) | 3° | closed |
| b05 下落 | 239 | 11 | 27 | ~225 | (112,150)/(134,150) | 1.5° | closed |
| b06 落地 | 250 | 0 | 31 | 220 | (110,156)/(136,156) | 0° | half |
| b07 收势 | 250 | 0 | 24 | 227 | (108,172)/(138,172) | 0° | open |

节奏（运行时 `durations`，与灰模一致）：b01 段 70ms，b02 60ms，b03 50ms，b04 65ms，b05 50ms，b06 60ms，落地后 45+145ms 回势；整段 **595ms**。

对比现版：离地 38px→18px，下蹲 43px→9px，整段 900ms→595ms，双臂大张→双手收胸前。

---

## 4. 画面风格、抗锯齿、颜色与质感

**全部继承 `docs/yuki-comb-action-prompts.md` §5，不重复发明。** 关键锚点：线稿 `#8FA9C6` 35–55% 不透明度；AA 在 256 下 0.6–1.2px 半透明过渡；发梢 1–2px 淡出、2–5 级 alpha；`measure.py` 判定区间 edge 14.6–16.6、aa 0.030–0.085、身高 222–236、脚底 233–252。

---

## 5. 生成与后期流程

1. **一帧一张**，`--quality high --size 1024x1024`，白底或绿幕 `#00ff00`（二选一，整批统一）。
2. 抠图：白底走 rembg `isnet-anime`（白发与浅灰底靠颜色键分不开）；绿幕走 `chroma_key`，`alpha = clip((65 − (G − max(R,B)))·255/40, 0, 255)`，再 `C = (C − 255·(1−a)) / a` 去白边。
3. 归一化：按**头宽**锁尺度（对齐 `idle-anchor-256`），脚底质心放到 y=250、身体中心 x=123/127；用 `action-work/sad-v2/prepare_pose.py <src> <out> --height N`。
4. 缩到 256 用预乘 alpha 的 Lanczos；**不要**对抠图本体锐化。
5. 逐帧叠 50% 与母版对一遍轮廓，检查是否被"重画"。
6. 补中间帧：AI 不插帧（见 `docs/动作插帧提示词.md`），眼皮状态也不交给光流；b01–b07 之外用整帧位移/压缩做少量中间帧，或直接把 7 拍按上面的 `durations` 播。
7. 验收后按 `action-work/sad-v2/publish.py` 的写法出 atlas、写 catalog（`frames`、`durations` 必须和真实文件数一致）、更新 `frame-alignment.json`。

---

## 6. 验收清单

- [ ] 每帧 `measure.py`：edge 14.6–16.6、aa 0.030–0.085、身高 222–236、脚底 233–252
- [ ] 离地峰值 ≤18px（脚底 ≥232），下蹲最深 ≥218px 高
- [ ] 相邻帧差峰值 ≤25；落地那一拍若超标，补一帧脚底 245 的中间帧
- [ ] 每帧眼睛虹膜连通域 = 1（没有多瞳孔／断开的虹膜）
- [ ] 双臂没有外张：手的位置在 x∈[104,142]、y∈[140,175] 区间内
- [ ] 双脚没有分开：两脚质心水平距离 ≤14px
- [ ] 头发轮廓与母版逐帧叠合，横向偏移 ≤2px（头发不许动）
- [ ] 雪片发夹始终在观众右侧、不被手或头发遮挡
- [ ] 脸/眼型/眼大小与母版一致，线宽没有变粗
- [ ] 循环播放 3 次无闪烁、无重影、无横移
- [ ] 首帧≈待机、末帧≈待机，能无缝接回
- [ ] 交付 GIF 或对比图，不只给 PNG 序列

### 幅度：256 格的高度上限（2026-10-30）

顶点能抬多高由格子的头顶余量决定，不是随便填数字：

| 档位 | 脚底 y | 离地 | 头顶 y | 结论 |
| --- | --- | --- | --- | --- |
| 上一版 | 232 | 19px | 28 | 偏小 |
| A | 220 | 31px | 16 | 可用 |
| **B** | **212** | **39px** | **8** | **推荐，接近旧版 38px，头顶留 8px** |
| C | 204 | 47px | 0 | 耳朵贴到上沿被切，不能用 |

关键是**先靠收脚把人物压矮**：深收脚把身高从 214 压到 204，头顶才有余量；单靠平移，头顶到 0 就封顶了。同时补一张屈膝帧（身高 209、头顶 42），起跳前下沉 20px，39px 的腾空才读得出来。

再要更高只能改画布（比如 256×288 或给该动作单独加头顶留白），但 catalog 有三份副本、前端构建期打包、frame-alignment 也要跟着改，属于全链路改动，先定幅度再动。

### 睁眼：换锚点重跑，不要贴眼区（2026-10-30）

闭眼锚点生成的整条链（手臂 / 收脚 / 屈膝）眼睛都是闭的。试过把 `idle-anchor` 的眼区（y82–101, x97–153）按面部质心对齐贴回去，失败了两次：第一次矩形羽化留出浅色方框；第二次改成"只贴非肤色像素"，还是对不准——闭眼眼弧和睁眼虹膜的中心本来就不在一个位置，而且 AI 每拍的脸位置差 1–2px，贴出来不是重影就是错位。

正解：**整条链从睁眼锚点 `ref/master-white.png` 重跑**，三张提示词里加一句 `Keep the eyes exactly as in the input — open, same shape, same highlights, same gaze`。眼睛由 AI 每拍自己画，和待机同一套虹膜/睫毛/高光，没有任何贴片边界。

代价是每拍的眼睛大小有细微差别（o-neut 比锚点略大、o-crouch 略小），9 拍连播时要盯一眼有没有"眼睛跳"。

### 结论链（当前状态）

| 帧 | 头顶 | 脚底 | 离地 | 身高 |
| --- | --- | --- | --- | --- |
| 待机锚点 | 24 | 250 | 0 | 226 |
| 中立（手到胸前） | 22 | 251 | 0 | 229 |
| 屈膝 | 36 | 251 | 0 | 215 |
| 顶点 | 5 | 212 | **39px** | 207 |

还差：蹬地、上升、下落、缓冲、收势 5 拍；9 拍时轴与 catalog 落地。

### 表情按拍：预备睁眼、顶点闭眼（2026-10-30 用户确认）

- 待机 / 手到胸前 / 屈膝蓄力：**睁眼**（和读待机同一套虹膜高光）。
- 顶点（腾空那一拍）：**闭眼，开心弧**，睫毛保留。
- 落地恢复睁眼。

做法：顶点帧从同一条链的睁眼手臂帧派生，提示词里加一条"眼睛在此拍眯起成开心弧"，其余 UNCHANGED 不动——这样身体和睁眼拍出自同一次生成，不会因为换锚点而整体偏移。不要用 `master-white-closed` 那条链的顶点帧来顶替：那是另一条链，身体是另一次重画。

### 10 拍 660ms 完整版（2026-10-30）

按"首末帧落在待机姿"的接法组好了，产物在 `action-work/leap-v4/qa-hair/leap10.gif`。

| # | 拍 | 时长 | 离地 | 来源 |
| --- | --- | --- | --- | --- |
| 01 | 待机姿 | 50 | 0 | 锚点原样 |
| 02 | 手臂半抬 | 50 | 0 | 生成 `open-half` |
| 03 | 手到胸前 | 70 | 0 | `o-neut` |
| 04 | 屈膝蓄力 | 80 | 0 | `o-crouch` |
| 05 | 蹬地离地 | 50 | 6 | `o-neut` 抬到 244 |
| 06 | 顶点 | 120 | 38 | `o-apexC` |
| 07 | 下落 | 80 | 16 | 生成 `open-fall2` |
| 08 | 落地缓冲 | 70 | 0 | `o-crouch` 复用 |
| 09 | 手臂下放 | 50 | 0 | 复用 02 |
| 10 | 待机姿 | 40 | 0 | 锚点原样 |

**蹬地和下落两帧踩过的坑**：第一版让 AI"腿伸直蹬地 / 腿向下伸"，它把人物画成了长腿普通比例（身高 240，头顶被切）。必须显式写"chibi 2.4 头身、腿很短、裙摆几乎盖住腿、人物总高不变"，重生成才回到位。蹬地最后直接复用"手在胸前、直腿"那帧抬到 244，不再单独生成。

**色差**：各拍之间中间调差 3–9 个色阶（偏暖），按中间调中位数做了一次逐通道增益归一，色差压到 ±3。

**未做**：运行时资产（`assets/actions/leap/` 10 帧 + atlas + poster）、catalog 三份副本、frame-alignment 都没动。
