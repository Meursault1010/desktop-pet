# Yuki 窗口顶角攀爬 · 详细生成关键词

用途：生成“从窗口侧边贴着边框爬到顶端平台”的单帧序列。**重点是侧身、躬身、手在身体前方扶住顶边，身体贴着边框，靠手臂和腿发力慢慢上去。**

先改下面的关键词，再按帧生成。建议一帧一张，不要一次生成整张分镜表。

---

## 1. 共用角色与画风

```text
Single full-body 2D chibi anime sprite of Yuki, newly drawn in the exact same flat cel-shaded style as the reference image. Yuki is a cute catgirl with long straight white hair, large blue eyes, white cat ears, a light-blue off-shoulder dress with white lace trim, white socks, blue shoes, and a small pale-blue snowflake hairclip on the viewer's RIGHT side of her head. Flat cel-shaded anime style, clean thin blue-gray line art, soft pastel blue/white palette, same head/body proportions and line weight as the reference. Full body from ear tips to shoes, centered, generous margin, nothing cropped. Flat solid chroma-key green background (#00FF00).
```

## 2. 动作核心关键词

```text
side profile view, three-quarter side view, torso bent forward at the waist, hips kept close to the vertical frame, the ENTIRE left silhouette flush against the vertical rail with zero green gap (left hair/head edge, shoulder, hip, thigh, shin and braced foot all touching or slightly overlapping the rail; the rail stays just outside the left contour and never cuts across the face), both hands in front of the body at chest height, hands gripping the horizontal top edge, elbows bent down, shoulders over the hands, one knee lifted toward the top edge, the other foot braced against the vertical frame, hips rising, knee coming onto the top edge, hips rolling over the edge, belly/chest low on the top, kneeling on the top, slow heavy effortful climb, arm pull, leg push, hip drive, weight shift, body hugging the frame, strained cute expression
```

## 3. 负向关键词

```text
jumping, leap, hop, spring, mid-air, floating, standing on air, both hands above the head, arms straight overhead, one-hand vault, straight-arm support, front-facing belly flop, feet off the frame, gap between body and vertical frame, rail crossing the face, window frame, rail, ledge, platform surface, thick visible line, background objects, floor, shadow, text, watermark, cropped head, cropped feet, extra limbs, deformed hands, different outfit, extra jewelry, hairclip on viewer left, mirrored character, 3D render, realistic, soft painting, detailed shading
```

如果模型必须看到支撑才能摆对姿势，允许画面里出现**一条很细的中性灰参考线**表示顶边、**一条很细的灰线**表示侧边框；生成后后期擦掉。除此之外不要画窗口、栏杆或平台面。若不用参考线，把上面的 `thick visible line` 改成 `any visible line`。

---

## 4. 逐帧关键词

每帧都先放“共用角色与画风”，再放本帧关键词。

### F1 侧边低位攀爬

```text
Yuki is low on the RIGHT side of an invisible vertical frame, below the top edge. Seen from the side. Her viewer-LEFT hand grips high on the vertical frame at head height; her viewer-RIGHT hand grips lower near her waist. Her hips are close to the frame; one knee is lifted, the other foot is braced against the vertical frame. Her torso is slightly bent forward; she looks up toward the top edge. This is the start of a slow climb. No top-edge contact yet.
```

### F2 继续爬高，上面的手接近顶角

```text
Same side view, higher on the vertical frame. Her viewer-LEFT hand has reached the top corner; her viewer-RIGHT hand is still lower on the vertical frame. Her hip has risen and stays close to the frame; the lifted knee is higher; the other foot is braced. Her torso is bent forward; she looks at the top edge. Slow and effortful, not a jump.
```

### F3 上面的手先扶住顶边

```text
Side profile. Her viewer-LEFT hand is now planted on the horizontal top edge in front of her chest, fingers curled over it; her viewer-RIGHT hand is still on the vertical frame. Her torso is bent forward at the waist; her hips remain close to the vertical frame. One knee is lifted, the other foot braced. She looks at her planted hand with a determined, strained face. This is the first hand securing the platform. No jump, no overhead reach.
```

### F4 手臂发力，身体上移

```text
Side profile. The elbow of the planted viewer-LEFT hand bends down and the shoulder rises over the hand; her chest comes close to the top edge. Her hips stay close to the vertical frame; the viewer-RIGHT hand is still low; one knee lifts higher; the other foot pushes the frame. Her face strains with effort. This is a slow arm-powered rise, not a jump.
```

### F5 另一只手也扶住顶边

```text
Side profile. Both hands are now on the horizontal top edge in front of her body, shoulder-width apart; her elbows bend down and her chest is at the edge. Her hips are still low and close to the vertical frame; both knees are bent, feet braced. Her body hugs the corner; she looks down at the edge with a focused, effortful face. Slow two-hand pull, not a raised-arm celebration.
```

### F6 手脚一起发力，膝盖往上收

