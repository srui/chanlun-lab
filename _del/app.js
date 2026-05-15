// ====== State ======
const S = {
  // 主周期数据
  primary: {
    klines: null,
    fractals: null,
    turningPoints: [],
    strokes: [],
    segments: [],
    zhongshuList: [],
    segmentZhongshu: [],
    higherSegments: [],
    buySellPoints: [],
    macd: null,
    divergencePoints: [],
  },

  // 上下文周期数据（只读）
  context: {
    klines: null,
    fractals: null,
    turningPoints: [],
    segments: [],
    zhongshu: [],
    interval: null,
  },

  // 元数据
  currentSymbol: null,
  primaryInterval: null,
  contextInterval: null,
  deletedTurningPoints: new Set(),

  // UI 状态
  drawingMode: false,
  drawStart: null,
  chartCoords: [],
  chartLayout: null,
  drawZsMode: false,
  zsDrawStart: null,
  isDraggingZs: false,
  zsDragIdx: -1,
  zsDragEdge: null,
  isDragging: false,
  dragIdx: -1,
  showSegZs: true,
  showBuySell: true,
  showKlines: true,
  showContext: true,
  drawSegZsMode: false,
  segZsDrawStart: null,
  drawHigherMode: false,
  higherDrawStart: null,
  drawStrokeMode: false,
  strokeDrawLastIdx: null,
  autoRefresh: false,
  autoRefreshTimer: null,
  lastSignalState: null,
  loadingOlder: false,
  oldestKlineTime: null,
  macdOffset: 0,
};

// ====== UI Helpers ======
function resetPrimary() {
  S.primary.segments = [];
  S.deletedTurningPoints = new Set();
  S.primary.zhongshuList = [];
  S.primary.segmentZhongshu = [];
  S.primary.higherSegments = [];
  S.primary.buySellPoints = [];
  S.primary.macd = null;
  S.primary.divergencePoints = [];
  S.drawStart = null;
  S.zsDrawStart = null;
  S.segZsDrawStart = null;
  S.higherDrawStart = null;
  S.strokeDrawLastIdx = null;
  S.drawingMode = false;
  S.drawZsMode = false;
  S.drawSegZsMode = false;
  S.drawHigherMode = false;
  S.drawStrokeMode = false;
  document.getElementById('drawHint').style.display = 'none';
  document.getElementById('drawBtn').textContent = '手动画段';
  document.getElementById('drawZsBtn').textContent = '手动画中枢';
  document.getElementById('drawSegZsBtn').textContent = '手动画';
  document.getElementById('drawHigherBtn').textContent = '手动画';
  document.getElementById('drawStrokeBtn').textContent = '手动画笔';
  document.getElementById('emptyState').style.display = 'none';
  const tpReady = S.primary.turningPoints.length >= 2;
  const segReady = S.primary.turningPoints.length >= 8;
  document.getElementById('drawBtn').disabled = !tpReady;
  document.getElementById('autoSegBtn').disabled = !segReady;
  document.getElementById('autoZsBtn').disabled = !segReady;
  document.getElementById('drawZsBtn').disabled = !tpReady;
  document.getElementById('autoBuySellBtn').disabled = !segReady;
  document.getElementById('autoSegZsBtn').disabled = !segReady;
  document.getElementById('drawSegZsBtn').disabled = !segReady;
  document.getElementById('autoHigherBtn').disabled = !segReady;
  document.getElementById('drawHigherBtn').disabled = !segReady;
  document.getElementById('undoZsBtn').disabled = true;
  document.getElementById('undoSegBtn').disabled = true;
  document.getElementById('undoSegZsBtn').disabled = true;
  document.getElementById('undoHigherBtn').disabled = true;
  document.getElementById('undoStrokeBtn').disabled = true;
  document.getElementById('autoStrokeBtn').disabled = !S.primary.klines;
}

function resetAll() {
  S.primary.klines = null;
  S.primary.fractals = null;
  S.primary.turningPoints = [];
  S.primary.strokes = [];
  S.currentSymbol = null;
  S.primaryInterval = null;
  S.contextInterval = null;
  S.oldestKlineTime = null;
  S.loadingOlder = false;
  S.context = { klines: null, fractals: null, turningPoints: [], segments: [], zhongshu: [], interval: null };
  resetPrimary();
}

// Legacy alias
function resetUIState() { resetPrimary(); }

function getMinSegmentRatio() {
  return (parseFloat(document.getElementById('minSegRatio').value) || 0) / 100;
}

function getMinKlineGap() {
  return parseInt(document.getElementById('minKlineGap').value) || 4;
}

// ====== API Calls ======

// 周期 → 分钟数映射
const INTERVAL_MINUTES = {
  '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
  '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480,
  '12h': 720, '1d': 1440, '3d': 4320, '1w': 10080, '1M': 43200,
};

function getDaysKlineCount(interval, days = 60) {
  const mins = INTERVAL_MINUTES[interval] || 60;
  return Math.ceil(days * 1440 / mins);
}

async function loadBinanceKlines() {
  const symbol = document.getElementById('binanceSymbol').value.trim().toUpperCase();
  const interval = document.getElementById('binanceInterval').value;
  const limit = 500;
  if (!symbol) { alert('请输入交易对'); return; }

  const statusEl = document.getElementById('binanceStatus');
  statusEl.textContent = '加载中...';
  statusEl.style.color = '#ffc832';

  try {
    const resp = await fetch('/api/compute/dual', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({symbol, interval, limit, minSegmentRatio: getMinSegmentRatio(), minKlineGap: getMinKlineGap()})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');

    // 重置全部状态
    resetAll();

    // 主周期数据
    const primary = data.primary;

    // 上下文周期数据（只读）
    if (data.context) {
      S.context.klines = data.context.klines;
      S.context.fractals = data.context.fractals || null;
      S.context.turningPoints = data.context.turningPoints || [];
      S.context.segments = data.context.segments || [];
      S.context.zhongshu = data.context.zhongshu || [];
      S.context.interval = data.context.interval;
      S.contextInterval = data.context.interval;
    }

    resetPrimary(); // 设置按钮状态（会清空 segments 等）

    // 在 resetPrimary 之后存入数据
    S.primary.klines = primary.klines;
    S.oldestKlineTime = primary.klines.length ? primary.klines[0].openTime : null;
    S.loadingOlder = false;
    S.currentSymbol = primary.symbol;
    S.primaryInterval = primary.interval;
    S.primary.fractals = primary.fractals || [];
    S.primary.turningPoints = primary.turningPoints;
    S.primary.strokes = primary.strokes;
    S.primary.macd = primary.macd || null;
    S.primary.buySellPoints = primary.buySellPoints || [];
    S.primary.divergencePoints = primary.divergences || [];
    renderStrokeList();
    drawChart();
    updateContextPanel();

    // Auto-restore saved annotations
    await loadSavedAnnotation();
    if (S.primary.segments.length || S.primary.zhongshuList.length || S.primary.segmentZhongshu.length || S.primary.higherSegments.length) {
      drawChart();
      renderSegList();
      renderZhongshuList();
      renderSegZsList();
      renderHigherList();
    }

    let statusText = `${symbol} ${interval} · ${primary.klines.length} K线 · ${primary.turningPoints.length} 转折点`;
    if (S.context.interval) statusText += ` · 上下文: ${S.context.interval}`;
    statusEl.textContent = statusText;
    statusEl.style.color = '#51cf66';
    if (primary.warning) {
      statusEl.textContent += ' ⚠ ' + primary.warning;
      statusEl.style.color = '#ffc832';
    }

    // Refresh signal panel
    refreshSignal();
    // Restart auto-refresh with new interval if enabled
    if (S.autoRefresh) startAutoRefresh();
  } catch (err) {
    statusEl.textContent = '错误: ' + err.message;
    statusEl.style.color = '#ff6b6b';
  }
}

async function loadOlderKlines() {
  if (S.loadingOlder || !S.primary.klines || !S.oldestKlineTime) return;
  S.loadingOlder = true;
  drawChart(); // show loading indicator

  try {
    const symbol = S.currentSymbol;
    const interval = S.primaryInterval;
    const resp = await fetch(`/api/klines/older?symbol=${encodeURIComponent(symbol)}&interval=${interval}&beforeTime=${S.oldestKlineTime}&count=500`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');

    const olderKlines = data.klines;
    if (!olderKlines || olderKlines.length === 0) {
      S.loadingOlder = false;
      return; // no more data
    }

    // Prepend older klines
    S.primary.klines = olderKlines.concat(S.primary.klines);
    S.oldestKlineTime = olderKlines[0].openTime;

    // Re-analyze the full expanded kline array
    const analyzeResp = await fetch('/api/compute/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        klines: S.primary.klines,
        minKlineGap: getMinKlineGap(),
        minSegmentRatio: getMinSegmentRatio(),
      })
    });
    const analysis = await analyzeResp.json();
    if (!analyzeResp.ok) throw new Error(analysis.error || '分析失败');

    // Replace all analysis state with new results
    S.primary.fractals = analysis.fractals || [];
    S.primary.turningPoints = analysis.turningPoints || [];
    S.primary.strokes = analysis.strokes || [];
    S.primary.segments = analysis.segments || [];
    S.primary.zhongshuList = analysis.zhongshu || [];
    S.primary.segmentZhongshu = analysis.segmentZhongshu || [];
    S.primary.higherSegments = analysis.higherSegments || [];
    S.primary.buySellPoints = analysis.buySellPoints || [];
    S.primary.macd = analysis.macd || null;
    S.primary.divergencePoints = analysis.divergences || [];
    S.macdOffset = 0;
    S.deletedTurningPoints = new Set();

    // Re-render
    renderStrokeList();
    renderSegList();
    renderZhongshuList();
    renderSegZsList();
    renderHigherList();
    renderBsList();
    drawChart();
    autoSaveAnnotation();

    const statusEl = document.getElementById('binanceStatus');
    statusEl.textContent = `${symbol} ${interval} · ${S.primary.klines.length} K线 · ${S.primary.turningPoints.length} 转折点`;
    statusEl.style.color = '';
  } catch (err) {
    console.error('加载历史数据失败:', err);
    const statusEl = document.getElementById('binanceStatus');
    statusEl.textContent = '加载历史失败: ' + err.message;
    statusEl.style.color = '#ff6b6b';
  } finally {
    S.loadingOlder = false;
    drawChart();
  }
}

async function autoDetectStrokes() {
  if (!S.primary.klines) { alert('请先加载K线数据'); return; }
  const statusEl = document.getElementById('binanceStatus');
  try {
    statusEl.textContent = '计算笔...';
    statusEl.style.color = '#ffc832';
    const resp = await fetch('/api/compute/strokes', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ klines: S.primary.klines, minKlineGap: getMinKlineGap() })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');

    resetUIState();
    S.primary.fractals = data.fractals || [];
    S.primary.turningPoints = data.turningPoints;
    S.primary.strokes = data.strokes;

    renderStrokeList();
    drawChart();
    document.getElementById('undoStrokeBtn').disabled = S.primary.turningPoints.length === 0;

    statusEl.textContent = `${S.currentSymbol} ${S.primaryInterval} · ${S.primary.klines.length} K线 · ${S.primary.turningPoints.length} 笔`;
    statusEl.style.color = '#51cf66';

    document.getElementById('autoSegBtn').disabled = S.primary.turningPoints.length < 8;
    document.getElementById('drawBtn').disabled = S.primary.turningPoints.length < 2;
    document.getElementById('autoZsBtn').disabled = S.primary.turningPoints.length < 4;
    document.getElementById('drawZsBtn').disabled = S.primary.turningPoints.length < 2;
  } catch (err) {
    statusEl.textContent = '计算笔失败: ' + err.message;
    statusEl.style.color = '#ff6b6b';
  }
}

