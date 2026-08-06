from itertools import chain
from unittest import mock, skipUnless
from django.db.models import Count
from spellbook.models.combo import CardInCombo, FeatureNeededInCombo
from spellbook.models.feature_attribute import FeatureAttribute
from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from spellbook.models import Variant, Card, OrderedIngredient, CardInVariant, TemplateInVariant, Template, Combo, Feature, VariantAlias, FeatureOfCard, ZoneLocation
from spellbook.models import VariantGenerationFingerprints, VariantOfCombo, FeatureProducedByVariant, id_from_cards_and_templates_ids
from spellbook.variants.combo_graph import FeatureWithAttributes
from spellbook.variants.multiset import FrozenMultiset
from spellbook.variants.variant_data import Data
from spellbook.variants import variants_generator
from spellbook.variants.variants_generator import get_variants_from_graph, get_default_zone_location_for_card, update_state_with_default, merge_used_faces
from spellbook.variants.replacements import ReplacementContext
from spellbook.variants.variants_generator import generate_variants, subtract_features, update_state
from spellbook.variants.variants_generator import sync_variant_aliases, restore_variants
from spellbook.variants.variants_generator import VariantDefinition, _restore_variant, _update_variant, _create_variant, _perform_bulk_saves
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
                self.assertEqual(sut.zone_locations, OrderedIngredient._meta.get_field('zone_locations').get_default())  # pyright: ignore[reportAttributeAccessIssue]

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

    def test_merge_used_faces(self):
        # No contributor specifies a face -> blank
        self.assertIsNone(merge_used_faces([CardInVariant(), CardInVariant()]))
        # A single specified face among blanks is kept (blanks are ignored)
        self.assertEqual(merge_used_faces([CardInVariant(used_face=2), CardInVariant()]), 2)
        # All specified faces agree -> that face
        self.assertEqual(merge_used_faces([CardInVariant(used_face=1), CardInVariant(used_face=1)]), 1)
        # Conflicting specified faces -> blank
        self.assertIsNone(merge_used_faces([CardInVariant(used_face=1), CardInVariant(used_face=2)]))

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
        dfc_card = Card.objects.create(
            name='Front Face // Back Face',
            type_line='Creature - Human // Creature - Zombie',
            faces=2,
        )
        legendary_face_card = Card.objects.create(
            name='Enchanted Front, with Words // The Lord, the Legend',
            type_line='Enchantment - Aura // Legendary Creature - Avatar',
            faces=2,
        )
        fx = Feature.objects.create(name='FX')
        fy = Feature.objects.create(name='FY')
        fz = Feature.objects.create(name='FZ')
        fw = Feature.objects.create(name='FW')
        fd = Feature.objects.create(name='FDFC')
        fl = Feature.objects.create(name='FLDFC')
        fattr = FeatureAttribute.objects.create(name='FAttr')
        spaced_attr = FeatureAttribute.objects.create(name='Spaced Attr')
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
            FeatureWithAttributes(fz, frozenset({spaced_attr.id})): [([normal_card], [])],  # Test for an attribute name with spaces
            FeatureWithAttributes(fw, frozenset()): [([legendary_card, non_legendary_card, legendary_modal_card, normal_card], [])],
            FeatureWithAttributes(fd, frozenset()): [([dfc_card], [])],
            FeatureWithAttributes(fl, frozenset()): [([legendary_face_card], [])],
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
            ('Test replacement attribute selector: [[FY$FAttr]]', 'Test replacement attribute selector: Normal Card'),
            ('Test replacement attribute selector case insensitivity: [[FY$fattr]]', 'Test replacement attribute selector case insensitivity: Normal Card'),
            ('Test unknown attribute selector: [[FY$Unknown]]', 'Test unknown attribute selector: [[FY$Unknown]]'),
            ('Test attribute selector with spaces: [[FZ$Spaced Attr]]', 'Test attribute selector with spaces: Normal Card'),
            ('Test attribute selector with spaces and alias: [[FZ|X$Spaced Attr|Y]] - [[Y]]', 'Test attribute selector with spaces and alias: Normal Card - Normal Card'),
            ('Test replacement selector alias: [[FY$1|X]] - [[FY$2|Y]] - [[X]] - [[Y]]', 'Test replacement selector alias: The Name, different Title - Normal Card - The Name, different Title - Normal Card'),
            ('Test replacement selector postfix alias: [[FY|X$1|Y]] - [[X]] - [[X$2]] - [[Y]] - [[Y$2]]', 'Test replacement selector postfix alias: The Name, different Title - The Name, different Title - Normal Card - The Name, different Title - [[Y$2]]'),
            ('Legendary modal name never cut: [[FZ]]', 'Legendary modal name never cut: The Name, the Title  // Another Name, Another Title'),
            ('Multiple replacements: [[FW]]', 'Multiple replacements: The Name + The Name, different Title + The Name, the Title  // Another Name, Another Title + Normal Card'),
            # Face selector in the text: whole name by default, a specific half when a valid face is given
            ('Whole multi-faced card by default: [[FDFC]]', 'Whole multi-faced card by default: Front Face // Back Face'),
            ('Face selector front: [[FDFC#1]]', 'Face selector front: Front Face'),
            ('Face selector back: [[FDFC#2]]', 'Face selector back: Back Face'),
            ('Out of range face falls back to default: [[FDFC#3]]', 'Out of range face falls back to default: Front Face // Back Face'),
            ('Face selector alias saves the face name: [[FDFC#1|f]] then [[f]]', 'Face selector alias saves the face name: Front Face then Front Face'),
            ('Face selector ignored on single-faced card: [[FA#2]]', 'Face selector ignored on single-faced card: A A'),
            ('Whole modal name never cut: [[FLDFC]]', 'Whole modal name never cut: Enchanted Front, with Words // The Lord, the Legend'),
            ('Legendary creature face cut before comma: [[FLDFC#2]]', 'Legendary creature face cut before comma: The Lord'),
            ('Non-legendary face not cut before comma: [[FLDFC#1]]', 'Non-legendary face not cut before comma: Enchanted Front, with Words'),
        ]
        data = Data()
        # A context per case, so that the aliases registered by one do not leak into the next
        for test in tests:
            context = ReplacementContext.build(data, replacements, [combo], {})
            self.assertEqual(context.apply(test[0]), test[1])
        # When the used_face field is specified, the placeholder defaults to that half of the name,
        # while a face selector in the text still overrides it
        face_tests = [
            ('Used face defaults to that half: [[FDFC]]', 'Used face defaults to that half: Back Face'),
            ('Text face still overrides the used face: [[FDFC#1]]', 'Text face still overrides the used face: Front Face'),
            ('Used face is cut before comma as well: [[FLDFC]]', 'Used face is cut before comma as well: The Lord'),
        ]
        for test in face_tests:
            context = ReplacementContext.build(data, replacements, [combo], {dfc_card.id: 2, legendary_face_card.id: 2})
            self.assertEqual(context.apply(test[0]), test[1])
        # One context spans a whole variant, so an alias registered by one text is visible to the next
        context = ReplacementContext.build(data, replacements, [combo], {})
        self.assertEqual(context.apply('alias registered here: [[FA|XYZ]]'), 'alias registered here: A A')
        self.assertEqual(context.apply('and used in another text: [[XYZ]]'), 'and used in another text: A A')
        # while a newly built one starts over without it
        self.assertEqual(ReplacementContext.build(data, replacements, [combo], {}).apply('unknown here: [[XYZ]]'), 'unknown here: [[XYZ]]')

    def test_replacement_order_follows_needed_features(self):
        landfall = FeatureAttribute.objects.create(name='Landfall')
        untapper = FeatureAttribute.objects.create(name='Untapper Effect')
        token_maker = Feature.objects.create(name='FToken')
        landfall_card = Card.objects.create(name='Landfall Card', type_line='Creature - Elf')
        untapper_card = Card.objects.create(name='Untapper Card', type_line='Creature - Elf')
        combo = Combo.objects.create(status=Combo.Status.UTILITY)
        needs_landfall_first = FeatureNeededInCombo.objects.create(combo=combo, feature=token_maker, order=1)
        needs_landfall_first.any_of_attributes.add(landfall)
        needs_untapper_second = FeatureNeededInCombo.objects.create(combo=combo, feature=token_maker, order=2)
        needs_untapper_second.any_of_attributes.add(untapper)
        other_combo = Combo.objects.create(status=Combo.Status.UTILITY)
        needs_untapper_first = FeatureNeededInCombo.objects.create(combo=other_combo, feature=token_maker, order=1)
        needs_untapper_first.any_of_attributes.add(untapper)
        needs_landfall_second = FeatureNeededInCombo.objects.create(combo=other_combo, feature=token_maker, order=2)
        needs_landfall_second.any_of_attributes.add(landfall)
        landfall_replacement = (FeatureWithAttributes(token_maker, frozenset({landfall.id})), [([landfall_card], [])])
        untapper_replacement = (FeatureWithAttributes(token_maker, frozenset({untapper.id})), [([untapper_card], [])])
        text = '[[FToken$1]] then [[FToken$2]]'
        data = Data()
        # The order the replacements are discovered in is not stable across variants, so it must not matter
        for replacements in (
            dict([landfall_replacement, untapper_replacement]),
            dict([untapper_replacement, landfall_replacement]),
        ):
            with self.subTest(replacements=list(replacements)):
                context = ReplacementContext.build(data, replacements, [combo, other_combo], {})
                self.assertEqual(context.apply(text, combo.id), 'Landfall Card then Untapper Card')
                # The same text renders against the needed features of the combo it belongs to
                self.assertEqual(context.apply(text, other_combo.id), 'Untapper Card then Landfall Card')
                # The attribute selector does not depend on any ordering
                self.assertEqual(context.apply('[[FToken$Landfall]]', other_combo.id), 'Landfall Card')
                self.assertEqual(context.apply('[[FToken$Untapper Effect]]', combo.id), 'Untapper Card')

    def test_replacement_from_a_transitive_feature_dependency(self):
        card1 = Card.objects.create(name='Transitive Card One', type_line='Creature - Elf')
        card2 = Card.objects.create(name='Transitive Card Two', type_line='Creature - Elf')
        feature_a = Feature.objects.create(name='TFA', status=Feature.Status.HIDDEN_UTILITY)
        feature_b = Feature.objects.create(name='TFB', status=Feature.Status.STANDALONE)
        feature_c = Feature.objects.create(name='TFC', status=Feature.Status.HIDDEN_UTILITY)
        FeatureOfCard.objects.create(card=card2, feature=feature_c, zone_locations=ZoneLocation.BATTLEFIELD)
        producing_a = Combo.objects.create(status=Combo.Status.UTILITY)
        FeatureNeededInCombo.objects.create(combo=producing_a, feature=feature_c, order=1)
        producing_a.produces.add(feature_a)
        # TFC is never needed by this combo: it only reaches it through TFA, produced by the combo above
        main = Combo.objects.create(status=Combo.Status.GENERATOR, description='a mention of [[TFC]] here')
        CardInCombo.objects.create(combo=main, card=card1, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureNeededInCombo.objects.create(combo=main, feature=feature_a, order=1)
        main.produces.add(feature_b)

        self.generate_variants()

        variant = Variant.objects.get(of=main)
        self.assertSetEqual({c.name for c in variant.uses.all()}, {'Transitive Card One', 'Transitive Card Two'})
        self.assertEqual(variant.description, 'a mention of Transitive Card Two here')

    def test_restore_variant(self):
        data = Data()
        variants = get_variants_from_graph(data)
        for id, variant_def in variants.items():
            with self.subTest(variant=id):
                variant = Variant(id=id)
                save_item = _restore_variant(data=data, variant=variant, variant_def=variant_def, restore_fields=True)
                self.assertEqual(variant.status, Variant.Status.NEW)
                self.assertGreater(len(variant.name), 0)
                self.assertGreater(len(variant.description), 0)
                self.assertSetEqual(save_item.of, variant_def.of_ids)
                self.assertSetEqual(save_item.includes, variant_def.included_ids)
                self.assertSetEqual({c.card_id for c in save_item.uses}, set(variant_def.card_ids.distinct_elements()))
                self.assertSetEqual({t.template_id for t in save_item.requires}, set(variant_def.template_ids.distinct_elements()))
                self.assertSetEqual(save_item.produces_ids, set(subtract_features(data, variant_def.included_ids, variant_def.feature_ids).distinct_elements()))
                self.assertEqual([c.order for c in save_item.uses], list(range(1, len(save_item.uses) + 1)))
                self.assertEqual([t.order for t in save_item.requires], list(range(1, len(save_item.requires) + 1)))
                self.assertEqual(save_item.uses_to_create, save_item.uses)
                self.assertEqual(save_item.requires_to_create, save_item.requires)
                self.assertEqual(save_item.produces_to_create, save_item.produces)
                self.assertFalse(save_item.uses_to_update)
                self.assertFalse(save_item.requires_to_update)
                self.assertFalse(save_item.produces_to_update)
        self.assertEqual(Variant.objects.count(), 0)
        # An included combo may contain cards that the variant does not use
        variant_def = VariantDefinition(
            card_ids=FrozenMultiset({self.c4_id: 1}),
            template_ids=FrozenMultiset(),
            of_ids={self.b3_id},
            feature_ids=FrozenMultiset(),
            included_ids={self.b3_id},
            feature_replacements={},
            needed_combos={self.b3_id},
            needed_features_of_cards=set(),
        )
        variant = Variant(id=id_from_cards_and_templates_ids([self.c4_id], []))
        save_item = _restore_variant(data=data, variant=variant, variant_def=variant_def, restore_fields=True)
        self.assertEqual([c.card_id for c in save_item.uses], [self.c4_id])
        self.assertEqual(save_item.uses[0].zone_locations, ZoneLocation.HAND)
        self.assertEqual(variant.description, Combo.objects.get(pk=self.b3_id).description)

        self.generate_variants()
        Variant.objects.update(status=Variant.Status.OK, generated_by=None)
        data = Data()
        variants = get_variants_from_graph(data)
        id = next(iter(variants))
        variant = data.fetch_variants([id])[id]
        variant.description = 'not restored'
        save_item = _restore_variant(data=data, variant=variant, variant_def=variants[id], restore_fields=False)
        self.assertEqual(variant.description, 'not restored')
        self.assertEqual(variant.status, Variant.Status.OK)
        self.assertFalse(save_item.uses_to_create)
        self.assertFalse(save_item.uses_to_update)
        self.assertFalse(save_item.requires_to_create)
        self.assertFalse(save_item.requires_to_update)
        self.assertFalse(save_item.produces_to_create)
        self.assertFalse(save_item.produces_to_update)
        to_update, to_create = restore_variants(
            data=data,
            variants=variants,
            variant_instances=data.fetch_variants(variants.keys()),
            to_restore={id},
            job='a-job',
        )
        self.assertFalse(to_create)
        for item in to_update:
            if item.variant.id == id:
                self.assertEqual(item.variant.generated_by, 'a-job')
                self.assertEqual(item.variant.status, Variant.Status.NEW)
            else:
                self.assertIsNone(item.variant.generated_by)
                self.assertEqual(item.variant.status, Variant.Status.OK)

    def test_update_variant(self):
        self.generate_variants()
        Variant.objects.update(status=Variant.Status.OK, generated_by=None)
        data = Data()
        variants = get_variants_from_graph(data)
        id = next(iter(variants))
        variant_def = variants[id]
        variant = data.fetch_variants([id])[id]
        save_item = _update_variant(data=data, id=id, variant_def=variant_def, variant=variant, restore=False, job='a-job')
        self.assertFalse(save_item.variant_changed)
        self.assertEqual(variant.status, Variant.Status.OK)
        self.assertIsNone(variant.generated_by)
        variant = data.fetch_variants([id])[id]
        variant.description_line_count += 5
        save_item = _update_variant(data=data, id=id, variant_def=variant_def, variant=variant, restore=False, job='a-job')
        self.assertTrue(save_item.variant_changed)
        self.assertEqual(variant.description_line_count, variant.description.count('\n') + 1 if variant.description else 0)
        variant = data.fetch_variants([id])[id]
        description = variant.description
        variant.description = 'stale description'
        save_item = _update_variant(data=data, id=id, variant_def=variant_def, variant=variant, restore=True, job='a-job')
        self.assertTrue(save_item.variant_changed)
        self.assertEqual(variant.description, description)
        self.assertEqual(variant.status, Variant.Status.NEW)
        self.assertEqual(variant.generated_by, 'a-job')
        # Nothing is written to the database before the bulk save
        self.assertEqual(Variant.objects.get(pk=id).status, Variant.Status.OK)

    def test_create_variant(self):
        data = Data()
        variants = get_variants_from_graph(data)
        for id, variant_def in variants.items():
            with self.subTest(variant=id):
                save_item = _create_variant(data=data, id=id, variant_def=variant_def, job='a-job')
                variant = save_item.variant
                self.assertEqual(variant.id, id)
                self.assertEqual(variant.generated_by, 'a-job')
                self.assertEqual(variant.status, Variant.Status.NEW)
                self.assertTrue(save_item.variant_changed)
                self.assertEqual(save_item.uses_to_create, save_item.uses)
                self.assertEqual(save_item.requires_to_create, save_item.requires)
                self.assertEqual(save_item.produces_to_create, save_item.produces)
                self.assertFalse(save_item.uses_to_update)
                self.assertFalse(save_item.requires_to_update)
                self.assertFalse(save_item.produces_to_update)
                # pre_save already ran, so the computed fields are consistent with the text ones
                self.assertEqual(variant.description_line_count, variant.description.count('\n') + 1 if variant.description else 0)
        self.assertEqual(Variant.objects.count(), 0)

    def test_perform_bulk_save(self):
        data = Data()
        variants = get_variants_from_graph(data)
        to_update, to_create = restore_variants(data=data, variants=variants, variant_instances={}, to_restore=set(), job='a-job')
        self.assertFalse(to_update)
        _perform_bulk_saves(data, to_create, [])
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        for item in to_create:
            variant = Variant.objects.get(pk=item.variant.id)
            self.assertEqual(variant.generated_by, 'a-job')
            self.assertSetEqual(set(variant.uses.values_list('id', flat=True)), {c.card_id for c in item.uses})
            self.assertSetEqual(set(variant.requires.values_list('id', flat=True)), {t.template_id for t in item.requires})
            self.assertSetEqual(set(variant.produces.values_list('id', flat=True)), item.produces_ids)
            self.assertSetEqual(set(variant.of.values_list('id', flat=True)), item.of)
            self.assertSetEqual(set(variant.includes.values_list('id', flat=True)), item.includes)
        v: Variant = Variant.objects.first()  # type: ignore
        stale_of = VariantOfCombo.objects.create(variant=v, combo_id=self.b7_id)
        stale_produces = FeatureProducedByVariant.objects.create(variant=v, feature_id=self.f5_id, quantity=1)
        stale_use: CardInVariant = v.cardinvariant_set.first()  # type: ignore
        CardInVariant.objects.filter(pk=stale_use.pk).update(battlefield_card_state='stale state', order=99)
        data = Data()
        variants = get_variants_from_graph(data)
        to_update, to_create = restore_variants(
            data=data,
            variants=variants,
            variant_instances=data.fetch_variants(variants.keys()),
            to_restore={v.id},
            job='another-job',
        )
        self.assertFalse(to_create)
        _perform_bulk_saves(data, [], to_update)
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        self.assertFalse(VariantOfCombo.objects.filter(pk=stale_of.pk).exists())
        self.assertFalse(FeatureProducedByVariant.objects.filter(pk=stale_produces.pk).exists())
        stale_use.refresh_from_db()
        self.assertNotEqual(stale_use.battlefield_card_state, 'stale state')
        self.assertNotEqual(stale_use.order, 99)
        v.refresh_from_db()
        self.assertEqual(v.generated_by, 'another-job')
        self.assertEqual(v.status, Variant.Status.NEW)

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
        combo: Combo = Combo.objects.filter(status=Combo.Status.GENERATOR).first()  # type: ignore
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
        flagged = list(combo.variants.values_list('id', flat=True))  # pyright: ignore[reportAttributeAccessIssue]
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
