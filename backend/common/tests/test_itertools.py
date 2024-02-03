from django.test import TestCase
from common.itertools import roundrobin


class TestRoundrobin(TestCase):
    def test_roundrobin(self):
        self.assertListEqual(
            list(roundrobin('ABC', 'D', 'EF')),
            ['A', 'D', 'E', 'B', 'F', 'C']
        )
        self.assertListEqual(
            list(roundrobin('ABC', 'D', 'EF', 'G')),
            ['A', 'D', 'E', 'G', 'B', 'F', 'C']
        )
        self.assertListEqual(
            list(roundrobin([1, 4, 2], 'AAAEEE', [], [3.4])),
            [1, 'A', 3.4, 4, 'A', 2, 'A', 'E', 'E', 'E']
        )