```text
Side profile. Both hands press down on the top edge; one knee comes up along the vertical frame toward the top edge; her other foot pushes against the frame; her hips rise. Her torso stays low and forward, shoulders working; eyes squeezed, cheeks slightly puffed. The arms pull and the legs push together. No jump.
```

### F7 膝盖上顶边

```text
Side profile. One knee is now on the top edge; both hands are still planted in front of her; her hips are at the edge; the other leg still hangs/braces against the vertical frame. Her body is low and close to the frame; she looks down at her knee with a tired, determined face. This is the slow knee-over moment, not a vault.
```

### F8 胯部翻上顶边

```text
Side profile. Her hips roll over the top edge; her belly and chest stay low on the top surface; both hands push in front of her; one leg is still coming over the edge. Her body hugs the edge; her hair and dress hang. She is low, heavy and effortful, slowly bringing the whole body onto the platform. No jump.
```

### F9 跪起

```text
Yuki is kneeling on the top edge, both knees under her, hands on the platform in front of her, hips over the edge, head up, tired but relieved. Her hair and dress settle around her. She is fully on the platform; no jumping, no floating.
```

### F10 清理裙子上的灰

```text
Kneeling on the platform, Yuki brushes dust off the front of her dress with her viewer-RIGHT hand. Only a few tiny pale dust puffs appear at the brushing hand; no other particles. She looks down with a small pout; her other hand supports her on the platform. She remains kneeling on top.
```

### F11 清理肩头和头发上的灰

```text
Yuki lifts the same hand to brush dust from her shoulder and the side of her hair. Only a few tiny pale dust puffs near that hand. Her eyes are half-closed with a satisfied, tired expression; she is still kneeling on the platform. The snowflake hairclip stays on the viewer's RIGHT.
```

### F12 顶端的坐姿

```text
Yuki sits on the edge of the top platform in her established top-rest pose: both legs hanging over the front, hands on her lap, shoulders relaxed, eyes half-closed with a small satisfied smile. Her hair and dress are settled; the snowflake hairclip is on the viewer's RIGHT. This is the calm final pose after climbing and dusting off.
```

---

## 5. 左侧版本

左侧不是镜像角色，只镜像空间方向：

- 把 `RIGHT side of the vertical frame` 改成 `LEFT side of the vertical frame`。
- F1/F2 的高位手改成 viewer RIGHT，低位手改成 viewer LEFT。
- F3 先扶顶边的手改成 viewer RIGHT；另一只手在 viewer LEFT。
- F5 双手位置对调；F6/F7 抬起的膝盖方向相反。
- F10/F11 刷灰的手改成 viewer LEFT。
- 每一帧都加：`Do not mirror the character; the snowflake hairclip stays on the viewer's RIGHT.`

---

## 6. 参考图

- `console-v2/assets/motion-v2/climb-right/12.png`（右侧侧爬姿态和比例）
- `console-v2/assets/motion-v2/climb-left/12.png`（左侧侧爬姿态）
- `console-v2/assets/motion-v2/hang/00.png`（双手扶边的接触感觉；不要照抄它的正面和过头姿势）
- `console-v2/assets/actions/prone-chin/34.png`、`35.png`（手在身体前方、膝盖撑起的姿态参考；只参考身体低伏和手脚位置，不要照抄正面朝向）
- `console-v2/assets/actions/play-top-rest/01.png`（最终坐姿）

参考图只用于角色身份、画风、比例、发夹位置。**不要复制参考图里的窗口、背景、线条或已有动作帧。**

---

## 7. 生成与检查

- 1:1，1024×1024，一次一帧。
- 绿幕 `#00FF00`。
- 每帧全身完整，耳朵和鞋不要出画。
- 同一组固定同一张角色参考，避免头身比和服装漂移。
- 每帧检查：
  1. 是否侧身/侧 3/4，而不是正面；
  2. 整个左侧轮廓（头发外缘、肩、髋、腿、支撑脚）是否贴住侧边框，是否有绿色空隙，边框是否没有穿过脸；
  3. 手是否在身体前方、胸/肩高度，而不是举过头顶；
  4. 是否有手臂拉、腿蹬、髋上移的配合；
  5. 膝盖是否真的上到顶边，而不是悬空；
  6. 发夹是否在 viewer RIGHT；
  7. 是否又画了跳跃、单手撑跳、正面趴或栏杆；
  8. 12 帧的头身比、服装、发夹是否一致。

---

## 8. 你修改时可以直接替换的句子

- 视角：`side profile view` / `three-quarter side view`
- 躯干：`torso bent forward at the waist` / `hips close to the vertical frame`
- 手：`both hands in front at chest height, elbows bent down` / `hands gripping the top edge`
- 腿：`one knee lifted toward the top edge, the other foot braced against the frame`
- 发力：`slow heavy effortful climb, arm pull, leg push, hip drive`
- 贴身：`body hugging the frame, hips kept against the side`
- 禁止：`no jump, no leap, no one-hand vault, no overhead reach, no front-facing flop`