async function autoDetectSegments() {
  if (S.primary.turningPoints.length < 8) { alert('至少需要8个转折点才能自动画段（当前' + S.primary.turningPoints.length + '个）'); return; }
  try {
    const resp = await fetch('/api/compute/segments', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({turningPoints: S.primary.turningPoints, minSegmentRatio: getMinSegmentRatio()})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    S.primary.segments = data.segments;
    redrawSegments();
    renderSegList();
    document.getElementById('undoSegBtn').disabled = false;
    document.getElementById('autoSegZsBtn').disabled = S.primary.segments.length < 3;
    document.getElementById('drawSegZsBtn').disabled = S.primary.segments.length < 3;
    document.getElementById('autoHigherBtn').disabled = S.primary.segments.length < 4;
    document.getElementById('drawHigherBtn').disabled = S.primary.segments.length < 3;
    autoSaveAnnotation();
  } catch (err) {
    alert('计算失败: ' + err.message);
  }
}

async function autoDetectZhongshu() {
  if (S.primary.turningPoints.length < 4) { alert('至少需要4个点'); return; }
  try {
    const resp = await fetch('/api/compute/zhongshu', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({turningPoints: S.primary.turningPoints, segments: S.primary.segments, minSegmentRatio: getMinSegmentRatio()})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    S.primary.zhongshuList = data.zhongshu;
    drawChart();
    renderZhongshuList();
    document.getElementById('undoZsBtn').disabled = S.primary.zhongshuList.length === 0;
    document.getElementById('autoBuySellBtn').disabled = S.primary.zhongshuList.length === 0;
    autoSaveAnnotation();
  } catch (err) {
    alert('计算失败: ' + err.message);
  }
}

async function recomputeWithRatio() {
  if (S.primary.turningPoints.length < 4) { alert('至少需要4个点'); return; }
  try {
    const ratio = getMinSegmentRatio();
    const resp = await fetch('/api/compute/recompute', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({turningPoints: S.primary.turningPoints, minSegmentRatio: ratio})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    S.primary.segments = data.segments;
    S.primary.zhongshuList = data.zhongshu;
    S.primary.segmentZhongshu = data.segmentZhongshu;
    S.primary.higherSegments = data.higherSegments;
    S.primary.buySellPoints = data.buySellPoints || [];
    S.primary.divergencePoints = data.divergences || [];

    drawChart();
    renderSegList();
    renderZhongshuList();
    renderSegZsList();
    renderHigherList();
    renderBsList();
    document.getElementById('undoSegBtn').disabled = S.primary.segments.length === 0;
    document.getElementById('undoZsBtn').disabled = S.primary.zhongshuList.length === 0;
    document.getElementById('autoSegZsBtn').disabled = S.primary.segments.length < 3;
    document.getElementById('drawSegZsBtn').disabled = S.primary.segments.length < 3;
    document.getElementById('undoSegZsBtn').disabled = S.primary.segmentZhongshu.length === 0;
    document.getElementById('autoHigherBtn').disabled = S.primary.segments.length < 4;
    document.getElementById('drawHigherBtn').disabled = S.primary.segments.length < 3;
    document.getElementById('undoHigherBtn').disabled = S.primary.higherSegments.length === 0;
    document.getElementById('autoBuySellBtn').disabled = S.primary.zhongshuList.length === 0;
    autoSaveAnnotation();
  } catch (err) {
    alert('计算失败: ' + err.message);
  }
}

async function recomputeSegmentLevel() {
  if (S.primary.turningPoints.length < 4 || S.primary.segments.length < 3) {
    S.primary.segmentZhongshu = [];
    S.primary.higherSegments = [];
    return;
  }
  try {
    const resp = await fetch('/api/compute/segment-level', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({turningPoints: S.primary.turningPoints, segments: S.primary.segments, minSegmentRatio: getMinSegmentRatio()})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    S.primary.segmentZhongshu = data.segmentZhongshu;
    S.primary.higherSegments = data.higherSegments;
  } catch (err) {
    console.error('段级别计算失败:', err);
  }
}

async function autoDetectSegmentZhongshu() {
  if (S.primary.turningPoints.length < 4) return;
  await recomputeSegmentLevel();
  drawChart();
  renderSegZsList();
  renderHigherList();
  document.getElementById('undoSegZsBtn').disabled = S.primary.segmentZhongshu.length === 0;
  document.getElementById('undoHigherBtn').disabled = S.primary.higherSegments.length === 0;
}

async function autoDetectHigherSegments() {
  if (S.primary.turningPoints.length < 4) return;
  await recomputeSegmentLevel();
  drawChart();
  renderSegZsList();
  renderHigherList();
  document.getElementById('undoHigherBtn').disabled = S.primary.higherSegments.length === 0;
  document.getElementById('undoSegZsBtn').disabled = S.primary.segmentZhongshu.length === 0;
}

function renderSegZsList() {
  const list = document.getElementById('segZsList');
  list.innerHTML = '';
  S.primary.segmentZhongshu.forEach((zs, i) => {
    const div = document.createElement('div');
    div.className = 'zs-item';
    const from = S.primary.turningPoints[zs.fromIdx];
    const to = S.primary.turningPoints[zs.toIdx];
    div.innerHTML = `
      <span class="range" style="color:#4a9eff">ZG=${Math.round(zs.zg * 100) / 100} ZD=${Math.round(zs.zd * 100) / 100}</span>
      <span class="del" onclick="removeSegZs(${i})">×</span>
    `;
    list.appendChild(div);
  });
}

function renderHigherList() {
  const list = document.getElementById('higherList');
  list.innerHTML = '';
  S.primary.higherSegments.forEach((seg, i) => {
    const from = S.primary.turningPoints[seg.fromIdx];
    const to = S.primary.turningPoints[seg.toIdx];
    if (from === undefined || to === undefined) return;
    const isUp = to > from;
    const div = document.createElement('div');
    div.className = 'seg-item';
    div.innerHTML = `
      <span class="dir ${isUp ? 'up' : 'down'}">${isUp ? '↑' : '↓'}</span>
      <span class="range" style="color:#ff6b6b">${Math.round(from * 100) / 100} → ${Math.round(to * 100) / 100}</span>
      <span class="del" onclick="removeHigher(${i})">×</span>
    `;
    list.appendChild(div);
  });
}

async function recomputeBuySell() {
  if (S.primary.turningPoints.length < 4 || S.primary.zhongshuList.length === 0) {
    S.primary.buySellPoints = [];
    return;
  }
  try {
    const resp = await fetch('/api/compute/buy-sell', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({turningPoints: S.primary.turningPoints, segments: S.primary.segments, minSegmentRatio: getMinSegmentRatio()})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    S.primary.buySellPoints = data.buySellPoints || [];
    S.primary.divergencePoints = [];
  } catch (err) {
    S.primary.buySellPoints = [];
    S.primary.divergencePoints = [];
  }
}

async function autoDetectBuySell() {
  if (S.primary.turningPoints.length < 4) { alert('至少需要4个点'); return; }
  try {
    const resp = await fetch('/api/compute/buy-sell', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({turningPoints: S.primary.turningPoints, segments: S.primary.segments, minSegmentRatio: getMinSegmentRatio()})
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    S.primary.buySellPoints = data.buySellPoints || [];
    S.primary.divergencePoints = [];
    drawChart();
    renderBsList();
  } catch (err) {
    alert('计算失败: ' + err.message);
  }
}

function renderBsList() {
  const list = document.getElementById('bsList');
  list.innerHTML = '';
  if (!S.primary.buySellPoints.length) return;
  const divByIdx = {};
  S.primary.divergencePoints.forEach(d => { divByIdx[d.idx] = d; });
  S.primary.buySellPoints.forEach(p => {
    const price = S.primary.turningPoints[p.idx];
    if (price === undefined) return;
    const isBuy = p.type === 'buy';
    const tag = isBuy ? p.label : p.label + "'";
    const typeName = isBuy ? '买' : '卖';
    const divTag = p.hasDivergence ? (isBuy ? ' 底背驰' : ' 顶背驰') : '';
    const div = document.createElement('div');
    div.className = 'seg-item';
    div.innerHTML = `
      <span style="display:inline-block;width:18px;height:18px;border-radius:50%;background:${isBuy ? '#00c853' : '#ff1744'};color:#fff;text-align:center;line-height:18px;font-size:11px;font-weight:bold;flex-shrink:0">${tag}</span>
      <span class="range" style="color:${isBuy ? '#00c853' : '#ff1744'}">${typeName}${divTag} · ${Math.round(price * 100) / 100}</span>
    `;
    list.appendChild(div);
  });
}

function toggleSegZs() {
  S.showSegZs = !S.showSegZs;
  const btn = document.getElementById('segZsToggle');
  btn.textContent = S.showSegZs ? 'ON' : 'OFF';
  btn.className = 'btn-toggle ' + (S.showSegZs ? 'on' : 'off');
  drawChart();
}

function toggleBuySell() {
  S.showBuySell = !S.showBuySell;
  const btn = document.getElementById('bsToggle');
  btn.textContent = S.showBuySell ? 'ON' : 'OFF';
  btn.className = 'btn-toggle ' + (S.showBuySell ? 'on' : 'off');
  drawChart();
}

function toggleKlines() {
  S.showKlines = !S.showKlines;
  const btn = document.getElementById('klineToggle');
  btn.textContent = S.showKlines ? 'K线ON' : 'K线OFF';
  btn.className = 'btn-toggle ' + (S.showKlines ? 'on' : 'off');
  drawChart();
}

function toggleContext() {
  S.showContext = !S.showContext;
  const btn = document.getElementById('contextToggle');
  btn.textContent = S.showContext ? '隐藏' : '显示';
  drawChart();
}

function updateContextPanel() {
  const panel = document.getElementById('contextPanel');
  if (!S.context.interval) { panel.style.display = 'none'; return; }
  panel.style.display = '';
  document.getElementById('contextIntervalLabel').textContent = S.context.interval;
  document.getElementById('contextSegCount').textContent = (S.context.segments || []).length;
  document.getElementById('contextZsCount').textContent = (S.context.zhongshu || []).length;
}

// ====== Annotation Auto-Save ======
let _saveTimer = null;

function autoSaveAnnotation() {
  if (!S.currentSymbol || !S.primaryInterval) return;
  if (_saveTimer) clearTimeout(_saveTimer);
  _saveTimer = setTimeout(() => {
    const data = {
      symbol: S.currentSymbol,
      interval: S.primaryInterval,
      turningPoints: S.primary.turningPoints,
      segments: S.primary.segments,
      zhongshu: S.primary.zhongshuList,
      segmentZhongshu: S.primary.segmentZhongshu,
      higherSegments: S.primary.higherSegments,
      deletedTurningPoints: [...S.deletedTurningPoints],
    };
    fetch('/api/annotation/save', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    }).catch(() => {});
  }, 2000);
}

async function loadSavedAnnotation() {
  if (!S.currentSymbol || !S.primaryInterval) return;
  try {
    const resp = await fetch(`/api/annotation/load?symbol=${encodeURIComponent(S.currentSymbol)}&interval=${encodeURIComponent(S.primaryInterval)}`);
    const data = await resp.json();
    if (!data.annotation) return;

    const a = data.annotation;
    const tpLen = S.primary.turningPoints.length;

    // 校验索引范围
    const validateIdx = (idx) => typeof idx === 'number' && idx >= 0 && idx < tpLen;
    const validateRange = (item) => validateIdx(item.fromIdx) && validateIdx(item.toIdx);

    if (a.turningPoints && a.turningPoints.length === tpLen) {
      // 转折点数量匹配，恢复标注
      if (a.segments) S.primary.segments = a.segments.filter(validateRange);
      if (a.zhongshu) S.primary.zhongshuList = a.zhongshu.filter(validateRange);
      if (a.segmentZhongshu) S.primary.segmentZhongshu = a.segmentZhongshu.filter(validateRange);
      if (a.higherSegments) S.primary.higherSegments = a.higherSegments.filter(validateRange);
      if (a.deletedTurningPoints) S.deletedTurningPoints = new Set(a.deletedTurningPoints.filter(i => i < tpLen));
    }
  } catch (e) {
    // 静默失败
  }
}

function clearSavedAnnotation() {
  if (!S.currentSymbol || !S.primaryInterval) return;
  fetch(`/api/annotation/clear?symbol=${encodeURIComponent(S.currentSymbol)}&interval=${encodeURIComponent(S.primaryInterval)}`, { method: 'DELETE' })
    .catch(() => {});
}

// ====== Signal Panel ======
async function refreshSignal() {
  if (!S.currentSymbol || !S.primaryInterval) return;
  const btn = document.getElementById('signalRefreshBtn');
  btn.disabled = true;
  btn.textContent = '计算中...';
  try {
    const resp = await fetch('/api/signal', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        symbol: S.currentSymbol,
        interval: S.primaryInterval,
        contextInterval: S.contextInterval,
        minSegmentRatio: getMinSegmentRatio(),
        minKlineGap: getMinKlineGap()
      })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    renderSignalPanel(data.signal);
  } catch (err) {
    console.error('信号计算失败:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = '刷新信号';
  }
}

function renderSignalPanel(signal) {
  const el = document.getElementById('signalContent');
  if (!signal) { el.innerHTML = '<div class="signal-detail">无数据</div>'; return; }

  const dir = signal.direction || 'neutral';
  const state = signal.state || 'IDLE';
  const setup = signal.activeSetup;

  // Direction arrow
  const dirArrow = dir === 'long' ? '↑' : dir === 'short' ? '↓' : '–';
  const dirLabel = dir === 'long' ? '做多' : dir === 'short' ? '做空' : '震荡';

  // State label
  const stateLabels = {
    'IDLE': '无信号',
    'WATCHING': '发现机会',
    'CONFIRMING': '等待确认',
    'READY': '可以入场'
  };

  let html = '';
  html += `<div class="signal-direction ${dir}">${dirArrow} ${dirLabel}</div>`;
  html += `<div class="signal-state ${state.toLowerCase()}">${stateLabels[state] || state}</div>`;

  // Details
  html += '<div class="signal-detail">';
  // Context info
  const ctxSeg = signal.contextSegments || 0;
  const ctxDir = signal.contextDirection || 'neutral';
  const ctxDirLabel = ctxDir === 'long' ? '上升段' : ctxDir === 'short' ? '下降段' : '无方向';
  const ctxOk = ctxDir !== 'neutral';
  html += `<div>${ctxOk ? '<span class="check">✓</span>' : '<span class="cross">✗</span>'} 上下文 (${ctxDirLabel})</div>`;

  // Primary zhongshu
  const zsCount = signal.primaryZhongshu || 0;
  html += `<div>${zsCount > 0 ? '<span class="check">✓</span>' : '<span class="wait">○</span>'} 主周期中枢 ×${zsCount}</div>`;

  // Buy/sell points
  const bsCount = signal.primaryBuySell || 0;
  html += `<div>${bsCount > 0 ? '<span class="check">✓</span>' : '<span class="wait">○</span>'} 买卖点 ×${bsCount}</div>`;

  html += '</div>';

  // Active setup details
  if (setup) {
    const typeLabel = setup.type === 'buy' ? '买点' : '卖点';
    const divStar = setup.hasDivergence ? '<span class="div-star"> ★ 背驰确认</span>' : '<span class="wait"> △ 暂无背驰</span>';
    html += '<div class="signal-setup">';
    html += `<div>${typeLabel} ${setup.label} ${divStar}</div>`;
    if (setup.price !== null && setup.price !== undefined) {
      html += `<div class="price">${Math.round(setup.price * 100) / 100}</div>`;
    }
    html += '</div>';
  }

  el.innerHTML = html;

  // Detect state change for animation
  const stateKey = `${signal.direction}:${signal.state}`;
  if (S.lastSignalState && S.lastSignalState !== stateKey) {
    el.style.transition = 'background 0.3s';
    el.style.background = 'rgba(255,200,50,0.15)';
    setTimeout(() => { el.style.background = ''; }, 800);
  }
  S.lastSignalState = stateKey;
}

async function toggleAutoRefresh() {
  S.autoRefresh = !S.autoRefresh;
  const btn = document.getElementById('autoRefreshBtn');
  const statusEl = document.getElementById('pollStatus');

  if (S.autoRefresh) {
    btn.textContent = '停止刷新';
    btn.className = 'btn btn-danger';
    btn.style.flex = '1';
    startAutoRefresh();
  } else {
    btn.textContent = '自动刷新';
    btn.className = 'btn btn-warn';
    btn.style.flex = '1';
    stopAutoRefresh();
    statusEl.textContent = '';
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  if (!S.autoRefresh || !S.primaryInterval) return;

  // Fetch polling interval from backend
  fetch(`/api/config/poll-interval?interval=${encodeURIComponent(S.primaryInterval)}`)
    .then(r => r.json())
    .then(cfg => {
      const seconds = cfg.pollSeconds || 60;
      const statusEl = document.getElementById('pollStatus');
      statusEl.textContent = `每 ${seconds}s 自动刷新`;
      S.autoRefreshTimer = setInterval(() => {
        if (S.autoRefresh && S.currentSymbol && S.primaryInterval) {
          refreshSignal();
        }
      }, seconds * 1000);
    })
    .catch(() => {
      // Fallback to 60s
      S.autoRefreshTimer = setInterval(() => {
        if (S.autoRefresh && S.currentSymbol && S.primaryInterval) {
          refreshSignal();
        }
      }, 60000);
    });
}

function stopAutoRefresh() {
  if (S.autoRefreshTimer) {
    clearInterval(S.autoRefreshTimer);
    S.autoRefreshTimer = null;
  }
}

// ====== Watchlist ======
function getWatchlist() {
  try { return JSON.parse(localStorage.getItem('chanlun_watchlist') || '[]'); }
  catch { return []; }
}

function saveWatchlist(list) {
  localStorage.setItem('chanlun_watchlist', JSON.stringify(list));
}

function addToWatchlist() {
  const input = document.getElementById('watchlistInput');
  const sym = (input.value || '').trim().toUpperCase();
  if (!sym) return;
  const list = getWatchlist();
  if (list.includes(sym)) { input.value = ''; return; }
  list.push(sym);
  saveWatchlist(list);
  input.value = '';
  renderWatchlist();
  pollWatchlist();
}

function removeFromWatchlist(sym) {
  const list = getWatchlist().filter(s => s !== sym);
  saveWatchlist(list);
  renderWatchlist();
}

function toggleWatchlist() {
  const container = document.getElementById('watchlistContainer');
  const btn = document.getElementById('watchlistToggle');
  const visible = container.style.display !== 'none';
  container.style.display = visible ? 'none' : 'block';
  btn.textContent = visible ? 'OFF' : 'ON';
  btn.className = 'btn-toggle ' + (visible ? 'off' : 'on');
  if (!visible) pollWatchlist();
}

function renderWatchlist() {
  const el = document.getElementById('watchlistItems');
  const list = getWatchlist();
  if (!list.length) { el.innerHTML = '<div class="status-text" style="color:#5577aa">空列表</div>'; return; }
  el.innerHTML = list.map(sym => `
    <div class="watch-item" id="watch-${sym}" onclick="loadWatchSymbol('${sym}')">
      <span class="sym">${sym}</span>
      <span class="dir neutral" id="watch-dir-${sym}">–</span>
      <span class="st idle" id="watch-st-${sym}">…</span>
      <span class="del" onclick="event.stopPropagation();removeFromWatchlist('${sym}')">×</span>
    </div>
  `).join('');
}

async function pollWatchlist() {
  const list = getWatchlist();
  if (!list.length) return;
  const interval = S.primaryInterval || '4h';
  const statusEl = document.getElementById('watchlistStatus');
  statusEl.textContent = '刷新中...';

  for (const sym of list) {
    try {
      const resp = await fetch('/api/signal', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ symbol: sym, interval })
      });
      const data = await resp.json();
      if (data.signal) {
        const sig = data.signal;
        const dirEl = document.getElementById(`watch-dir-${sym}`);
        const stEl = document.getElementById(`watch-st-${sym}`);
        if (dirEl) {
          dirEl.textContent = sig.direction === 'long' ? '↑' : sig.direction === 'short' ? '↓' : '–';
          dirEl.className = 'dir ' + sig.direction;
        }
        if (stEl) {
          const labels = {IDLE: 'IDLE', WATCHING: 'WATCH', CONFIRMING: 'CONF', READY: 'READY'};
          stEl.textContent = labels[sig.state] || sig.state;
          stEl.className = 'st ' + sig.state.toLowerCase();
        }
      }
    } catch {
      // Skip failed symbols
    }
  }
  statusEl.textContent = `已刷新 · ${list.length} 标的`;
}

function loadWatchSymbol(sym) {
  document.getElementById('binanceSymbol').value = sym;
  loadBinanceKlines();
}

// Auto-poll watchlist every 60s when visible
setInterval(() => {
  const container = document.getElementById('watchlistContainer');
  if (container && container.style.display !== 'none' && getWatchlist().length > 0) {
    pollWatchlist();
  }
}, 60000);

// Initial render
renderWatchlist();

// Call autoSaveAnnotation after drawChart in edit functions
function drawChartAndSave() {
  drawChart();
  autoSaveAnnotation();
}

function drawBuySellMarkers() {
  if (!S.chartLayout || S.chartCoords.length === 0 || !S.primary.buySellPoints.length) return;

  // Build divergence lookup by idx (for type info)
  const divByIdx = {};
  S.primary.divergencePoints.forEach(d => { divByIdx[d.idx] = d; });

  // Group by idx — one marker per turning point, show all labels
  const grouped = {};
  S.primary.buySellPoints.forEach(p => {
    if (!grouped[p.idx]) grouped[p.idx] = [];
    grouped[p.idx].push(p);
  });

  Object.entries(grouped).forEach(([idx, points]) => {
    const i = parseInt(idx);
    const coord = S.chartCoords[i];
    if (!coord) return;

    const x = coord.x, y = coord.y;

    // Determine combined label text
    const buyLabels = points.filter(p => p.type === 'buy').map(p => p.label).sort().join('');
    const sellLabels = points.filter(p => p.type === 'sell').map(p => p.label).sort().map(l => l + "'").join('');
    const hasDiv = points.some(p => p.hasDivergence) ? divByIdx[i] : null;

    // Draw sell markers (red, above the point)
    if (sellLabels) {
      const r = 10;
      chart.appendChild(svgEl("circle", {
        cx: x, cy: y - r - 4, r, fill: "#ff1744", opacity: 0.92, class: "bs-marker"
      }));
      const lbl = svgEl("text", {
        x, y: y - r - 4 + 4, fill: "#fff", "font-size": 12, "font-weight": "bold",
        "text-anchor": "middle", "dominant-baseline": "middle", class: "bs-marker"
      });
      lbl.textContent = sellLabels;
      chart.appendChild(lbl);
    }

    // Draw buy markers (green, below the point)
    if (buyLabels) {
      const r = 10;
      chart.appendChild(svgEl("circle", {
        cx: x, cy: y + r + 4, r, fill: "#00c853", opacity: 0.92, class: "bs-marker"
      }));
      const lbl = svgEl("text", {
        x, y: y + r + 4 + 4, fill: "#fff", "font-size": 12, "font-weight": "bold",
        "text-anchor": "middle", "dominant-baseline": "middle", class: "bs-marker"
      });
      lbl.textContent = buyLabels;
      chart.appendChild(lbl);
    }

    // 背驰 indicator
    if (hasDiv) {
      const isTop = hasDiv.type === 'top';
      const tagY = isTop ? y - 28 : y + 30;
      chart.appendChild(svgEl("rect", {
        x: x + 10, y: tagY - 8, width: 20, height: 16, rx: 3,
        fill: isTop ? "rgba(255,23,68,0.85)" : "rgba(0,200,83,0.85)", class: "bs-marker"
      }));
      const divLbl = svgEl("text", {
        x: x + 20, y: tagY + 3, fill: "#fff", "font-size": 10, "font-weight": "bold",
        "text-anchor": "middle", "dominant-baseline": "middle", class: "bs-marker"
      });
      divLbl.textContent = "背";
      chart.appendChild(divLbl);
    }
  });
}

async function exportJSON() {
  try {
    const resp = await fetch('/api/compute/export', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        turningPoints: S.primary.turningPoints,
        segments: S.primary.segments,
        zhongshu: S.primary.zhongshuList,
        klines: S.primary.klines,
        symbol: S.currentSymbol,
        interval: S.primaryInterval,
        minSegmentRatio: getMinSegmentRatio()
      })
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || '未知错误');
    document.getElementById('exportArea').style.display = 'block';
    document.getElementById('exportText').value = JSON.stringify(data, null, 2);
  } catch (err) {
    alert('导出失败: ' + err.message);
  }
}

// ====== Render Functions ======
function renderStrokeList() {
  const list = document.getElementById('strokeList');
  list.innerHTML = '';
  S.primary.strokes.forEach((s, i) => {
    const div = document.createElement('div');
    div.className = 'stroke-item';
    div.innerHTML = `
      <span class="dir ${s.dir}">${i + 1} ${s.dir === 'down' ? '↓' : '↑'}</span>
      <span class="val" onclick="editStroke(${i}, this)">${typeof s.val === 'number' ? Math.round(s.val * 100) / 100 : s.val}</span>
      <span class="del" onclick="removeStroke(${i})">×</span>
    `;
    list.appendChild(div);
  });
}

function removeStroke(i) {
  S.primary.strokes.splice(i, 1);
  S.primary.turningPoints.splice(i, 1);
  if (S.primary.fractals && i < S.primary.fractals.length) {
    S.primary.fractals.splice(i, 1);
  }
  // Update deletedTurningPoints: remove i, shift > i down by 1
  S.deletedTurningPoints.delete(i);
  const newSet = new Set();
  S.deletedTurningPoints.forEach(v => newSet.add(v > i ? v - 1 : v));
  S.deletedTurningPoints = newSet;
  // Remove segments/zhongshu that reference the deleted point
  S.primary.segments = S.primary.segments.filter(s => s.fromIdx !== i && s.toIdx !== i).map(s => ({
    ...s,
    fromIdx: s.fromIdx > i ? s.fromIdx - 1 : s.fromIdx,
    toIdx: s.toIdx > i ? s.toIdx - 1 : s.toIdx,
  }));
  S.primary.zhongshuList = S.primary.zhongshuList.filter(z => z.fromIdx !== i && z.toIdx !== i).map(z => ({
    ...z,
    fromIdx: z.fromIdx > i ? z.fromIdx - 1 : z.fromIdx,
    toIdx: z.toIdx > i ? z.toIdx - 1 : z.toIdx,
  }));
  S.primary.segmentZhongshu = S.primary.segmentZhongshu.filter(s => s.fromIdx !== i && s.toIdx !== i).map(s => ({
    ...s,
    fromIdx: s.fromIdx > i ? s.fromIdx - 1 : s.fromIdx,
    toIdx: s.toIdx > i ? s.toIdx - 1 : s.toIdx,
  }));
  S.primary.higherSegments = S.primary.higherSegments.filter(s => s.fromIdx !== i && s.toIdx !== i).map(s => ({
    ...s,
    fromIdx: s.fromIdx > i ? s.fromIdx - 1 : s.fromIdx,
    toIdx: s.toIdx > i ? s.toIdx - 1 : s.toIdx,
  }));
  // Update stroke fromIdx/toIdx references
  S.primary.strokes = S.primary.strokes.map(s => ({
    ...s,
    fromIdx: s.fromIdx != null ? (s.fromIdx > i ? s.fromIdx - 1 : (s.fromIdx === i ? null : s.fromIdx)) : null,
    toIdx: s.toIdx != null ? (s.toIdx > i ? s.toIdx - 1 : s.toIdx) : null,
  }));
  // Clear buy/sell points and divergences (they reference turning point indices)
  S.primary.buySellPoints = [];
  S.primary.macd = null;
  S.primary.divergencePoints = [];
  document.getElementById('undoStrokeBtn').disabled = S.primary.turningPoints.length === 0;
  renderStrokeList();
  drawChartAndSave();
}

function editStroke(i, el) {
  const currentVal = S.primary.strokes[i].val;
  const input = document.createElement('input');
  input.type = 'number';
  input.className = 'val-input';
  input.value = currentVal;
  input.step = '1';
  el.replaceWith(input);
  input.focus();
  input.select();

  function save() {
    const v = parseFloat(input.value);
    if (!isNaN(v)) {
      S.primary.strokes[i].val = Math.round(v * 100) / 100;
      S.primary.turningPoints[i] = Math.round(v * 100) / 100;
    }
    renderStrokeList();
  }
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); save(); } if (e.key === 'Escape') { renderStrokeList(); } });
}

