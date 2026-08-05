from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from common.inspection import count_methods
from spellbook.models import Card, Combo, Template, Variant
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH


class TemplateTests(SpellbookTestCaseWithSeeding):
    def test_template_fields(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')
        self.assertEqual(t.description, 'hello.')

    def test_query_string(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn('tou%3E5', t.query_string() or '')
        self.assertIn('legal%3Acommander', t.query_string() or '')
        self.assertTrue((t.query_string() or '').startswith('q='))

    def test_scryfall_api_url(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_API_ROOT, t.scryfall_api() or '')
        self.assertIn(t.query_string(), t.scryfall_api() or '')

    def test_scryfall_link(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link() or '')
        self.assertIn(t.query_string(), t.scryfall_link() or '')
        self.assertIn('<a', t.scryfall_link() or '')
        self.assertIn('target="_blank"', t.scryfall_link() or '')
        self.assertTrue((t.scryfall_link(raw=True) or '').startswith('http'))
        self.assertIn(t.scryfall_link(raw=True), t.scryfall_link(raw=False) or '')

        t.scryfall_query = ''
        self.assertNotIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link() or '')
        self.assertNotIn(t.query_string(), t.scryfall_link() or '')
        self.assertNotIn('<a', t.scryfall_link() or '')
        self.assertNotIn('target="_blank"', t.scryfall_link() or '')

    def test_card_replacements(self):
        t = Template.objects.get(id=self.t2_id)
        self.assertEqual(t.replacements.count(), 1)
        self.assertEqual(t.scryfall_link(), None)
        t.replacements.add(Card.objects.get(id=self.c4_id))
        self.assertEqual(t.replacements.count(), 2)

    def test_method_count(self):
        self.assertEqual(count_methods(Template), 4)

    def test_renaming_a_template_updates_variant_and_combo_names(self):
        self.generate_variants()
        template = Template.objects.get(id=self.t1_id)
        old_name = template.name
        variant_ids = [variant.id for variant in Variant.objects.filter(requires=template)]
        combo_ids = [combo.id for combo in Combo.objects.filter(requires=template)]
        self.assertGreater(len(variant_ids), 0)
        self.assertGreater(len(combo_ids), 0)

        template.name = 'Renamed Template'
        template.save()

        for variant in Variant.objects.filter(id__in=variant_ids):
            with self.subTest(variant=variant.pk):
                self.assertIn('Renamed Template', variant.name)
                self.assertNotIn(old_name, variant.name)
        for combo in Combo.objects.filter(id__in=combo_ids):
            with self.subTest(combo=combo.pk):
                self.assertIn('Renamed Template', combo.name)
                self.assertNotIn(old_name, combo.name)

    def test_saving_a_template_without_renaming_it_skips_updates(self):
        self.generate_variants()
        template = Template.objects.get(id=self.t1_id)
        template.description = 'Another description'
        # only the update itself: the loaded name rules out a rename without any lookup
        with self.assertNumQueries(1):
            template.save()
