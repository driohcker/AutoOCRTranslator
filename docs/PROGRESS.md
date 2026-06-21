# AutoOCRTranslator 项目进度记录

> 本文件用于记录项目各开发阶段的计划、执行内容与验证结果，便于跟踪整体进度和上下文恢复。

---

## 项目概述

- **项目名称**：AutoOCRTranslator
- **项目目标**：开发一款 Windows 平台轻量级游戏实时 OCR 翻译 overlay 工具。
- **核心功能**：
  1. 实时捕获指定游戏窗口画面。
  2. 使用 OCR 识别画面中文字（重点支持日文/中文）及位置。
  3. 调用翻译 API 将文字翻译为目标语言（中文）。
  4. SQLite 缓存翻译结果，避免重复翻译。
  5. 以置顶半透明覆盖层将译文显示在原文字位置。
  6. 提供配置界面，支持调整 OCR、翻译、显示等参数。

---

## 完整开发计划

| 步骤 | 阶段 | 目标 | 可交付/可验证点 | 状态 |
|------|------|------|-----------------|------|
| 0 | 需求分析与技术文档 | 明确功能/非功能需求、技术选型、架构设计 | 需求文档、技术栈文档、架构设计文档 | ✅ 已完成 |
| 1 | 项目初始化 | 搭建项目结构、虚拟环境、依赖配置、基础配置文件 | 目录结构清晰，可运行最小入口 | ✅ 已完成 |
| 2 | 窗口捕获模块 | 实现游戏窗口检测、选择、实时截图 | 能正确捕获指定窗口并保存/预览 | ✅ 已完成 |
| 3 | OCR 模块 | 集成 PaddleOCR，识别截图中的文字及位置 | 输出文本块和对应坐标 | ✅ 已完成 |
| 4 | 翻译模块 | 接入翻译 API，实现文字翻译 | 输入日文，输出中文 | ✅ 已完成 |
| 5 | 缓存模块 | SQLite 缓存：原文→译文、坐标、时间戳 | 重复文本命中缓存不调用 API | ✅ 已完成 |
| 6 | 覆盖层模块 | 无边框置顶透明窗口，显示翻译结果 | 翻译文字覆盖在原游戏文字位置 | ✅ 已完成 |
| 7 | 主程序集成 | 组合各模块，实现定时循环：截图→OCR→查缓存/翻译→显示 | 运行主程序即可实时翻译游戏画面 | ✅ 已完成 |
| 8 | 配置与设置界面 | 提供 GUI 配置窗口、热键、参数持久化 | 用户可配置 API、目标语言、显示样式等 | ✅ 已完成 |
| 9 | 测试与优化 | 单元测试、性能优化、错误处理 | 主要场景稳定运行 | ⏳ 进行中 |
| 10 | 打包发布 | 使用 PyInstaller 打包为单文件 exe | 无需 Python 环境即可运行 | ⏳ 待开始 |

---

## 各步骤详细记录

### 步骤 0：需求分析与技术文档

- **时间**：2026-06-20
- **目的**：
  - 将用户需求从对话抽象为明确、可验证的需求文档，避免开发过程中的理解偏差。
  - 确定技术选型及理由，为后续模块实现提供一致的技术基础。
  - 设计清晰的模块划分、数据流和接口约定，降低模块耦合度。
  - 建立项目前期工作的可追溯性，方便后续审查和维护。

- **计划内容**：
  1. 编写 `docs/REQUIREMENTS.md`：功能需求、非功能需求、用户场景、验收标准。
  2. 编写 `docs/TECH_STACK.md`：技术选型、依赖清单、开发环境、风险应对。
  3. 编写 `docs/ARCHITECTURE.md`：整体架构、模块划分、数据流、接口约定、配置结构、错误处理和日志策略。
  4. 确保三份文档与项目代码结构、配置文件保持一致。

- **实际完成**：
  - 完成 `docs/REQUIREMENTS.md`，包含 9 个功能需求类别、6 类非功能需求、6 个用户场景、验收标准。
  - 完成 `docs/TECH_STACK.md`，明确 Python + PyQt6 + mss + pywin32 + PaddleOCR + SQLite + YAML + PyInstaller 技术栈。
  - 完成 `docs/ARCHITECTURE.md`，定义了 6 个核心模块的接口、数据流、配置结构和错误处理策略。
  - 更新 `docs/PROGRESS.md`，将前期工作纳入项目进度管理。

