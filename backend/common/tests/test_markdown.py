from django.test import TestCase
from common.markdown_utils import escape_markdown


class TestEscapeMarkdown(TestCase):
    def test_escape_markdown(self):
        self.assertEqual(
            escape_markdown('Hello, _world_!'),
            'Hello, \\_world\\_!'
        )
        self.assertEqual(
            escape_markdown('Hello, *world*!'),
            'Hello, \\*world\\*!'
        )
        self.assertEqual(
            escape_markdown('Hello, `world`!'),
            'Hello, \\`world\\`!'
        )
        self.assertEqual(
            escape_markdown('Hello, [world]!'),
            'Hello, \\[world]!'
        )
        self.assertEqual(
            escape_markdown('Hello, _*`[world]`*_!'),
            'Hello, \\_\\*\\`\\[world]\\`\\*\\_!'
        )
        self.assertEqual(
            escape_markdown('Hello, world!'),
            'Hello, world!'
        )
        self.assertEqual(
            escape_markdown('Hello, _world_! *Hello, world!*'),
            'Hello, \\_world\\_! \\*Hello, world!\\*'
        )
        self.assertEqual(
            escape_markdown('Hello, _world_! *Hello, world!* `Hello, world!`'),
            'Hello, \\_world\\_! \\*Hello, world!\\* \\`Hello, world!\\`'
        )
        self.assertEqual(
            escape_markdown('Hello, _world_! *Hello, world!* `Hello, world!` [Hello, world!]'),
            'Hello, \\_world\\_! \\*Hello, world!\\* \\`Hello, world!\\` \\[Hello, world!]'
        )
