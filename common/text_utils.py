from typing import Callable, TypeVar, Awaitable


DISCORD_MESSAGE_LIMIT = 2000
TELEGRAM_MESSAGE_LIMIT = 4096


def text_chunk(message: str, size: int) -> list[str]:
    messages = []
    content = message
    while content:
        next_block = content[:size]
        if len(content) > size and '\n' in next_block:
            split = next_block.rindex('\n')
        elif len(content) > size and ' ' in next_block:
            split = next_block.rindex(' ')
        else:
            split = size
        messages.append(content[:split])
        content = content[split + 1:]
    return messages


def discord_chunk(message: str) -> list[str]:
    return text_chunk(message, DISCORD_MESSAGE_LIMIT)


def telegram_chunk(message: str) -> list[str]:
    return text_chunk(message, TELEGRAM_MESSAGE_LIMIT)


T = TypeVar('T')


async def chunk_diff_async(
        new_chunks: list[str],
        add: Callable[[int, str], Awaitable[T]],
        update: Callable[[int, T, str], Awaitable[T]] | None = None,
        remove: Callable[[int, T], Awaitable] | None = None,
        old_chunks_wrappers: list[T] | None = None,
        unwrap: Callable[[T], str] | None = None,
) -> list[T]:
    if old_chunks_wrappers is None:
        old_chunks_wrappers = []
    if unwrap is None:
        def _unwrap(_: T) -> str:
            raise NotImplementedError
        unwrap = _unwrap
    result: list[T] = []
    for i, new_chunk in enumerate(new_chunks):
        if i >= len(old_chunks_wrappers):
            result.append(await add(i, new_chunk))
        elif new_chunk != unwrap(old_chunks_wrappers[i]):
            if update is None and remove is not None:
                await remove(i, old_chunks_wrappers[i])
                result.append(await add(i, new_chunk))
            elif update is not None:
                result.append(await update(i, old_chunks_wrappers[i], new_chunk))
    if remove is not None:
        for i in range(len(new_chunks), len(old_chunks_wrappers)):
            await remove(i, old_chunks_wrappers[i])
    return result
