import unittest

from src.trading_day import now
import src.outputs.json_dump as json_dump


class TestJsonDump(unittest.TestCase):
    def test_timezone_preservation(self):
        right_now = now()
        message = json_dump.to_json_string({'d': right_now})
        d = json_dump.from_json_string(message)

        assert right_now == d['d']
