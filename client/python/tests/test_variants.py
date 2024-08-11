from .testing import SpellbookClientTest


class TestVariants(SpellbookClientTest):
    async def test_variants_without_parameters(self):
        variants = await self.spellbook_client_anonymous.variants.get()
        self.assertIsNotNone(variants)
