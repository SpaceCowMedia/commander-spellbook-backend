from itertools import chain
from unittest import mock, skipUnless
from django.db.models import Count
from spellbook.models.combo import CardInCombo, FeatureNeededInCombo
from spellbook.models.feature_attribute import FeatureAttribute
from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from spellbook.models import Variant, Card, IngredientInCombination, CardInVariant, TemplateInVariant, Template, Combo, Feature, VariantAlias, FeatureOfCard, ZoneLocation
from spellbook.models import VariantGenerationFingerprints
from spellbook.variants.combo_graph import FeatureWithAttributes
from spellbook.variants.multiset import FrozenMultiset
from spellbook.variants.variant_data import Data
from spellbook.variants import variants_generator
from spellbook.variants.variants_generator import get_variants_from_graph, get_default_zone_location_for_card, update_state_with_default
from spellbook.variants.variants_generator import generate_variants, apply_replacements, build_replacement_strings, subtract_features, update_state
from spellbook.variants.variants_generator import sync_variant_aliases, restore_variants
from multiprocessing_utils import parallelism_is_available


class VariantsGeneratorTests(SpellbookTestCaseWithSeeding):
    def test_get_variants_from_graph(self):
        result = get_variants_from_graph(data=Data())
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), self.expected_variant_count)
        self.generate_variants()
        self.assertEqual(len(result), Variant.objects.count())
        self.assertEqual(set(result.keys()), set(Variant.objects.values_list('id', flat=True)))
        for variant_definition in result.values():
            card_set = set(variant_definition.card_ids.distinct_elements())
            template_set = set(variant_definition.template_ids.distinct_elements())
            for feature_replacement_list in variant_definition.feature_replacements.values():
                self.assertGreater(len(feature_replacement_list), 0)
                for feature_replacement in feature_replacement_list:
                    self.assertTrue(card_set.issuperset(feature_replacement.card_ids.distinct_elements()))
                    self.assertTrue(template_set.issuperset(feature_replacement.template_ids.distinct_elements()))

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
        f.status = Feature.Status.HIDDEN_UTILITY
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
        civs = list(CardInVariant(card=c) for c in Card.objects.all())
        tivs = list(TemplateInVariant(template=t) for t in Template.objects.all())
        for sut1, sut2 in zip(chain(civs, tivs), chain(reversed(civs), reversed(tivs))):  # type: ignore
            sut1.battlefield_card_state = 'battlefield_card_state'
            sut1.exile_card_state = 'exile_card_state'
            sut1.graveyard_card_state = 'graveyard_card_state'
            sut1.library_card_state = 'library_card_state'
            sut1.must_be_commander = True
            sut1.zone_locations = ZoneLocation.COMMAND_ZONE + ZoneLocation.BATTLEFIELD
            update_state(destination=sut2, initial_states=[sut1])
            self.assertEqual(sut2.battlefield_card_state, sut1.battlefield_card_state)
            self.assertEqual(sut2.exile_card_state, sut1.exile_card_state)
            self.assertEqual(sut2.graveyard_card_state, sut1.graveyard_card_state)
            self.assertEqual(sut2.library_card_state, sut1.library_card_state)
            self.assertEqual(sut2.must_be_commander, sut1.must_be_commander)
            self.assertEqual(sut2.zone_locations, sut1.zone_locations)
            other = CardInVariant(
                battlefield_card_state='battlefield_card_state2',
                exile_card_state='exile_card_state2',
                graveyard_card_state='graveyard_card_state2',
                library_card_state='library_card_state2',
                must_be_commander=False,
                zone_locations=ZoneLocation.BATTLEFIELD + ZoneLocation.EXILE,
            )
            update_state(destination=sut2, initial_states=[sut1, other])
            self.assertEqual(sut2.battlefield_card_state, 'battlefield_card_state and battlefield_card_state2')
            self.assertEqual(sut2.exile_card_state, 'exile_card_state and exile_card_state2')
            self.assertEqual(sut2.graveyard_card_state, 'graveyard_card_state and graveyard_card_state2')
            self.assertEqual(sut2.library_card_state, 'library_card_state and library_card_state2')
            self.assertEqual(sut2.must_be_commander, True)
            self.assertEqual(sut2.zone_locations, ZoneLocation.BATTLEFIELD)
            third = CardInVariant(
                battlefield_card_state='battlefield_card_state3',
                zone_locations=ZoneLocation.HAND,
            )
            update_state(destination=sut2, initial_states=[sut1, other, third])
            self.assertEqual(sut2.battlefield_card_state, 'battlefield_card_state, battlefield_card_state2 and battlefield_card_state3')
            self.assertEqual(sut2.exile_card_state, 'exile_card_state and exile_card_state2')
            self.assertEqual(sut2.zone_locations, ZoneLocation.BATTLEFIELD)
            empty_zones = CardInVariant(zone_locations='')
            update_state(destination=sut2, initial_states=[empty_zones, sut1])
            self.assertEqual(sut2.zone_locations, sut1.zone_locations)
            self.assertEqual(sut2.battlefield_card_state, sut1.battlefield_card_state)

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
        replacement_strings = build_replacement_strings(data, replacements, {combo.id})
        for test in tests:
            self.assertEqual(apply_replacements(test[0], replacement_strings), test[1])

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
                    self.assertEqual(variant.is_mana_needed_an_accurate_minimum, not variant.mana_needed or all(
                        c.is_mana_needed_an_accurate_minimum
                        for c in variant.includes.all()
                    ))
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
        useless_feature = Feature.objects.create(name='Useless', status=Feature.Status.PUBLIC_UTILITY)
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
        useless_feature.status = Feature.Status.HIDDEN_UTILITY
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
        useless_feature = Feature.objects.create(name='Useless', status=Feature.Status.HIDDEN_UTILITY)
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
        useless_feature.status = Feature.Status.PUBLIC_UTILITY
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

    def test_text_field_composition(self):
        c = Combo.objects.create(mana_needed='{1}{U}', status=Combo.Status.GENERATOR, easy_prerequisites='A', notable_prerequisites='A')
        c.cardincombo_set.create(card_id=self.c1_id, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        c.produces.add(self.f1_id)
        c.produces.add(self.f2_id)
        c2 = Combo.objects.create(mana_needed='{2}{U}{U}', status=Combo.Status.UTILITY, easy_prerequisites='B', notable_prerequisites='B')
        c2.cardincombo_set.create(card_id=self.c1_id, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        c2.removes.add(self.f1_id)
        c2.produces.add(self.f3_id)
        card = Card.objects.get(pk=self.c1_id)
        card.featureofcard_set.create(feature_id=self.f2_id, zone_locations=ZoneLocation.HAND, mana_needed='{X}{U}{1}', easy_prerequisites='C', notable_prerequisites='C')
        generate_variants(c.id)
        v: Variant = Variant.objects.get(of=c)
        self.assertEqual(v.mana_value_needed, 8)
        self.assertEqual(v.mana_needed, '{X}{4}{U}{U}{U}{U}')
        self.assertEqual(v.easy_prerequisites, 'A\nB\nC')
        self.assertEqual(v.notable_prerequisites, 'A\nB\nC')


class DeltaWritesTests(SpellbookTestCaseWithSeeding):
    def test_unchanged_variants_produce_no_writes(self):
        generate_variants()
        data = Data()
        variants = get_variants_from_graph(data)
        variant_instances = data.fetch_variants(variants.keys())
        to_update, to_create = restore_variants(
            data=data,
            variants=variants,
            variant_instances=variant_instances,
            to_restore=set(),
            job=None,
        )
        self.assertEqual(len(to_create), 0)
        self.assertEqual(len(to_update), self.expected_variant_count)
        for item in to_update:
            self.assertFalse(item.variant_changed, f'variant {item.variant.id} was detected as changed')
            self.assertFalse(item.uses_to_create)
            self.assertFalse(item.uses_to_update)
            self.assertFalse(item.requires_to_create)
            self.assertFalse(item.requires_to_update)
            self.assertFalse(item.produces_to_create)
            self.assertFalse(item.produces_to_update)

    def test_stale_line_counts_are_healed(self):
        generate_variants()
        v: Variant = Variant.objects.exclude(description='').first()  # type: ignore
        correct_count = v.description_line_count
        Variant.objects.filter(pk=v.pk).update(description_line_count=correct_count + 5, prerequisites_line_count=42)
        generate_variants()
        v.refresh_from_db()
        self.assertEqual(v.description_line_count, correct_count)
        self.assertEqual(
            v.prerequisites_line_count,
            (v.easy_prerequisites.count('\n') + 1 if v.easy_prerequisites else 0) + (v.notable_prerequisites.count('\n') + 1 if v.notable_prerequisites else 0),
        )

    def test_restored_variants_are_detected_as_changed(self):
        generate_variants()
        Variant.objects.update(status=Variant.Status.OK)
        data = Data()
        variants = get_variants_from_graph(data)
        variant_instances = data.fetch_variants(variants.keys())
        to_update, _ = restore_variants(
            data=data,
            variants=variants,
            variant_instances=variant_instances,
            to_restore=set(variants.keys()),
            job='test-job',
        )
        for item in to_update:
            self.assertTrue(item.variant_changed, f'variant {item.variant.id} was not detected as changed')


class IncrementalGenerationTests(SpellbookTestCaseWithSeeding):
    def assert_full_generation_is_noop(self):
        added, restored, deleted = generate_variants()
        self.assertEqual((added, restored, deleted), (0, 0, 0), 'incremental generation left the database in a state that differs from a full generation')

    def test_first_incremental_run_falls_back_to_full(self):
        added, restored, deleted = generate_variants(incremental=True)
        self.assertEqual(added, self.expected_variant_count)
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        self.assertGreater(VariantGenerationFingerprints.objects.count(), 0)

    def test_incremental_run_without_changes_is_noop(self):
        generate_variants()
        added, restored, deleted = generate_variants(incremental=True)
        self.assertEqual((added, restored, deleted), (0, 0, 0))
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)

    def test_incremental_after_combo_text_edit(self):
        generate_variants()
        Variant.objects.update(status=Variant.Status.OK)
        combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()
        combo.description += ' edited'
        combo.save()
        added, restored, deleted = generate_variants(incremental=True)
        self.assertEqual((added, restored, deleted), (0, 0, 0))
        self.assert_full_generation_is_noop()

    def test_incremental_restores_flagged_variants(self):
        generate_variants()
        Variant.objects.update(status=Variant.Status.OK)
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
        combo.description = 'A new description'
        combo.save()
        flagged = list(combo.variants.values_list('id', flat=True))
        Variant.objects.filter(id__in=flagged).update(status=Variant.Status.RESTORE)
        added, restored, deleted = generate_variants(incremental=True)
        self.assertEqual(added, 0)
        self.assertEqual(restored, len(flagged))
        self.assertEqual(deleted, 0)
        for variant in Variant.objects.filter(id__in=flagged):
            self.assertEqual(variant.status, Variant.Status.NEW)
            self.assertIn(combo.description, variant.description)
        self.assert_full_generation_is_noop()

    def test_incremental_after_generator_demotion(self):
        generate_variants()
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
        combo.status = Combo.Status.DRAFT
        combo.save()
        generate_variants(incremental=True)
        self.assertFalse(Variant.objects.filter(of=combo).exists())
        self.assert_full_generation_is_noop()
        combo.status = Combo.Status.GENERATOR
        combo.save()
        added, restored, deleted = generate_variants(incremental=True)
        self.assertGreaterEqual(added, 1)
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        self.assert_full_generation_is_noop()

    def test_incremental_after_new_combo(self):
        generate_variants()
        new_combo = Combo.objects.create(mana_needed='{W}', is_mana_needed_an_accurate_minimum=True, description='new combo', status=Combo.Status.GENERATOR)
        new_combo.cardincombo_set.create(card_id=self.c7_id, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        new_combo.produces.add(self.f4_id)
        added, restored, deleted = generate_variants(incremental=True)
        self.assertEqual(added, 1)
        self.assertEqual(deleted, 0)
        self.assertTrue(Variant.objects.filter(of=new_combo).exists())
        self.assert_full_generation_is_noop()

    def test_incremental_after_feature_status_change(self):
        generate_variants()
        feature = Feature.objects.get(pk=self.f3_id)
        feature.status = Feature.Status.HIDDEN_UTILITY
        feature.save()
        generate_variants(incremental=True)
        self.assert_full_generation_is_noop()
        feature.status = Feature.Status.STANDALONE
        feature.save()
        generate_variants(incremental=True)
        self.assert_full_generation_is_noop()

    def test_incremental_after_card_feature_change(self):
        generate_variants()
        feature_of_card = FeatureOfCard.objects.create(card_id=self.c2_id, feature_id=self.f1_id, zone_locations=ZoneLocation.BATTLEFIELD)
        generate_variants(incremental=True)
        self.assert_full_generation_is_noop()
        feature_of_card.delete()
        generate_variants(incremental=True)
        self.assert_full_generation_is_noop()

    def test_incremental_after_combo_requirement_change(self):
        generate_variants()
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR, cardincombo__isnull=False).first()  # type: ignore
        card_in_combo: CardInCombo = combo.cardincombo_set.first()  # type: ignore
        card_in_combo.quantity += 1
        card_in_combo.save()
        generate_variants(incremental=True)
        self.assert_full_generation_is_noop()

    def test_incremental_after_combo_deletion_falls_back_to_full(self):
        generate_variants()
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
        combo.delete()
        generate_variants(incremental=True)
        self.assert_full_generation_is_noop()

    def test_single_combo_generation_does_not_store_fingerprints(self):
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
        generate_variants(combo.id)
        self.assertEqual(VariantGenerationFingerprints.objects.count(), 0)

    def _generate_capturing_metadata(self, **kwargs) -> dict[str, object]:
        captured = dict[str, object]()
        generate_variants(metadata=lambda key, value: captured.__setitem__(key, value), **kwargs)
        return captured

    def test_metadata_reports_not_incremental_on_fallback_to_full(self):
        captured = self._generate_capturing_metadata(incremental=True)
        self.assertIs(captured['incremental'], False)

    def test_metadata_reports_incremental_when_nothing_changed(self):
        generate_variants()
        captured = self._generate_capturing_metadata(incremental=True)
        self.assertIs(captured['incremental'], True)

    def test_metadata_reports_incremental_on_partial_regeneration(self):
        generate_variants()
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
        combo.description += ' edited'
        combo.save()
        captured = self._generate_capturing_metadata(incremental=True)
        self.assertIs(captured['incremental'], True)

    def test_metadata_reports_not_incremental_on_full_generation(self):
        captured = self._generate_capturing_metadata()
        self.assertIs(captured['incremental'], False)

    def test_metadata_reports_not_incremental_on_single_combo(self):
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
        captured = self._generate_capturing_metadata(combo=combo.id)
        self.assertIs(captured['incremental'], False)


class ParallelGenerationTests(SpellbookTestCaseWithSeeding):
    @skipUnless(parallelism_is_available(), 'parallel generation requires the fork start method and a non-daemonic process')
    def test_parallel_generation_matches_serial(self):
        with mock.patch.object(variants_generator, 'MIN_COMBOS_FOR_PARALLELISM', 1), \
                mock.patch.object(variants_generator, 'MIN_VARIANTS_FOR_PARALLELISM', 1):
            added, restored, deleted = generate_variants(workers=2)
        self.assertEqual(added, self.expected_variant_count)
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        # A serial full generation over the parallel result must be a no-op
        added, restored, deleted = generate_variants(workers=1)
        self.assertEqual((added, restored, deleted), (0, 0, 0))
