# 迭代开发任务拆分

基于 `multi-timeframe-design.md` 设计文档，将完整方案拆分为 8 个可独立验证的迭代。

**原则**：
- 每个迭代有明确的完成标准（代码 + 测试通过）
- 每个迭代完成后，之前迭代的功能不退化
- 迭代之间有明确依赖关系，不可跨迭代并行开发
- 避免 Big Bang 重构，每次只改一个关注点

---

## 迭代 0 — 基线整固（前置条件） ✅ 已完成

> **目标**：修复已知 bug，清理死代码，消除代码重复，补充测试覆盖，拆分前端 JS 文件。为后续迭代提供安全网。

### 前置完成的工作

- ✅ 移除 `generate_random_zigzag` 和 `import random`（死代码清理）
- ✅ `_pop_segment_fallback` 复用 `_merge_same_direction`（消除重复）
- ✅ 后端 API 支持传入 `segments` 参数避免重复计算
- ✅ 新增 `/api/compute/recompute` 合并接口
- ✅ 前端 JS 拆分到 `static/app.js`，HTML 降至 291 行
- ✅ 40+ 全局变量重构为 `S` 状态对象
- ✅ 买卖点 `peak_set` 构造修复（改用奇偶索引）
- ✅ 买卖点 3 买/3 卖/2 买/2 卖增加 `has_continuation` 确认
- ✅ 买卖点搜索范围扩展到数据末尾
- ✅ `README.md` 项目文档

### 迭代 0 执行结果

**0-A ✅ 清理 algorithms.py 死代码**

删除 6 个无调用函数：`_strokes_overlap`、`_can_form_opposite_segment`、`_last_pair_ok`、`_remove_degenerate_segments`、`_find_vovs`、`_extremum_tracking`（包装函数，改为直接调用 `_extremum_tracking_core`）。

**0-B ✅ 修复 `removeStroke` 索引同步 bug**

在 `removeStroke()` 中增加了 `S.strokes` 的 `fromIdx`/`toIdx` 索引偏移处理，并清除 `S.buySellPoints` 和 `S.divergencePoints`。

**0-C ✅ 修复拖拽越界 bug**

在 mouseup 处理中对 `S.strokes[S.dragIdx]` 添加边界检查。

**0-D ✅ 补充 API 响应检查**

7 个 fetch 调用点添加 `resp.ok` 检查：`autoDetectSegments`、`autoDetectZhongshu`、`recomputeWithRatio`、`recomputeSegmentLevel`、`recomputeBuySell`、`autoDetectBuySell`、`exportJSON`。

**0-E ✅ 消除中枢检测代码重复**

提取 3 个通用函数：
- `_detect_zhongshu_in_units(units_high, units_low, start, end)` — 通用滑动窗口检测
- `_trim_and_merge_zhongshu(zs_list, unit_dir, container_dir)` — 通用方向裁剪 + 重叠合并
- `_detect_zhongshu_in_range()` 改为委托给通用函数

`compute_auto_zhongshu()` 和 `compute_segment_zhongshu()` 均改用通用函数。删除了 `_detect_seg_zhongshu_range()` 和 `_clean_seg_zhongshu_list()`（约 90 行）。

**0-F ✅ binance_service 单元测试**

新增 21 个测试覆盖 `binance_service.py`：
- `_has_inclusion`：5 个测试（完全包含、反向包含、相等、部分交叉、不包含）
- `merge_klines_with_inclusion`：6 个测试（上升合并、下降合并、连续包含、无包含、边界）
- `detect_fractals_from_klines`：5 个测试（顶分型、底分型、平坦序列、交替分型、边界）
- `fractals_to_turning_points`：5 个测试（基本 zigzag、同类型合并、间距过滤、zigzag 违规、空输入）

**0-G ✅ 加强中枢和买卖点测试**

- 中枢 ZG/ZD 精确值断言（验证 `min(笔高点)` 和 `max(笔低点)`）
- 中枢不跨越段边界断言
- 1 买/1 卖检测基本测试（向下/向上离开中枢）
- 买卖点索引范围和类型校验

