# AutoOCRTranslator 架构设计文档

> 版本：v0.1.0  
> 状态：已确认

---

## 1. 整体架构

AutoOCRTranslator 采用**模块化、分层**架构，各模块职责单一，通过主控制流程串联。

```
┌─────────────────────────────────────────────────────────────┐
│                        用户交互层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   主控制面板  │  │   设置窗口   │  │   系统托盘   │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          └─────────────────┴─────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                        主控制流程                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  启动 → 加载配置 → 选择窗口 → 定时循环（截图→OCR→翻译→显示）│   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   窗口捕获模块    │ │   OCR 模块       │ │   翻译模块       │
│  WindowCapture  │ │  PaddleOCREngine│ │  Translator     │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                       缓存模块                            │
│                  TranslationCache (SQLite)              │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                      覆盖层模块                          │
│                 OverlayWindow (PyQt6)                   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 模块划分

### 2.1 配置模块 `src/config.py`

- **职责**：加载、保存、访问 YAML 配置文件。
- **核心类**：`AppConfig`
- **接口**：
  - `load()`：从文件加载配置。
  - `save()`：保存配置到文件。
  - `get(key, default)`：使用点号键读取配置，如 `capture.interval_ms`。
  - `set(key, value)`：使用点号键设置配置。

### 2.2 窗口捕获模块 `src/capture/`

- **职责**：枚举窗口、选择窗口、截取窗口客户区图像。
- **核心类**：`WindowCapture`
- **接口**：
  - `list_windows()`：返回可见窗口列表 `[(hwnd, title)]`。
  - `find_window(keyword)`：根据标题关键词查找窗口。
  - `set_target(hwnd)`：设置目标窗口。
  - `capture()`：截取目标窗口客户区，返回 `PIL.Image`。
  - `is_valid()`：检查目标窗口是否仍有效。

### 2.3 OCR 模块 `src/ocr/`

- **职责**：识别图像中的文字内容及位置。
- **核心类**：`PaddleOCREngine`
- **接口**：
  - `__init__(lang, use_gpu, **kwargs)`：初始化 OCR 引擎。
  - `recognize(image)`：输入 `PIL.Image`，返回识别结果列表。
  - 返回结果格式：`[{ "text": str, "box": [(x1,y1), (x2,y2), (x3,y3), (x4,y4)], "score": float }]`

### 2.4 翻译模块 `src/translate/`

- **职责**：将原文翻译为目标语言。
- **核心类**：`Translator`（工厂），`GoogleFreeProvider`（默认实现），`TranslationProvider`（接口）
- **接口**：
  - `translate(text, source_lang, target_lang) -> str`：返回译文。
  - `test()`：测试翻译服务连通性。
- **扩展**：新增翻译源只需实现 `TranslationProvider` 接口并注册。

### 2.5 缓存模块 `src/cache/`

- **职责**：存储翻译结果，避免重复调用 API。
- **核心类**：`TranslationCache`
- **接口**：
  - `get(text, source_lang, target_lang) -> str | None`：查询缓存。
  - `set(text, source_lang, target_lang, translation)`：写入缓存。
  - `clear()`：清空缓存。
  - `cleanup_expired(ttl_days)`：清理过期缓存。
- **数据表结构**：
  ```sql
  CREATE TABLE translations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_text TEXT NOT NULL,
      source_lang TEXT NOT NULL,
      target_lang TEXT NOT NULL,
      translation TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      hit_count INTEGER DEFAULT 0,
      UNIQUE(source_text, source_lang, target_lang)
  );
  CREATE INDEX idx_translation_lookup
  ON translations(source_text, source_lang, target_lang);
  ```

### 2.6 覆盖层模块 `src/overlay/`

- **职责**：将译文以覆盖层形式显示在游戏画面上。
- **核心类**：`OverlayWindow`
- **接口**：
  - `update_translations(items)`：更新要显示的译文列表。
  - `show()` / `hide()`：显示/隐藏覆盖层。
  - `set_target_window(hwnd)`：绑定目标窗口以跟随移动。
  - `apply_style(font, size, color, bg_color)`：应用显示样式。

### 2.7 主程序 `src/main.py`

- **职责**：组合所有模块，驱动主循环。
- **核心类**：`App`
- **流程**：
  1. 加载配置。
  2. 初始化 OCR、翻译、缓存、覆盖层。
  3. 选择目标窗口。
  4. 启动定时器，循环执行：
     - 截图
     - OCR 识别
     - 对每段文字：
       - 查缓存，命中则使用缓存译文。
       - 未命中则调用翻译 API，并将结果写入缓存。
     - 更新覆盖层显示。
  5. 处理退出、暂停、热键等事件。

---

## 3. 数据流

```
游戏窗口画面
    │
    ▼