function clearAll() {
  S.primary.strokes = [];
  S.primary.turningPoints = [];
  S.deletedTurningPoints = new Set();
  S.primary.segments = [];
  S.primary.zhongshuList = [];
  S.primary.segmentZhongshu = [];
  S.primary.higherSegments = [];
  S.primary.buySellPoints = [];
  S.primary.macd = null;
  S.primary.divergencePoints = [];
  S.primary.klines = null;
  S.currentSymbol = null;
  S.primaryInterval = null;
  S.primary.fractals = null;
  S.drawStart = null;
  S.zsDrawStart = null;
  S.segZsDrawStart = null;
  S.higherDrawStart = null;
  S.strokeDrawLastIdx = null;
  S.drawingMode = false;
  S.drawZsMode = false;
  S.drawSegZsMode = false;
  S.drawHigherMode = false;
  S.drawStrokeMode = false;
  document.getElementById('drawBtn').textContent = '手动画段';
  document.getElementById('drawZsBtn').textContent = '手动画中枢';
  document.getElementById('drawSegZsBtn').textContent = '手动画';
  document.getElementById('drawHigherBtn').textContent = '手动画';
  document.getElementById('drawStrokeBtn').textContent = '手动画笔';
  document.getElementById('drawBtn').disabled = true;
  document.getElementById('autoStrokeBtn').disabled = true;
  document.getElementById('autoSegBtn').disabled = true;
  document.getElementById('autoZsBtn').disabled = true;
  document.getElementById('autoSegZsBtn').disabled = true;
  document.getElementById('drawSegZsBtn').disabled = true;
  document.getElementById('undoSegZsBtn').disabled = true;
  document.getElementById('autoHigherBtn').disabled = true;
  document.getElementById('drawHigherBtn').disabled = true;
  document.getElementById('undoHigherBtn').disabled = true;
  document.getElementById('autoBuySellBtn').disabled = true;
  document.getElementById('drawZsBtn').disabled = true;
  document.getElementById('drawHint').style.display = 'none';
  document.getElementById('emptyState').style.display = 'block';
  document.getElementById('undoSegBtn').disabled = true;
  document.getElementById('undoZsBtn').disabled = true;
  document.getElementById('undoStrokeBtn').disabled = true;
  document.getElementById('binanceStatus').textContent = '';
  renderStrokeList();
  renderSegZsList();
  renderHigherList();
  renderBsList();
  clearSVG();
  clearSavedAnnotation();
  // Reset signal panel and stop auto-refresh
  stopAutoRefresh();
  S.autoRefresh = false;
  S.lastSignalState = null;
  const autoBtn = document.getElementById('autoRefreshBtn');
  if (autoBtn) { autoBtn.textContent = '自动刷新'; autoBtn.className = 'btn btn-warn'; autoBtn.style.flex = '1'; }
  document.getElementById('pollStatus').textContent = '';
  document.getElementById('signalContent').innerHTML =
    '<div class="signal-direction neutral">--</div><div class="signal-state idle">无数据</div>';
}