### 测试统计

测试总数从 13 增加到 39，全部通过：
- `TestComputeAutoSegments`：8 个（快照 + 边界）
- `TestComputeAutoZhongshu`：2 个
- `TestZhongshuProperties`：2 个（新增）
- `TestBuySellPoints`：3 个（新增）
- `TestBuildStrokes`：2 个
- `TestSegmentZhongshu`：1 个
- `TestHasInclusion`：5 个（新增）
- `TestMergeKlines`：6 个（新增）
- `TestDetectFractals`：5 个（新增）
- `TestFractalsToTurningPoints`：5 个（新增）
- `TestPropertyBased`：1 个（200 轮随机数据）

---

## 迭代 1 — 双周期后端 + K 线缓存 ✅ 已完成

> **目标**：引入 SQLite 缓存减少 API 调用，实现周期配对逻辑，提取分析流水线为可复用函数，新增 `/api/compute/dual` 接口。

### 依赖
- 迭代 0 全部完成 ✅

### 迭代 1 执行结果

**1-A ✅ 创建 K 线缓存模块**

新建 `chanlun/kline_cache.py`：
- SQLite 数据库 `data/klines.db`，主键 `(symbol, interval, open_time)`
- `save_klines()` — INSERT OR REPLACE，跳过最后一根（未收盘）
- `get_cached_klines()` — 支持时间范围过滤
- `get_latest_cached_time()` — 返回最新缓存时间戳
- `.gitignore` 已添加 `data/`

**1-B ✅ 改造 fetch_klines 接入缓存**

在 `chanlun/binance_service.py` 新增 `fetch_klines_cached()`：
- 有缓存时：从 `latest_cached_time + 1ms` 开始只拉缺失部分，合并缓存+新数据
- 无缓存时：直接 fetch 全量，然后 save
- 有 `start_time`/`end_time` 时回退到直接 API 调用
- 保持原 `fetch_klines` 不变

**1-C ✅ 周期配对配置**

新建 `chanlun/config.py`：
- `INTERVAL_PAIRS` 字典（11 对配对，覆盖 1m→1w 全部常用周期）
- `get_context_interval(primary_interval)` 函数

**1-D ✅ 提取分析流水线**

新建 `chanlun/pipeline.py`：
- `analyze_klines(klines, min_kline_gap, min_segment_ratio)` — 完整流水线：K线→分型→转折点→笔→段→中枢→买卖点
- `recompute_from_turning_points(turning_points, min_segment_ratio)` — 从转折点重新计算段/中枢/买卖点
- `app.py` 的 `/api/compute/all` 和 `/api/compute/recompute` 改为调用 pipeline 函数（行为不变）

**1-E ✅ 实现 `/api/compute/dual`**

`app.py` 新增端点：
- 请求参数：`symbol, interval, contextInterval(可选), limit(=300), minKlineGap, minSegmentRatio`
- 自动通过 `get_context_interval()` 确定上下文周期
- 两个周期均走 `fetch_klines_cached` 缓存
- 上下文 K 线数量 = `max(50, limit // 4)`
- 返回 `{ primary: {..., interval}, context: {..., interval} | null }`

**1-F ✅ 新模块测试**

新建 `tests/test_kline_cache.py`（14 个测试）：
- `TestKlineCache`（8 个）：写入读取、跳过最后一根、重复覆盖、时间范围过滤、最新时间戳、增量写入、空写入
- `TestIntervalConfig`（3 个）：已知配对、未知返回 None、全部配对合法性
- `TestPipeline`（3 个）：返回结构完整性、转折点不足时的 warning、recompute 与 analyze 一致性

### 测试统计
总测试数 53（39 原有 + 14 新增），全部通过。

### 新增/修改文件

