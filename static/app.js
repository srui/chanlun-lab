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
  klineViewStart: 0,
  klineViewEnd: 0,
  isPanning: false,
  panStartX: 0,
  panViewStart: 0,
  panViewEnd: 0,
  autoRefresh: false,
  autoRefreshTimer: null,
  lastSignalState: null,
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
  S.klineViewStart = 0;
  S.klineViewEnd = 0;
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
async function loadBinanceKlines() {
  const symbol = document.getElementById('binanceSymbol').value.trim().toUpperCase();
  const interval = document.getElementById('binanceInterval').value;
  const limit = parseInt(document.getElementById('binanceCount').value) || 200;
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
  S.klineViewStart = 0;
  S.klineViewEnd = 0;
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

// ====== SVG Drawing ======
const SVG_NS = "http://www.w3.org/2000/svg";
const chart = document.getElementById('chart');

function svgEl(tag, attrs) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

function clearSVG() {
  while (chart.firstChild) chart.removeChild(chart.firstChild);
  S.chartCoords = [];
}

function drawChart() {
  if (S.primary.turningPoints.length < 2) return;
  clearSVG();
  const rect = chart.parentElement.getBoundingClientRect();
  const W = rect.width, H = rect.height;
  chart.setAttribute('viewBox', `0 0 ${W} ${H}`);

  const klineMode = !!S.primary.klines && S.primary.klines.length > 0;
  const left = 80, right = 60, top = 30;

  // Split into price area + MACD area
  const macdH = klineMode ? Math.max(100, H * 0.22) : 0;
  const macdGap = klineMode ? 20 : 0;  // gap between panels
  const priceH = H - top - 30 - macdH - macdGap;
  const macdTop = top + priceH + macdGap;
  const cW = W - left - right;

  // === Price range ===
  let minP, maxP;
  let visStart = 0, visEnd = 0, visibleKlines = S.primary.klines;
  if (klineMode) {
    const totalKlines = S.primary.klines.length;
    if (S.klineViewEnd > S.klineViewStart) {
      visStart = Math.max(0, Math.floor(S.klineViewStart));
      visEnd = Math.min(totalKlines, Math.ceil(S.klineViewEnd));
    } else {
      visStart = 0;
      visEnd = totalKlines;
    }
    visibleKlines = S.primary.klines.slice(visStart, visEnd);
    if (S.showKlines) {
      minP = Math.min(...visibleKlines.map(k => k.low), ...S.primary.turningPoints);
      maxP = Math.max(...visibleKlines.map(k => k.high), ...S.primary.turningPoints);
    } else {
      minP = Math.min(...S.primary.turningPoints);
      maxP = Math.max(...S.primary.turningPoints);
    }
  } else {
    minP = Math.min(...S.primary.turningPoints);
    maxP = Math.max(...S.primary.turningPoints);
  }
  const padding = (maxP - minP) * 0.06 || 5;
  const rangeMin = minP - padding;
  const rangeMax = maxP + padding;
  const range = rangeMax - rangeMin;
  const yScale = priceH / range;
  const toY = p => top + priceH - (p - rangeMin) * yScale;

  // === X-axis ===
  let toX, tpKlineIdx = null, klineBarW = 0, timeMin = 0, timeRange = 1;
  if (klineMode) {
    timeMin = visibleKlines[0].openTime;
    const timeMax = visibleKlines[visibleKlines.length - 1].closeTime;
    timeRange = timeMax - timeMin || 1;
    const timeToX = t => left + (t - timeMin) / timeRange * cW;
    // Build tpKlineIdx: map turning point index -> kline index
    tpKlineIdx = S.primary.fractals ? S.primary.fractals.map(f => f.klineIdx) : [];
    toX = i => {
      if (tpKlineIdx && i < tpKlineIdx.length && tpKlineIdx[i] < S.primary.klines.length) {
        return timeToX(S.primary.klines[tpKlineIdx[i]].openTime);
      }
      return left + i * (cW / Math.max(S.primary.turningPoints.length - 1, 1));
    };
    // Bar width from typical kline interval
    const interval = S.primary.klines.length > 1 ? S.primary.klines[1].openTime - S.primary.klines[0].openTime : 60000;
    klineBarW = Math.max(1, (interval / timeRange) * cW * 0.8);
  } else {
    const gap = cW / (S.primary.turningPoints.length - 1);
    toX = i => left + i * gap;
  }

  // Store layout for other functions
  S.chartLayout = {
    top, left, right, cW,
    priceH, priceBottom: top + priceH,
    macdTop, macdH, macdBottom: macdTop + macdH,
    minP: rangeMin, maxP: rangeMax, yScale,
    klineMode, W, H,
    timeMin, timeRange, klineBarW, tpKlineIdx,
    visStart, visEnd, totalKlines: S.primary.klines ? S.primary.klines.length : 0
  };
  S.chartCoords = S.primary.turningPoints.map((p, i) => ({ x: toX(i), y: toY(p), price: p }));

  // === Price grid ===
  const dataRange = maxP - minP;
  const rawStep = dataRange / 8;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  let step;
  if (rawStep / mag < 2) step = 2 * mag;
  else if (rawStep / mag < 5) step = 5 * mag;
  else step = 10 * mag;
  const gridStart = Math.floor(rangeMin / step) * step;
  for (let p = gridStart; p <= rangeMax; p += step) {
    const y = toY(p);
    chart.appendChild(svgEl("line", { x1: left - 5, y1: y, x2: left + cW + 5, y2: y, stroke: "#1e3050", "stroke-width": 0.5, "stroke-dasharray": "3,3" }));
    const lbl = svgEl("text", { x: left - 10, y: y + 4, fill: "#5577aa", "font-size": 11, "text-anchor": "end", "font-family": "SF Mono,Menlo,monospace" });
    lbl.textContent = Math.round(p * 100) / 100;
    chart.appendChild(lbl);
  }

  // === K-line candlesticks ===
  if (klineMode && S.showKlines) {
    const timeToX = t => left + (t - timeMin) / timeRange * cW;
    visibleKlines.forEach((k, idx) => {
      const cx = timeToX(k.openTime);
      const yH = toY(k.high), yL = toY(k.low);
      const yO = toY(k.open), yC = toY(k.close);
      const bull = k.close >= k.open;
      const color = bull ? "#26a69a" : "#ef5350";
      const bodyTop = Math.min(yO, yC), bodyH = Math.max(Math.abs(yO - yC), 1);
      // Wick
      chart.appendChild(svgEl("line", { x1: cx, y1: yH, x2: cx, y2: yL, stroke: color, "stroke-width": 1 }));
      // Body
      chart.appendChild(svgEl("rect", {
        x: cx - klineBarW / 2, y: bodyTop, width: klineBarW, height: bodyH,
        fill: bull ? color : color, stroke: color, "stroke-width": 0.5, opacity: 0.9
      }));
    });
  }

  // === MACD panel ===
  if (klineMode) {
    drawMACDPanel(macdTop, macdH, left, cW);
  }

  // === Context period overlays ===
  if (klineMode && S.showContext && S.context.interval && S.context.klines && S.context.klines.length > 0) {
    const ctxTimeToX = t => left + (t - timeMin) / timeRange * cW;
    // Build context tp index → klineIdx map from fractals
    const ctxFractals = S.context.fractals;
    const ctxTpTime = (idx) => {
      if (ctxFractals && idx < ctxFractals.length) {
        const kIdx = ctxFractals[idx].klineIdx;
        if (kIdx < S.context.klines.length) return S.context.klines[kIdx].openTime;
      }
      return null;
    };
    // Render context zhongshu (behind context segments)
    S.context.zhongshu.forEach(zs => {
      const tFrom = ctxTpTime(zs.fromIdx);
      const tTo = ctxTpTime(zs.toIdx);
      if (tFrom === null || tTo === null) return;
      const x1 = ctxTimeToX(tFrom), x2 = ctxTimeToX(tTo);
      const zgY = toY(zs.zg), zdY = toY(zs.zd);
      if (x1 > left + cW || x2 < left) return; // clip
      chart.appendChild(svgEl("rect", {
        x: x1 - 2, y: zgY, width: x2 - x1 + 4, height: zdY - zgY,
        fill: "rgba(230,119,0,0.08)", stroke: "rgba(230,119,0,0.3)", "stroke-width": 2,
        rx: 3, class: "ctx-zs-rect"
      }));
    });
    // Render context segments
    S.context.segments.forEach(seg => {
      const tFrom = ctxTpTime(seg.fromIdx);
      const tTo = ctxTpTime(seg.toIdx);
      if (tFrom === null || tTo === null) return;
      const x1 = ctxTimeToX(tFrom), x2 = ctxTimeToX(tTo);
      if (x1 > left + cW || x2 < left) return; // clip
      const pFrom = S.context.turningPoints[seg.fromIdx];
      const pTo = S.context.turningPoints[seg.toIdx];
      const isUp = pTo > pFrom;
      chart.appendChild(svgEl("line", {
        x1, y1: toY(pFrom), x2, y2: toY(pTo),
        stroke: isUp ? "rgba(47,158,68,0.5)" : "rgba(201,42,42,0.5)",
        "stroke-width": 4, "stroke-linecap": "round", class: "ctx-seg-line"
      }));
    });
  }

  // === Overlays ===
  // 中枢 rectangles (behind segments)
  drawZhongshuRectangles();
  if (S.showSegZs) drawSegmentZhongshuRects();

  // Segments
  S.primary.segments.forEach((seg, i) => drawSegmentLine(seg.fromIdx, seg.toIdx, i));

  // Zigzag strokes — draw only strokes that exist in the strokes array
  if (S.primary.strokes.length >= 1) {
    const strokeColor = klineMode ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.85)";
    const strokeWidth = klineMode ? 1 : 0.8;
    S.primary.strokes.forEach((s, si) => {
      if (s.fromIdx === null || s.fromIdx === undefined) return;
      const x1 = toX(s.fromIdx), y1 = toY(S.primary.turningPoints[s.fromIdx]);
      const x2 = toX(s.toIdx), y2 = toY(S.primary.turningPoints[s.toIdx]);
      const hidden = S.deletedTurningPoints.has(s.fromIdx) || S.deletedTurningPoints.has(s.toIdx);
      if (!hidden) {
        chart.appendChild(svgEl("line", {
          x1, y1, x2, y2,
          stroke: strokeColor, "stroke-width": strokeWidth,
          "stroke-linecap": "round"
        }));
      }
      // Hit area always present
      chart.appendChild(svgEl("line", {
        x1, y1, x2, y2,
        stroke: "transparent", "stroke-width": 14,
        class: "stroke-hit", "data-stroke-idx": s.toIdx,
        style: hidden ? "cursor:default" : "cursor:pointer"
      }));
    });
  }
  // Turning point dots — skip deleted
  S.primary.turningPoints.forEach((p, i) => {
    if (S.deletedTurningPoints.has(i)) return;
    const x = toX(i), y = toY(p);

    // Visual dots — always show
    if (klineMode) {
      // Kline mode: colored dots — green for bottom, red for top
      const isTop = i > 0 && i < S.primary.turningPoints.length - 1 && S.primary.turningPoints[i] > S.primary.turningPoints[i-1] && S.primary.turningPoints[i] > S.primary.turningPoints[i+1];
      const isBottom = i > 0 && i < S.primary.turningPoints.length - 1 && S.primary.turningPoints[i] < S.primary.turningPoints[i-1] && S.primary.turningPoints[i] < S.primary.turningPoints[i+1];
      const dotColor = isTop ? "#ff6b6b" : isBottom ? "#51cf66" : "#00e5ff";
      chart.appendChild(svgEl("circle", { cx: x, cy: y, r: 5, fill: dotColor, stroke: "#fff", "stroke-width": 1, class: "tp-dot", "data-idx": i, style: "cursor:pointer" }));
      // Price label
      const ly = isTop ? y - 10 : isBottom ? y + 16 : y - 10;
      const lbl = svgEl("text", { x, y: ly, fill: dotColor, "font-size": 10, "text-anchor": "middle", "font-family": "SF Mono,Menlo,monospace", class: "tp-label", "data-idx": i });
      lbl.textContent = Math.round(p * 100) / 100;
      chart.appendChild(lbl);
    } else {
      chart.appendChild(svgEl("circle", { cx: x, cy: y, r: 7, fill: "none", stroke: "rgba(255,255,255,0.2)", "stroke-width": 1, opacity: 0.25 }));
      chart.appendChild(svgEl("circle", { cx: x, cy: y, r: 5, fill: "#16213e", stroke: "rgba(255,255,255,0.85)", "stroke-width": 1.5, class: "tp-dot", "data-idx": i, style: "cursor:grab" }));
      const isPeak = i > 0 && i < S.primary.turningPoints.length - 1 && S.primary.turningPoints[i] > S.primary.turningPoints[i-1] && S.primary.turningPoints[i] > S.primary.turningPoints[i+1];
      const isValley = i > 0 && i < S.primary.turningPoints.length - 1 && S.primary.turningPoints[i] < S.primary.turningPoints[i-1] && S.primary.turningPoints[i] < S.primary.turningPoints[i+1];
      let ly = isPeak ? y - 14 : isValley ? y + 20 : (i === 0 ? y - 14 : y + 20);
      const lbl = svgEl("text", { x, y: ly, fill: "#99aabb", "font-size": 12, "text-anchor": "middle", "font-family": "SF Mono,Menlo,monospace", class: "tp-label", "data-idx": i });
      lbl.textContent = Math.round(p * 100) / 100;
      chart.appendChild(lbl);
    }

    // Hit area for click interaction — always render
    const hitCursor = klineMode ? "pointer" : "grab";
    const hitCircle = svgEl("circle", { cx: x, cy: y, r: klineMode ? 10 : 18, fill: "transparent", stroke: "none", class: "tp-hit", "data-idx": i, style: `cursor:${hitCursor}` });
    const tipEl = svgEl("title", {});
    tipEl.textContent = Math.round(p * 100) / 100;
    hitCircle.appendChild(tipEl);
    chart.appendChild(hitCircle);
  });

  // Buy/sell markers
  if (S.showBuySell) drawBuySellMarkers();

  // Higher-level segments (red dashed)
  drawHigherSegmentLines();

  // Time labels (kline mode)
  if (klineMode) {
    const timeToX = t => left + (t - timeMin) / timeRange * cW;
    const labelY = H - 8;
    const step2 = Math.max(1, Math.floor(visibleKlines.length / 10));
    for (let vi = 0; vi < visibleKlines.length; vi += step2) {
      const k = visibleKlines[vi];
      const x = timeToX(k.openTime);
      const dt = new Date(k.openTime);
      const txt = S.primaryInterval && (S.primaryInterval.includes('d') || S.primaryInterval === '1w' || S.primaryInterval === '1M')
        ? `${(dt.getMonth()+1).toString().padStart(2,'0')}/${dt.getDate().toString().padStart(2,'0')}`
        : `${dt.getHours().toString().padStart(2,'0')}:${dt.getMinutes().toString().padStart(2,'0')}`;
      const lbl = svgEl("text", { x, y: labelY, fill: "#5577aa", "font-size": 10, "text-anchor": "middle", "font-family": "SF Mono,Menlo,monospace" });
      lbl.textContent = txt;
      chart.appendChild(lbl);
    }
  }

  if (klineMode) initCrosshair();
}