function renderSegList() {
  const list = document.getElementById('segList');
  if (!list) return;
  list.innerHTML = '';
  S.primary.segments.forEach((seg, i) => {
    const from = S.primary.turningPoints[seg.fromIdx];
    const to = S.primary.turningPoints[seg.toIdx];
    if (from === undefined || to === undefined) return;
    const isUp = to > from;
    const div = document.createElement('div');
    div.className = 'seg-item';
    div.innerHTML = `
      <span class="dir ${isUp ? 'up' : 'down'}">${isUp ? '↑' : '↓'}</span>
      <span class="range">${Math.round(from * 100) / 100} → ${Math.round(to * 100) / 100}</span>
      <span class="del" onclick="removeSegment(${i})">×</span>
    `;
    list.appendChild(div);
  });
}

function renderZhongshuList() {
  const list = document.getElementById('zsList');
  if (!list) return;
  list.innerHTML = '';
  S.primary.zhongshuList.forEach((zs, i) => {
    const div = document.createElement('div');
    div.className = 'zs-item';
    const from = S.primary.turningPoints[zs.fromIdx];
    const to = S.primary.turningPoints[zs.toIdx];
    div.innerHTML = `
      <span class="range">ZG=${Math.round(zs.zg * 100) / 100} ZD=${Math.round(zs.zd * 100) / 100} (${Math.round(from * 100) / 100}→${Math.round(to * 100) / 100})</span>
      <span class="del" onclick="removeZhongshu(${i})">×</span>
    `;
    list.appendChild(div);
  });
}


// ====== SVG Drawing + Lightweight Charts ======
const SVG_NS = "http://www.w3.org/2000/svg";
const chart = document.getElementById('chart');

// LC instances
let lcChart = null;
let lcCandleSeries = null;
let lcVolumeSeries = null;
let lcMacdHistSeries = null;
let lcDifSeries = null;
let lcDeaSeries = null;
let lcOverlayScheduled = false;

function svgEl(tag, attrs) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

function clearSVG() {
  while (chart.firstChild) chart.removeChild(chart.firstChild);
  S.chartCoords = [];
}

// ====== LC Init / Data ======
function initLC() {
  if (lcChart) lcChart.remove();
  const container = document.getElementById('lcContainer');
  lcChart = LightweightCharts.createChart(container, {
    layout: { background: { color: '#1a1a2e' }, textColor: '#5577aa', fontSize: 11 },
    grid: { vertLines: { color: '#1e3050' }, horzLines: { color: '#1e3050' } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: '#1a3a5c' },
    timeScale: { borderColor: '#1a3a5c', timeVisible: true, secondsVisible: false },
  });

  lcCandleSeries = lcChart.addCandlestickSeries({
    upColor: '#26a69a', downColor: '#ef5350',
    borderUpColor: '#26a69a', borderDownColor: '#ef5350',
    wickUpColor: '#26a69a', wickDownColor: '#ef5350',
  });

  lcVolumeSeries = lcChart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
  });
  lcChart.priceScale('volume').applyOptions({
    scaleMargins: { top: 0.85, bottom: 0 },
  });

  // MACD pane
  lcMacdHistSeries = lcChart.addHistogramSeries({ pane: 1, priceScaleId: 'macd_hist' });
  lcDifSeries = lcChart.addLineSeries({ pane: 1, color: '#2196f3', lineWidth: 1, priceScaleId: 'macd_hist' });
  lcDeaSeries = lcChart.addLineSeries({ pane: 1, color: '#ff9800', lineWidth: 1, priceScaleId: 'macd_hist' });

  lcChart.timeScale().subscribeVisibleLogicalRangeChange(onLCVisibleRangeChange);
}

