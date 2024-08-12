from django.test import LiveServerTestCase
from kiota_abstractions.authentication.anonymous_authentication_provider import AnonymousAuthenticationProvider
from kiota_http.httpx_request_adapter import HttpxRequestAdapter
from kiota_abstractions.base_request_configuration import RequestConfiguration
from ..models.paginated_variant_list import PaginatedVariantList
from ..spellbook_client import SpellbookClient
from spellbook.tests.testing import TestCaseMixinWithSeeding


class SpellbookClientTest(TestCaseMixinWithSeeding, LiveServerTestCase):
    def setUp(self):
        super().setUp()
        super().generate_and_publish_variants()
        self.anonymous_auth_provider = AnonymousAuthenticationProvider()
        self.anonymous_request_adapter = HttpxRequestAdapter(self.anonymous_auth_provider, base_url=self.live_server_url)
        self.spellbook_client_anonymous = SpellbookClient(self.anonymous_request_adapter)

    async def get_variants(self, q='') -> PaginatedVariantList:
        result = await self.spellbook_client_anonymous.variants.get(
            request_configuration=RequestConfiguration[self.spellbook_client_anonymous.variants.VariantsRequestBuilderGetQueryParameters](
                query_parameters=self.spellbook_client_anonymous.variants.VariantsRequestBuilderGetQueryParameters(
                    q=q,
                ),
            ),
        )
        assert result is not None
        return result
