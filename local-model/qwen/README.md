# Yuki 内置 Qwen

- 模型：Empero AI 发布的 `Qwen3.8-4B-Distill-GGUF`，`Qwen3.8-4B-Q4_K_M.gguf`，Apache-2.0。
- 固定来源：<https://huggingface.co/empero-ai/Qwen3.8-4B-Distill-GGUF/tree/391fc7d>；文件 SHA-256 见 `manifest.json`。
- 推理运行库：官方 `ggml-org/llama.cpp` Windows x64 Vulkan 发行版 `b12464`，MIT；构建脚本会校验发行 ZIP 的 SHA-256。
- 本机接口：`http://127.0.0.1:1236/v1`，模型名 `qwen3.8-4b-distill`。默认关闭；启用后由 Yuki 本机启动服务，退出时关闭。
- 文本模型，不支持视觉输入；图片文字由本机 OCR 提取。
- 本地构建时，模型文件保存在被 Git 忽略的目录；`build-electron.ps1` 在缺失时从固定的公开模型版本下载并校验。
