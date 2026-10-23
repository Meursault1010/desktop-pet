# Yuki 内置 Qwen

本目录保存实际模型和推理运行库，运行时无需联网或启动 LM Studio。

- 模型：`Qwen3.8-4B-Q4_K_M.gguf`，从本机 LM Studio 的 `empero-ai/Qwen3.8-4B-Distill-GGUF` 复制。
- 运行库：本机 LM Studio `llama.cpp-win-x86_64-vulkan-avx2-2.55.0` 的 EXE/DLL，使用 Vulkan GPU 加速。
- 私有本机接口：`http://127.0.0.1:1236/v1`，模型名 `qwen3.8-4b-distill`。
- Yuki 启动后自动加载，聊天与划词翻译共用该接口；正常退出时关闭自己启动的推理进程。
- 首次加载需要几秒钟；模型不具备视觉输入能力，图片文字由现有 OCR 处理。

请保留整个项目目录。模型权重约 2.8 GB，权重及运行库已加入 Git 忽略规则，只保存在本地磁盘；单独克隆代码不包含它们。正式打包会复制到 `resources/local-model/qwen`，便携版需要完整目录一起移动。

如用户已配置其他模型服务，Yuki 保留该配置。在 AI 助手连接设置里填写上述接口和模型名即可改用内置模型。

来源和校验记录见 `manifest.json`。此副本来源于本机已有文件；对外分发前应一并核实模型及原运行库附带的许可。