- **验证方式**：
  - 三份文档均存在于 `docs/` 目录。
  - 文档中的模块划分与 `src/` 目录结构一致。
  - 配置结构与 `config/settings.yaml` 一致。

- **对项目的意义**：
  - 使开发从“凭感觉”变为“按文档执行”，每个模块有明确输入输出。
  - 为后续代码审查、测试和扩展提供了依据。
  - 防止上下文丢失，新参与者可通过文档快速理解项目。

---

### 步骤 1：项目初始化

- **时间**：2026-06-20
- **目的**：
  - 为整个项目建立清晰、可维护的代码组织方式。
  - 隔离 Python 依赖环境，避免与系统 Python 冲突。
  - 提供统一的配置管理机制，方便后续模块读取和修改配置。
  - 确保项目从第一天起就能运行一个最小入口，验证环境正确。

- **计划内容**：
  1. 创建项目目录结构（`src/` 各模块、`config/`、`data/cache/`、`tests/`、`docs/`、`assets/`）。
  2. 创建 Python 虚拟环境 `.venv/`。
  3. 编写 `requirements.txt`，安装基础依赖（Pillow、PyYAML、PyQt6、mss、pywin32、requests、numpy）。
  4. 编写 `.gitignore`。
  5. 编写 `README.md`，记录项目结构和使用方式。
  6. 编写 `config/settings.yaml` 默认配置。
  7. 编写 `src/config.py` 配置管理类。
  8. 编写 `src/main.py` 与 `run.py` 最小入口。

- **实际完成**：
  - 使用 Python 3.13.5 创建虚拟环境并安装全部基础依赖。
  - 建立完整目录结构。
  - 完成 `README.md`、`.gitignore`、`requirements.txt`。
  - 完成默认配置文件和配置加载模块，支持点号键访问（如 `capture.interval_ms`）。
  - 完成最小可运行入口，运行 `python run.py` 成功。

- **验证方式**：
  ```bash
  .venv\Scripts\python run.py
  # 输出：启动 AutoOCRTranslator v0.1.0
  #      项目初始化完成，后续将逐步集成各模块。
  ```

- **对项目的意义**：
  - 奠定了模块化架构基础，后续窗口捕获、OCR、翻译、缓存、覆盖层可按独立模块并行开发。
  - 配置与依赖管理规范化，降低后续开发环境不一致风险。
  - 建立了项目进度记录机制（本文件），便于长期跟踪。

---

### 步骤 2：窗口捕获模块

- **时间**：2026-06-20
- **目的**：
  - 获取目标游戏窗口的实时画面，为 OCR 模块提供输入图像。
  - 支持用户选择窗口，避免硬编码窗口标题。
  - 检测窗口有效性，处理窗口关闭/最小化等边界情况。
- **计划内容**：
  1. 使用 `win32gui` 枚举所有可见窗口并获取标题。
  2. 提供按标题关键词匹配或弹窗选择目标窗口的接口。
  3. 使用 `mss` + `Pillow` 截取窗口客户区。
  4. 返回 `PIL.Image` 对象，支持保存为文件便于调试。
  5. 编写单元测试：验证窗口枚举、截图返回图像尺寸正确。
- **实际完成**：
  - 完成 `src/capture/window_capture.py`，实现 `WindowCapture` 类。
  - 实现接口：`list_windows()`、`find_window()`、`set_target()`、`get_target()`、`is_valid()`、`get_client_rect()`、`capture()`。
  - 实现 `select_window_dialog()` 函数，使用 PyQt6 弹出窗口选择对话框。
  - 修复 `mss.mss()` 废弃警告，改用 `mss.MSS()`。
  - 完成 `tests/test_capture.py` 单元测试，覆盖窗口枚举、查找、无效句柄、真实窗口截图、空列表对话框等场景。
  - 安装 pytest 并更新 `requirements.txt`。
- **验证方式**：
  - 运行 `python -m pytest tests/test_capture.py -v`，6 个测试全部通过。
  - 测试截图成功保存为 `tests/capture_test_output.png`（约 655KB），尺寸正确。
  - 命令输出：
    ```
    6 passed in 0.33s
    ```
