"""标注持久化 — 用户手动标注的保存与恢复"""

import json
import os

ANNOTATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "annotations"
)


def _get_path(symbol, interval):
    """返回标注文件路径。"""
    safe_name = f"{symbol}_{interval}".replace("/", "_")
    return os.path.join(ANNOTATIONS_DIR, f"{safe_name}.json")


def save_annotation(symbol, interval, data):
    """保存标注数据到 JSON 文件。

    data 结构:
    {
        "turningPoints": [...],
        "segments": [{"fromIdx": int, "toIdx": int}, ...],
        "zhongshu": [{"fromIdx": int, "toIdx": int, "zg": float, "zd": float}, ...],
        "segmentZhongshu": [...],
        "higherSegments": [...],
        "deletedTurningPoints": [int, ...]
    }
    """
    os.makedirs(ANNOTATIONS_DIR, exist_ok=True)
    path = _get_path(symbol, interval)
    data["symbol"] = symbol
    data["interval"] = interval
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_annotation(symbol, interval):
    """加载标注数据。文件不存在返回 None。"""
    path = _get_path(symbol, interval)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clear_annotation(symbol, interval):
    """删除标注文件。文件不存在不报错。"""
    path = _get_path(symbol, interval)
    if os.path.exists(path):
        os.remove(path)
