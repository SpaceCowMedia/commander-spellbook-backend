from .testing import SpellbookClientTest
from kiota_abstractions.api_error import APIError
from kiota_abstractions.base_request_configuration import RequestConfiguration


class TestCardListFromUrl(SpellbookClientTest):
    async def test_with_invalid_url(self):
        with self.assertRaises(APIError):
            await self.spellbook_client_anonymous.card_list_from_url.get(
                request_configuration=RequestConfiguration[self.spellbook_client_anonymous.card_list_from_url.CardListFromUrlRequestBuilderGetQueryParameters](
                    query_parameters=self.spellbook_client_anonymous.card_list_from_url.CardListFromUrlRequestBuilderGetQueryParameters(
                        url='https://example.com',
                    )
                )
            )