- **对项目的意义**：
  - 为 OCR 模块提供了稳定的图像输入来源。
  - 实现了窗口选择和有效性检测，满足需求 FR-01 全部子项。
  - 奠定了后续模块测试的基础（pytest 已就绪）。

---

### 步骤 3：OCR 模块

- **时间**：2026-06-20
- **目的**：
  - 从游戏截图中提取文字内容及其在画面中的位置。
  - 将 PaddleOCR 输出转换为项目统一格式，供翻译和覆盖层模块使用。
- **计划内容**：
  1. 安装并集成 PaddleOCR（优先 CPU 版，可选 GPU 版）。
  2. 封装 OCR 类，支持语言参数（日文 `japan`、中文 `ch` 等）。
  3. 返回结构化结果：文本、置信度、边界框坐标。
  4. 过滤低置信度文本。
  5. 编写测试用例验证日文/中文识别。
- **实际完成**：
  - 安装 `paddlepaddle==3.3.1` 和 `paddleocr==3.7.0`。
  - 发现 Python 3.13 + PaddlePaddle 3.x 默认启用 oneDNN 会导致 `ConvertPirAttribute2RuntimeAttribute` 错误，通过设置环境变量 `FLAGS_use_mkldnn=0` 解决。
  - 完成 `src/ocr/paddle_ocr.py`，封装 `PaddleOCREngine` 类。
  - 支持语言标准化映射（ja→japan, zh→ch, en→en 等）。
  - 支持 `drop_score` 过滤低置信度结果。
  - 将 PaddleOCR 输出解析为统一格式 `{"text", "box", "score"}`。
  - 关闭文档方向分类、去扭曲、文本方向分类等非必要功能，将初始化时间从约 2 分钟降至约 4 秒。
  - 完成 `tests/test_ocr.py` 单元测试，覆盖语言标准化、结果格式、日文识别、英文识别、空输入等场景。
  - 更新 `requirements.txt`，将 OCR 依赖从注释状态改为正式依赖。
- **验证方式**：
  - 运行 `python -m pytest tests/test_ocr.py -v`，6 个测试全部通过。
  - 运行全部测试 `python -m pytest tests/ -v`，12 个测试全部通过。
  - 命令输出：
    ```
    6 passed, 1 warning in 40.14s
    12 passed, 1 warning in 52.47s
    ```
- **对项目的意义**：
  - 实现了从图像到结构化文字识别的关键转换。
  - 解决了 PaddleOCR 3.x 在 Python 3.13 下的兼容性陷阱，为后续开发扫清障碍。
  - 输出格式统一，便于翻译模块和覆盖层模块消费。

---

### 步骤 4：翻译模块

- **时间**：2026-06-20
- **目的**：
  - 将 OCR 识别的日文/英文文本翻译为目标语言（中文）。
  - 提供可扩展的翻译提供者架构，便于后续接入商业 API。
- **计划内容**：
  1. 设计翻译提供者接口（Provider）。
  2. 先实现一个免费/易用的方案（如 Google Translate 免费接口或 LibreTranslate）。
  3. 预留 DeepL、腾讯云、阿里云等商业 API 扩展点。
  4. 支持源语言、目标语言配置。
  5. 错误处理和重试机制。
- **实际完成**：
  - 完成 `src/translate/translator.py`，定义 `TranslationProvider` 抽象基类。
  - 实现 `GoogleFreeProvider`（Google Translate 免费网页接口），支持 ja→zh-CN 等翻译。
  - 实现 `Translator` 工厂类，支持按名称创建提供者和注册新提供者。
  - 实现了空文本处理、网络错误处理、响应格式异常处理。
  - 完成 `tests/test_translate.py` 单元测试，使用 mock 避免依赖真实网络，覆盖正常翻译、多句合并、空文本、网络错误、异常响应、工厂创建、提供者注册等场景。
- **验证方式**：
  - 运行 `python -m pytest tests/test_translate.py -v`，10 个测试全部通过。
  - 运行全部测试 `python -m pytest tests/ -v`，22 个测试全部通过。
  - 命令输出：
    ```
    10 passed in 0.29s
    22 passed, 1 warning in 21.30s
    ```
- **对项目的意义**：
  - 实现了原文到译文的转换，是翻译流程的核心环节。
  - 提供者架构便于后续接入 DeepL、腾讯云、阿里云等商业 API，满足需求 FR-03.3。
  - 完善的错误处理确保单个翻译失败不会影响后续帧处理。