function updateLCData() {
  if (!lcChart || !S.primary.klines) return;
  const candleData = S.primary.klines.map(k => ({
    time: Math.round(k.openTime / 1000),
    open: k.open, high: k.high, low: k.low, close: k.close,
  }));
  lcCandleSeries.setData(candleData);

  const volumeData = S.primary.klines.map(k => ({
    time: Math.round(k.openTime / 1000),
    value: k.volume || 0,
    color: k.close >= k.open ? 'rgba(38,166,154,0.3)' : 'rgba(239,83,80,0.3)',
  }));
  lcVolumeSeries.setData(volumeData);

  if (S.primary.macd) {
    const { dif, dea, histogram } = S.primary.macd;
    const offset = S.macdOffset;
    const histData = [], difData = [], deaData = [];
    for (let i = 0; i < dif.length; i++) {
      const kIdx = i + offset;
      if (kIdx < 0 || kIdx >= S.primary.klines.length) continue;
      const t = Math.round(S.primary.klines[kIdx].openTime / 1000);
      histData.push({ time: t, value: histogram[i], color: histogram[i] >= 0 ? '#26a69a' : '#ef5350' });
      difData.push({ time: t, value: dif[i] });
      deaData.push({ time: t, value: dea[i] });
    }
    lcMacdHistSeries.setData(histData);
    lcDifSeries.setData(difData);
    lcDeaSeries.setData(deaData);
  } else {
    lcMacdHistSeries.setData([]);
    lcDifSeries.setData([]);
    lcDeaSeries.setData([]);
  }
}

// ====== Coordinate Bridge ======
function tpToLCPoint(tpIdx) {
  if (!lcCandleSeries || !S.primary.fractals) return null;
  const price = S.primary.turningPoints[tpIdx];
  if (tpIdx >= S.primary.fractals.length) return null;
  const klineIdx = S.primary.fractals[tpIdx].klineIdx;
  if (klineIdx === undefined || klineIdx >= S.primary.klines.length) return null;
  const lcTime = Math.round(S.primary.klines[klineIdx].openTime / 1000);
  const x = lcCandleSeries.timeToCoordinate(lcTime);
  const y = lcCandleSeries.priceToCoordinate(price);
  if (x === null || y === null) return null;
  return { x, y, price };
}

function rebuildChartCoords() {
  S.chartCoords = S.primary.turningPoints.map((p, i) => {
    if (S.primary.klines && S.primary.klines.length > 0) {
      const pt = tpToLCPoint(i);
      if (pt) return pt;
    }
    return { x: -1000, y: -1000, price: p };
  });
}

function lcPriceToY(price) {
  if (!lcCandleSeries) return null;
  return lcCandleSeries.priceToCoordinate(price);
}

function lcTimeToX(timestamp) {
  if (!lcCandleSeries) return null;
  return lcCandleSeries.timeToCoordinate(Math.round(timestamp / 1000));
}

// ====== Viewport change handler ======
function onLCVisibleRangeChange(range) {
  if (!range) return;
  // Left edge detection
  if (range.from < 20 && !S.loadingOlder && S.primary.klines) {
    loadOlderKlines();
  }
  // Schedule overlay redraw
  if (!lcOverlayScheduled) {
    lcOverlayScheduled = true;
    requestAnimationFrame(() => {
      lcOverlayScheduled = false;
      drawOverlay();
    });
  }
}

// ====== Main drawChart ======
function drawChart() {
  if (S.primary.turningPoints.length < 2 && !S.primary.klines) return;
  const klineMode = !!S.primary.klines && S.primary.klines.length > 0;

  if (klineMode) {
    if (!lcChart) initLC();
    updateLCData();
    // drawOverlay will be triggered by LC's viewport change callback
    // but also call it directly for immediate render
    requestAnimationFrame(() => drawOverlay());
  } else {
    // Non-kline mode: pure SVG rendering
    drawOverlayPure();
  }
}

// ====== SVG Overlay (kline mode) ======
function drawOverlay() {
  if (S.primary.turningPoints.length < 2) return;
  clearSVG();
  const klineMode = !!S.primary.klines && S.primary.klines.length > 0;
  if (!klineMode) { drawOverlayPure(); return; }

  rebuildChartCoords();
  S.chartLayout = { klineMode: true };

  // Context period overlays
  if (S.showContext && S.context.interval && S.context.klines && S.context.klines.length > 0) {
    const ctxFractals = S.context.fractals;
    const ctxTpTime = (idx) => {
      if (ctxFractals && idx < ctxFractals.length) {
        const kIdx = ctxFractals[idx].klineIdx;
        if (kIdx < S.context.klines.length) return S.context.klines[kIdx].openTime;
      }
      return null;
    };
    S.context.zhongshu.forEach(zs => {
      const tFrom = ctxTpTime(zs.fromIdx);
      const tTo = ctxTpTime(zs.toIdx);
      if (tFrom === null || tTo === null) return;
      const x1 = lcTimeToX(tFrom), x2 = lcTimeToX(tTo);
      const zgY = lcPriceToY(zs.zg), zdY = lcPriceToY(zs.zd);
      if (x1 === null || x2 === null || zgY === null || zdY === null) return;
      chart.appendChild(svgEl("rect", {
        x: x1 - 2, y: zgY, width: x2 - x1 + 4, height: zdY - zgY,
        fill: "rgba(230,119,0,0.08)", stroke: "rgba(230,119,0,0.3)", "stroke-width": 2,
        rx: 3, class: "ctx-zs-rect"
      }));
    });
    S.context.segments.forEach(seg => {
      const tFrom = ctxTpTime(seg.fromIdx);
      const tTo = ctxTpTime(seg.toIdx);
      if (tFrom === null || tTo === null) return;
      const x1 = lcTimeToX(tFrom), x2 = lcTimeToX(tTo);
      if (x1 === null || x2 === null) return;
      const pFrom = S.context.turningPoints[seg.fromIdx];
      const pTo = S.context.turningPoints[seg.toIdx];
      const y1 = lcPriceToY(pFrom), y2 = lcPriceToY(pTo);
      if (y1 === null || y2 === null) return;
      const isUp = pTo > pFrom;
      chart.appendChild(svgEl("line", {
        x1, y1, x2, y2,
        stroke: isUp ? "rgba(47,158,68,0.5)" : "rgba(201,42,42,0.5)",
        "stroke-width": 4, "stroke-linecap": "round", class: "ctx-seg-line"
      }));
    });
  }

  // Zhongshu + Segment zhongshu
  drawZhongshuRectangles();
  if (S.showSegZs) drawSegmentZhongshuRects();

  // Segments
  S.primary.segments.forEach((seg, i) => drawSegmentLine(seg.fromIdx, seg.toIdx, i));

  // Zigzag strokes
  if (S.primary.strokes.length >= 1) {
    S.primary.strokes.forEach((s) => {
      if (s.fromIdx === null || s.fromIdx === undefined) return;
      const from = S.chartCoords[s.fromIdx], to = S.chartCoords[s.toIdx];
      if (!from || !to || from.x < 0 || to.x < 0) return;
      const hidden = S.deletedTurningPoints.has(s.fromIdx) || S.deletedTurningPoints.has(s.toIdx);
      if (!hidden) {
        chart.appendChild(svgEl("line", {
          x1: from.x, y1: from.y, x2: to.x, y2: to.y,
          stroke: "rgba(255,255,255,0.7)", "stroke-width": 1,
          "stroke-linecap": "round"
        }));
      }
      chart.appendChild(svgEl("line", {
        x1: from.x, y1: from.y, x2: to.x, y2: to.y,
        stroke: "transparent", "stroke-width": 14,
        class: "stroke-hit", "data-stroke-idx": s.toIdx,
        style: hidden ? "cursor:default" : "cursor:pointer"
      }));
    });
  }

  // Turning point dots
  S.primary.turningPoints.forEach((p, i) => {
    if (S.deletedTurningPoints.has(i)) return;
    const c = S.chartCoords[i];
    if (!c || c.x < 0) return;

    const isTop = i > 0 && i < S.primary.turningPoints.length - 1 && S.primary.turningPoints[i] > S.primary.turningPoints[i-1] && S.primary.turningPoints[i] > S.primary.turningPoints[i+1];
    const isBottom = i > 0 && i < S.primary.turningPoints.length - 1 && S.primary.turningPoints[i] < S.primary.turningPoints[i-1] && S.primary.turningPoints[i] < S.primary.turningPoints[i+1];
    const dotColor = isTop ? "#ff6b6b" : isBottom ? "#51cf66" : "#00e5ff";
    chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 5, fill: dotColor, stroke: "#fff", "stroke-width": 1, class: "tp-dot", "data-idx": i, style: "cursor:pointer" }));
    const ly = isTop ? c.y - 10 : isBottom ? c.y + 16 : c.y - 10;
    const lbl = svgEl("text", { x: c.x, y: ly, fill: dotColor, "font-size": 10, "text-anchor": "middle", "font-family": "SF Mono,Menlo,monospace", class: "tp-label", "data-idx": i });
    lbl.textContent = Math.round(p * 100) / 100;
    chart.appendChild(lbl);
    // Hit area
    const hitCircle = svgEl("circle", { cx: c.x, cy: c.y, r: 10, fill: "transparent", stroke: "none", class: "tp-hit", "data-idx": i, style: "cursor:pointer" });
    const tipEl = svgEl("title", {});
    tipEl.textContent = Math.round(p * 100) / 100;
    hitCircle.appendChild(tipEl);
    chart.appendChild(hitCircle);
  });

  // Buy/sell markers
  if (S.showBuySell) drawBuySellMarkers();

  // Higher-level segments
  drawHigherSegmentLines();

  // Divergence lines on MACD pane
  if (S.primary.divergencePoints.length && lcDifSeries) {
    S.primary.divergencePoints.forEach(div => {
      const k1 = S.primary.klines[div.compareKlineIdx];
      const k2 = S.primary.klines[div.klineIdx];
      if (!k1 || !k2) return;
      const x1 = lcDifSeries.timeToCoordinate(Math.round(k1.openTime / 1000));
      const x2 = lcDifSeries.timeToCoordinate(Math.round(k2.openTime / 1000));
      const y1 = lcDifSeries.priceToCoordinate(S.primary.macd.dif[div.compareKlineIdx - S.macdOffset]);
      const y2 = lcDifSeries.priceToCoordinate(S.primary.macd.dif[div.klineIdx - S.macdOffset]);
      if (x1 === null || x2 === null || y1 === null || y2 === null) return;
      const isTop = div.type === 'top';
      const color = isTop ? "#ff1744" : "#00c853";
      chart.appendChild(svgEl("line", { x1, y1, x2, y2, stroke: color, "stroke-width": 1.5, opacity: 0.9, class: "div-line" }));
      chart.appendChild(svgEl("circle", { cx: x1, cy: y1, r: 3, fill: color, opacity: 0.9, class: "div-line" }));
      chart.appendChild(svgEl("circle", { cx: x2, cy: y2, r: 3, fill: color, opacity: 0.9, class: "div-line" }));
      const midX = (x1 + x2) / 2, midY = (y1 + y2) / 2;
      const tag = isTop ? "顶背驰" : "底背驰";
      const bg = svgEl("rect", { x: midX - 22, y: midY - 16, width: 44, height: 16, rx: 3, fill: color, opacity: 0.85, class: "div-line" });
      chart.appendChild(bg);
      const txt = svgEl("text", { x: midX, y: midY - 6, fill: "#fff", "font-size": 10, "font-weight": "bold", "text-anchor": "middle", class: "div-line" });
      txt.textContent = tag;
      chart.appendChild(txt);
    });
  }

  // Loading indicator
  if (S.loadingOlder) {
    const indicator = svgEl("text", { x: 8, y: 20, fill: "#ffc832", "font-size": 12, "font-family": "SF Mono,Menlo,monospace", class: "loading-older-indicator" });
    indicator.textContent = "加载历史数据...";
    chart.appendChild(indicator);
  }
}

