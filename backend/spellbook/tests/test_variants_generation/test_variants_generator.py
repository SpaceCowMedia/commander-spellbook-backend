from itertools import chain
from spellbook.tests.abstract_test import AbstractModelTests
from spellbook.models import Job, Variant, Card, IngredientInCombination, CardInVariant, TemplateInVariant, Template
from spellbook.variants.variant_data import Data
from spellbook.variants.variants_generator import get_variants_from_graph, get_default_zone_location_for_card, update_state_with_default
from spellbook.utils import launch_job_command


class VariantsGeneratorTests(AbstractModelTests):
    def test_get_variants_from_graph(self):
        job = Job.start('test_get_variants_from_graph')
        if job is None:
            self.fail('Job.start() returned None')
        result = get_variants_from_graph(data=Data(), job=job)
        self.assertIsInstance(result, dict)
        self.assertEquals(len(result), self.expected_variant_count)
        self.assertGreater(len(job.message), 0)
        launch_job_command('generate_variants')
        self.assertEqual(len(result), Variant.objects.count())
        self.assertEqual(set(result.keys()), set(Variant.objects.values_list('id', flat=True)))

    def test_subtract_removed_features(self):
        # TODO: Implement
        pass

    def test_default_zone_location_for_card(self):
        for card in Card.objects.all():
            location = get_default_zone_location_for_card(card)
            self.assertIsInstance(location, str)
            self.assertGreater(len(location), 0)
            if any(ct in card.type_line for ct in ('Instant', 'Sorcery')):
                self.assertEqual(location, IngredientInCombination.ZoneLocation.HAND)
            else:
                self.assertEqual(location, IngredientInCombination.ZoneLocation.BATTLEFIELD)

    def test_default_ingredient_state(self):
        civs = (CardInVariant(card=c) for c in Card.objects.all())
        tivs = (TemplateInVariant(template=t) for t in Template.objects.all())
        for sut in chain(civs, tivs):
            update_state_with_default(sut)
            self.assertEqual(sut.battlefield_card_state, '')
            self.assertEqual(sut.exile_card_state, '')
            self.assertEqual(sut.graveyard_card_state, '')
            self.assertEqual(sut.library_card_state, '')
            self.assertEqual(sut.must_be_commander, False)
            if isinstance(sut, CardInVariant):
                self.assertEqual(sut.zone_locations, get_default_zone_location_for_card(sut.card))
            else:
                self.assertEqual(sut.zone_locations, IngredientInCombination._meta.get_field('zone_locations').get_default())
