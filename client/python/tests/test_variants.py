from .testing import SpellbookClientTest


class TestVariants(SpellbookClientTest):
    async def test_variants_without_parameters(self):
        variants = await self.get_variants()
        assert variants.results is not None
        self.assertEqual(7, len(variants.results))
