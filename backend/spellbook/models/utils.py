import unicodedata


def recipe(ingredients: list[str], results: list[str], negative_results: list[str] = []):
    return ' + '.join(ingredients) \
        + ' ➜ ' + ' + '.join(results[:3]) \
        + ('...' if len(results) > 3 else '') \
        + (' - ' + ' - '.join(negative_results[:3]) if negative_results else '') \
        + ('...' if len(negative_results) > 3 else '')


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def id_from_cards_and_templates_ids(cards: list[int], templates: list[int]) -> str:
    sorted_templates = sorted(templates)
    return '-'.join(str(c) for c in sorted(cards)) + ('--' + '--'.join(str(t) for t in sorted_templates) if len(sorted_templates) > 0 else '')
