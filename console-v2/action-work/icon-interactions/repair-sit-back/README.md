# sit-back 补腿记录

原始 512 原画 `original-sit-back-512.png` 只有一条腿，坐在图标上时裙下缺口会露出桌面图标。
`repaired-sit-back-512.png` 保留原姿势，把可见腿/鞋镜像补到左侧，并在原画图层下方合成，裙摆自然遮住腿根；随后运行 `build_interaction_assets.py` 重建 16 帧开/眨眼动画。
运行时旧帧备份在 `original-runtime-frames/`。