---

### 步骤 5：缓存模块

- **时间**：2026-06-20
- **目的**：
  - 避免对相同原文重复调用翻译 API，节省时间和 API 额度。
  - 提供稳定、持久化的翻译结果本地存储。
- **计划内容**：
  1. 使用 SQLite 存储 `原文 → 译文` 映射。
  2. 记录语言对、时间戳、命中次数。
  3. 支持精确匹配查询。
  4. 支持缓存过期清理（TTL）。
  5. 编写单元测试验证缓存命中和过期逻辑。
- **实际完成**：
  - 完成 `src/cache/translation_cache.py`，封装 `TranslationCache` 类。
  - 使用 SQLite 存储翻译缓存，表字段包括 `source_text`、`source_lang`、`target_lang`、`translation`、`created_at`、`last_accessed`、`hit_count`。
  - 实现 `get()` 精确匹配查询，命中时自动更新 `hit_count` 和 `last_accessed`。
  - 实现 `set()` 写入缓存，存在冲突时更新译文并增加命中次数。
  - 实现 `clear()` 清空缓存。
  - 实现 `cleanup_expired(ttl_days)` 按最后访问时间清理过期缓存；`ttl_days <= 0` 表示永不过期。
  - 实现 `stats()` 统计缓存数量和总命中次数。
  - 使用自定义 `_connect()` 上下文管理器确保 SQLite 连接正确关闭，避免 Windows 下文件占用问题。
  - 完成 `tests/test_cache.py` 单元测试，覆盖写入/读取、命中统计、更新、清空、过期清理、TTL=0、统计、多语言对独立等场景。
  - 更新 `docs/ARCHITECTURE.md` 中的缓存表结构，补充 `last_accessed` 字段和索引。
- **验证方式**：
  - 运行 `python -m pytest tests/test_cache.py -v`，9 个测试全部通过。
  - 运行全部测试 `python -m pytest tests/ -v`，31 个测试全部通过。
  - 命令输出：
    ```
    9 passed in 0.42s
    31 passed, 1 warning in 33.83s
    ```
- **对项目的意义**：
  - 显著减少翻译 API 调用次数，降低延迟和成本。
  - 缓存持久化到本地，程序重启后依然有效。
  - 命中统计便于后续分析和优化。

---

### 步骤 6：覆盖层模块

- **时间**：2026-06-20
- **目的**：
  - 将翻译结果以可视化方式叠加在游戏画面上，不影响游戏操作。
  - 使译文显示在原文字位置附近，并跟随目标窗口移动。
- **计划内容**：
  1. 使用 PyQt6 创建无边框、置顶、透明、点击穿透的窗口。
  2. 根据 OCR 坐标在对应位置绘制译文。
  3. 支持字体、字号、颜色、背景透明度配置。
  4. 跟随窗口移动实时更新位置。
- **实际完成**：
  - 完成 `src/overlay/overlay_window.py`，封装 `OverlayWindow` 类。
  - 设置窗口标志：`FramelessWindowHint`、`WindowStaysOnTopHint`、`Tool`、`WindowTransparentForInput`。
  - 启用 `WA_TranslucentBackground` 实现透明背景。
  - 实现 `set_target_window()` 绑定目标窗口。
  - 实现 `update_translations()` 接收翻译项列表并触发重绘。
  - 实现 `apply_style()` 支持字体、字号、颜色、背景色、边框色、最大宽度配置。
  - 使用 100ms 定时器持续跟随目标窗口客户区位置变化。
  - 在 `paintEvent()` 中按 OCR 边界框左上角位置绘制带半透明背景的译文文本。
  - 完成 `tests/test_overlay.py` 单元测试，覆盖窗口标志、透明背景、目标窗口设置、翻译项更新、样式应用、绘制事件不崩溃等场景。
- **验证方式**：
  - 运行 `python -m pytest tests/test_overlay.py -v`，6 个测试全部通过。
  - 运行全部测试 `python -m pytest tests/ -v`，37 个测试全部通过。
  - 命令输出：
    ```
    6 passed in 0.22s
    37 passed, 1 warning in 51.69s
    ```
- **对项目的意义**：
  - 实现了用户最直接感知的可视化输出，译文可叠加在游戏画面上。
  - 点击穿透设计确保不影响游戏操作。
  - 为后续主程序集成提供了最终的显示输出接口。

