# 缠论可视化分析工具 (chanlun-lab)

基于缠论（缠中说禅理论）的实时 K 线分析工具，支持从 Binance 获取加密货币 K 线数据，自动检测分型、笔、段、中枢和买卖点，并提供交互式 SVG 图表标注。

## 项目结构

```
chanlun/
  app.py                      # Flask 后端 API
  chanlun/
    algorithms.py              # 缠论核心算法
    binance_service.py         # Binance K线获取 + 分型检测
  static/
    app.js                     # 前端 SVG 图表渲染与交互
  templates/
    index.html                 # 单页 HTML 界面
  tests/
    test_algorithms.py         # 核心算法单元测试
```

## 数据处理流水线

```
Binance K线 API
  │
  ▼
fetch_klines()                   原始 K 线数据
  │
  ▼
merge_klines_with_inclusion()    处理包含关系 → 合并后 K 线
  │
  ▼
detect_fractals_from_klines()    检测顶底分型
  │
  ▼
fractals_to_turning_points()     筛选转折点 → zigzag 价格序列
  │
  ▼
build_strokes()                  构建笔列表
  │
  ▼
compute_auto_segments()          段检测（贪心扫描 + PoP 回退）
  │
  ├──► compute_auto_zhongshu()         笔中枢
  │         │
  │         └──► compute_buy_sell_points()   1/2/3 类买卖点
  │
  └──► compute_higher_segments()       更高级别段（递归）
          │
          └──► compute_segment_zhongshu()    段中枢
```

---

## 缠论概念与实现对照

### 1. K 线包含关系处理

**缠论定义**：相邻两根 K 线，如果一根的高低点完全包含另一根，则需按趋势方向合并。

**实现** (`binance_service.py: merge_klines_with_inclusion`)

```
原始:    ┃ ┃       (包含关系)
         ┃ ┃
合并后:  ┃   ┃     (取趋势方向的极值)
```

- **上升趋势**中（前高 > 更前高）：向上合并，取 `max(high)` + `max(low)`
- **下降趋势**中（前低 < 更前低）：向下合并，取 `min(high)` + `min(low)`
- 合并后保留 `highIdx` / `lowIdx`，追踪极值价格来自哪根原始 K 线（用于分型精确定位）

### 2. 分型检测

**缠论定义**：三根 K 线的中间那根，高点最高为顶分型，低点最低为底分型。相邻分型不能共用 K 线。

**实现** (`binance_service.py: detect_fractals_from_klines`)

在包含关系处理后的 K 线序列上检测：

```
顶分型:         底分型:
  O               O
 O O             O O
O                 O
```

- 顶分型：`k[i].high > k[i-1].high` 且 `k[i].high > k[i+1].high`
- 底分型：`k[i].low < k[i-1].low` 且 `k[i].low < k[i+1].low`
- 同时满足时，比较间隙大小决定归属

### 3. 笔的构建

**缠论定义**：顶底分型之间连成的线段为一笔。相邻两分型间至少间隔 5 根 K 线（含分型本身）。笔必须严格交替上下。

**实现** (`binance_service.py: fractals_to_turning_points`)

采用贪心 zigzag 算法，逐个处理分型：

1. **同类型分型**（连续两个顶或两个底）：保留更极端的值
2. **不同类型分型**：检查间距 ≥ `min_kline_gap`（默认 4，即 5 根 K 线间隔），再检查 zigzag 约束（顶必须高于前底，底必须低于前顶）

```python
# 间距约束：相邻分型间至少隔 min_kline_gap 根 K 线
gap = abs(f["klineIdx"] - prev["klineIdx"]) - 1
if gap < min_kline_gap:
    continue

# zigzag 约束：顶高于前底，底低于前顶
if prev["type"] == "bottom" and f["price"] <= prev["price"]:
    continue  # 顶不够高，跳过
```

### 4. 线段检测

**缠论定义**：
- 至少连续 3 笔出现更高的高点 + 更高的低点（向上段），或更低的高点 + 更低的低点（向下段）
- 线段只能被线段破坏
- 第一笔决定段的方向，笔数必须为奇数

**实现** (`algorithms.py: compute_auto_segments`)

采用两阶段策略：

#### 阶段一：贪心扫描 (`_scan_segments`)

从起始位置向前扫描，对每个候选段端点验证趋势条件：

**向上段趋势条件** (`_higher_high_higher_low`)：
- 所有谷值（支撑位）严格递增 — 不允许任何谷值下降

**向下段趋势条件** (`_lower_high_lower_low`)：
- 谷值整体下移，3 笔段必须严格递减，5 笔以上允许 1 次小幅反弹

端点选择策略：
1. 在所有满足趋势条件的端点中，选择能让**反向段最短闭合**的端点
2. 同分时选择**更极端**的端点（上升选更高峰，下降选更低谷）

```
候选端点: A(5笔) B(7笔) C(9笔)
          │      │      │
          ▼      ▼      ▼
反向段:   3笔    3笔    5笔   ← 选 B，反向段最短
```

**起始点重试**：如果从 TP[0] 扫描无结果，自动从 TP[1] 重试。

#### 阶段二：PoP 回退 (`_pop_segment_fallback`)

仅当主算法完全失败时启用：
1. 从转折点中提取峰之峰（PoP）— 峰序列中的局部极大值
2. 在相邻 PoP 之间插值谷值
3. 合并同方向段，过滤幅度过小的段

