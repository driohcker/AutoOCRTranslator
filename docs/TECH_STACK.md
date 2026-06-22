# AutoOCRTranslator 技术栈文档

> 版本：v0.1.0  
> 状态：已确认

---

## 1. 技术栈总览

| 层级 | 选型 | 版本要求 | 说明 |
|------|------|----------|------|
| 编程语言 | Python | >= 3.10 | 生态丰富，适合快速原型和工具开发 |
| 虚拟环境 | venv | 内置 | 隔离项目依赖 |
| GUI 框架 | PyQt6 | >= 6.6 | 跨平台 GUI，支持无边框透明置顶窗口 |
| 窗口捕获 | mss + pywin32 | 最新版 | mss 高性能截图，pywin32 操作 Windows 窗口 |
| OCR 引擎 | PaddleOCR | >= 2.7 | 对日文/中文识别效果较好，支持 CPU/GPU |
| 翻译服务 | Google Translate（免费）+ 可扩展 | - | 默认免费方案，预留商业 API 接口 |
| 缓存存储 | SQLite | 内置 | 轻量本地数据库，适合存储翻译缓存 |
| 配置格式 | YAML | - | 人类可读，便于手动编辑 |
| 打包工具 | PyInstaller | >= 6.0 | 打包为独立 Windows exe |
| 版本控制 | Git | - | 代码版本管理 |

---

## 2. 技术选型理由

### 2.1 Python

**选择理由**：
- 拥有丰富的 AI/图像处理生态（PaddleOCR、Pillow、OpenCV 等）。
- 开发效率高，适合快速迭代工具类项目。
- Windows 平台部署和打包成熟。

**替代方案**：
- C++：性能更高，但开发周期长，OCR/翻译集成成本高。
- C#：Windows 原生支持好，但 OCR/翻译生态不如 Python 丰富。

### 2.2 PyQt6

**选择理由**：
- 支持创建无边框、置顶、透明、点击穿透的覆盖层窗口。
- 提供丰富的 GUI 控件，便于开发设置界面。
- 信号槽机制适合处理定时截图和界面更新。

**替代方案**：
- tkinter：内置，但透明窗口和置顶效果较弱。
- PySide6：与 PyQt6 类似，授权不同（LGPL），可替代。

### 2.3 mss + pywin32

**选择理由**：
- `mss` 是高性能截图库，比 Pillow 的 `ImageGrab` 更快。
- `pywin32` 提供 Windows API 绑定，用于枚举窗口、获取窗口句柄和客户区坐标。
- 两者组合是实现窗口级实时截屏的标准方案。

**替代方案**：
- Pillow ImageGrab：简单但性能较低。
- D3D11/DXGI 截屏：性能极高但复杂度高，适合后续优化。

### 2.4 PaddleOCR

**选择理由**：
- 对日文、中文、英文识别效果优秀。
- 提供文本检测和识别一体化模型。
- 支持 CPU 推理，无需显卡即可运行。
- 可输出文字边界框坐标，满足覆盖层定位需求。

**已知兼容性处理**：
- 当前环境为 Python 3.13 + PaddlePaddle 3.3.1，默认启用 oneDNN 会导致 `ConvertPirAttribute2RuntimeAttribute` 运行时错误。
- 解决方案：在导入 `paddleocr` 前设置环境变量 `FLAGS_use_mkldnn=0`。
- 该处理已封装在 `src/ocr/paddle_ocr.py` 中，对其他模块透明。

**GPU 加速（实验性）**：
- PaddleOCR 支持通过 `paddlepaddle-gpu` 在 NVIDIA GPU 上推理，可显著降低单帧 OCR 耗时。
- 默认关闭（`ocr.use_gpu: false`），用户需在设置界面手动开启；仅当 OCR 引擎为 `paddle` 时生效。
- 若配置使用 GPU 但环境不支持（未安装 GPU 版 Paddle 或无 CUDA），系统会自动回退到 CPU 并记录警告。
- 启用步骤：卸载 CPU 版 `paddlepaddle`，按本机 CUDA 版本安装对应 `paddlepaddle-gpu`，然后在设置中勾选"启用 GPU 加速 OCR (实验性)"。
- 实测：在 NVIDIA GeForce RTX 3050（CUDA 12.6）上，同一张 400×100 测试图片的 PaddleOCR 识别耗时从约 1.0s（CPU）降至约 0.03s（GPU），加速比约 30 倍。