| 文件 | 操作 |
|------|------|
| `chanlun/kline_cache.py` | 新建 |
| `chanlun/config.py` | 新建 |
| `chanlun/pipeline.py` | 新建 |
| `chanlun/binance_service.py` | 新增 `fetch_klines_cached` |
| `app.py` | 重构 2 个端点 + 新增 `/api/compute/dual` |
| `.gitignore` | 添加 `data/` |
| `tests/test_kline_cache.py` | 新建 |

---

## 迭代 2 — 前端状态重构（只改结构，不改渲染） ✅ 已完成

> **目标**：将前端状态从扁平 `S` 结构拆为 `S.primary` / `S.context` 两层，切换到 `/api/compute/dual` 接口。**此迭代完成后，用户看到的功能与之前完全一致**（上下文数据已获取但不渲染）。

### 依赖
- 迭代 1 全部完成 ✅

### 迭代 2 执行结果

**2-A ✅ 状态对象拆分**

`static/app.js` 的 S 对象重构为两层：

- `S.primary`：11 个数据字段（klines, fractals, turningPoints, strokes, segments, zhongshuList, segmentZhongshu, higherSegments, buySellPoints, divergencePoints）
- `S.context`：5 个字段（klines, turningPoints, segments, zhongshu, interval）— 只读
- 顶层保留：currentSymbol, primaryInterval, contextInterval + 全部 UI 状态

全局替换 261 处引用：`S.turningPoints` → `S.primary.turningPoints` 等 11 个字段。`S.currentInterval` → `S.primaryInterval`。无残留旧引用。

**2-B ✅ resetUIState 拆分**

- `resetPrimary()`：清空分析数据和 UI 绘制状态，重设按钮状态
- `resetAll()`：清空 primary + context + 元数据，切换交易对时调用
- `resetUIState()` 保留为 `resetPrimary()` 的别名，向后兼容

**2-C ✅ 切换到 /api/compute/dual**

`loadBinanceKlines()` 改用 `/api/compute/dual`：
- 返回的 `primary` 写入 `S.primary`
- 返回的 `context` 写入 `S.context`
- 状态栏显示上下文周期信息（如 `· 上下文: 1h`）

**2-D ✅ 手动编辑功能不受影响**

全部手动操作（画段、画中枢、拖动转折点、删除笔等）只操作 `S.primary`，`S.context` 只读。

### 验证结果
- JS 语法检查通过（`node --check`）
- 53 个后端测试全部通过
- 无残留的旧 `S.xxx` 数据引用（grep 验证）

---

## 迭代 3 — 上下文周期渲染 ✅ 已完成

> **目标**：在主图上叠加显示上下文周期的段和中枢，实现时间轴对齐。

### 依赖
- 迭代 2 全部完成 ✅

### 迭代 3 执行结果

**3-A ✅ 时间轴对齐**

在 `drawChart()` 中通过上下文分型的 `klineIdx` 映射到上下文 K 线的 `openTime`，再用主周期的时间轴坐标函数 `ctxTimeToX(t)` 转换为像素坐标。超出视口范围的元素静默裁剪。

新增 `S.context.fractals` 字段存储上下文分型数据（含 `klineIdx`），`loadBinanceKlines` 中从 `/api/compute/dual` 的返回值写入。

**3-B ✅ 叠加渲染上下文段和中枢**

在 `drawChart()` 中主周期 Overlays 之前渲染上下文层（符合设计文档 5.1 视觉层级）：

| 元素 | 样式 |
|------|------|
| 段（上升） | `rgba(47,158,68,0.5)`，4px |
| 段（下降） | `rgba(201,42,42,0.5)`，4px |
| 中枢矩形 | `rgba(230,119,0,0.08)` 填充，`rgba(230,119,0,0.3)` 2px 边框 |
| 笔/分型 | 不显示 |

仅在 `klineMode` 且 `S.showContext` 开启时渲染。

**3-C ✅ 侧边栏上下文区块**

`templates/index.html` 新增 "上下文周期" 面板（`#contextPanel`）：
- 显示上下文周期名称（如 "1h"）
- 显示段数量、中枢数量
- 显示/隐藏按钮（调用 `toggleContext()`）
- 无上下文数据时自动隐藏

