from django.test import LiveServerTestCase
from spellbook_client.models.paginated_variant_list import PaginatedVariantList
from spellbook_client import ApiClient, configuration, VariantsApi
from spellbook.tests.testing import TestCaseMixinWithSeeding


class SpellbookClientTest(TestCaseMixinWithSeeding, LiveServerTestCase):
    def setUp(self):
        super().setUp()
        super().generate_and_publish_variants()
        self.anonymous_api_client_configuration = configuration.Configuration(
            host=self.live_server_url,
        )

    @property
    def anonymous_api_client(self):
        return ApiClient(self.anonymous_api_client_configuration)

    async def get_variants(self, q='') -> PaginatedVariantList:
        async with self.anonymous_api_client as api_client:
            api_instance = VariantsApi(api_client)
            result = await api_instance.variants_list(q=q)
            assert result is not None
            return result