**替代方案**：
- Tesseract：轻量，但对日文竖排、艺术字效果较差。
- EasyOCR：对多语言支持好，但模型较大，首次加载慢。
- 云端 OCR：需要联网且可能收费，不适合离线场景。

### 2.5 Google Translate（免费接口）

**选择理由**：
- 默认方案无需申请 API Key，降低上手门槛。
- 日文→中文翻译质量可接受。

**替代方案/扩展**：
- DeepL API：翻译质量高，但需要 API Key。
- 腾讯云/阿里云翻译：国内稳定，需申请和付费。
- LibreTranslate：开源本地翻译，可离线但质量一般。

### 2.6 SQLite

**选择理由**：
- Python 内置支持，无需额外服务。
- 轻量、文件化存储，适合单机工具。
- 支持索引和 TTL 查询。

**替代方案**：
- JSON 文件：简单但大数据量下性能差。
- Redis：需要额外服务，过于重量级。

### 2.7 YAML

**选择理由**：
- 人类可读，便于用户手动编辑。
- 支持注释，方便说明配置项含义。
- Python 有成熟解析库 PyYAML。

**替代方案**：
- JSON：不支持注释，可读性较差。
- TOML：可读性好，但用户熟悉度不如 YAML。

### 2.8 PyInstaller

**选择理由**：
- Windows 平台最常用的 Python 打包工具。
- 可打包为单文件 exe。
- 对 PyQt6、PaddleOCR 等大型库有成熟打包经验。

**替代方案**：
- cx_Freeze：配置较复杂。
- Nuitka：编译为 C++，性能更好但打包时间长。

---

## 3. 依赖清单

### 3.1 基础依赖（已安装）

| 包名 | 作用 |
|------|------|
| PyYAML | 解析和写入 YAML 配置文件 |
| Pillow | 图像处理、格式转换 |
| numpy | 图像数组运算 |
| mss | 高性能屏幕截图 |
| pywin32 | Windows API 调用 |
| PyQt6 | GUI 和覆盖层窗口 |
| requests | HTTP 请求，用于翻译 API |

### 3.2 OCR 依赖（后续安装）

| 包名 | 作用 |
|------|------|
| paddlepaddle | PaddleOCR 深度学习框架（CPU 版，默认） |
| paddleocr | OCR 识别库 |
| rapidocr-onnxruntime | 基于 ONNXRuntime 的轻量 OCR 引擎，CPU 默认 |

> 若用户有 NVIDIA GPU，可卸载 `paddlepaddle` 并安装 `paddlepaddle-gpu` 以启用 GPU 加速推理。
> 具体命令参考 `requirements-gpu.txt`。

### 3.3 打包依赖（后续安装）

| 包名 | 作用 |
|------|------|
| pyinstaller | 打包为 exe |

---

## 4. 开发环境

- **操作系统**：Windows 10/11
- **Python 版本**：3.13.5（推荐 3.10+）
- **Shell**：Git Bash / PowerShell / CMD
- **虚拟环境**：`.venv/`

### 常用命令

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows bash）
.venv/Scripts/activate

# 安装/更新依赖
python -m pip install -r requirements.txt

# 运行项目
python run.py

# 打包（后续步骤）
pyinstaller AutoOCRTranslator.spec
```

---

## 5. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| PaddleOCR 体积大、首次加载慢 | 打包后 exe 较大，启动慢 | 首次启动预加载模型；后续考虑模型裁剪 |
| 免费翻译 API 不稳定/限流 | 翻译失败或延迟高 | 缓存机制减少调用；预留多翻译源切换 |
| 全屏游戏截屏失败 | 部分游戏无法捕获 | 优先支持窗口化/无边框；研究 DXGI 截屏作为备选 |
| 高 DPI 屏幕坐标偏移 | 覆盖层位置不准 | 使用 DPI 感知 API 获取真实坐标 |
| 杀毒软件误报 exe | 用户无法运行 | 使用 PyInstaller 签名；提供源码运行说明 |

---

## 6. 扩展方向

- ✅ 支持 GPU 加速 OCR（已实现，实验性，默认关闭）。
- 支持更多翻译引擎（DeepL、OpenAI、本地模型等）。
- 支持文本区域手动框选/屏蔽。
- 支持语音朗读原文/译文。
- 支持历史翻译记录导出。