function drawMACDPanel(macdTop, macdH, left, cW) {
  // Use backend-provided MACD data
  if (!S.primary.macd) return;
  const { dif, dea, histogram } = S.primary.macd;

  const visStart = S.chartLayout.visStart;
  const visEnd = S.chartLayout.visEnd;

  // Visible slice of MACD data
  const visDif = dif.slice(visStart, visEnd);
  const visDea = dea.slice(visStart, visEnd);
  const visHist = histogram.slice(visStart, visEnd);

  // Panel background
  chart.appendChild(svgEl("rect", { x: left, y: macdTop, width: cW, height: macdH, fill: "rgba(10,20,40,0.5)", stroke: "#1e3050", "stroke-width": 0.5, rx: 3 }));

  // Label
  const label = svgEl("text", { x: left + 6, y: macdTop + 14, fill: "#5577aa", "font-size": 10, "font-family": "SF Mono,Menlo,monospace" });
  label.textContent = "MACD (12,26,9)";
  chart.appendChild(label);

  // MACD Y scale (from visible data only)
  const maxAbs = Math.max(0.001, Math.max(...visHist.map(Math.abs)), Math.max(...visDif.map(Math.abs)), Math.max(...visDea.map(Math.abs)));
  const macdYScale = (macdH - 24) / (2 * maxAbs);
  const zeroY = macdTop + macdH / 2;
  const toMY = v => zeroY - v * macdYScale;

  // Zero line
  chart.appendChild(svgEl("line", { x1: left, y1: zeroY, x2: left + cW, y2: zeroY, stroke: "#334466", "stroke-width": 0.5, "stroke-dasharray": "4,3" }));

  // Time-to-X helper
  const timeToX = t => left + (t - S.chartLayout.timeMin) / S.chartLayout.timeRange * cW;
  const barW = Math.max(1, S.chartLayout.klineBarW * 0.6);

  // Histogram bars (visible only)
  visHist.forEach((v, vi) => {
    const kIdx = visStart + vi;
    const x = timeToX(S.primary.klines[kIdx].openTime);
    const y = toMY(v);
    const h = Math.abs(y - zeroY);
    const prevV = vi > 0 ? visHist[vi - 1] : v;
    const color = v >= 0 ? (vi > 0 && v < prevV ? "#66bb6a" : "#26a69a") : (vi > 0 && v > prevV ? "#ef9a9a" : "#ef5350");
    chart.appendChild(svgEl("rect", {
      x: x - barW / 2, y: Math.min(y, zeroY), width: barW, height: Math.max(h, 0.5),
      fill: color, opacity: 0.8
    }));
  });

  // DIF line (visible only)
  let dDif = "";
  visDif.forEach((v, vi) => {
    const kIdx = visStart + vi;
    const x = timeToX(S.primary.klines[kIdx].openTime);
    const y = toMY(v);
    dDif += (vi === 0 ? "M" : "L") + ` ${x} ${y}`;
  });
  if (dDif) chart.appendChild(svgEl("path", { d: dDif, fill: "none", stroke: "#2196f3", "stroke-width": 1.2 }));

  // DEA line (visible only)
  let dDea = "";
  visDea.forEach((v, vi) => {
    const kIdx = visStart + vi;
    const x = timeToX(S.primary.klines[kIdx].openTime);
    const y = toMY(v);
    dDea += (vi === 0 ? "M" : "L") + ` ${x} ${y}`;
  });
  if (dDea) chart.appendChild(svgEl("path", { d: dDea, fill: "none", stroke: "#ff9800", "stroke-width": 1.2 }));

  // Divergence lines on MACD
  if (S.primary.divergencePoints.length) {
    S.primary.divergencePoints.forEach(div => {
      const kIdx1 = div.compareKlineIdx;
      const kIdx2 = div.klineIdx;
      // Only draw if both points are in visible range
      if (kIdx1 < visStart || kIdx1 >= visEnd || kIdx2 < visStart || kIdx2 >= visEnd) return;

      const x1 = timeToX(S.primary.klines[kIdx1].openTime);
      const y1 = toMY(dif[kIdx1]);
      const x2 = timeToX(S.primary.klines[kIdx2].openTime);
      const y2 = toMY(dif[kIdx2]);
      const isTop = div.type === 'top';
      const color = isTop ? "#ff1744" : "#00c853";

      // Divergence line on DIF
      chart.appendChild(svgEl("line", {
        x1, y1, x2, y2, stroke: color, "stroke-width": 1.5, opacity: 0.9, class: "div-line"
      }));
      // Dots at both ends
      chart.appendChild(svgEl("circle", { cx: x1, cy: y1, r: 3, fill: color, opacity: 0.9, class: "div-line" }));
      chart.appendChild(svgEl("circle", { cx: x2, cy: y2, r: 3, fill: color, opacity: 0.9, class: "div-line" }));
      // Label
      const midX = (x1 + x2) / 2, midY = (y1 + y2) / 2;
      const tag = isTop ? "顶背驰" : "底背驰";
      const bg = svgEl("rect", {
        x: midX - 22, y: midY - 16, width: 44, height: 16, rx: 3,
        fill: color, opacity: 0.85, class: "div-line"
      });
      chart.appendChild(bg);
      const txt = svgEl("text", {
        x: midX, y: midY - 6, fill: "#fff", "font-size": 10, "font-weight": "bold",
        "text-anchor": "middle", class: "div-line"
      });
      txt.textContent = tag;
      chart.appendChild(txt);
    });
  }

  // Separator line above MACD
  chart.appendChild(svgEl("line", { x1: left, y1: macdTop - 1, x2: left + cW, y2: macdTop - 1, stroke: "#2a3a5a", "stroke-width": 1 }));
}

