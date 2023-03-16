from urllib.parse import urlencode
from django.utils.html import format_html
from .scryfall import SCRYFALL_WEBSITE_CARD_SEARCH


class ScryfallLinkMixin:
    def query_string(self):
        cards_query = ' or '.join(f'!"{card.name}"' for card in self.cards())
        return urlencode({'q': cards_query})

    def scryfall_link(self):
        link = f'{SCRYFALL_WEBSITE_CARD_SEARCH}?{self.query_string()}'
        return format_html(f'<a href="{link}" target="_blank">Show cards on scryfall</a>')