---

### 步骤 7：主程序集成

- **时间**：2026-06-20
- **目的**：
  - 将各模块串联，形成完整工作流。
  - 实现从截图到显示的端到端自动化。
- **计划内容**：
  1. 设计主循环：选择窗口 → 定时截图 → OCR → 查缓存/翻译 → 显示覆盖层。
  2. 添加启停控制、热键支持。
  3. 异常捕获和日志记录。
  4. 资源释放（OCR 模型、窗口句柄等）。
- **实际完成**：
  - 新建 `src/app.py`，实现 `App` 主控制类。
  - `App.init()` 按配置初始化日志、OCR、翻译、缓存、覆盖层模块。
  - `App.select_window()` 弹出窗口选择对话框。
  - `App.start()` / `App.stop()` 控制翻译循环启停。
  - `App._process_frame()` 实现主循环：
    1. 调用 `WindowCapture.capture()` 截图；
    2. 调用 `PaddleOCREngine.recognize()` 识别文字；
    3. 对每段文字先查 `TranslationCache`，命中则直接使用；
    4. 未命中则调用 `Translator.translate()`，并将结果写入缓存；
    5. 调用 `OverlayWindow.update_translations()` 更新覆盖层。
  - 配置日志同时输出到控制台和 `data/cache/app.log`。
  - 翻译失败时回退显示原文，不影响后续帧处理。
  - 目标窗口无效时自动停止循环。
  - 更新 `src/main.py` 和 `run.py` 调用新的 `App` 入口。
  - 完成 `tests/test_app.py` 集成测试，覆盖初始化、缓存命中流程、缓存未命中流程、窗口无效停止、启停控制。
- **验证方式**：
  - 运行 `python -m pytest tests/test_app.py -v`，5 个测试全部通过。
  - 运行全部测试 `python -m pytest tests/ -v`，42 个测试全部通过。
  - 运行 `python -c "from src.app import App, main; print('import ok')"`，主程序导入正常。
  - 命令输出：
    ```
    5 passed in 2.31s
    42 passed, 1 warning in 22.78s
    import ok
    ```
- **对项目的意义**：
  - 所有独立模块首次串联成可运行的完整应用。
  - 实现了核心用户价值：选择游戏窗口后即可自动实时翻译画面文字。
  - 为后续 GUI 设置界面和系统托盘提供了控制入口。

---

### 步骤 8：配置与设置界面

- **时间**：2026-06-20
- **目的**：
  - 降低用户配置门槛，支持图形化调整参数。
  - 提供系统托盘入口，方便用户控制翻译启停和打开设置。
- **计划内容**：
  1. 使用 PyQt6 创建设置窗口。
  2. 支持配置翻译 API Key、目标语言、OCR 语言、截图间隔、显示样式。
  3. 配置修改后自动保存到 `config/settings.yaml`。
- **实际完成**：
  - 新建 `src/gui/` 目录，创建 `src/gui/settings_window.py`。
  - 实现 `SettingsWindow` 设置对话框，分组展示翻译、OCR、截图、覆盖层配置项。
  - 实现配置加载、保存到 `config/settings.yaml`。
  - 实现"测试翻译"按钮，调用当前配置测试翻译 API 连通性。
  - 在 `src/app.py` 中集成系统托盘：
    - 托盘右键菜单：显示主窗口、开始/停止翻译、退出；
    - 双击托盘图标打开主窗口。
  - 设置保存后自动重新加载配置并应用（覆盖层样式、截图间隔即时生效；OCR 语言/翻译提供者需重启生效）。
  - 完成 `tests/test_settings_window.py` 单元测试，覆盖配置加载、保存、翻译测试成功/失败场景。
- **验证方式**：
  - 运行 `python -m pytest tests/test_settings_window.py -v`，4 个测试全部通过。
  - 运行全部测试 `python -m pytest tests/ -v`，46 个测试全部通过。
  - 命令输出：
    ```
    4 passed in 0.64s
    46 passed, 1 warning in 53.63s
    ```
- **对项目的意义**：
  - 用户无需手动编辑 YAML 文件即可调整所有配置。
  - 系统托盘提供了不打扰游戏的控制入口。
  - 翻译 API 测试功能帮助用户快速排查连接问题。

---

### 步骤 9：测试与优化

- **时间**：进行中
- **目的**：
  - 提升系统稳定性和性能。
