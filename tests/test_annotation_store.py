"""标注持久化测试"""

import os
import tempfile
import json
import unittest

import chanlun.annotation_store as astore

# 使用临时目录
_test_dir = tempfile.mkdtemp()
astore.ANNOTATIONS_DIR = _test_dir


class TestAnnotationStore(unittest.TestCase):

    def test_save_and_load(self):
        """写入后应能读取相同数据。"""
        data = {
            "turningPoints": [100, 120, 90, 110],
            "segments": [{"fromIdx": 0, "toIdx": 3}],
            "zhongshu": [{"fromIdx": 1, "toIdx": 2, "zg": 115, "zd": 95}],
            "segmentZhongshu": [],
            "higherSegments": [],
            "deletedTurningPoints": [],
        }
        astore.save_annotation("BTCUSDT", "15m", data)
        loaded = astore.load_annotation("BTCUSDT", "15m")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["turningPoints"], [100, 120, 90, 110])
        self.assertEqual(len(loaded["segments"]), 1)
        self.assertEqual(loaded["symbol"], "BTCUSDT")
        self.assertEqual(loaded["interval"], "15m")

    def test_load_nonexistent(self):
        """不存在的标注应返回 None。"""
        result = astore.load_annotation("NONEXIST", "1d")
        self.assertIsNone(result)

    def test_overwrite(self):
        """重复写入应覆盖。"""
        astore.save_annotation("ETHUSDT", "1h", {"turningPoints": [1, 2]})
        astore.save_annotation("ETHUSDT", "1h", {"turningPoints": [3, 4, 5]})
        loaded = astore.load_annotation("ETHUSDT", "1h")
        self.assertEqual(loaded["turningPoints"], [3, 4, 5])

    def test_clear(self):
        """清除后应返回 None。"""
        astore.save_annotation("SOLUSDT", "4h", {"turningPoints": [10]})
        astore.clear_annotation("SOLUSDT", "4h")
        self.assertIsNone(astore.load_annotation("SOLUSDT", "4h"))

    def test_clear_nonexistent(self):
        """清除不存在的标注不应报错。"""
        astore.clear_annotation("NOFILE", "1m")

    def test_dir_auto_created(self):
        """保存时应自动创建目录。"""
        new_dir = os.path.join(tempfile.mkdtemp(), "subdir")
        astore.ANNOTATIONS_DIR = new_dir
        try:
            astore.save_annotation("TEST", "1m", {"turningPoints": []})
            self.assertTrue(os.path.exists(new_dir))
        finally:
            astore.ANNOTATIONS_DIR = _test_dir

    def test_different_symbols_isolated(self):
        """不同交易对的标注不应互相影响。"""
        astore.save_annotation("AAA", "1h", {"turningPoints": [1]})
        astore.save_annotation("BBB", "1h", {"turningPoints": [2]})
        self.assertEqual(astore.load_annotation("AAA", "1h")["turningPoints"], [1])
        self.assertEqual(astore.load_annotation("BBB", "1h")["turningPoints"], [2])

    def test_json_format(self):
        """存储文件应为合法 JSON。"""
        astore.save_annotation("JSONTEST", "1d", {"turningPoints": [100.5, 200.3]})
        path = astore._get_path("JSONTEST", "1d")
        with open(path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["turningPoints"], [100.5, 200.3])


if __name__ == "__main__":
    unittest.main()
