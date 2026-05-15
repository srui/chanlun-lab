"""缠论分析配置 — 周期配对、轮询频率"""

# 市场 K 线接口
MARKET_URLS = {
    "spot": "https://api.binance.com/api/v3/klines",
    "futures": "https://fapi.binance.com/fapi/v1/klines",
}

# 主周期 → 上下文周期映射（上下文 = 主周期 × 4~8 倍）
INTERVAL_PAIRS = {
    "1m": "5m",
    "3m": "15m",
    "5m": "30m",
    "15m": "1h",
    "30m": "4h",
    "1h": "4h",
    "2h": "1d",
    "4h": "1d",
    "6h": "1d",
    "1d": "1w",
    "1w": "1M",
}

# 操作周期 → 轮询间隔（秒）
POLL_INTERVALS = {
    "1m": 30,
    "3m": 30,
    "5m": 30,
    "15m": 30,
    "30m": 60,
    "1h": 60,
    "2h": 300,
    "4h": 300,
    "6h": 300,
    "8h": 300,
    "12h": 300,
    "1d": 300,
    "3d": 300,
    "1w": 300,
    "1M": 300,
}

_DEFAULT_POLL_INTERVAL = 60

# 启动预热：自动拉取的周期列表
PREFETCH_INTERVALS = ["5m", "15m", "30m", "1h", "4h", "1d"]
PREFETCH_DAYS = 60

# 周期 → 毫秒数（用于时间计算）
INTERVAL_MS = {
    "1m": 60000, "3m": 180000, "5m": 300000, "15m": 900000,
    "30m": 1800000, "1h": 3600000, "2h": 7200000, "4h": 14400000,
    "6h": 21600000, "8h": 28800000, "12h": 43200000, "1d": 86400000,
    "3d": 259200000, "1w": 604800000, "1M": 2592000000,
}


def get_context_interval(primary_interval):
    """返回主周期对应的上下文周期，无配对返回 None。"""
    return INTERVAL_PAIRS.get(primary_interval)


def get_poll_interval(interval):
    """返回指定周期的推荐轮询间隔（秒），未知周期返回 60。"""
    return POLL_INTERVALS.get(interval, _DEFAULT_POLL_INTERVAL)


# 默认监控的交易对（与前端 DEFAULT_SYMBOLS 一致）
DEFAULT_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT',
    'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'LINKUSDT',
]

# 缓存后台更新的周期列表
CACHE_INTERVALS = ["5m", "15m", "30m", "1h", "4h", "1d"]