新增 `S.showContext` 状态标志，新增 `toggleContext()` 和 `updateContextPanel()` 函数。

**3-D ✅ 隐藏调试控件**

- `minSegRatio` 输入行添加 `display:none`（值仍保留，`getMinSegmentRatio()` 仍可用）
- `binanceCount` 输入框添加 `display:none`，默认值改为 300

### 验证结果
- JS 语法检查通过
- HTML 解析通过
- 53 个后端测试全部通过
- 上下文元素使用独立 CSS class（`ctx-seg-line`、`ctx-zs-rect`），`clearSVG` 自动清理
- 切换交易对/周期后上下文数据正确更新

---

## 迭代 4 — 数据持久化（标注存档） ✅ 已完成

> **目标**：实现用户标注的本地保存和恢复，解决刷新后手动编辑丢失的问题。

### 依赖
- 迭代 2 全部完成 ✅

### 迭代 4 执行结果

**4-A ✅ 标注存储接口**

新建 `chanlun/annotation_store.py`：
- 存储路径：`data/annotations/{symbol}_{interval}.json`
- `save_annotation(symbol, interval, data)` — 自动创建目录，写入 JSON
- `load_annotation(symbol, interval)` — 文件不存在返回 None
- `clear_annotation(symbol, interval)` — 删除标注文件，不存在不报错

**4-B ✅ 后端标注 API**

`app.py` 新增 3 个端点：
- `POST /api/annotation/save` — 接收标注 JSON 写入文件
- `GET /api/annotation/load?symbol=X&interval=Y` — 返回已保存标注
- `DELETE /api/annotation/clear?symbol=X&interval=Y` — 删除标注文件

**4-C ✅ 前端自动保存与恢复**

新增函数：
- `autoSaveAnnotation()` — debounce 2 秒后保存，存储 turningPoints/segments/zhongshu/segmentZhongshu/higherSegments/deletedTurningPoints
- `loadSavedAnnotation()` — 加载 K 线后自动调用，校验索引范围后恢复标注
- `drawChartAndSave()` — 编辑操作的便捷包装（drawChart + autoSave）
- `clearSavedAnnotation()` — 清除已保存标注

触发时机：
- `loadBinanceKlines` 中 `drawChart` 后自动恢复标注
- `removeStroke`、`undoStrokeDraw`、`undoSegment`、`removeSegment`、`undoZhongshu`、`removeZhongshu`、`undoSegZs`、`removeSegZs`、`undoHigher`、`removeHigher` 后自动保存
- `autoDetectSegments`、`autoDetectZhongshu`、`recomputeWithRatio` 后自动保存
- `clearAll` 时清除标注

侧边栏新增"清除已保存标注"按钮。

**4-D ✅ 测试**

新建 `tests/test_annotation_store.py`（8 个测试）：
- 写入读取、不存在返回 None、覆盖更新
- 清除后返回 None、清除不存在不报错
- 目录自动创建、不同交易对隔离、JSON 格式验证

### 测试统计
总测试数 61（39 + 14 + 8），全部通过。

### 新增/修改文件

| 文件 | 操作 |
|------|------|
| `chanlun/annotation_store.py` | 新建 |
| `app.py` | 新增 3 个标注 API 端点 |
| `static/app.js` | 新增自动保存/恢复逻辑 |
| `templates/index.html` | 新增"清除已保存标注"按钮 |
| `tests/test_annotation_store.py` | 新建 |

---

## 迭代 5 — MACD 背驰移到后端 ✅

> **目标**：将 MACD 计算和背驰检测从前端移到后端，成为买卖点信号的置信度字段。

### 依赖
- 迭代 1 全部完成（需要 `pipeline.py`）

### 任务

**5-A：后端 MACD 计算** ✅

文件：`chanlun/indicators.py`（新建）