- **计划内容**：
  1. 为各模块补充单元测试和集成测试。
  2. 优化截图和 OCR 性能，降低 CPU/GPU 占用。
  3. 处理窗口最小化、切换、关闭等边界情况。
  4. 完善日志和错误提示。
- **实际完成**：
  - **GUI 主窗口重构**：
    - 新建 `src/gui/main_window.py`，实现持续可见的 `MainWindow` 主控制窗口。
    - 主窗口包含状态指示灯、目标窗口信息、截图间隔、开始/停止/选择窗口/设置/清空缓存等控制按钮。
    - 提供实时日志、最近识别文本表格（原文/译文/置信度）、缓存统计标签页。
    - ~~关闭主窗口时最小化到系统托盘~~ 改为关闭主窗口即退出程序，避免用户无法真正退出应用；托盘图标仍保留作为辅助控制入口。
    - 在 `src/app.py` 中集成主窗口：`App.init()` 创建并显示主窗口，翻译循环启停实时同步主窗口状态。
    - 托盘菜单"显示主窗口"与双击托盘图标均可唤起主窗口。
    - 调整 `App.run()` 启动流程：启动时仅显示主控制窗口，不再自动弹出窗口选择对话框，避免同时出现两个窗口；用户点击"选择窗口"或"开始翻译"后再进行选择。
    - 修复日志处理器在测试环境下导致 access violation 的问题：使用弱引用持有主窗口，窗口销毁或无 QApplication 时安全跳过日志发送。
    - 修复 `App.select_window()` 中未定义 `title` 变量的 bug。
    - 修复 `MainWindow.update_stats()` 对非标准统计值的兼容性。
  - **OCR 速度优化（第一轮）**：
    - 将 OCR 识别与翻译流程移到后台线程（`src/ocr/ocr_task.py`），主循环不再被阻塞。
    - 引入 `QThreadPool` 单线程队列，当上一帧 OCR 仍在处理时跳过本帧，避免任务堆积。
    - 将默认 `ocr.max_width` 从 800 降至 640，再降至 480，减少输入像素数。
    - 新增 `ocr.roi` 配置：支持按相对坐标 `[x, y, w, h]` 只 OCR 截图中的感兴趣区域（例如游戏对话框区域），默认使用屏幕下方 30%，大幅降低处理面积。
    - 提高默认 `ocr.det_db_thresh` 到 0.5、`ocr.drop_score` 到 0.7，过滤低置信度文本块，减少处理量。
    - 新增 `ocr.det_limit_side_len`（默认 480）限制文本检测最长边。
    - 默认截图间隔从 1000ms 调整为 5000ms，匹配"5 秒内一次翻译"目标，减少无效截图和跳帧。
    - OCR 区域改为"预设 + 自定义"模式：
      - 新增 `ocr.roi_preset` 配置，可选 `subtitle`（字幕/对话）、`bottom`（底部全宽）、`full`（全屏）、`custom`（自定义）。
      - 新增 `ocr.roi_custom` 保存自定义坐标。
      - 默认使用 `subtitle` 预设 `[0.1, 0.75, 0.8, 0.2]`，避开左右边缘 UI，专注底部字幕区。
      - 设置窗口提供下拉框选择预设，选择"自定义"时才启用坐标输入。
      - 新增 `tests/test_roi_preset.py` 验证预设解析。
    - 实现 `_init_ocr_for_preset()`：根据当前 ROI 预设自动切换 OCR 引擎参数，全屏模式下使用更高分辨率（1280）和更低阈值以提升召回。
    - 在主窗口状态栏显示最近一帧 OCR 耗时和跳过帧数，便于观察性能。
    - 设置窗口新增"OCR 引擎"、"OCR 最大宽度"、"检测最长边限制"、"OCR 区域 [x,y,w,h]"配置项。
    - 将 `run_ocr_pipeline()` 提取为可独立测试的同步函数，更新 `tests/test_app.py` 覆盖缓存命中/未命中和异步调度逻辑。
  - **OCR 速度优化（第二轮）**：
    - 新增 `src/ocr/rapid_ocr.py`，集成 RapidOCR（ONNXRuntime）作为默认 OCR 引擎。
    - RapidOCR 在 CPU 上通常比 PaddleOCR 快数倍，更适合实时字幕翻译场景。
    - 保留 PaddleOCR 作为可选引擎（`ocr.engine: paddle`），支持 GPU 加速。
    - 添加 GPU 可用性检测：配置使用 GPU 但环境不支持时自动回退 CPU 并记录警告。
    - 安装 `rapidocr-onnxruntime` 并更新 `requirements.txt`。
  - **悬浮日志窗口**：
    - 新增 `src/gui/log_overlay_window.py`，实现 `LogOverlayWindow`。
    - 窗口特性：无边框、置顶、半透明背景、可拖动、可右下角调整大小、右键菜单（清空/置顶/关闭）。
    - 固定屏幕位置显示，不跟随目标窗口，适合在全屏游戏/视频上调试。
    - 通过 `LogOverlayHandler` 将根日志重定向到悬浮窗口，线程安全。
    - `App` 提供 `show/hide/toggle_log_overlay()`，主窗口控制区新增"悬浮日志"切换按钮。
    - 新增 `log_overlay` 配置组：enabled、位置、大小、透明度、字体大小。
    - 设置窗口新增"悬浮日志窗口"配置组。
    - 新增 `tests/test_log_overlay_window.py` 覆盖基本功能。
  - **语言过滤与翻译质量控制**：
    - 新增 `src/translate/lang_filter.py`，提供 `should_translate()` 用于过滤非目标语言文本。
    - 默认启用 `translate.filter_source_lang: true`，只翻译属于源语言的文本。
    - 日文场景：包含假名或日文汉字的文本放行；URL、`www.`、`.com`、纯数字、明显英文 UI 等被过滤。
    - 在 `run_ocr_pipeline()` 中集成过滤，避免把网址、按钮文字送入翻译，减少无意义调用。
    - 设置窗口新增"只翻译源语言文本"复选框，用户可关闭过滤。
    - 新增 `tests/test_lang_filter.py` 覆盖语言识别、URL/数字过滤、日文汉字放行等场景。
  - 已完成对当前 Edge 浏览器日文页面的端到端真实场景测试：
    - 测试窗口：Microsoft Edge (hwnd=1509670)，页面为 Bilibili 日文页面。
    - 测试脚本：`tests/manual_edge_single_frame.py` 和 `tests/manual_edge_overlay_test.py`。
    - OCR 识别到 172~176 个文本块。
    - 覆盖层成功显示中文翻译文字，如"哔哩哔哩首页 动漫系列 直播游戏中心 界购漫画活动"、"我真的很喜欢下雨天"等。
    - 保存了测试截图：`tests/edge_test_output/single_frame_capture.png`、`overlay_display_test.png`。
    - 保存了翻译结果：`tests/edge_test_output/translation_results.txt`。
  - 发现的主要问题与优化进展：
    - **性能问题**：对 1920x1032 全屏页面 OCR 一帧耗时约 100 秒，无法满足实时需求。
      - 已通过后台线程 + 跳帧 + 降低默认分辨率 + ROI 裁剪 + 更高阈值 + RapidOCR 默认引擎显著改善：目标接近 5 秒/次翻译。
      - 若仍不满足，可继续：启用 GPU（PaddleOCR）、进一步缩小 ROI、降低分辨率到 320、使用商业 OCR API。
    - **误译非目标语言（URL/英文 UI）**：
      - 已通过源语言过滤解决：默认只翻译日文文本，URL 和英文按钮不再被翻译。
      - 用户可在设置中调整 OCR 区域以聚焦实际日文内容区域。
    - **翻译质量**：Google Translate 免费接口不稳定，部分中文/日文翻译结果不准确。
  - **自定义区域划分（新增功能）**：
    - 在保留原有"自定义（手动输入 [x,y,w,h]）"模式的前提下，新增 "自定义区域划分" ROI 模式。
    - 用户可通过全屏半透明遮罩在目标窗口截图上拖拽划定一个或多个矩形翻译区域。
    - 新增 `src/gui/zone_selector.py` 实现 `ZoneSelector` 区域拖拽选择器，支持 Enter 完成、Esc 取消、Ctrl+Z 撤销、Delete 清空。
    - 新增 `src/ocr/multi_zone_ocr_task.py` 实现 `MultiZoneOCRTask`，串行处理多个子区域 OCR+翻译，合并结果后统一回调。
    - 修改 `src/gui/settings_window.py`：ROI 预设下拉框新增"自定义区域划分"，选择后显示"划分区域"按钮和已划分区域数量，原有"自定义"输入框保持不变。
    - 修改 `src/app.py`：`_process_frame()` 识别 `custom_zones` 预设，按多个 ROI 裁剪并提交多区域任务；`_apply_config()` 将 `ocr.roi_zones` 同步到覆盖层。
    - 修改 `src/overlay/overlay_window.py`：在 `paintEvent()` 中先绘制半透明红色区域高亮框，让用户在翻译运行时"微微看到"翻译区域。
    - 新增 `ocr.roi_zones` 配置项，用于保存多区域相对坐标列表，并在 `config/settings.yaml` 中添加默认空列表。
    - 新增 `tests/test_zone_selector.py`、`tests/test_multi_zone_ocr_task.py`，并扩展 `tests/test_app.py` 覆盖 `custom_zones` 流程。
    - 优化区域划分体验：打开 `ZoneSelector` 前自动隐藏设置窗口和主窗口，避免本程序界面遮挡目标程序；延迟 300ms 截图确保目标窗口完全显示；选择完成后自动恢复本程序窗口。
    - 修复区域选择器不保存问题：将 `ZoneSelector` 改为继承 `QDialog` 并使用 `exec()`，避免手动 `QEventLoop` 不稳定；打开选择器前最小化而非隐藏设置/主窗口，保持合理的窗口层级关系。
    - 在 `save_config()` 和 `_apply_config()` 中添加异常捕获与错误提示，避免保存配置时直接闪退。
    - 修复测试污染默认配置的问题：`test_app.py` 中修改 `ocr.roi_preset` / `ocr.roi_zones` 的测试现在会在结束后恢复原始值。
  - **翻译质量与性能优化（新增）**：
    - 修复日文/中文误识别问题：新增 `translate.strict_source_lang` 严格过滤开关。开启时（默认），日文源语言下只翻译包含平假名/片假名的文本，避免把中文 UI 汉字误判为日文。
    - 实现批量翻译：`run_ocr_pipeline()` 把同一帧内所有待翻译原文用换行符拼接后一次性调用翻译 API，大幅减少网络请求次数；结果数量不匹配时自动回退到逐条翻译。
    - 优化默认 OCR 参数：`drop_score` 从 0.7 降到 0.55 提高召回，`max_width`/`det_limit_side_len` 从 480 提升到 640 提高精度。
    - 缩短默认截图间隔从 5000ms 到 3000ms，响应更快。
    - 覆盖层不再因空 OCR 结果立即清空，保留上一帧翻译直到识别到新文本，减少闪烁。
    - 在设置窗口添加“严格过滤”复选框。
