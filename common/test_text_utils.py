import asyncio
from unittest import TestCase
from text_utils import DISCORD_MESSAGE_LIMIT, TELEGRAM_MESSAGE_LIMIT, text_chunk, discord_chunk, telegram_chunk, chunk_diff_async


class TestTextUtils(TestCase):
    def test_discord_and_telegram_limits(self):
        self.assertEqual(DISCORD_MESSAGE_LIMIT, 2000)
        self.assertEqual(TELEGRAM_MESSAGE_LIMIT, 4096)

    def test_text_chunk_basic(self):
        msg = "a b c d e f g h i j"
        # chunk size larger than message
        self.assertEqual(text_chunk(msg, 100), [msg])

    def test_text_chunk_split_on_newline(self):
        msg = "line1\nline2\nline3"
        # chunk size splits after line1\nline2
        chunks = text_chunk(msg, 8)
        self.assertEqual(chunks, ["line1", "line2", "line3"])

    def test_text_chunk_split_on_space(self):
        msg = "word1 word2 word3"
        # chunk size splits after word1
        chunks = text_chunk(msg, 6)
        self.assertEqual(chunks, ["word1", "word2", "word3"])

    def test_text_chunk_exact_size(self):
        msg = "abcde"
        self.assertEqual(text_chunk(msg, 5), ["abcde"])

    def test_text_chunk_no_split_possible(self):
        msg = "abcdefghij"
        # No space or newline, so just split at size
        self.assertEqual(text_chunk(msg, 4), ["abcd", "efgh", "ij"])

    def test_discord_chunk(self):
        msg = "a" * (DISCORD_MESSAGE_LIMIT + 1)
        chunks = discord_chunk(msg)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), DISCORD_MESSAGE_LIMIT)
        self.assertEqual(chunks[0], "a" * DISCORD_MESSAGE_LIMIT)
        self.assertEqual(chunks[1], "a")

    def test_telegram_chunk(self):
        msg = "b" * (TELEGRAM_MESSAGE_LIMIT + 2)
        chunks = telegram_chunk(msg)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), TELEGRAM_MESSAGE_LIMIT)
        self.assertEqual(chunks[0], "b" * TELEGRAM_MESSAGE_LIMIT)
        self.assertEqual(chunks[1], "bb")


class TestTextUtilsAsync(TestCase):
    def test_chunk_diff_async_add_and_update(self):
        async def add(i, chunk):
            return f"add-{i}-{chunk}"

        async def update(i, old, chunk):
            return f"update-{i}-{old}-{chunk}"
        # add new chunks
        new_chunks = ["a", "b"]
        result = asyncio.run(chunk_diff_async(new_chunks, add, update=update))
        self.assertEqual(result, ["add-0-a", "add-1-b"])
        # update existing
        old_chunks = ["oldA", "oldB"]
        result = asyncio.run(chunk_diff_async(["A", "B"], add, update=update, old_chunks_wrappers=old_chunks, unwrap=lambda x: x.lower()))
        self.assertEqual(result, ["update-0-oldA-A", "update-1-oldB-B"])

    def test_chunk_diff_async_remove(self):
        async def add(i, chunk):
            return f"add-{i}-{chunk}"

        async def remove(i, old):
            self.removed.append((i, old))
        self.removed = []
        old_chunks = ["A", "B", "C"]
        # Remove last chunk
        result = asyncio.run(chunk_diff_async(["A", "B"], add, remove=remove, old_chunks_wrappers=old_chunks, unwrap=lambda x: x))
        self.assertEqual(result, [])
        self.assertEqual(self.removed, [(2, "C")])

    def test_chunk_diff_async_update_none_remove(self):
        async def add(i, chunk):
            return f"add-{i}-{chunk}"

        async def remove(i, old):
            self.removed.append((i, old))
        self.removed = []
        old_chunks = ["A", "B"]
        # update is None, remove is not None, so should remove and add
        result = asyncio.run(chunk_diff_async(["a", "B"], add, update=None, remove=remove, old_chunks_wrappers=old_chunks, unwrap=lambda x: x))
        self.assertEqual(result, ["add-0-a"])
        self.assertEqual(self.removed, [(0, "A")])

    def test_chunk_diff_async_unwrap_not_implemented(self):
        async def add(i, chunk):
            return chunk
        # Should raise NotImplementedError if unwrap is not provided and update is needed
        with self.assertRaises(NotImplementedError):
            asyncio.run(chunk_diff_async(["a"], add, update=None, old_chunks_wrappers=["b"]))
