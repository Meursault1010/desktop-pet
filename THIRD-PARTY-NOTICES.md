# 第三方组件与模型说明

Yuki 的桌宠素材、应用界面与项目源代码版权归项目作者所有；本仓库没有授予第三方复制、修改或再发布 Yuki 源码与原创素材的许可。下列第三方部分按各自许可分发。

| 组件 | 发行版本 / 来源 | 许可与随包文本 |
| --- | --- | --- |
| Electron / Chromium | Electron 44.9.0 | Electron MIT 许可和 Chromium 第三方许可清单随应用提供：`LICENSE`、`LICENSES.chromium.html` |
| Qwen3.8-4B-Distill-GGUF | Empero AI，固定仓库版本 `391fc7d` | Hugging Face 模型卡标注 Apache-2.0；随包提供 `licenses/Apache-2.0.txt` 和模型来源说明 |
| llama.cpp | ggml-org `b12464` Windows Vulkan x64 官方构建 | MIT；随包提供 `licenses/llama.cpp-MIT.txt`。该构建中的 OpenMP 组件另带 `LICENSE-LLVM-OpenMP` |
| Qt / PySide6 | PySide6 6.10.2 | LGPL-3.0；随包提供 `licenses/LGPL-3.0.txt`，对应 Qt/PySide 动态库保留在独立文件中 |
| OCR / 文档与图像处理依赖 | 随发行包的 RapidOCR、ONNX Runtime、OpenCV、NumPy、PyClipper 等 | 各依赖的许可证和版权文本按原包保留在对应 `*.dist-info/licenses` 或其上游发行文件中 |
| 前端运行依赖 | React、Radix UI、Lucide、Mammoth、pdf-parse、pinyin-pro 等 | 各依赖原包中的许可证与版权文件随 `resources/app/node_modules` 提供 |

Qwen3.8-4B-Distill-GGUF 是 Empero AI 社区发布的蒸馏模型，并非 Qwen 官方单独发布的 4B 权重。模型权重来源：<https://huggingface.co/empero-ai/Qwen3.8-4B-Distill-GGUF/tree/391fc7d>。llama.cpp 发行源：<https://github.com/ggml-org/llama.cpp/releases/tag/b12464>。

本说明记录本版本直接纳入的组件；组件自身许可证优先于本说明。使用云端模型时，另受用户选择的服务商条款约束。
