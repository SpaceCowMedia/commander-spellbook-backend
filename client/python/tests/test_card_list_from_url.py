from .testing import SpellbookClientTest
from spellbook_client import CardListFromUrlApi
from spellbook_client.exceptions import BadRequestException


class TestCardListFromUrl(SpellbookClientTest):
    async def test_with_invalid_url(self):
        with self.assertRaises(BadRequestException):
            async with self.anonymous_api_client as api_client:
                api_instance = CardListFromUrlApi(api_client)
                await api_instance.card_list_from_url_retrieve(url='https://example.com')
