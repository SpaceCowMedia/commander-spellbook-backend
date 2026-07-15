import re


MARKDOWN_ESCAPE_PATTERN = re.compile(f'([{re.escape(r"_*`[")}])')


def escape_markdown(text: str) -> str:
    return MARKDOWN_ESCAPE_PATTERN.sub(r'\\\1', text)