// ====== Pure SVG Overlay (non-kline mode) ======
function drawOverlayPure() {
  if (S.primary.turningPoints.length < 2) return;
  clearSVG();
  const rect = chart.parentElement.getBoundingClientRect();
  const W = rect.width, H = rect.height;
  chart.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const left = 80, right = 60, top = 30, cW = W - left - right;
  const priceH = H - top - 30;
  const minP = Math.min(...S.primary.turningPoints);
  const maxP = Math.max(...S.primary.turningPoints);
  const padding = (maxP - minP) * 0.06 || 5;
  const rangeMin = minP - padding, rangeMax = maxP + padding;
  const yScale = priceH / (rangeMax - rangeMin);
  const toY = p => top + priceH - (p - rangeMin) * yScale;
  const gap = cW / (S.primary.turningPoints.length - 1);
  const toX = i => left + i * gap;

  S.chartLayout = { top, left, cW, priceH, priceBottom: top + priceH, minP: rangeMin, maxP: rangeMax, yScale, klineMode: false, W, H };
  S.chartCoords = S.primary.turningPoints.map((p, i) => ({ x: toX(i), y: toY(p), price: p }));

  // Grid
  const dataRange = maxP - minP;
  const rawStep = dataRange / 8;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  let step = rawStep / mag < 2 ? 2 * mag : rawStep / mag < 5 ? 5 * mag : 10 * mag;
  const gridStart = Math.floor(rangeMin / step) * step;
  for (let p = gridStart; p <= rangeMax; p += step) {
    const y = toY(p);
    chart.appendChild(svgEl("line", { x1: left - 5, y1: y, x2: left + cW + 5, y2: y, stroke: "#1e3050", "stroke-width": 0.5, "stroke-dasharray": "3,3" }));
    const lbl = svgEl("text", { x: left - 10, y: y + 4, fill: "#5577aa", "font-size": 11, "text-anchor": "end", "font-family": "SF Mono,Menlo,monospace" });
    lbl.textContent = Math.round(p * 100) / 100;
    chart.appendChild(lbl);
  }

  drawZhongshuRectangles();
  if (S.showSegZs) drawSegmentZhongshuRects();
  S.primary.segments.forEach((seg, i) => drawSegmentLine(seg.fromIdx, seg.toIdx, i));

  // Strokes
  if (S.primary.strokes.length >= 1) {
    S.primary.strokes.forEach(s => {
      if (s.fromIdx === null || s.fromIdx === undefined) return;
      const hidden = S.deletedTurningPoints.has(s.fromIdx) || S.deletedTurningPoints.has(s.toIdx);
      if (!hidden) {
        chart.appendChild(svgEl("line", { x1: toX(s.fromIdx), y1: toY(S.primary.turningPoints[s.fromIdx]), x2: toX(s.toIdx), y2: toY(S.primary.turningPoints[s.toIdx]), stroke: "rgba(255,255,255,0.85)", "stroke-width": 0.8, "stroke-linecap": "round" }));
      }
      chart.appendChild(svgEl("line", { x1: toX(s.fromIdx), y1: toY(S.primary.turningPoints[s.fromIdx]), x2: toX(s.toIdx), y2: toY(S.primary.turningPoints[s.toIdx]), stroke: "transparent", "stroke-width": 14, class: "stroke-hit", "data-stroke-idx": s.toIdx, style: hidden ? "cursor:default" : "cursor:pointer" }));
    });
  }

  // Turning point dots
  S.primary.turningPoints.forEach((p, i) => {
    if (S.deletedTurningPoints.has(i)) return;
    const x = toX(i), y = toY(p);
    chart.appendChild(svgEl("circle", { cx: x, cy: y, r: 7, fill: "none", stroke: "rgba(255,255,255,0.2)", "stroke-width": 1, opacity: 0.25 }));
    chart.appendChild(svgEl("circle", { cx: x, cy: y, r: 5, fill: "#16213e", stroke: "rgba(255,255,255,0.85)", "stroke-width": 1.5, class: "tp-dot", "data-idx": i, style: "cursor:grab" }));
    const isPeak = i > 0 && i < S.primary.turningPoints.length - 1 && p > S.primary.turningPoints[i-1] && p > S.primary.turningPoints[i+1];
    const isValley = i > 0 && i < S.primary.turningPoints.length - 1 && p < S.primary.turningPoints[i-1] && p < S.primary.turningPoints[i+1];
    const ly = isPeak ? y - 14 : isValley ? y + 20 : (i === 0 ? y - 14 : y + 20);
    const lbl = svgEl("text", { x, y: ly, fill: "#99aabb", "font-size": 12, "text-anchor": "middle", "font-family": "SF Mono,Menlo,monospace", class: "tp-label", "data-idx": i });
    lbl.textContent = Math.round(p * 100) / 100;
    chart.appendChild(lbl);
    const hitCircle = svgEl("circle", { cx: x, cy: y, r: 18, fill: "transparent", stroke: "none", class: "tp-hit", "data-idx": i, style: "cursor:grab" });
    const tipEl = svgEl("title", {});
    tipEl.textContent = Math.round(p * 100) / 100;
    hitCircle.appendChild(tipEl);
    chart.appendChild(hitCircle);
  });

  if (S.showBuySell) drawBuySellMarkers();
  drawHigherSegmentLines();
}

// ====== Helper render functions ======
function drawSegmentLine(fromIdx, toIdx, segIdx) {
  const from = S.chartCoords[fromIdx], to = S.chartCoords[toIdx];
  if (!from || !to || from.x < 0 || to.x < 0) return;
  chart.appendChild(svgEl("line", {
    x1: from.x, y1: from.y, x2: to.x, y2: to.y,
    stroke: "transparent", "stroke-width": 12,
    "stroke-linecap": "round", class: "seg-hit", "data-seg-idx": segIdx, style: "cursor:pointer"
  }));
  chart.appendChild(svgEl("line", {
    x1: from.x, y1: from.y, x2: to.x, y2: to.y,
    stroke: "#4a9eff", "stroke-width": 1.5,
    "stroke-linecap": "round", opacity: 0.9, class: "seg-line", "data-seg-idx": segIdx
  }));
}

function redrawSegments() {
  chart.querySelectorAll(".seg-line,.seg-hit").forEach(el => el.remove());
  S.primary.segments.forEach((seg, i) => drawSegmentLine(seg.fromIdx, seg.toIdx, i));
  bindSegHover();
}

function bindSegHover() {
  chart.querySelectorAll('.seg-hit').forEach(el => {
    el.addEventListener('mouseenter', function() {
      const idx = this.getAttribute('data-seg-idx');
      const line = chart.querySelector(`.seg-line[data-seg-idx="${idx}"]`);
      if (line) line.classList.add('hover');
    });
    el.addEventListener('mouseleave', function() {
      const idx = this.getAttribute('data-seg-idx');
      const line = chart.querySelector(`.seg-line[data-seg-idx="${idx}"]`);
      if (line) line.classList.remove('hover');
    });
  });
  chart.querySelectorAll('.zs-rect').forEach(el => {
    el.addEventListener('mouseenter', function() { this.classList.add('hover'); });
    el.addEventListener('mouseleave', function() { this.classList.remove('hover'); });
  });
}

function drawZhongshuRectangles() {
  if (S.chartCoords.length === 0) return;
  S.primary.zhongshuList.forEach((zs, i) => {
    const from = S.chartCoords[zs.fromIdx];
    const to = S.chartCoords[zs.toIdx];
    if (!from || !to || from.x < 0 || to.x < 0) return;
    let zgY, zdY;
    if (S.chartLayout.klineMode && lcCandleSeries) {
      zgY = lcPriceToY(zs.zg);
      zdY = lcPriceToY(zs.zd);
    } else {
      zgY = S.chartLayout.priceBottom - (zs.zg - S.chartLayout.minP) * S.chartLayout.yScale;
      zdY = S.chartLayout.priceBottom - (zs.zd - S.chartLayout.minP) * S.chartLayout.yScale;
    }
    if (zgY === null || zdY === null) return;
    chart.appendChild(svgEl("rect", {
      x: from.x - 2, y: zgY, width: to.x - from.x + 4, height: zdY - zgY,
      fill: "rgba(255,255,255,0.12)", stroke: "rgba(255,255,255,0.6)", "stroke-width": 1,
      "stroke-dasharray": "6,3", rx: 3, class: "zs-rect", "data-zs-idx": i, style: "cursor:pointer"
    }));
    chart.appendChild(svgEl("line", { x1: from.x - 5, y1: zgY, x2: to.x + 5, y2: zgY, stroke: "rgba(255,255,255,0.6)", "stroke-width": 0.8, "stroke-dasharray": "4,2", class: "zs-line" }));
    chart.appendChild(svgEl("line", { x1: from.x - 5, y1: zdY, x2: to.x + 5, y2: zdY, stroke: "rgba(255,255,255,0.6)", "stroke-width": 0.8, "stroke-dasharray": "4,2", class: "zs-line" }));
  });
}

function drawSegmentZhongshuRects() {
  if (S.chartCoords.length === 0) return;
  S.primary.segmentZhongshu.forEach((zs, i) => {
    const from = S.chartCoords[zs.fromIdx];
    const to = S.chartCoords[zs.toIdx];
    if (!from || !to || from.x < 0 || to.x < 0) return;
    let zgY, zdY;
    if (S.chartLayout.klineMode && lcCandleSeries) {
      zgY = lcPriceToY(zs.zg);
      zdY = lcPriceToY(zs.zd);
    } else {
      zgY = S.chartLayout.priceBottom - (zs.zg - S.chartLayout.minP) * S.chartLayout.yScale;
      zdY = S.chartLayout.priceBottom - (zs.zd - S.chartLayout.minP) * S.chartLayout.yScale;
    }
    if (zgY === null || zdY === null) return;
    chart.appendChild(svgEl("rect", {
      x: from.x - 2, y: zgY, width: to.x - from.x + 4, height: zdY - zgY,
      fill: "rgba(74,158,255,0.08)", stroke: "rgba(74,158,255,0.6)", "stroke-width": 1.2,
      "stroke-dasharray": "6,3", rx: 3, class: "seg-zs-rect", "data-seg-zs-idx": i, style: "cursor:pointer"
    }));
    chart.appendChild(svgEl("line", { x1: from.x - 5, y1: zgY, x2: to.x + 5, y2: zgY, stroke: "rgba(74,158,255,0.6)", "stroke-width": 0.8, "stroke-dasharray": "4,2", class: "seg-zs-line" }));
    chart.appendChild(svgEl("line", { x1: from.x - 5, y1: zdY, x2: to.x + 5, y2: zdY, stroke: "rgba(74,158,255,0.6)", "stroke-width": 0.8, "stroke-dasharray": "4,2", class: "seg-zs-line" }));
  });
}

function drawHigherSegmentLines() {
  if (S.chartCoords.length === 0) return;
  S.primary.higherSegments.forEach((seg, i) => {
    const from = S.chartCoords[seg.fromIdx];
    const to = S.chartCoords[seg.toIdx];
    if (!from || !to || from.x < 0 || to.x < 0) return;
    chart.appendChild(svgEl("line", {
      x1: from.x, y1: from.y, x2: to.x, y2: to.y,
      stroke: "transparent", "stroke-width": 12,
      "stroke-linecap": "round", class: "higher-hit", "data-higher-idx": i, style: "cursor:pointer"
    }));
    chart.appendChild(svgEl("line", {
      x1: from.x, y1: from.y, x2: to.x, y2: to.y,
      stroke: "#ff6b6b", "stroke-width": 2,
      "stroke-linecap": "round", "stroke-dasharray": "8,4", class: "higher-line", opacity: 0.85
    }));
  });
}

