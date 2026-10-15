# 小橘桌面宠物

Windows 桌面宠物原型，Python 3.10+ 与 PySide6。

首次运行，在本文件所在目录打开终端：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

如果当前 Python 已安装 PySide6，可以直接双击 `start.bat`。

左键点击跳跃并打招呼；按住拖动位置；右键打开暂停、跳跃、回到底部与退出菜单。宠物会随机待机和左右行走，并在当前屏幕工作区边缘折返。暂停只暂停自主移动，眨眼与点击仍然有效。

当前角色由 Qt 矢量绘图实现，无需图片或联网。此版本包含透明置顶窗口、简单动画和交互；尚未加入 AI 聊天、语音、开机启动、位置保存或安装包。后续可以将绘制层替换为角色精灵图，再扩展行为状态机与聊天模块。

无界面启动验证：`python main.py --smoke-test`（搭配 `QT_QPA_PLATFORM=offscreen`）。
