# Yuki 项目简介

Yuki（雪）是 Windows x64 桌面宠物与工作台。当前公开版本为 **v1.1.1**，下载方式见 [GitHub Releases](https://github.com/Meursault1010/desktop-pet/releases/latest)。

## 用户能做什么

- 在桌面上陪伴雪：看她呼吸、眨眼、走动、播放动作，并拖动她与桌面图标或窗口边缘互动。
- 在工作台查看状态、调整角色行为、使用 AI 助手和常用工具。
- 使用专注计时、待办提醒、OCR、文档读取、划词翻译和本机剪贴板暂存。
- 按需安装内置 Qwen，或连接兼容的本地模型服务和云端 API。

## 当前边界

- 提供 Windows x64 便携版。v1.1.2 起支持应用内更新。
- 内置模型可选；AI 助手不联网搜索。使用云端 API 时，消息会发送给用户配置的服务。
- 剪贴板和 OCR/文档解析在本机处理；剪贴板内容不会自动发送给模型。
- 雪使用 PNG 动作帧与程序微动，不是 Live2D。桌面图标、窗口信息只用于可见位置互动，不操作其他应用。

## 开发入口

- 桌宠和本地服务：`console-v2/` 下的 Python / PySide6。
- 工作台：`console-v2/frontend/` 下的 React / TypeScript / Electron。
- 开发启动：运行 `install-electron.bat` 安装依赖，再运行 `start.bat`。
- 便携版构建：运行 `build-electron.ps1`。

历史架构、设计决策与逐次实现记录见 [产品实现记录](产品实现记录.md)、[Electron 迁移总结](Electron迁移总结.md) 和 [CHANGELOG](../CHANGELOG.md)。这些历史记录不代表当前版本仍包含其中所有旧功能。