function redrawZhongshu() {
  chart.querySelectorAll('.zs-rect, .zs-line, .zs-label, .seg-zs-rect, .seg-zs-line, .bs-marker, .div-line, .higher-line, .higher-hit').forEach(el => el.remove());
  drawZhongshuRectangles();
  if (S.showSegZs) drawSegmentZhongshuRects();
  if (S.showBuySell) drawBuySellMarkers();
  drawHigherSegmentLines();
}

// ====== Interaction ======
function setSVGPointerEvents(enabled) {
  chart.style.pointerEvents = enabled ? 'auto' : 'none';
}

function setSegHitEvents(enabled) {
  chart.querySelectorAll('.seg-hit, .zs-rect, .seg-zs-rect, .higher-hit, .stroke-hit').forEach(el => {
    el.style.pointerEvents = enabled ? '' : 'none';
  });
}

function toggleDraw() {
  S.drawingMode = !S.drawingMode;
  S.drawStart = null;
  const btn = document.getElementById('drawBtn');
  const hint = document.getElementById('drawHint');
  if (S.drawingMode) {
    if (S.drawZsMode) toggleDrawZhongshu();
    if (S.drawSegZsMode) toggleDrawSegZs();
    if (S.drawHigherMode) toggleDrawHigher();
    if (S.drawStrokeMode) toggleDrawStroke();
    btn.textContent = '停止手动画';
    hint.textContent = '画段模式：点击起点 → 点击终点';
    hint.style.display = 'block';
    setSegHitEvents(false);
    setSVGPointerEvents(true);
  } else {
    btn.textContent = '手动画段';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
    setSVGPointerEvents(false);
  }
}

function toggleDrawZhongshu() {
  S.drawZsMode = !S.drawZsMode;
  S.zsDrawStart = null;
  const btn = document.getElementById('drawZsBtn');
  const hint = document.getElementById('drawHint');
  if (S.drawZsMode) {
    if (S.drawingMode) toggleDraw();
    if (S.drawSegZsMode) toggleDrawSegZs();
    if (S.drawHigherMode) toggleDrawHigher();
    if (S.drawStrokeMode) toggleDrawStroke();
    btn.textContent = '停止手动画';
    hint.textContent = '画中枢模式：点击起点 → 点击终点';
    hint.style.display = 'block';
    setSegHitEvents(false);
    setSVGPointerEvents(true);
  } else {
    btn.textContent = '手动画中枢';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
    setSVGPointerEvents(false);
  }
}

function toggleDrawSegZs() {
  S.drawSegZsMode = !S.drawSegZsMode;
  S.segZsDrawStart = null;
  const btn = document.getElementById('drawSegZsBtn');
  const hint = document.getElementById('drawHint');
  if (S.drawSegZsMode) {
    if (S.drawingMode) toggleDraw();
    if (S.drawZsMode) toggleDrawZhongshu();
    if (S.drawHigherMode) toggleDrawHigher();
    if (S.drawStrokeMode) toggleDrawStroke();
    btn.textContent = '停止手动画';
    hint.textContent = '画段中枢模式：点击起点 → 点击终点';
    hint.style.display = 'block';
    setSegHitEvents(false);
    setSVGPointerEvents(true);
  } else {
    btn.textContent = '手动画';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
    setSVGPointerEvents(false);
  }
}

function toggleDrawHigher() {
  S.drawHigherMode = !S.drawHigherMode;
  S.higherDrawStart = null;
  const btn = document.getElementById('drawHigherBtn');
  const hint = document.getElementById('drawHint');
  if (S.drawHigherMode) {
    if (S.drawingMode) toggleDraw();
    if (S.drawZsMode) toggleDrawZhongshu();
    if (S.drawSegZsMode) toggleDrawSegZs();
    if (S.drawStrokeMode) toggleDrawStroke();
    btn.textContent = '停止手动画';
    hint.textContent = '画段的段模式：点击起点 → 点击终点';
    hint.style.display = 'block';
    setSegHitEvents(false);
    setSVGPointerEvents(true);
  } else {
    btn.textContent = '手动画';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
    setSVGPointerEvents(false);
  }
}

function undoSegZs() {
  if (S.primary.segmentZhongshu.length === 0) return;
  S.primary.segmentZhongshu.pop();
  drawChartAndSave();
  renderSegZsList();
  document.getElementById('undoSegZsBtn').disabled = S.primary.segmentZhongshu.length === 0;
}

function removeSegZs(i) {
  S.primary.segmentZhongshu.splice(i, 1);
  drawChartAndSave();
  renderSegZsList();
  document.getElementById('undoSegZsBtn').disabled = S.primary.segmentZhongshu.length === 0;
}

function undoHigher() {
  if (S.primary.higherSegments.length === 0) return;
  S.primary.higherSegments.pop();
  drawChartAndSave();
  renderHigherList();
  document.getElementById('undoHigherBtn').disabled = S.primary.higherSegments.length === 0;
}

function removeHigher(i) {
  S.primary.higherSegments.splice(i, 1);
  drawChartAndSave();
  renderHigherList();
  document.getElementById('undoHigherBtn').disabled = S.primary.higherSegments.length === 0;
}

function findSnapPoint(clientX, clientY) {
  if (!S.primary.klines || !lcCandleSeries) return null;
  let bestDist = Infinity, bestIdx = 0, useHigh = true;
  for (let ki = 0; ki < S.primary.klines.length; ki++) {
    const k = S.primary.klines[ki];
    const t = Math.round(k.openTime / 1000);
    const x = lcCandleSeries.timeToCoordinate(t);
    if (x === null) continue;
    const dx = Math.abs(clientX - x);
    if (dx < bestDist) {
      bestDist = dx;
      bestIdx = ki;
      const yH = lcCandleSeries.priceToCoordinate(k.high);
      const yL = lcCandleSeries.priceToCoordinate(k.low);
      if (yH !== null && yL !== null) useHigh = Math.abs(clientY - yH) < Math.abs(clientY - yL);
    }
  }
  const k = S.primary.klines[bestIdx];
  const price = useHigh ? k.high : k.low;
  const x = lcCandleSeries.timeToCoordinate(Math.round(k.openTime / 1000));
  const y = lcCandleSeries.priceToCoordinate(price);
  if (x === null || y === null) return null;
  return { x, y, price, klineIdx: bestIdx, useHigh };
}

function toggleDrawStroke() {
  S.drawStrokeMode = !S.drawStrokeMode;
  S.strokeDrawLastIdx = null;
  const btn = document.getElementById('drawStrokeBtn');
  const hint = document.getElementById('drawHint');
  if (S.drawStrokeMode) {
    if (S.drawingMode) toggleDraw();
    if (S.drawZsMode) toggleDrawZhongshu();
    if (S.drawSegZsMode) toggleDrawSegZs();
    if (S.drawHigherMode) toggleDrawHigher();
    btn.textContent = '停止手动画';
    hint.textContent = '画笔模式：点击图表，吸附最近K线的顶或底';
    hint.style.display = 'block';
    chart.querySelectorAll('.snap-preview').forEach(el => el.remove());
    setSegHitEvents(false);
    setSVGPointerEvents(true);
  } else {
    btn.textContent = '手动画笔';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight, .snap-preview').forEach(el => el.remove());
    setSegHitEvents(true);
    setSVGPointerEvents(false);
  }
}

function undoStrokeDraw() {
  if (S.primary.turningPoints.length === 0) return;
  S.primary.strokes.pop();
  S.primary.turningPoints.pop();
  if (S.primary.fractals && S.primary.fractals.length > S.primary.turningPoints.length) {
    S.primary.fractals.pop();
  }
  S.primary.segments = S.primary.segments.filter(s => s.fromIdx < S.primary.turningPoints.length && s.toIdx < S.primary.turningPoints.length);
  S.primary.zhongshuList = S.primary.zhongshuList.filter(z => z.fromIdx < S.primary.turningPoints.length && z.toIdx < S.primary.turningPoints.length);
  S.primary.segmentZhongshu = S.primary.segmentZhongshu.filter(s => s.fromIdx < S.primary.turningPoints.length && s.toIdx < S.primary.turningPoints.length);
  S.primary.higherSegments = S.primary.higherSegments.filter(s => s.fromIdx < S.primary.turningPoints.length && s.toIdx < S.primary.turningPoints.length);
  document.getElementById('undoStrokeBtn').disabled = S.primary.turningPoints.length === 0;
  renderStrokeList();
  drawChartAndSave();
}

