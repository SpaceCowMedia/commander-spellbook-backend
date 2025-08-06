from itertools import chain
from multiset import FrozenMultiset
from django.test import TestCase
from django.db.models import Count
from spellbook.models.combo import FeatureNeededInCombo
from spellbook.models.feature_attribute import FeatureAttribute
from spellbook.tests.testing import TestCaseMixinWithSeeding
from spellbook.models import Job, Variant, Card, IngredientInCombination, CardInVariant, TemplateInVariant, Template, Combo, Feature, VariantAlias, FeatureOfCard, ZoneLocation
from spellbook.variants.combo_graph import FeatureWithAttributes
from spellbook.variants.variant_data import Data
from spellbook.variants.variants_generator import get_variants_from_graph, get_default_zone_location_for_card, update_state_with_default
from spellbook.variants.variants_generator import generate_variants, apply_replacements, subtract_features, update_state
from spellbook.variants.variants_generator import sync_variant_aliases
from spellbook.utils import launch_job_command


class VariantsGeneratorTests(TestCaseMixinWithSeeding, TestCase):
    def test_get_variants_from_graph(self):
        job = Job.start('test_get_variants_from_graph')
        if job is None:
            self.fail('Job.start() returned None')
        result = get_variants_from_graph(data=Data(), single_combo=None, job=job, log_count=100)
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), self.expected_variant_count)
        self.assertGreater(len(job.message), 0)
        launch_job_command('generate_variants')
        self.assertEqual(len(result), Variant.objects.count())
        self.assertEqual(set(result.keys()), set(Variant.objects.values_list('id', flat=True)))
        for variant_definition in result.values():
            card_set = set(variant_definition.card_ids)
            template_set = set(variant_definition.template_ids)
            for feature_replacement_list in variant_definition.feature_replacements.values():
                self.assertGreater(len(feature_replacement_list), 0)
                for feature_replacement in feature_replacement_list:
                    self.assertTrue(card_set.issuperset(feature_replacement.card_ids))
                    self.assertTrue(template_set.issuperset(feature_replacement.template_ids))

    def test_subtract_features(self):
        c = Combo.objects.create(mana_needed='{W}', status=Combo.Status.UTILITY)
        c.cardincombo_set.create(card_id=self.c1_id, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        c.removes.add(self.f1_id)
        c.removes.add(self.f2_id)
        data = Data()
        features = subtract_features(
            data,
            includes={c.id},
            features=FrozenMultiset({self.f1_id: 3, self.f2_id: 2, self.f3_id: 5}),
        )
        self.assertEqual(features, FrozenMultiset({self.f3_id: 5}))
        c.status = Combo.Status.GENERATOR
        c.save()
        c2 = Combo.objects.create(mana_needed='{W}', status=Combo.Status.UTILITY)
        c2.cardincombo_set.create(card_id=self.c1_id, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        c2.removes.add(self.f3_id)
        data = Data()
        features = subtract_features(
            data,
            includes={c.id, c2.id},
            features=FrozenMultiset({self.f1_id: 3, self.f2_id: 2, self.f3_id: 5}),
        )
        self.assertEqual(features, FrozenMultiset())
        f = Feature.objects.get(pk=self.f1_id)
        f.status = Feature.Status.UTILITY
        f.save()
        data = Data()
        features = subtract_features(
            data,
            includes=set(),
            features=FrozenMultiset({self.f1_id: 3, self.f2_id: 2, self.f3_id: 5}),
        )
        self.assertEqual(features, FrozenMultiset({self.f2_id: 2, self.f3_id: 5}))

    def test_default_zone_location_for_card(self):
        for card in Card.objects.all():
            location = get_default_zone_location_for_card(card)
            self.assertIsInstance(location, str)
            self.assertGreater(len(location), 0)
            if any(ct in card.type_line for ct in ('Instant', 'Sorcery')):
                self.assertEqual(location, ZoneLocation.HAND)
            else:
                self.assertEqual(location, ZoneLocation.BATTLEFIELD)

    def test_update_state_with_default(self):
        data = Data()
        civs = (CardInVariant(card=c) for c in Card.objects.all())
        tivs = (TemplateInVariant(template=t) for t in Template.objects.all())
        for sut in chain(civs, tivs):
            update_state_with_default(data, sut)
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
        data = Data()
        civs = list(CardInVariant(card=c) for c in Card.objects.all())
        tivs = list(TemplateInVariant(template=t) for t in Template.objects.all())
        for sut1, sut2 in zip(chain(civs, tivs), chain(reversed(civs), reversed(tivs))):  # type: ignore
            sut1.battlefield_card_state = 'battlefield_card_state'
            sut1.exile_card_state = 'exile_card_state'
            sut1.graveyard_card_state = 'graveyard_card_state'
            sut1.library_card_state = 'library_card_state'
            sut1.must_be_commander = True
            sut1.zone_locations = ZoneLocation.COMMAND_ZONE + ZoneLocation.BATTLEFIELD
            update_state_with_default(data, sut2)
            update_state(dst=sut2, src=sut1, overwrite=True)
            self.assertEqual(sut2.battlefield_card_state, sut1.battlefield_card_state)
            self.assertEqual(sut2.exile_card_state, sut1.exile_card_state)
            self.assertEqual(sut2.graveyard_card_state, sut1.graveyard_card_state)
            self.assertEqual(sut2.library_card_state, sut1.library_card_state)
            self.assertEqual(sut2.must_be_commander, sut1.must_be_commander)
            self.assertEqual(sut2.zone_locations, sut1.zone_locations)
            sut2.battlefield_card_state = 'battlefield_card_state2'
            sut2.exile_card_state = 'exile_card_state2'
            sut2.graveyard_card_state = 'graveyard_card_state2'
            sut2.library_card_state = 'library_card_state2'
            sut2.must_be_commander = False
            sut2.zone_locations = ZoneLocation.BATTLEFIELD + ZoneLocation.EXILE
            update_state(dst=sut2, src=sut1, overwrite=False)
            self.assertIn(sut1.battlefield_card_state, sut2.battlefield_card_state)
            self.assertIn('battlefield_card_state2', sut2.battlefield_card_state)
            self.assertIn(sut1.exile_card_state, sut2.exile_card_state)
            self.assertIn('exile_card_state2', sut2.exile_card_state)
            self.assertIn(sut1.graveyard_card_state, sut2.graveyard_card_state)
            self.assertIn('graveyard_card_state2', sut2.graveyard_card_state)
            self.assertIn(sut1.library_card_state, sut2.library_card_state)
            self.assertIn('library_card_state2', sut2.library_card_state)
            self.assertEqual(sut2.must_be_commander, True)
            self.assertEqual(sut2.zone_locations, ZoneLocation.BATTLEFIELD)
            sut2.zone_locations = ZoneLocation.HAND
            update_state(dst=sut2, src=sut1, overwrite=False)
            self.assertEqual(sut2.zone_locations, ZoneLocation.HAND)
            sut2.zone_locations = ''
            update_state(dst=sut2, src=sut1, overwrite=False)
            self.assertEqual(sut2.zone_locations, sut1.zone_locations)

    def test_apply_replacements(self):
        legendary_card = Card.objects.create(
            name='The Name, the Title',
            type_line='Legendary Creature - Human',
        )
        non_legendary_card = Card.objects.create(
            name='The Name, different Title',
            type_line='Creature - Human',
        )
        legendary_modal_card = Card.objects.create(
            name='The Name, the Title  // Another Name, Another Title',
            type_line='Legendary Creature - Human // Legendary Enchantment',
        )
        normal_card = Card.objects.create(
            name='Normal Card',
            type_line='Instant',
        )
        fx = Feature.objects.create(name='FX')
        fy = Feature.objects.create(name='FY')
        fz = Feature.objects.create(name='FZ')
        fw = Feature.objects.create(name='FW')
        fattr = FeatureAttribute.objects.create(name='FAttr')
        combo = Combo.objects.create(status=Combo.Status.UTILITY)
        fn = FeatureNeededInCombo.objects.create(combo=combo, feature=fx)
        fn.none_of_attributes.add(fattr)
        replacements = {
            FeatureWithAttributes(Feature.objects.get(id=self.f1_id), frozenset()): [([Card.objects.get(id=self.c1_id)], []), ([Card.objects.get(id=self.c2_id)], [])],
            FeatureWithAttributes(Feature.objects.get(id=self.f2_id), frozenset()): [([], [Template.objects.get(id=self.t1_id)]), ([], [Template.objects.get(id=self.t2_id)])],
            FeatureWithAttributes(Feature.objects.get(id=self.f3_id), frozenset()): [([Card.objects.get(id=self.c1_id), Card.objects.get(id=self.c2_id)], [Template.objects.get(id=self.t1_id), Template.objects.get(id=self.t2_id)])],
            FeatureWithAttributes(fx, frozenset({fattr.id})): [([normal_card], [])],  # Test invalid entries due to attributes
            FeatureWithAttributes(fx, frozenset()): [([legendary_card], [])],
            FeatureWithAttributes(fy, frozenset()): [([non_legendary_card], [])],
            FeatureWithAttributes(fy, frozenset({fattr.id})): [([normal_card], [])],  # Test for multiple valid entries with different attributes
            FeatureWithAttributes(fz, frozenset()): [([legendary_modal_card], [])],
            FeatureWithAttributes(fw, frozenset()): [([legendary_card, non_legendary_card, legendary_modal_card, normal_card], [])],
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
            ('Legendary name cut before comma: [[FX]]', 'Legendary name cut before comma: The Name'),
            ('Non-legendary name not cut before comma: [[FY]]', 'Non-legendary name not cut before comma: The Name, different Title'),
            ('Test replacement selector: [[FY$1]] - [[FY$2]]', 'Test replacement selector: The Name, different Title - Normal Card'),
            ('Test replacement selector alias: [[FY$1|X]] - [[FY$2|Y]] - [[X]] - [[Y]]', 'Test replacement selector alias: The Name, different Title - Normal Card - The Name, different Title - Normal Card'),
            ('Test replacement selector postfix alias: [[FY|X$1|Y]] - [[X]] - [[X$2]] - [[Y]] - [[Y$2]]', 'Test replacement selector postfix alias: The Name, different Title - The Name, different Title - Normal Card - The Name, different Title - [[Y$2]]'),
            ('Legendary modal name never cut: [[FZ]]', 'Legendary modal name never cut: The Name, the Title  // Another Name, Another Title'),
            ('Multiple replacements: [[FW]]', 'Multiple replacements: The Name + The Name, different Title + The Name, the Title  // Another Name, Another Title + Normal Card'),
        ]
        data = Data()
        for test in tests:
            self.assertEqual(apply_replacements(data, test[0], replacements, {combo.id}), test[1])

    def test_restore_variant(self):
        # TODO: Implement
        # TODO: Regression test for restore_variant with a variant that includes a combo that contains a card missing from the variant
        # TODO: Test if restoring a variant with a Job updates the generated_by field
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
        for _ in range(20):
            Variant.objects.all().delete()
            with self.subTest():
                added, restored, deleted = generate_variants()
                self.assertEqual(Variant.objects.count(), self.expected_variant_count)
                self.assertEqual(added, self.expected_variant_count)
                self.assertEqual(restored, 0)
                self.assertEqual(deleted, 0)
                variant: Variant
                for variant in Variant.objects.all():
                    self.assertEqual(variant.status, Variant.Status.NEW)
                    self.assertEqual(variant.mana_value, sum(variant.uses.values_list('mana_value', flat=True)))
                    self.assertGreater(len(variant.name), 0)
                    self.assertGreater(len(variant.description), 0)
                    self.assertGreater(len(variant.comment), 0)
                    self.assertGreater(len(variant.notes), 0)
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
        Combo.objects.filter(status=Combo.Status.GENERATOR).update(status=Combo.Status.DRAFT)
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 0)
        self.assertEqual(deleted, self.expected_variant_count)
        self.assertEqual(Variant.objects.count(), 0)

    def test_generate_variants_deletion(self):
        for status in Variant.Status.values:
            Combo.objects.filter(status=Combo.Status.DRAFT).update(status=Combo.Status.GENERATOR, allow_many_cards=True)
            generate_variants()
            self.assertEqual(Variant.objects.count(), self.expected_variant_count)
            Variant.objects.update(status=status)
            Combo.objects.filter(status=Combo.Status.GENERATOR).update(status=Combo.Status.DRAFT)
            generate_variants()
            self.assertEqual(Variant.objects.count(), 0)

    def test_restore_zombie_variants(self):
        Combo.objects.filter(status=Combo.Status.DRAFT).update(status=Combo.Status.GENERATOR)
        generate_variants()
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        Variant.objects.update(status=Variant.Status.OK)
        v: Variant = Variant.objects.alias(of_count=Count('of')).filter(of_count=1).first()  # type: ignore
        c: Combo = v.of.first()  # type: ignore
        c.status = Combo.Status.DRAFT
        c.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 0)
        self.assertGreaterEqual(deleted, 1)
        c.status = Combo.Status.GENERATOR
        c.save()
        added, restored, deleted = generate_variants()
        self.assertGreaterEqual(added, 1)
        self.assertEqual(restored, 0)
        self.assertEqual(deleted, 0)
        Variant.objects.update(status=Variant.Status.OK)
        to_restore: list[str] = list(c.variants.values_list('id', flat=True))  # type: ignore
        c.variantofcombo_set.all().delete()  # type: ignore
        c.description = 'New description'
        c.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, len(to_restore))
        self.assertEqual(deleted, 0)
        for v_id in to_restore:
            v: Variant = Variant.objects.get(pk=v_id)  # type: ignore
            self.assertEqual(v.status, Variant.Status.NEW)
            self.assertIn(c.description, v.description)
            self.assertIn(c.comment, v.comment)
            self.assertIn(c.notes, v.notes)

    def test_unwanted_text_with_combo(self):
        generate_variants()
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        v: Variant = Variant.objects.first()  # type: ignore
        useless_combo = Combo.objects.create(mana_needed='{W}', status=Combo.Status.UTILITY, description='<<<Unwanted text>>>')
        for i, card in enumerate(v.uses.all(), start=1):
            useless_combo.cardincombo_set.create(card=card, order=i, zone_locations=ZoneLocation.BATTLEFIELD)
        useless_feature = Feature.objects.create(name='Useless', status=Feature.Status.UTILITY)
        useless_combo.produces.add(useless_feature)
        v.status = Variant.Status.RESTORE
        v.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(deleted, 0)
        v.refresh_from_db()
        self.assertNotIn(useless_combo.description, v.description)
        useless_feature.status = Feature.Status.CONTEXTUAL
        useless_feature.save()
        v.status = Variant.Status.RESTORE
        v.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(deleted, 0)
        v.refresh_from_db()
        self.assertIn(useless_combo.description, v.description)
        useless_feature.status = Feature.Status.UTILITY
        useless_feature.save()
        enabler = Combo.objects.create(mana_needed='{W}', status=Combo.Status.UTILITY)
        result = Feature.objects.create(name='Result', status=Feature.Status.CONTEXTUAL)
        enabler.produces.add(result)
        enabler.needs.add(useless_feature)
        v.status = Variant.Status.RESTORE
        v.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(deleted, 0)
        v.refresh_from_db()
        self.assertIn(useless_combo.description, v.description)

    def test_unwanted_text_with_card(self):
        generate_variants()
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        v: Variant = Variant.objects.first()  # type: ignore
        useless_feature = Feature.objects.create(name='Useless', status=Feature.Status.UTILITY)
        foc = FeatureOfCard.objects.create(
            card=v.uses.first(),
            feature=useless_feature,
            zone_locations=ZoneLocation.BATTLEFIELD,
            battlefield_card_state='<<<Unwanted text>>>'
        )
        v.status = Variant.Status.RESTORE
        v.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(deleted, 0)
        v.refresh_from_db()
        self.assertNotIn(foc.battlefield_card_state, v.cardinvariant_set.filter(card=foc.card).first().battlefield_card_state)  # type: ignore
        for status in [Feature.Status.CONTEXTUAL, Feature.Status.STANDALONE, Feature.Status.HELPER]:
            useless_feature.status = status
            useless_feature.save()
            v.status = Variant.Status.RESTORE
            v.save()
            added, restored, deleted = generate_variants()
            self.assertEqual(added, 0)
            self.assertEqual(restored, 1)
            self.assertEqual(deleted, 0)
            v.refresh_from_db()
            self.assertIn(foc.battlefield_card_state, v.cardinvariant_set.filter(card=foc.card).first().battlefield_card_state)  # type: ignore
        useless_feature.status = Feature.Status.UTILITY
        useless_feature.save()
        enabler = Combo.objects.create(mana_needed='{W}', status=Combo.Status.UTILITY)
        result = Feature.objects.create(name='Result', status=Feature.Status.CONTEXTUAL)
        enabler.produces.add(result)
        enabler.needs.add(useless_feature)
        v.status = Variant.Status.RESTORE
        v.save()
        added, restored, deleted = generate_variants()
        self.assertEqual(added, 0)
        self.assertEqual(restored, 1)
        self.assertEqual(deleted, 0)
        v.refresh_from_db()
        self.assertIn(foc.battlefield_card_state, v.cardinvariant_set.filter(card=foc.card).first().battlefield_card_state)  # type: ignore

    def test_sync_variant_aliases(self):
        VariantAlias.objects.all().delete()
        self.generate_variants()
        [v1, v2, v3, v4] = list[Variant](Variant.objects.all()[:4])
        data = Data()
        added, deleted = sync_variant_aliases(
            data,
            {v1.id, v2.id},
            {v3.id, v4.id},
        )
        self.assertEqual(added, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(VariantAlias.objects.count(), 0)
        for v in [v1, v2, v3, v4]:
            v.status = Variant.Status.OK
            v.save()
        data = Data()
        added, deleted = sync_variant_aliases(
            data,
            {v1.id, v2.id},
            {v3.id, v4.id},
        )
        self.assertEqual(added, 2)
        self.assertEqual(deleted, 0)
        self.assertEqual(VariantAlias.objects.count(), 2)
        self.assertEqual(set(VariantAlias.objects.values_list('id', flat=True)), {v3.id, v4.id})
        data = Data()
        added, deleted = sync_variant_aliases(
            data,
            {v3.id, v4.id},
            {v1.id, v2.id},
        )
        self.assertEqual(added, 2)
        self.assertEqual(deleted, 2)
        self.assertEqual(VariantAlias.objects.count(), 2)
        self.assertEqual(set(VariantAlias.objects.values_list('id', flat=True)), {v1.id, v2.id})
        data = Data()
        added, deleted = sync_variant_aliases(
            data,
            {v1.id, v2.id},
            set(),
        )
        self.assertEqual(added, 0)
        self.assertEqual(deleted, 2)
        self.assertEqual(VariantAlias.objects.count(), 0)
        data = Data()
        added, deleted = sync_variant_aliases(
            data,
            set(),
            set()
        )
        self.assertEqual(added, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(VariantAlias.objects.count(), 0)