- `compute_macd(closes, fast=12, slow=26, signal=9) → { dif, dea, histogram }`
- `compute_macd_area(histogram, from_idx, to_idx) → float`

**5-B：背驰检测** ✅

文件：`chanlun/indicators.py`

- `detect_divergences(klines, turning_points, fractals, buy_sell_points) → [{ type, idx, compareIdx, klineIdx, compareKlineIdx }]`
- 逻辑与现有前端 `detectDivergences()` 完全一致

**5-C：集成到 pipeline** ✅

- `analyze_klines` 返回结果新增 `macd` 和 `divergences` 字段
- 买卖点对象新增 `hasDivergence` 布尔字段
- `recompute_from_turning_points` 返回 `divergences: []`（无 K 线无法算 MACD）

**5-D：前端适配** ✅

- 删除 `app.js` 中的 `ema()`、`computeMACD()`、`detectDivergences()` 函数（约 115 行）
- `drawMACDPanel()` 改用 `S.primary.macd` 后端数据
- `renderBsList()` 和 `drawBuySellMarkers()` 改用 `hasDivergence` 字段
- `loadBinanceKlines()` 存储 `macd` 和 `divergences`
- `resetPrimary()` / `clearAll()` / `removeStroke()` 清理 `macd` 和 `divergencePoints`

**5-E：测试** ✅

- `tests/test_indicators.py`：19 个测试全部通过
  - TestComputeMACD: 8 个（空输入、单值、长度、公式验证、常量收敛、趋势方向、自定义参数）
  - TestComputeMACDArea: 4 个（基本面积、反向索引、单元素、全零）
  - TestDetectDivergences: 4 个（空输入、无买卖点、返回格式、顶背驰格式）
  - TestPipelineIntegration: 3 个（macd 字段、divergences 字段、hasDivergence 标记）

### 完成标准
- ✅ MACD 面板渲染与之前视觉一致（drawMACDPanel 使用后端数据，渲染逻辑不变）
- ✅ 背驰标记渲染正确（后端 detect_divergences 逻辑与前端一致）
- ✅ 前端减少约 115 行代码（ema + computeMACD + detectDivergences 删除）
- ✅ 全部 80 个测试通过

### 新建/修改文件
| 文件 | 操作 |
|------|------|
| `chanlun/indicators.py` | 新建（compute_macd, compute_macd_area, detect_divergences） |
| `chanlun/pipeline.py` | 修改（新增 macd/divergences 字段、import indicators） |
| `static/app.js` | 修改（删除前端 MACD/背驰函数，改用后端数据） |
| `tests/test_indicators.py` | 新建（19 个测试） |

---

## 迭代 6 — 信号引擎与交易状态面板 ✅

> **目标**：实现区间套状态机 + 信号面板，为交易决策提供计算核心。

### 依赖
- 迭代 3（上下文渲染）和迭代 5（背驰字段）全部完成

### 任务

**6-A：信号引擎** ✅

文件：`chanlun/signal.py`（新建）

- `compute_signal(primary_result, context_result) → dict`
- 纯函数，无外部状态
- 输出：`direction`（long/short/neutral）、`state`（IDLE/WATCHING/CONFIRMING/READY）、`activeSetup`
- 状态逻辑：
  - IDLE → 无上下文或方向为 neutral
  - WATCHING → 上下文方向明确 + 主周期出现中枢
  - CONFIRMING → 匹配方向的买卖点已出现（无背驰）
  - READY → 买卖点 + 背驰确认
- 失效条件：上下文价格突破中枢 ZG/ZD → IDLE，上下文段方向反转 → IDLE

**6-B：信号接口** ✅

文件：`app.py`

- `POST /api/signal`：接受 symbol, interval，内部调用 dual 逻辑 + compute_signal()
- 自动推导上下文周期，支持 contextInterval 参数覆盖

**6-C：交易状态面板** ✅

文件：`static/app.js` + `templates/index.html`