[WindowCapture.capture()] ──▶ PIL.Image
    │
    ▼
[PaddleOCREngine.recognize()] ──▶ 文本块列表 [{text, box, score}]
    │
    ▼
对每段文本：
    │
    ├── 查询 [TranslationCache.get()] ──▶ 命中：返回缓存译文
    │                                    未命中：调用翻译 API
    │                                          │
    │                                          ▼
    │                              [Translator.translate()]
    │                                          │
    │                                          ▼
    │                              [TranslationCache.set()]
    │                                          │
    ▼                                          ▼
[OverlayWindow.update_translations()] ◀── 译文 + 坐标
    │
    ▼
屏幕覆盖层显示
```

---

## 4. 接口约定

### 4.1 OCR 输出格式

```python
OCRResult = Dict[str, Any]
# {
#     "text": "こんにちは",
#     "box": [(x1, y1), (x2, y2), (x3, y3), (x4, y4)],
#     "score": 0.95
# }
```

### 4.2 翻译项格式

```python
TranslationItem = Dict[str, Any]
# {
#     "original": "こんにちは",
#     "translated": "你好",
#     "box": [(x1, y1), (x2, y2), (x3, y3), (x4, y4)],
#     "source_lang": "ja",
#     "target_lang": "zh-CN"
# }
```

### 4.3 窗口信息格式

```python
WindowInfo = Tuple[int, str]
# (hwnd, title)
```

---

## 5. 配置结构

配置文件路径：`config/settings.yaml`

```yaml
app:
  name: "AutoOCRTranslator"
  version: "0.1.0"

capture:
  interval_ms: 1000
  target_window_title: ""

ocr:
  lang: "japan"
  use_gpu: false
  det_db_thresh: 0.3
  drop_score: 0.5

translate:
  provider: "google_free"
  source_lang: "ja"
  target_lang: "zh-CN"
  api_key: ""
  api_secret: ""

cache:
  enabled: true
  db_path: "data/cache/translations.db"
  ttl_days: 30

overlay:
  font_family: "Microsoft YaHei"
  font_size: 18
  font_color: "#FFFFFF"
  bg_color: "#80000000"
  border_color: "#FF000000"
  max_width: 400
```

---

## 6. 错误处理策略

| 模块 | 可能的错误 | 处理方式 |
|------|-----------|----------|
| 配置加载 | 配置文件缺失或格式错误 | 使用默认配置并提示用户 |
| 窗口捕获 | 目标窗口关闭或最小化 | 跳过本轮，记录日志，提示用户重新选择 |
| OCR | 模型加载失败 | 程序启动时检查，失败则退出并提示 |
| 翻译 | API 调用失败/限流 | 返回原文或空字符串，记录日志，下次重试 |
| 缓存 | 数据库损坏 | 尝试重建数据库，失败则禁用缓存 |
| 覆盖层 | 窗口创建失败 | 提示用户，退出程序 |

---

## 7. 日志策略

- 使用 Python 标准库 `logging`。
- 日志级别：DEBUG / INFO / WARNING / ERROR。
- 日志输出：控制台 + 文件（`data/cache/app.log`）。
- 关键事件必须记录：
  - 程序启动/退出
  - 窗口选择/丢失
  - OCR/翻译失败
  - 缓存命中/未命中

---

## 8. 性能考虑

- **截图频率可配置**：默认 1 秒/帧，避免过高 CPU 占用。
- **OCR 异步化**：后续可将 OCR 放在独立线程，避免阻塞主界面。
- **缓存优先**：重复文本不调用翻译 API。
- **增量更新**：仅当画面文字变化时更新覆盖层。
- **模型预热**：程序启动时预加载 OCR 模型，避免首次识别卡顿。

---

## 9. 测试策略

- **单元测试**：针对配置、缓存、翻译提供者编写测试。
- **集成测试**：验证截图 → OCR → 翻译 → 显示的完整流程。
- **手动测试**：在真实游戏窗口上测试覆盖层效果。
- **性能测试**：监控 CPU/内存占用，优化截图和 OCR 频率。
