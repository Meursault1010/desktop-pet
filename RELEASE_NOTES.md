# Yuki v1.1.1 · Windows x64

一只会在桌面陪伴你的宠物，也带有 AI 助手和日常小工具。解压即可运行，不需要另装 Python 或 Node。

## 下载

- **轻量版：**`yuki-win32-x64-v1.1.1.zip`
- **可选本地模型：**`yuki-model-v1.1.1.part01` 与 `yuki-model-v1.1.1.part02`（约 2.8 GB）

轻量版解压后运行 `yuki.exe`。需要内置模型时，把三个文件放在同一下载目录，解压应用包后，在解压出的 `yuki-win32-x64` 文件夹运行：

```powershell
.\install-yuki.ps1 -AssetsPath "$HOME\Downloads" -IncludeModel
```

把 `$HOME\Downloads` 改成实际下载目录。安装后到“设置 → 通用”开启内置模型。

## 包含功能

桌宠动作与桌面互动、五栏工作台、AI 聊天、专注计时、待办提醒、OCR、文档读取、划词翻译和剪贴板暂存。

内置模型在本机运行；也可配置兼容的本地服务或云端 API。使用云端服务时，对话内容会发送给该服务。AI 助手不提供联网搜索。

当前为未签名的 Windows 便携版，暂不支持自动更新。Windows 可能显示发布者提示。