- 图表右侧新增 220px 固定信号面板
- 显示：方向箭头+标签（↑做多绿/↓做空红/–震荡灰）、状态标签（四色）、上下文/中枢/买卖点检查项、activeSetup 详情（价格+背驰标记）
- 手动刷新按钮，加载K线后自动刷新
- clearAll 时重置面板

**6-D：测试** ✅

- `tests/test_signal.py`：18 个测试全部通过
  - TestContextDirection: 3 个（无段neutral、上升段long、下降段short）
  - TestStateTransitions: 7 个（无上下文IDLE、context neutral IDLE、WATCHING×2、CONFIRMING、READY、short READY）
  - TestInvalidation: 3 个（方向反转、做多价格破ZD、做空价格破ZG）
  - TestSymmetry: 2 个（做多做空对称、反向买卖点不匹配）
  - TestResultFields: 3 个（完整字段、计数准确、价格正确）

### 完成标准
- ✅ 信号面板正确渲染四个状态（IDLE/WATCHING/CONFIRMING/READY）
- ✅ 做多/做空方向对称触发（TestSymmetry 验证）
- ✅ 不破坏任何已有图表和编辑功能（98 个测试全部通过）

### 新建/修改文件
| 文件 | 操作 |
|------|------|
| `chanlun/signal.py` | 新建（compute_signal 纯函数） |
| `app.py` | 修改（新增 /api/signal 端点） |
| `static/app.js` | 修改（refreshSignal, renderSignalPanel, clearAll 重置） |
| `templates/index.html` | 修改（信号面板 HTML + CSS） |
| `tests/test_signal.py` | 新建（18 个测试） |

---

## 迭代 7 — 轮询与多标的监控 ✅

> **目标**：自动轮询和多标的并行监控，完成平台最终形态。

### 依赖
- 迭代 6 全部完成

### 任务

**7-A：自适应轮询频率** ✅

文件：`chanlun/config.py`

- 新增 `POLL_INTERVALS` 字典（覆盖全部 15 个 Binance 合法周期）
- 新增 `get_poll_interval(interval)` 函数
- 新增 `GET /api/config/poll-interval?interval=X` 端点

| 操作周期 | 轮询间隔 |
|---------|---------|
| 1m–15m  | 30 秒   |
| 30m–1h  | 60 秒   |
| 2h–1M   | 300 秒  |

**7-B：前端自动轮询** ✅

- 信号面板新增"自动刷新/停止刷新"切换按钮
- 开启时从 `/api/config/poll-interval` 获取间隔，setInterval 调用 refreshSignal
- 切换交易对/周期时自动重启定时器
- 状态变化时面板黄色闪烁动画
- clearAll 停止并重置
- `S.autoRefresh`、`S.autoRefreshTimer`、`S.lastSignalState` 新增状态

**7-C：多标的监控列表** ✅

- 侧边栏底部新增监控面板（localStorage 持久化列表）
- 输入框 + 添加按钮管理标的
- 每个条目显示：symbol、方向箭头、状态缩写
- 点击条目切换主图表（自动填入 symbol 并加载）
- 显示/隐藏开关
- 每 60 秒自动轮询（仅面板可见时）
- 轮询使用 `/api/signal`（走 K 线缓存，不重复拉网）

**7-D：测试** ✅

- `test_kline_cache.py` 新增 `TestPollInterval` 类（4 个测试）
  - 已知周期返回正确间隔
  - 未知周期返回默认 60 秒
  - 所有 Binance 合法周期都有配置
  - 间隔在 10-600 秒合理范围

### 完成标准
- ✅ 自动轮询按配置频率工作（30s/60s/300s 三档）
- ✅ 不超出 Binance API 频率限制（走缓存 + 合理间隔）
- ✅ 全部 102 个测试通过

### 新建/修改文件
| 文件 | 操作 |
|------|------|
| `chanlun/config.py` | 修改（新增 POLL_INTERVALS、get_poll_interval） |
| `app.py` | 修改（新增 /api/config/poll-interval 端点） |
| `static/app.js` | 修改（自动轮询、监控列表、状态动画） |
| `templates/index.html` | 修改（自动刷新按钮、监控面板 HTML+CSS） |
| `tests/test_kline_cache.py` | 修改（新增 TestPollInterval 4 个测试） |

