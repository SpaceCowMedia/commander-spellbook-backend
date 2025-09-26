from django.test import LiveServerTestCase
from django.utils.functional import classproperty
from spellbook_client.models.paginated_variant_list import PaginatedVariantList
from spellbook_client import ApiClient, configuration, VariantsApi
from spellbook.tests.testing import SpellbookTestCaseWithSeeding


class SpellbookClientTest(SpellbookTestCaseWithSeeding, LiveServerTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        super().generate_and_publish_variants()
        cls.anonymous_api_client_configuration = configuration.Configuration(
            host=cls.live_server_url,
        )

    @classproperty
    def anonymous_api_client(cls):
        return ApiClient(cls.anonymous_api_client_configuration)

    @classmethod
    async def get_variants(cls, q='') -> PaginatedVariantList:
        async with cls.anonymous_api_client as api_client:
            api_instance = VariantsApi(api_client)
            result = await api_instance.variants_list(q=q)
            assert result is not None
            return result
