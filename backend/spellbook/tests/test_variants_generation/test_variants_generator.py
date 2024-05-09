from itertools import chain
from spellbook.tests.abstract_test import AbstractTestCaseWithSeeding
from spellbook.models import Job, Variant, Card, IngredientInCombination, CardInVariant, TemplateInVariant, Template, Combo, Feature
from spellbook.variants.variant_data import Data
from spellbook.variants.variants_generator import get_variants_from_graph, get_default_zone_location_for_card, update_state_with_default, generate_variants, apply_replacements
from spellbook.utils import launch_job_command


class VariantsGeneratorTests(AbstractTestCaseWithSeeding):
    def test_get_variants_from_graph(self):
        job = Job.start('test_get_variants_from_graph')
        if job is None:
            self.fail('Job.start() returned None')
        result = get_variants_from_graph(data=Data(), job=job)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), self.expected_variant_count)
        self.assertGreater(len(job.message), 0)
        launch_job_command('generate_variants')
        self.assertEqual(len(result), Variant.objects.count())
        self.assertEqual(set(result.keys()), set(Variant.objects.values_list('id', flat=True)))
        for variant_definition in result.values():
            card_set = set(variant_definition.card_ids)
            template_set = set(variant_definition.template_ids)
            for feature, feature_replacement_list in variant_definition.feature_replacements.items():
                self.assertIn(feature, variant_definition.feature_ids)
                self.assertGreater(len(feature_replacement_list), 0)
                for feature_replacement in feature_replacement_list:
                    self.assertTrue(card_set.issuperset(feature_replacement.card_ids))
                    self.assertTrue(template_set.issuperset(feature_replacement.template_ids))

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

    def test_update_state_with_default(self):
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

    def test_update_state(self):
        # TODO: Implement
        pass

    def test_apply_replacements(self):
        replacements = {
            Feature.objects.get(id=self.f1_id): [([Card.objects.get(id=self.c1_id)], []), ([Card.objects.get(id=self.c2_id)], [])],
            Feature.objects.get(id=self.f2_id): [([], [Template.objects.get(id=self.t1_id)]), ([], [Template.objects.get(id=self.t2_id)])],
            Feature.objects.get(id=self.f3_id): [([Card.objects.get(id=self.c1_id), Card.objects.get(id=self.c2_id)], [Template.objects.get(id=self.t1_id), Template.objects.get(id=self.t2_id)])],
        }
        tests = [
            ('', ''),
            ('no replacements\n ok?', 'no replacements\n ok?'),
            ('a sentence with one [[FA]] replacement.', 'a sentence with one A A replacement.'),
            ('two replacements: [[FA]] and [[FB]].', 'two replacements: A A and TA.'),
            ('repeated replacements: [[FA]][[FA]][FA].', 'repeated replacements: A AA A[FA].'),
            ('combined replacement with [[FC]]', 'combined replacement with A A + B B + TA + TB'),
            ('not found [[XYZ]] replacement.', 'not found [[XYZ]] replacement.'),
            ('replacement with alias: [[FA|XYZ]]', 'replacement with alias: A A'),
            ('alias [[FA|XYZ]] invocation in [[XYZ]]', 'alias A A invocation in A A'),
            ('alias [[FA|asd ok]] invocation in [[asd ok]]', 'alias A A invocation in A A'),
            ('alias edge case [[FA|FB]] invocation in [[FB]]', 'alias edge case A A invocation in A A'),
        ]
        for test in tests:
            self.assertEqual(apply_replacements(test[0], replacements), test[1])

    def test_restore_variant(self):
        # TODO: Implement
        # TODO: Regression test for restore_variant with a variant that includes a combo that contains a card missing from the variant
        pass

    def test_update_variant(self):
        # TODO: Implement
        pass

    def test_create_variant(self):
        # TODO: Implement
        pass

    def test_perform_bulk_save(self):
        # TODO: Implement
        pass

    def test_generate_variants(self):
        added, restored, deleted = generate_variants()
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        self.assertEqual(added, self.expected_variant_count)
        self.assertEqual(restored, 0)
        self.assertEqual(deleted, 0)
        for variant in Variant.objects.all():
            self.assertEqual(variant.status, Variant.Status.NEW)
            self.assertGreater(len(variant.name), 0)
            self.assertGreater(len(variant.description), 0)
            if variant.cards():
                self.assertTrue(any(
                    len(text_field) > 0
                    for card_in_variant in variant.cardinvariant_set.all()
                    for text_field in (
                        card_in_variant.battlefield_card_state,
                        card_in_variant.exile_card_state,
                        card_in_variant.graveyard_card_state,
                        card_in_variant.library_card_state
                    )
                ))
            if variant.templates():
                self.assertTrue(any(
                    len(text_field) > 0
                    for template_in_variant in variant.templateinvariant_set.all()
                    for text_field in (
                        template_in_variant.battlefield_card_state,
                        template_in_variant.exile_card_state,
                        template_in_variant.graveyard_card_state,
                        template_in_variant.library_card_state
                    )
                ))
        Variant.objects.update(status=Variant.Status.OK)
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 0)
        self.assertEqual(deleted, 0)
        self.assertTrue(all(variant.status == Variant.Status.OK for variant in Variant.objects.all()))
        Variant.objects.update(status=Variant.Status.RESTORE)
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, self.expected_variant_count)
        self.assertEqual(deleted, 0)
        self.assertTrue(all(variant.status == Variant.Status.NEW for variant in Variant.objects.all()))
        Combo.objects.filter(status__in=(Combo.Status.GENERATOR, Combo.Status.GENERATOR_WITH_MANY_CARDS)).update(status=Combo.Status.DRAFT)
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 0)
        self.assertEqual(deleted, self.expected_variant_count)
        self.assertEqual(Variant.objects.count(), 0)

    def test_generate_variants_deletion(self):
        for status in Variant.Status.values:
            Combo.objects.filter(status=Combo.Status.DRAFT).update(status=Combo.Status.GENERATOR_WITH_MANY_CARDS)
            generate_variants()
            self.assertEqual(Variant.objects.count(), self.expected_variant_count)
            Variant.objects.update(status=status)
            Combo.objects.filter(status__in=(Combo.Status.GENERATOR, Combo.Status.GENERATOR_WITH_MANY_CARDS)).update(status=Combo.Status.DRAFT)
            generate_variants()
            self.assertEqual(Variant.objects.count(), 0)

    def test_variant_aliases_update(self):
        # TODO: Implement
        pass
