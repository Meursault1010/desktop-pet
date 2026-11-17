# Yuki v1.1.1 · Windows x64

桌面宠物、工作台、离线 OCR、文档工具和可选内置 Qwen 模型。免安装便携版，首次下载约 4 GB；解压后约需 5 GB 磁盘空间。

- 解压后即可启动桌面宠物和工作台；无需单独安装 Python、Node 或模型服务。
- 内置 Qwen 默认关闭；首次开启会占用约 2.8 GB 磁盘及数 GB 内存。也可改连兼容的本地服务或云端 API。
- 云端模型需用户自备服务地址与 API 密钥。选择云端后，对话内容会发送给所选服务。
- Windows x64；未签名，Windows 可能显示未知发布者提示。
- 目前为便携版，不含自动更新；更新时先正常退出，再安装新版本，用户设置保存在本机。
- 若分段下载，请运行发行版中的 `install-yuki.ps1`；脚本会校验 SHA-256、合并并解压安装包。

依赖和模型来源见仓库 `local-model/qwen/README.md`、`build-llama-runtime.ps1` 与 `THIRD-PARTY-NOTICES.md`。