- **验证方式**：
  - 真实 Edge 窗口测试：OCR 识别、翻译、覆盖层显示均正常工作。
  - 覆盖层截图 `overlay_display_test.png` 中可见大量中文覆盖文字。
- **对项目的意义**：
  - 验证了从截图到覆盖层显示的完整端到端流程在真实场景下可行。
  - 发现了性能瓶颈和翻译质量瓶颈，为后续优化提供了明确方向。

---

### 步骤 10：打包发布

- **时间**：待开始
- **目的**：
  - 让最终用户无需安装 Python 环境即可使用。
- **计划内容**：
  1. 安装 PyInstaller。
  2. 编写打包脚本或 spec 文件。
  3. 测试打包后的 exe 在干净环境中的运行情况。
  4. 编写发布说明。
- **实际完成**：待填写
- **验证方式**：待填写
- **对项目的意义**：待填写

---

## 当前状态

- **当前步骤**：步骤 9 进行中（自定义区域划分功能已实现）
- **下一步骤**：继续步骤 9 —— OCR 性能优化与翻译质量提升，或根据用户反馈优化区域选择器多显示器支持
- **已知问题/注意事项**：
  - 当前 Shell 中中文输出可能显示为乱码，系控制台编码问题，不影响程序逻辑。
  - PaddleOCR 较重，将在步骤 3 单独安装，未包含在基础依赖中。

---

## 附录：常用命令

```bash
# 激活虚拟环境（Windows bash）
.venv/Scripts/activate

# 安装依赖
python -m pip install -r requirements.txt

# 运行项目
python run.py

# 查看项目结构（排除 .venv）
find . -maxdepth 3 -type f ! -path './.venv/*' | sort
```
