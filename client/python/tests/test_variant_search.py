from .testing import SpellbookClientTest


class TestVariantSearch(SpellbookClientTest):
    async def test_without_parameters(self):
        variants = await self.get_variants()
        self.assertEqual(self.expected_variant_count, len(variants.results))

    async def test_by_card_name(self):
        variants = await self.get_variants(q='"A A"')
        for variant in variants.results:
            self.assertTrue(any(
                'A A' in card.card.name for card in variant.uses
            ))

    async def test_by_results(self):
        variants = await self.get_variants(q='"A A" result:C')
        for variant in variants.results:
            self.assertTrue(any(
                'A A' in card.card.name for card in variant.uses
            ))
            self.assertTrue(any(
                'C' in result.feature.name for result in variant.produces
            ))