### 5. 中枢检测

**缠论定义**：某级别走势类型中，被至少三个连续次级别走势类型所重叠的部分。上升段中的中枢起始于下、终结于下；下降段反之。

**实现** (`algorithms.py: compute_auto_zhongshu`)

在每个段的**内部笔**（排除首尾笔）中检测：

```
向上段中的中枢：
  笔1 ↗  笔2 ↘  笔3 ↗  笔4 ↘  笔5 ↗
          │      │      │
          └──────┼──────┘
                 中枢
         ZD ← 高中取低 → ZG
```

- **ZG**（中枢高）= 重叠笔的高点中的最低点
- **ZD**（中枢低）= 重叠笔的低点中的最高点
- ZG > ZD 时中枢成立
- 中枢可向前延伸，只要新笔仍与 ZG/ZD 重叠
- **方向约束裁剪**：上升段中中枢的首尾笔必须是下降笔

**段中枢** (`compute_segment_zhongshu`)：同样的逻辑递归应用于段级别 — 将段视为"笔"，在高级别段中寻找重叠。

### 6. 更高级别段

**实现** (`algorithms.py: compute_higher_segments`)

将段端点价格提取为新转折点序列，递归调用 `compute_auto_segments`，结果映射回原始转折点索引。

```
原始转折点: ● ● ● ● ● ● ● ● ● ● ● ●
段:         [━━━━━━━][━━━━][━━━━━━━━]
段端点:     ●         ●    ●         ●
高级别段:   [━━━━━━━━━━━━━━━━━━━━━━]
```

### 7. 买卖点检测

**缠论定义**：
- **1 买/1 卖**：价格离开中枢的第一类买卖点
- **2 买/2 卖**：离开后回调不破前低/前高的第二类买卖点
- **3 买/3 卖**：回踩中枢边沿确认的第三类买卖点

**实现** (`algorithms.py: compute_buy_sell_points`)

峰谷识别：转折点序列本身交替，根据第一笔方向确定奇偶索引的峰谷归属。

```
价格 ↑
      │     ● 1卖
   ZG ┤----╳────────
      │   ╱ │  ╲
   ZD ┤──╳───│───╳───
      │ ╱  3买  ╲ │
      │╱         ╲│
      ● 1买        ● 2买
      │
价格 ↓
```

检测流程：
1. 确定离开方向（第一个穿越 ZG 的峰 → 向上离开，或第一个穿越 ZD 的谷 → 向下离开）
2. **向下离开**：标注 1 买 → 寻找 3 卖（回弹不破 ZD）和 2 买（更高低点）
3. **向上离开**：标注 1 卖 → 寻找 3 买（回踩不破 ZG）和 2 卖（更低高点）
4. 每个买卖点需要 `has_continuation` 确认后续走势方向一致

### 8. MACD 与背驰检测

**实现** (`static/app.js: computeMACD, detectDivergences`)

前端计算 MACD（12/26/9 参数）并检测价格与 MACD 的背驰：

- **顶背驰**：价格创新高但 MACD 柱状面积缩小
- **底背驰**：价格创新低但 MACD 柱状面积缩小

---

## API 接口

| 接口 | 说明 |
|------|------|
| `POST /api/compute/strokes` | K 线 → 分型 → 转折点 → 笔 |
| `POST /api/compute/segments` | 转折点 → 段 |
| `POST /api/compute/zhongshu` | 转折点 → 笔中枢 |
| `POST /api/compute/segment-level` | 段中枢 + 高级别段 |
| `POST /api/compute/buy-sell` | 买卖点检测 |
| `POST /api/compute/recompute` | 一次返回段+中枢+高级别段+段中枢+买卖点 |
| `POST /api/compute/all` | 完整流水线：Binance K 线 → 全部结果 |
| `POST /api/compute/manual-zhongshu` | 手动选范围计算 ZG/ZD |
| `POST /api/compute/export` | 导出标注 JSON |

所有接口支持 `segments` 参数传入已计算的段，避免重复计算。

---

## 快速开始

```bash
pip install flask requests
python app.py
```

打开 `http://localhost:5000`，输入交易对（如 BTCUSDT），选择周期，点击「加载 K 线」。

---

## 缠论参考

### 段的定义
1. 连续 3 笔间如果存在重叠部分，连接起点和终点即为线段
2. 至少连续 3 笔中出现更高的高点 + 更高的低点，或更低的高点 + 更低的低点

### 段的规则
1. 第一笔决定段的方向
2. 最少 3 笔，笔数必须为奇数
3. 向上段必须由向上笔结束，向下段必须由向下笔结束

### 段的产生与破坏
- 新线段形成且方向与原线段相反 → 原线段结束
- 线段只能被线段破坏

### 特征序列
- 向上段的向下笔、向下段的向上笔 — 即段中的回调笔
- 向上段中特征序列的顶分型、向下段中特征序列的底分型，标志段的结束

### 中枢
- 某级别走势类型中，被至少三个连续次级别走势类型所重叠的部分
- 上升段中的中枢起始于下、终结于下；下降段反之
- 画中枢时，在重叠的笔中取高点中的低点（ZG）、低点中的高点（ZD）

### 层级关系
```
线段 > 中枢 > 小级别线段 / 当前级别笔 > 分型
```