---

## 迭代依赖图

```
迭代 0（基线整固：bug修复 + 死代码 + 测试 + 消除重复）
    │
迭代 1（双周期后端 + K线缓存 + 流水线提取）
    │
迭代 2（前端状态重构：S.primary/S.context，只改结构不改渲染）
    │
    ├── 迭代 3（上下文周期渲染叠加）
    │
    ├── 迭代 4（标注持久化）  ← 可与 3 并行
    │
    └── 迭代 5（MACD 背驰后移） ← 可与 3/4 并行
            │
         迭代 6（信号引擎 + 交易状态面板）
            │
         迭代 7（轮询 + 多标的监控）
```

迭代 3、4、5 理论上无相互依赖（都只依赖迭代 2），但建议按 3→4→5 的顺序执行，因为：
- 迭代 3 的可视化结果可以验证双周期结构是否合理
- 迭代 4 的标注持久化保证手动编辑不丢失（高频使用场景）
- 迭代 5 的背驰后移为迭代 6 准备数据

---

## 各迭代测试文件索引

| 迭代 | 新增/修改测试文件 |
|------|----------------|
| 0    | `tests/test_algorithms.py`（39 个测试，含 binance_service + 中枢 + 买卖点） |
| 1    | `tests/test_kline_cache.py`（14 个测试：缓存+配置+流水线） |
| 2    | JS 语法检查 + grep 验证无残留旧引用（前端重构，后端无变化） |
| 3    | 手动 checklist（前端渲染验证） |
| 4    | `tests/test_annotation_store.py`（8 个测试：读写/覆盖/清除/隔离/JSON 格式） |
| 5    | `tests/test_indicators.py`（新建） |
| 6    | `tests/test_signal.py`（新建） |
| 7    | 集成测试 / 手动验证 |

---

## 与 multi-timeframe-design.md 的阶段映射

| 设计文档阶段 | 对应迭代 | 说明 |
|------------|---------|------|
| 阶段一：算法修复 | 迭代 0（部分） | 峰值条件移出，见下方说明 |
| 阶段二：数据持久化 | 迭代 1（K线缓存）+ 迭代 4（标注持久化） | 拆分为两个迭代 |
| 阶段三：双周期后端 | 迭代 1 | 合并 K 线缓存和双周期 API |
| 阶段四：前端状态重构 | 迭代 2 | |
| 阶段五：上下文渲染 | 迭代 3 | |
| 阶段六：买卖点修复 | 迭代 5（背驰部分） | 买卖点搜索边界已在之前修复 |
| 阶段七：三栏联动 | 迭代 6 | |
| 阶段八：状态面板 | 迭代 6 + 迭代 7 | |

---

## 关于"峰值条件"的说明

设计文档 2.2 节要求"补充高点验证逻辑"，但实际测试表明：

- 贪心扫描器的端点选择完全基于 `_is_segment_formed` 的返回值
- 峰值条件（无论严格还是宽松）都会改变哪些端点被视为"有效"，导致级联变化
- BTC 15m 数据：纯谷值条件 → 9 段（正确），加任意峰值条件 → 8 段或更少

原因：段检测算法是围绕谷值条件整体校准的，峰值条件不是简单的"加一个 check"，而是需要重新设计端点选择策略。

**建议**：将峰值条件作为后续独立研究课题，不纳入当前迭代。当前纯谷值方案已在 BTC 多周期数据上验证正确。

---

## 不在本次迭代范围内的内容

- **峰值条件补充**：需独立研究，不阻塞其他迭代
- **三周期（triple）模式**：设计文档中提及，属于迭代 7 之后的扩展
- **特征序列段终结检测**：当前用贪心扫描，未实现缠论严格定义
- **前端主题和移动端适配**
