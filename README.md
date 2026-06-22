# AutoOCRTranslator

一款轻量级 Windows 平台实时 OCR 翻译 overlay 工具，主要用于游戏/视频/应用窗口的实时字幕翻译。

![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ 功能特性

- **实时窗口捕获**：选择任意可见窗口，定时截取画面。
- **多引擎 OCR**：支持 PaddleOCR 与 RapidOCR，可识别日文、简体中文、繁体中文、英文等。
- **多源翻译**：内置 Google 翻译免费接口，并支持 DeepL、腾讯云、阿里云等商业 API。
- **SQLite 缓存**：自动缓存翻译结果，避免重复请求，节省 API 额度与时间。
- **置顶覆盖层**：以半透明窗口将译文显示在原文字位置，不影响操作。
- **自定义翻译区域**：可手动划分多个 ROI 区域，只翻译关注区域。
- **系统托盘**：最小化到托盘，双击显示/隐藏主窗口。
- **悬浮日志窗口**：实时查看运行日志，便于调试。

---

## 📦 项目结构

```text
AutoOCRTranslator/
├── .venv/                  # Python 虚拟环境
├── assets/                 # 静态资源（图标等）
├── config/                 # 配置文件
│   └── settings.yaml
├── data/cache/             # SQLite 缓存与日志
├── docs/                   # 项目文档
│   ├── REQUIREMENTS.md     # 需求文档
│   ├── TECH_STACK.md       # 技术栈说明
│   ├── ARCHITECTURE.md     # 架构设计
│   └── PROGRESS.md         # 开发进度
├── src/                    # 源代码
│   ├── app.py              # 应用主控制
│   ├── main.py             # 程序入口
│   ├── config.py           # 配置加载
│   ├── capture/            # 窗口捕获模块
│   ├── ocr/                # OCR 模块
│   ├── translate/          # 翻译模块
│   ├── cache/              # 缓存模块
│   ├── overlay/            # 覆盖层模块
│   ├── gui/                # 设置与主窗口
│   └── worker/             # 翻译子进程
├── tests/                  # 单元测试
├── requirements.txt        # Python 依赖
├── run.py                  # 快速启动脚本
└── README.md
```

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/driohcker/AutoOCRTranslator.git
cd AutoOCRTranslator
```

### 2. 创建并激活虚拟环境

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

> **注意**：PaddleOCR 首次运行会自动下载模型文件，可能需要几分钟并占用磁盘空间。

### 4. 运行程序

```bash
python run.py
```

---

## 📖 使用说明

1. 运行后会弹出**主窗口**，同时系统托盘会显示 **AutoOCRTranslator** 图标（若系统托盘不可用，则以纯窗口模式运行）。
2. 在主窗口点击"选择窗口"，选择要翻译的游戏/应用窗口。
3. 点击"开始翻译"后进入循环：**截图 → OCR → 查缓存/翻译 → 显示覆盖层**。
4. 在设置窗口的 **OCR 区域预设** 中可选择：
   - **字幕/对话**、**底部全宽**、**全屏**：使用固定区域。
   - **自定义**：手动输入 `[x, y, w, h]` 单个区域。
   - **自定义区域划分**：点击"划分区域"按钮，在目标窗口上拖拽画出多个矩形翻译区域；翻译运行时这些区域会微微高亮显示。
5. 右键托盘图标可选择：
   - **开始翻译 / 停止翻译**：控制翻译循环。
   - **显示主窗口**：打开/前置主控制窗口。
   - **退出**：关闭程序。
6. 双击托盘图标可快速打开主窗口。

---

## ⚙️ 配置说明

配置文件位于 `config/settings.yaml`，主要配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `app.name` | 应用名称 | `AutoOCRTranslator` |
| `app.version` | 应用版本 | `0.0.2` |
| `capture.interval_ms` | 截图间隔（毫秒） | `3000` |
| `capture.target_window_title` | 目标窗口标题（可选） | `''` |
| `ocr.engine` | OCR 引擎：`paddle` / `rapid` | `paddle` |
| `ocr.lang` | OCR 语言：`japan` / `ch` / `ch_tra` / `en` | `japan` |
| `ocr.use_gpu` | 是否使用 GPU | `false` |
| `ocr.drop_score` | 置信度阈值，低于此值的文字会被丢弃 | `0.3` |
| `ocr.roi_preset` | 区域预设：`subtitle` / `bottom` / `full` / `custom` / `custom_zones` | `custom_zones` |
| `ocr.roi_custom` | 自定义模式下的单个区域 `[x, y, w, h]` | - |
| `ocr.roi_zones` | 自定义区域划分模式下的多个区域列表 | - |
| `translate.provider` | 翻译提供者：`google_free` / `deep_l` / `tencent` / `aliyun` | `google_free` |
| `translate.source_lang` | 源语言，如 `ja` / `en` | `ja` |
| `translate.target_lang` | 目标语言，如 `zh-CN` / `zh-TW` / `en` | `zh-CN` |
| `translate.api_key` | API Key / SecretId / AccessKey ID | `''` |
| `translate.api_secret` | API Secret / SecretKey / AccessKey Secret | `''` |
| `translate.proxy` | 代理地址 | `''` |
| `translate.filter_source_lang` | 是否按源语言过滤 | `true` |
| `translate.strict_source_lang` | 严格过滤，日文只翻译含假名文本 | `true` |
| `cache.enabled` | 是否启用缓存 | `true` |
| `cache.db_path` | 缓存数据库路径 | `data/cache/translations.db` |
| `cache.ttl_days` | 缓存有效期（天） | `30` |
| `overlay.font_family` | 覆盖层字体 | `Microsoft YaHei` |
| `overlay.font_size` | 字体大小 | `18` |
| `overlay.font_color` | 字体颜色 | `#FFFFFF` |
| `overlay.bg_color` | 背景颜色（ARGB） | `#80000000` |
| `overlay.border_color` | 边框颜色 | `#FF000000` |
| `overlay.max_width` | 覆盖层最大宽度 | `400` |

> **提示**：修改配置后，可在设置窗口点击"确定"自动保存；手动编辑 YAML 后需重启生效。

---

## 🔑 翻译 API 配置

### Google 翻译（默认，免费）

无需配置 Key，直接使用。但免费接口可能不稳定，适合轻度使用。

```yaml
translate:
  provider: google_free
```

### DeepL

1. 在 [DeepL 官网](https://www.deepl.com/pro-api) 申请 API Key。
2. 配置：

```yaml
translate:
  provider: deep_l
  api_key: your-auth-key
```

> 免费版 Key 以 `:fx` 结尾。

### 腾讯云翻译

1. 在 [腾讯云控制台](https://console.cloud.tencent.com/cam/capi) 获取 SecretId 与 SecretKey。
2. 配置：

```yaml
translate:
  provider: tencent
  api_key: your-secret-id
  api_secret: your-secret-key
```

### 阿里云翻译

1. 在 [阿里云 RAM 控制台](https://ram.console.aliyun.com/manage/ak) 获取 AccessKey ID 与 AccessKey Secret。
2. 配置：

```yaml
translate:
  provider: aliyun
  api_key: your-access-key-id
  api_secret: your-access-key-secret
```

---

## 🛠️ 开发说明

### 运行测试

```bash
.venv\Scripts\activate
python -m pytest tests/ -v
```

### 代码风格

- 类型注解：关键函数与类请添加类型提示。
- 日志：使用 `logging` 模块，避免 `print`。
- 子进程：`src/worker/translation_worker.py` 运行在独立进程中，请勿导入 GUI 相关代码。

---

## ⚠️ 已知问题与性能提示

- **OCR 性能**：当前使用 PaddleOCR CPU 版，对高分辨率全屏画面处理较慢（约数十秒/帧）。
  - 建议将游戏/应用设为窗口化或较低分辨率。
  - 可通过 `ocr.roi_preset` 只翻译关注区域，显著提升速度。
  - 也可切换到 `rapid` 引擎以获得更快的 CPU 推理速度。
- **翻译质量**：默认使用 Google Translate 免费接口，可能存在不稳定或翻译不准确的情况。
  - 如需稳定高质量翻译，请在设置中配置 DeepL、腾讯云、阿里云等商业 API（需自行申请 Key）。
- **首次启动**：PaddleOCR 首次运行会自动下载模型文件，可能需要几分钟并占用磁盘空间。
- **高 DPI 显示**：部分窗口坐标在高 DPI 环境下可能存在偏差，可尝试调整显示缩放设置。

---

## 📄 项目文档

- [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) —— 需求文档（功能/非功能需求、用户场景、验收标准）
- [`docs/TECH_STACK.md`](docs/TECH_STACK.md) —— 技术栈文档（选型理由、依赖清单、风险应对）
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) —— 架构设计文档（模块划分、数据流、接口约定）
- [`docs/PROGRESS.md`](docs/PROGRESS.md) —— 项目进度记录

---

## 📝 更新日志

### v0.0.2

- **实验性功能**：支持 GPU 加速 OCR。
  - 在设置界面新增「启用 GPU 加速 OCR (实验性)」开关，默认关闭。
  - 仅对 PaddleOCR 引擎有效；环境不支持时自动回退 CPU。
  - 保存 GPU 设置后，若翻译循环正在运行会自动重启以生效。
- 新增 `requirements-gpu.txt`，记录 GPU 版依赖安装方式。
- 新增 `tests/test_gpu_ocr.py`，验证 CPU/GPU OCR 识别结果一致性与加速比。
- 修复 `ResultReader` 线程在停止时可能阻塞的问题。

### v0.0.1

- 初始版本发布。
- 支持窗口实时捕获、OCR 识别、翻译与覆盖层显示。
- 支持 PaddleOCR / RapidOCR 双引擎。
- 支持 Google 免费翻译、DeepL、腾讯云、阿里云翻译 API。
- 支持 SQLite 翻译缓存。
- 支持自定义翻译区域与系统托盘控制。

---

## 📜 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

## 🙏 致谢

- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [RapidOCR](https://github.com/RapidAI/RapidOCR)
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- [mss](https://github.com/BoboTiG/python-mss)