// ====== Click handler ======
chart.addEventListener('click', function(e) {
  if (S.isDragging || S.isDraggingZs) return;
  const noDrawMode = !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode && !S.drawStrokeMode;

  const strokeHit = e.target.closest('.stroke-hit');
  if (strokeHit && noDrawMode) {
    const idx = parseInt(strokeHit.getAttribute('data-stroke-idx'));
    if (!isNaN(idx) && idx > 0 && idx < S.primary.turningPoints.length) {
      S.deletedTurningPoints.add(idx - 1);
      S.deletedTurningPoints.add(idx);
      drawChart();
    }
    return;
  }

  const tpHit = e.target.closest('.tp-dot, .tp-hit');
  if (tpHit && noDrawMode) {
    const idx = parseInt(tpHit.getAttribute('data-idx'));
    if (!isNaN(idx) && idx < S.primary.turningPoints.length) {
      removeStroke(idx);
    }
    return;
  }

  const segHit = e.target.closest('.seg-hit');
  if (segHit && noDrawMode) {
    const idx = parseInt(segHit.getAttribute('data-seg-idx'));
    if (!isNaN(idx) && idx < S.primary.segments.length) {
      S.primary.segments.splice(idx, 1);
      redrawSegments();
      document.getElementById('undoSegBtn').disabled = S.primary.segments.length === 0;
    }
    return;
  }

  const zsRect = e.target.closest('.zs-rect');
  if (zsRect && noDrawMode) {
    const idx = parseInt(zsRect.getAttribute('data-zs-idx'));
    if (!isNaN(idx) && idx < S.primary.zhongshuList.length) {
      S.primary.zhongshuList.splice(idx, 1);
      drawChart();
      document.getElementById('undoZsBtn').disabled = S.primary.zhongshuList.length === 0;
    }
    return;
  }

  const segZsRect = e.target.closest('.seg-zs-rect');
  if (segZsRect && noDrawMode) {
    const idx = parseInt(segZsRect.getAttribute('data-seg-zs-idx'));
    if (!isNaN(idx) && idx < S.primary.segmentZhongshu.length) {
      S.primary.segmentZhongshu.splice(idx, 1);
      drawChart();
      renderSegZsList();
      document.getElementById('undoSegZsBtn').disabled = S.primary.segmentZhongshu.length === 0;
    }
    return;
  }

  const higherHit = e.target.closest('.higher-hit');
  if (higherHit && noDrawMode) {
    const idx = parseInt(higherHit.getAttribute('data-higher-idx'));
    if (!isNaN(idx) && idx < S.primary.higherSegments.length) {
      S.primary.higherSegments.splice(idx, 1);
      drawChart();
      renderHigherList();
      document.getElementById('undoHigherBtn').disabled = S.primary.higherSegments.length === 0;
    }
    return;
  }

  // Manual stroke drawing
  if (S.drawStrokeMode) {
    if (!S.primary.klines || !lcCandleSeries) return;
    const snap = findSnapPoint(e.clientX, e.clientY);
    if (!snap) return;
    const price = snap.price;
    const snapKlineIdx = snap.klineIdx;

    let dir;
    const isManualFirst = S.strokeDrawLastIdx === null;
    if (isManualFirst) {
      dir = 'down';
    } else {
      const lastPrice = S.primary.turningPoints[S.strokeDrawLastIdx];
      dir = price > lastPrice ? 'up' : 'down';
    }

    S.primary.turningPoints.push(price);
    if (S.primary.fractals && snapKlineIdx !== null && snapKlineIdx < S.primary.klines.length) {
      S.primary.fractals.push({ klineIdx: snapKlineIdx, type: dir === 'up' ? 'top' : 'bottom', price, time: S.primary.klines[snapKlineIdx].openTime });
    }
    if (!isManualFirst) {
      S.primary.strokes.push({ dir, val: price, fromIdx: S.strokeDrawLastIdx, toIdx: S.primary.turningPoints.length - 1 });
    }
    S.strokeDrawLastIdx = S.primary.turningPoints.length - 1;
    document.getElementById('undoStrokeBtn').disabled = false;
    renderStrokeList();
    drawChart();
    return;
  }

  if (noDrawMode) return;
  const target = e.target.closest('[data-idx]');
  if (!target) return;
  const idx = parseInt(target.getAttribute('data-idx'));

  if (S.drawingMode) {
    if (S.drawStart === null) {
      S.drawStart = idx;
      const c = S.chartCoords[idx];
      if (c) chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
    } else {
      if (idx === S.drawStart) return;
      S.primary.segments.push({ fromIdx: S.drawStart, toIdx: idx });
      S.drawStart = null;
      chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
      redrawSegments();
      document.getElementById('undoSegBtn').disabled = false;
    }
  } else if (S.drawZsMode) {
    if (S.zsDrawStart === null) {
      S.zsDrawStart = idx;
      const c = S.chartCoords[idx];
      if (c) chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
    } else {
      if (idx === S.zsDrawStart) return;
      const fromIdx = Math.min(S.zsDrawStart, idx);
      const toIdx = Math.max(S.zsDrawStart, idx);
      const tp = S.primary.turningPoints;
      let minHigh = Infinity, maxLow = -Infinity;
      for (let i = fromIdx; i < toIdx; i++) {
        minHigh = Math.min(minHigh, Math.max(tp[i], tp[i+1]));
        maxLow = Math.max(maxLow, Math.min(tp[i], tp[i+1]));
      }
      if (minHigh > maxLow) {
        S.primary.zhongshuList.push({fromIdx, toIdx, zg: minHigh, zd: maxLow});
        document.getElementById('undoZsBtn').disabled = false;
      }
      S.zsDrawStart = null;
      chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
      drawChart();
    }
  } else if (S.drawSegZsMode) {
    if (S.segZsDrawStart === null) {
      S.segZsDrawStart = idx;
      const c = S.chartCoords[idx];
      if (c) chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
    } else {
      if (idx === S.segZsDrawStart) return;
      const fromIdx = Math.min(S.segZsDrawStart, idx);
      const toIdx = Math.max(S.segZsDrawStart, idx);
      const inRangeSegs = S.primary.segments.filter(s => s.fromIdx >= fromIdx && s.toIdx <= toIdx);
      if (inRangeSegs.length >= 3) {
        let minHigh = Infinity, maxLow = -Infinity;
        for (const seg of inRangeSegs) {
          const segHigh = Math.max(S.primary.turningPoints[seg.fromIdx], S.primary.turningPoints[seg.toIdx]);
          const segLow = Math.min(S.primary.turningPoints[seg.fromIdx], S.primary.turningPoints[seg.toIdx]);
          minHigh = Math.min(minHigh, segHigh);
          maxLow = Math.max(maxLow, segLow);
        }
        if (minHigh > maxLow) {
          S.primary.segmentZhongshu.push({
            fromIdx: inRangeSegs[0].fromIdx,
            toIdx: inRangeSegs[inRangeSegs.length - 1].toIdx,
            zg: minHigh, zd: maxLow
          });
          document.getElementById('undoSegZsBtn').disabled = false;
        }
      }
      S.segZsDrawStart = null;
      chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
      drawChart();
      renderSegZsList();
    }
  } else if (S.drawHigherMode) {
    if (S.higherDrawStart === null) {
      S.higherDrawStart = idx;
      const c = S.chartCoords[idx];
      if (c) chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
    } else {
      if (idx === S.higherDrawStart) return;
      S.primary.higherSegments.push({ fromIdx: S.higherDrawStart, toIdx: idx });
      S.higherDrawStart = null;
      chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
      drawChart();
      renderHigherList();
      document.getElementById('undoHigherBtn').disabled = false;
    }
  }
});

function undoSegment() {
  if (S.primary.segments.length === 0) return;
  S.primary.segments.pop();
  redrawSegments();
  renderSegList();
  document.getElementById('undoSegBtn').disabled = S.primary.segments.length === 0;
  autoSaveAnnotation();
}

function removeSegment(i) {
  S.primary.segments.splice(i, 1);
  redrawSegments();
  renderSegList();
  document.getElementById('undoSegBtn').disabled = S.primary.segments.length === 0;
  autoSaveAnnotation();
}

function undoZhongshu() {
  if (S.primary.zhongshuList.length === 0) return;
  S.primary.zhongshuList.pop();
  drawChartAndSave();
  renderZhongshuList();
  document.getElementById('undoZsBtn').disabled = S.primary.zhongshuList.length === 0;
}

function removeZhongshu(i) {
  S.primary.zhongshuList.splice(i, 1);
  drawChartAndSave();
  renderZhongshuList();
  document.getElementById('undoZsBtn').disabled = S.primary.zhongshuList.length === 0;
}

// ====== Drag (turning point + zhongshu edge) ======
function yToPrice(y) {
  if (S.chartLayout && !S.chartLayout.klineMode) {
    return S.chartLayout.minP + (S.chartLayout.priceBottom - y) / S.chartLayout.yScale;
  }
  if (lcCandleSeries) return lcCandleSeries.coordinateToPrice(y);
  return 0;
}

chart.addEventListener('mousedown', function(e) {
  const tpTarget = e.target.closest('.tp-hit, .tp-dot');
  if (tpTarget && !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode) {
    const idx = parseInt(tpTarget.getAttribute('data-idx'));
    if (isNaN(idx)) return;
    S.isDragging = true;
    S.dragIdx = idx;
    e.preventDefault();
    chart.querySelectorAll(`[data-idx="${idx}"].tp-dot`).forEach(d => { d.setAttribute('r', 7); d.setAttribute('fill', '#00d4ff'); d.style.cursor = 'grabbing'; });
    chart.querySelectorAll(`[data-idx="${idx}"].tp-hit`).forEach(h => h.style.cursor = 'grabbing');
    return;
  }

  const zsRect = e.target.closest('.zs-rect');
  if (zsRect && !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode) {
    const zsIdx = parseInt(zsRect.getAttribute('data-zs-idx'));
    if (!isNaN(zsIdx) && zsIdx < S.primary.zhongshuList.length) {
      const zs = S.primary.zhongshuList[zsIdx];
      const zgY = lcPriceToY(zs.zg);
      const zdY = lcPriceToY(zs.zd);
      if (zgY !== null && zdY !== null) {
        if (Math.abs(e.clientY - zgY) < 15) {
          S.isDraggingZs = true; S.zsDragIdx = zsIdx; S.zsDragEdge = 'top';
          e.preventDefault(); return;
        } else if (Math.abs(e.clientY - zdY) < 15) {
          S.isDraggingZs = true; S.zsDragIdx = zsIdx; S.zsDragEdge = 'bottom';
          e.preventDefault(); return;
        }
      }
    }
  }
});

document.addEventListener('mousemove', function(e) {
  if (S.isDragging && S.dragIdx >= 0) {
    const price = yToPrice(e.clientY);
    if (!price) return;
    const clampedY = lcCandleSeries ? lcCandleSeries.priceToCoordinate(price) : e.clientY;
    if (clampedY === null) return;
    chart.querySelectorAll(`[data-idx="${S.dragIdx}"].tp-dot`).forEach(d => d.setAttribute('cy', clampedY));
    chart.querySelectorAll(`[data-idx="${S.dragIdx}"].tp-hit`).forEach(h => h.setAttribute('cy', clampedY));
    const label = chart.querySelector(`[data-idx="${S.dragIdx}"].tp-label`);
    if (label) {
      label.textContent = Math.round(price * 100) / 100;
      const prices = S.primary.turningPoints, i = S.dragIdx;
      const isPeak = i > 0 && i < prices.length - 1 && prices[i] > prices[i-1] && prices[i] > prices[i+1];
      const ly = isPeak ? clampedY - 14 : clampedY + 20;
      label.setAttribute('y', ly);
    }
    return;
  }

  if (S.isDraggingZs && S.zsDragIdx >= 0) {
    const price = Math.round(yToPrice(e.clientY) * 100) / 100;
    const zs = S.primary.zhongshuList[S.zsDragIdx];
    if (S.zsDragEdge === 'top') {
      zs.zg = Math.max(price, zs.zd + 0.01);
    } else {
      zs.zd = Math.min(price, zs.zg - 0.01);
    }
    redrawZhongshu();
    renderZhongshuList();
    return;
  }
});

document.addEventListener('mouseup', function(e) {
  if (S.isDragging && S.dragIdx >= 0) {
    const newPrice = Math.round(yToPrice(e.clientY) * 100) / 100;
    S.primary.turningPoints[S.dragIdx] = newPrice;
    if (S.dragIdx < S.primary.strokes.length) {
      S.primary.strokes[S.dragIdx].val = newPrice;
    }
    S.isDragging = false;
    S.dragIdx = -1;
    renderStrokeList();
    drawChart();
    return;
  }

  if (S.isDraggingZs && S.zsDragIdx >= 0) {
    S.isDraggingZs = false;
    S.zsDragIdx = -1;
    S.zsDragEdge = null;
    drawChart();
    return;
  }
});

function updateZigzagPath(changedIdx, newY) {
  // For non-kline mode only
  if (!S.chartLayout || S.chartLayout.klineMode) return;
  const path = chart.querySelector('path:not(.seg-line)');
  if (!path) return;
  const prices = S.primary.turningPoints;
  const toY = p => S.chartLayout.priceBottom - (p - S.chartLayout.minP) * S.chartLayout.yScale;
  const gap = S.chartLayout.cW / (prices.length - 1);
  const toX = i => S.chartLayout.left + i * gap;
  let d = `M ${toX(0)} ${changedIdx === 0 ? newY : toY(prices[0])}`;
  for (let i = 1; i < prices.length; i++) {
    const y = i === changedIdx ? newY : toY(prices[i]);
    d += ` L ${toX(i)} ${y}`;
  }
  path.setAttribute('d', d);
}

window.addEventListener('resize', () => {
  if (lcChart) lcChart.timeScale().fitContent();
  if (S.primary.turningPoints.length >= 2) drawChart();
});

// ====== Auto-load on page load ======
document.addEventListener('DOMContentLoaded', async () => {
  const statusEl = document.getElementById('binanceStatus');
  try {
    let status;
    do {
      const resp = await fetch('/api/prefetch/status');
      status = await resp.json();
      if (!status.complete) {
        const done = Object.values(status.intervals || {}).filter(v => v !== 'pending').length;
        const total = Object.keys(status.intervals || {}).length;
        statusEl.textContent = `数据预热中... (${done}/${total})`;
        statusEl.style.color = '#ffc832';
        await new Promise(r => setTimeout(r, 2000));
      }
    } while (!status.complete);

    statusEl.textContent = '预热完成，加载中...';
    statusEl.style.color = '#ffc832';
    await loadBinanceKlines();
  } catch (err) {
    statusEl.textContent = '自动加载失败: ' + err.message;
    statusEl.style.color = '#ff6b6b';
  }
});
