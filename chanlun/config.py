"""缠论分析配置 — 周期配对、轮询频率"""

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


def get_context_interval(primary_interval):
    """返回主周期对应的上下文周期，无配对返回 None。"""
    return INTERVAL_PAIRS.get(primary_interval)


def get_poll_interval(interval):
    """返回指定周期的推荐轮询间隔（秒），未知周期返回 60。"""
    return POLL_INTERVALS.get(interval, _DEFAULT_POLL_INTERVAL)