function drawSegmentLine(fromIdx, toIdx, segIdx) {
  const from = S.chartCoords[fromIdx], to = S.chartCoords[toIdx];
  if (!from || !to) return;
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
  if (!S.chartLayout || S.chartCoords.length === 0) return;
  S.primary.zhongshuList.forEach((zs, i) => {
    const from = S.chartCoords[zs.fromIdx];
    const to = S.chartCoords[zs.toIdx];
    if (!from || !to) return;

    const zgY = S.chartLayout.priceBottom - (zs.zg - S.chartLayout.minP) * S.chartLayout.yScale;
    const zdY = S.chartLayout.priceBottom - (zs.zd - S.chartLayout.minP) * S.chartLayout.yScale;

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
  if (!S.chartLayout || S.chartCoords.length === 0) return;
  S.primary.segmentZhongshu.forEach((zs, i) => {
    const from = S.chartCoords[zs.fromIdx];
    const to = S.chartCoords[zs.toIdx];
    if (!from || !to) return;

    const zgY = S.chartLayout.priceBottom - (zs.zg - S.chartLayout.minP) * S.chartLayout.yScale;
    const zdY = S.chartLayout.priceBottom - (zs.zd - S.chartLayout.minP) * S.chartLayout.yScale;

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
  if (!S.chartLayout || S.chartCoords.length === 0) return;
  S.primary.higherSegments.forEach((seg, i) => {
    const from = S.chartCoords[seg.fromIdx];
    const to = S.chartCoords[seg.toIdx];
    if (!from || !to) return;
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
  } else {
    btn.textContent = '手动画段';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
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
  } else {
    btn.textContent = '手动画中枢';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
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
  } else {
    btn.textContent = '手动画';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
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
  } else {
    btn.textContent = '手动画';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight').forEach(el => el.remove());
    setSegHitEvents(true);
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

function findSnapPoint(pt) {
  if (!S.primary.klines || !S.chartLayout) return null;
  const timeToX = t => S.chartLayout.left + (t - S.chartLayout.timeMin) / S.chartLayout.timeRange * S.chartLayout.cW;
  const visStart = S.chartLayout.visStart || 0;
  const visEnd = S.chartLayout.visEnd || S.primary.klines.length;
  let bestDist = Infinity, bestIdx = 0, useHigh = true;
  for (let ki = visStart; ki < visEnd; ki++) {
    const k = S.primary.klines[ki];
    const x = timeToX(k.openTime);
    const dx = Math.abs(pt.x - x);
    if (dx < bestDist) {
      bestDist = dx;
      bestIdx = ki;
      const toY = p => S.chartLayout.priceBottom - (p - S.chartLayout.minP) * S.chartLayout.yScale;
      const dyHigh = Math.abs(pt.y - toY(k.high));
      const dyLow = Math.abs(pt.y - toY(k.low));
      useHigh = dyHigh < dyLow;
    }
  }
  const k = S.primary.klines[bestIdx];
  const price = useHigh ? k.high : k.low;
  return { x: timeToX(k.openTime), y: S.chartLayout.priceBottom - (price - S.chartLayout.minP) * S.chartLayout.yScale, price, klineIdx: bestIdx, useHigh };
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
    hideCrosshair();
    chart.querySelectorAll('.snap-preview').forEach(el => el.remove());
    setSegHitEvents(false);
  } else {
    btn.textContent = '手动画笔';
    hint.style.display = 'none';
    chart.querySelectorAll('.tp-highlight, .snap-preview').forEach(el => el.remove());
    setSegHitEvents(true);
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

chart.addEventListener('click', function(e) {
  if (S.isDragging || S.isDraggingZs || S.isPanning) return;
  const noDrawMode = !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode && !S.drawStrokeMode;

  // Click on stroke line to delete line + both endpoint turning points, no reconnection
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

  // Click on turning point to delete it (non-draw mode)
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

  // Manual stroke drawing — click on chart, snap to nearest kline high/low
  if (S.drawStrokeMode) {
    const pt = svgPoint(e);
    if (!pt || !S.chartLayout) return;
    if (pt.x < S.chartLayout.left || pt.x > S.chartLayout.left + S.chartLayout.cW) return;
    if (pt.y < S.chartLayout.top || pt.y > S.chartLayout.priceBottom) return;

    let price, snapKlineIdx = null;
    if (S.primary.klines) {
      const snap = findSnapPoint(pt);
      if (!snap) return;
      price = snap.price;
      snapKlineIdx = snap.klineIdx;
    } else {
      price = parseFloat(yToPrice(pt.y).toFixed(2));
    }

    let dir;
    const isManualFirst = S.strokeDrawLastIdx === null;
    if (isManualFirst) {
      dir = 'down';
    } else {
      const lastPrice = S.primary.turningPoints[S.strokeDrawLastIdx];
      dir = price > lastPrice ? 'up' : 'down';
    }

    S.primary.turningPoints.push(price);
    if (S.primary.klines && snapKlineIdx !== null && snapKlineIdx < S.primary.klines.length) {
      if (!S.primary.fractals) S.primary.fractals = [];
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
      chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
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
      chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
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
      chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
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
            zg: minHigh,
            zd: maxLow
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
      chart.appendChild(svgEl("circle", { cx: c.x, cy: c.y, r: 14, fill: "none", stroke: "#ffc832", "stroke-width": 2, opacity: 0.6, class: "tp-highlight" }));
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

// ====== Drag ======
function svgPoint(evt) {
  const pt = chart.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  const ctm = chart.getScreenCTM();
  if (!ctm) return null;
  return pt.matrixTransform(ctm.inverse());
}

function yToPrice(y) {
  if (!S.chartLayout) return 0;
  return S.chartLayout.minP + (S.chartLayout.priceBottom - y) / S.chartLayout.yScale;
}

chart.addEventListener('mousedown', function(e) {
  const tpTarget = e.target.closest('.tp-hit, .tp-dot');
  if (tpTarget && !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode && !S.primary.klines) {
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
  if (zsRect && !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode && S.chartLayout) {
    const zsIdx = parseInt(zsRect.getAttribute('data-zs-idx'));
    if (!isNaN(zsIdx) && zsIdx < S.primary.zhongshuList.length) {
      const pt = svgPoint(e);
      if (pt) {
        const zs = S.primary.zhongshuList[zsIdx];
        const zgY = S.chartLayout.priceBottom - (zs.zg - S.chartLayout.minP) * S.chartLayout.yScale;
        const zdY = S.chartLayout.priceBottom - (zs.zd - S.chartLayout.minP) * S.chartLayout.yScale;
        if (Math.abs(pt.y - zgY) < 15) {
          S.isDraggingZs = true; S.zsDragIdx = zsIdx; S.zsDragEdge = 'top';
          e.preventDefault(); return;
        } else if (Math.abs(pt.y - zdY) < 15) {
          S.isDraggingZs = true; S.zsDragIdx = zsIdx; S.zsDragEdge = 'bottom';
          e.preventDefault(); return;
        }
      }
    }
  }

  // Pan: click-drag on empty space in kline mode
  if (S.primary.klines && S.chartLayout && S.chartLayout.klineMode &&
      !S.isDragging && !S.isDraggingZs && !S.drawingMode && !S.drawZsMode && !S.drawSegZsMode && !S.drawHigherMode && !S.drawStrokeMode) {
    const pt = svgPoint(e);
    if (pt && pt.x >= S.chartLayout.left && pt.x <= S.chartLayout.left + S.chartLayout.cW &&
        pt.y >= S.chartLayout.top && pt.y <= S.chartLayout.macdBottom) {
      S.isPanning = true;
      S.panStartX = e.clientX;
      const totalKlines = S.primary.klines.length;
      if (S.klineViewEnd <= S.klineViewStart) {
        S.panViewStart = 0;
        S.panViewEnd = totalKlines;
      } else {
        S.panViewStart = S.klineViewStart;
        S.panViewEnd = S.klineViewEnd;
      }
      e.preventDefault();
      chart.style.cursor = 'grabbing';
    }
  }
});

document.addEventListener('mousemove', function(e) {
  if (S.isDragging && S.dragIdx >= 0) {
    const pt = svgPoint(e);
    if (!pt) return;
    const yMin = S.chartLayout.top, yMax = S.chartLayout.priceBottom;
    const clampedY = Math.max(yMin, Math.min(yMax, pt.y));
    const rawPrice = yToPrice(clampedY);
    chart.querySelectorAll(`[data-idx="${S.dragIdx}"].tp-dot`).forEach(d => d.setAttribute('cy', clampedY));
    chart.querySelectorAll(`[data-idx="${S.dragIdx}"].tp-hit`).forEach(h => h.setAttribute('cy', clampedY));
    const label = chart.querySelector(`[data-idx="${S.dragIdx}"].tp-label`);
    if (label) {
      label.textContent = Math.round(rawPrice * 100) / 100;
      const prices = S.primary.turningPoints, i = S.dragIdx;
      const isPeak = i > 0 && i < prices.length - 1 && prices[i] > prices[i-1] && prices[i] > prices[i+1];
      const isValley = i > 0 && i < prices.length - 1 && prices[i] < prices[i-1] && prices[i] < prices[i+1];
      const ly = isPeak ? clampedY - 14 : isValley ? clampedY + 20 : (i === 0 ? clampedY - 14 : clampedY + 20);
      label.setAttribute('y', ly);
    }
    updateZigzagPath(S.dragIdx, clampedY);
    return;
  }

  if (S.isDraggingZs && S.zsDragIdx >= 0 && S.chartLayout) {
    const pt = svgPoint(e);
    if (!pt) return;
    const yMin = S.chartLayout.top, yMax = S.chartLayout.priceBottom;
    const clampedY = Math.max(yMin, Math.min(yMax, pt.y));
    const price = Math.round(yToPrice(clampedY) * 100) / 100;
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

  // Panning — right edge anchored, only move start
  if (S.isPanning && S.chartLayout) {
    const dx = e.clientX - S.panStartX;
    const klinesPerPx = (S.panViewEnd - S.panViewStart) / S.chartLayout.cW;
    const shift = -dx * klinesPerPx;
    let newStart = S.panViewStart + shift;
    newStart = Math.max(0, Math.min(S.panViewEnd - 10, newStart));
    S.klineViewStart = newStart;
    S.klineViewEnd = S.panViewEnd; // right edge stays fixed
    drawChart();
  }
});

document.addEventListener('mouseup', function(e) {
  if (S.isDragging && S.dragIdx >= 0) {
    const pt = svgPoint(e);
    let newPrice;
    if (pt) {
      const yMin = S.chartLayout.top, yMax = S.chartLayout.priceBottom;
      const clampedY = Math.max(yMin, Math.min(yMax, pt.y));
      newPrice = Math.round(yToPrice(clampedY) * 100) / 100;
    } else {
      newPrice = S.primary.turningPoints[S.dragIdx];
    }
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

  if (S.isPanning) {
    S.isPanning = false;
    chart.style.cursor = '';
  }
});

function updateZigzagPath(changedIdx, newY) {
  const path = chart.querySelector('path:not(.seg-line)');
  if (!path || !S.chartLayout) return;

  const prices = S.primary.turningPoints;
  const toY = p => S.chartLayout.priceBottom - (p - S.chartLayout.minP) * S.chartLayout.yScale;
  const gap = S.chartLayout.cW / (S.primary.turningPoints.length - 1);
  const toX = i => S.chartLayout.left + i * gap;

  let d = `M ${toX(0)} ${changedIdx === 0 ? newY : toY(prices[0])}`;
  for (let i = 1; i < prices.length; i++) {
    const y = i === changedIdx ? newY : toY(prices[i]);
    d += ` L ${toX(i)} ${y}`;
  }
  path.setAttribute('d', d);
}

window.addEventListener('resize', () => {
  if (S.primary.turningPoints.length >= 2) drawChart();
});

// ====== Zoom / Pan (K线模式) ======
chart.addEventListener('wheel', function(e) {
  if (!S.primary.klines || !S.chartLayout || !S.chartLayout.klineMode) return;
  e.preventDefault();
  const pt = svgPoint(e);
  if (!pt) return;
  // Only zoom if cursor is inside chart area
  if (pt.x < S.chartLayout.left || pt.x > S.chartLayout.left + S.chartLayout.cW) return;

  const totalKlines = S.primary.klines.length;
  if (S.klineViewEnd <= S.klineViewStart) {
    S.klineViewStart = 0;
    S.klineViewEnd = totalKlines;
  }

  const range = S.klineViewEnd - S.klineViewStart;
  const frac = Math.max(0, Math.min(1, (pt.x - S.chartLayout.left) / S.chartLayout.cW));
  const factor = e.deltaY > 0 ? 1.15 : 1 / 1.15;
  let newRange = range * factor;
  newRange = Math.max(10, Math.min(totalKlines, newRange));

  let newStart = S.klineViewStart + frac * (range - newRange);
  let newEnd = newStart + newRange;
  if (newStart < 0) { newStart = 0; newEnd = newRange; }
  if (newEnd > totalKlines) { newEnd = totalKlines; newStart = totalKlines - newRange; }

  S.klineViewStart = Math.max(0, newStart);
  S.klineViewEnd = Math.min(totalKlines, newEnd);
  drawChart();
}, { passive: false });

chart.addEventListener('dblclick', function(e) {
  if (!S.primary.klines) return;
  S.klineViewStart = 0;
  S.klineViewEnd = 0;
  drawChart();
});

// ====== Crosshair (Binance K线模式) ======
function initCrosshair() {
  if (chart.querySelector('.crosshair-h')) return;
  chart.appendChild(svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 0, stroke: "rgba(255,255,255,0.25)", "stroke-width": 0.5, "stroke-dasharray": "4,3", class: "crosshair-h", display: "none" }));
  chart.appendChild(svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 0, stroke: "rgba(255,255,255,0.25)", "stroke-width": 0.5, "stroke-dasharray": "4,3", class: "crosshair-v", display: "none" }));
  chart.appendChild(svgEl("rect", { x: 0, y: 0, width: 72, height: 18, fill: "#0f3460", stroke: "rgba(255,255,255,0.3)", "stroke-width": 0.5, rx: 3, class: "crosshair-y-bg", display: "none" }));
  chart.appendChild(svgEl("text", { x: 0, y: 0, fill: "#e0e0e0", "font-size": 11, "font-family": "SF Mono,Menlo,monospace", "text-anchor": "end", class: "crosshair-y-label", display: "none" }));
  chart.appendChild(svgEl("rect", { x: 0, y: 0, width: 30, height: 18, fill: "#0f3460", stroke: "rgba(255,255,255,0.3)", "stroke-width": 0.5, rx: 3, class: "crosshair-x-bg", display: "none" }));
  chart.appendChild(svgEl("text", { x: 0, y: 0, fill: "#e0e0e0", "font-size": 11, "font-family": "SF Mono,Menlo,monospace", "text-anchor": "middle", class: "crosshair-x-label", display: "none" }));
}

chart.addEventListener('mousemove', function(e) {
  if (!S.chartLayout) return;
  if (S.isDragging || S.isDraggingZs || S.isPanning || S.drawingMode || S.drawZsMode || S.drawSegZsMode || S.drawHigherMode) return;
  if (!S.primary.klines && !S.drawStrokeMode) return;

  const pt = svgPoint(e);
  if (!pt) return;

  const { top, priceBottom, left, cW, priceH, minP, yScale, klineMode, W, H, macdBottom } = S.chartLayout;
  const rightEdge = left + cW;

  if (pt.x < left || pt.x > rightEdge || pt.y < top || pt.y > H - 30) {
    hideCrosshair();
    chart.querySelectorAll('.snap-preview').forEach(el => el.remove());
    return;
  }

  // In drawStrokeMode, show snap preview instead of full crosshair
  if (S.drawStrokeMode) {
    chart.querySelectorAll('.snap-preview').forEach(el => el.remove());
    if (S.primary.klines) {
      const snap = findSnapPoint(pt);
      if (snap) {
        chart.appendChild(svgEl("circle", { cx: snap.x, cy: snap.y, r: 6, fill: snap.useHigh ? "rgba(255,80,80,0.6)" : "rgba(80,255,80,0.6)", stroke: "#fff", "stroke-width": 1.5, class: "snap-preview" }));
        // Show price label
        const yBg = chart.querySelector('.crosshair-y-bg');
        yBg.setAttribute('x', left - 76);
        yBg.setAttribute('y', snap.y - 9);
        yBg.setAttribute('display', '');
        const yLbl = chart.querySelector('.crosshair-y-label');
        yLbl.setAttribute('x', left - 8);
        yLbl.setAttribute('y', snap.y + 4);
        yLbl.textContent = (Math.round(snap.price * 100) / 100).toString();
        yLbl.setAttribute('display', '');
      }
    }
    return;
  }

  const hLine = chart.querySelector('.crosshair-h');
  hLine.setAttribute('x1', left);
  hLine.setAttribute('y1', pt.y);
  hLine.setAttribute('x2', rightEdge);
  hLine.setAttribute('y2', pt.y);
  hLine.setAttribute('display', '');

  const vLine = chart.querySelector('.crosshair-v');
  vLine.setAttribute('x1', pt.x);
  vLine.setAttribute('y1', top);
  vLine.setAttribute('x2', pt.x);
  vLine.setAttribute('y2', H - 30);
  vLine.setAttribute('display', '');

  // Price label (only when in price area)
  if (pt.y >= top && pt.y <= priceBottom) {
    const price = yToPrice(pt.y);
    const priceStr = (Math.round(price * 100) / 100).toString();
    const yBg = chart.querySelector('.crosshair-y-bg');
    yBg.setAttribute('x', left - 76);
    yBg.setAttribute('y', pt.y - 9);
    yBg.setAttribute('display', '');
    const yLbl = chart.querySelector('.crosshair-y-label');
    yLbl.setAttribute('x', left - 8);
    yLbl.setAttribute('y', pt.y + 4);
    yLbl.textContent = priceStr;
    yLbl.setAttribute('display', '');
  } else {
    chart.querySelector('.crosshair-y-bg').setAttribute('display', 'none');
    chart.querySelector('.crosshair-y-label').setAttribute('display', 'none');
  }

  // Time label at bottom
  if (klineMode && S.primary.klines) {
    const timeMin = S.chartLayout.timeMin;
    const timeRange = S.chartLayout.timeRange;
    const t = timeMin + (pt.x - left) / cW * timeRange;
    // Find nearest kline
    const dt = new Date(t);
    const txt = S.primaryInterval && (S.primaryInterval.includes('d') || S.primaryInterval === '1w' || S.primaryInterval === '1M')
      ? `${(dt.getMonth()+1).toString().padStart(2,'0')}/${dt.getDate().toString().padStart(2,'0')}`
      : `${dt.getHours().toString().padStart(2,'0')}:${dt.getMinutes().toString().padStart(2,'0')}`;
    const xBg = chart.querySelector('.crosshair-x-bg');
    xBg.setAttribute('x', pt.x - 20);
    xBg.setAttribute('y', H - 28);
    xBg.setAttribute('display', '');
    const xLbl = chart.querySelector('.crosshair-x-label');
    xLbl.setAttribute('x', pt.x);
    xLbl.setAttribute('y', H - 16);
    xLbl.textContent = txt;
    xLbl.setAttribute('display', '');
  }

});

chart.addEventListener('mouseleave', hideCrosshair);

function hideCrosshair() {
  chart.querySelectorAll('.crosshair-h,.crosshair-v,.crosshair-y-bg,.crosshair-y-label,.crosshair-x-bg,.crosshair-x-label').forEach(el => el.setAttribute('display', 'none'));
  chart.querySelectorAll('.snap-preview').forEach(el => el.remove());
}
