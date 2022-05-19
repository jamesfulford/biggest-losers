import unittest
import src.results.metadata as metadata
import datetime


class TestMetadata(unittest.TestCase):
    def test_serialization(self):
        m = metadata.Metadata(
            commit_id='123', last_updated=datetime.datetime.now())
        message = m.to_dict()
        m2 = metadata.Metadata.from_dict(message)
        self.assertEqual(m, m2)
