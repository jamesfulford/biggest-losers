

import datetime
import unittest
from src.results import summary


class TestMetadata(unittest.TestCase):
    def test_serialization(self):
        s = summary.Summary(start=datetime.date(
            2020, 1, 1), end=datetime.date(2020, 1, 2), roi=0.1)
        message = s.to_dict()
        s2 = summary.Summary.from_dict(message)
        self.assertEqual(s, s2)
