# Yuki v1.1.1 · Windows x64

桌面宠物、工作台、离线 OCR 与文档工具。Windows x64 便携版；本地 Qwen 模型可选。

- 解压后即可启动桌面宠物和工作台；无需单独安装 Python、Node 或模型服务。
- 本地模型分为两个下载文件，合计约 2.8 GB；安装时可选择不安装。启用模型会额外占用数 GB 内存，也可改连兼容的本地服务或云端 API。
- 云端模型需用户自备服务地址与 API 密钥。选择云端后，对话内容会发送给所选服务。
- Windows x64；未签名，Windows 可能显示未知发布者提示。
- 目前为便携版，不含自动更新；更新时先正常退出，再安装新版本，用户设置保存在本机。
- 下载文件：应用包 `yuki-win32-x64-v1.1.1.tar.gz`，可选模型卷 `yuki-model-v1.1.1.part01` 与 `part02`。解压应用包即可使用轻量版。

依赖和模型来源见仓库 `local-model/qwen/README.md`、`build-llama-runtime.ps1` 与 `THIRD-PARTY-NOTICES.md`。
## 安装本地模型

三件文件下载到同一目录，解压应用包后，在 PowerShell 中运行 `./install-yuki.ps1 -AssetsPath "下载目录" -IncludeModel`。安装脚本会校验并合并模型、创建桌面快捷方式。省略 `-IncludeModel` 可安装轻量版。

