from urllib.parse import urlencode


SCRYFALL_API_ROOT = 'https://api.scryfall.com'

SCRYFALL_API_CARD_SEARCH = SCRYFALL_API_ROOT + '/cards/search'

SCRYFALL_WEBSITE_ROOT = 'https://scryfall.com'

SCRYFALL_WEBSITE_CARD_SEARCH = SCRYFALL_WEBSITE_ROOT + '/search'

SCRYFALL_LEGAL_IN_COMMANDER = 'legal:commander'

SCRYFALL_MAX_QUERY_LENGTH = 1024


def scryfall_query_string_for_card_names(card_names: list[str]) -> str:
    cards_query = ' or '.join(f'!"{card}"' for card in card_names)
    return urlencode({'q': cards_query})


def scryfall_link_for_query(query: str) -> str:
    if len(query) > SCRYFALL_MAX_QUERY_LENGTH:
        raise ValueError(f'Query is too long: {len(query)} > {SCRYFALL_MAX_QUERY_LENGTH}')
    return f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{query}'


def scryfall_query_legal_in_commander(q: str) -> str:
    if q:
        return f'({q}) {SCRYFALL_LEGAL_IN_COMMANDER}'
    return SCRYFALL_LEGAL_IN_COMMANDER
