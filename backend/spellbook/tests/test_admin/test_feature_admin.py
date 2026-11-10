from ..testing import SpellbookTestCaseWithSeeding, curated_card
from spellbook.admin.feature_admin import merge_feature
from spellbook.models import CardInCombo, Combo, Feature, FeatureAttribute, FeatureNeededInCombo, FeatureOfCard, FeatureProducedInCombo, FeatureRemovedInCombo, Variant, ZoneLocation
from spellbook.models.references import format_alias_reference, format_line_reference, rename_references


class FeatureAdminTests(SpellbookTestCaseWithSeeding):
    def test_rename_feature_references(self):
        for test_text, verified_text, old_name, new_name in [
            ('[[Feature1]]', '[[Feature2]]', 'Feature1', 'Feature2'),
            ('[[fEature1]]', '[[Feature2]]', 'Feature1', 'Feature2'),
            ('[[Feature1|alias]]', '[[Feature2|alias]]', 'Feature1', 'Feature2'),
            ('[[Feature1|alias]] and [[Feature1]]', '[[Feature2|alias]] and [[Feature2]]', 'Feature1', 'Feature2'),
            ('[[Feature1|alias]] and [[Feature2|alias]]', '[[Feature2|alias]] and [[Feature2|alias]]', 'Feature1', 'Feature2'),
            ('[[feature1]] and [[feature2]]', '[[feature2]] and [[feature2]]', 'feature1', 'feature2'),
            (f'[[Feature1|alias]] asd {format_alias_reference("alias")}', f'[[Feature2|alias]] asd {format_alias_reference("alias")}', 'Feature1', 'Feature2'),
            (f'[[Other|Feature1]] then {format_alias_reference("Feature1")} and {format_alias_reference("Feature1", "description")}', f'[[Other|Feature1]] then {format_alias_reference("Feature1")} and {format_alias_reference("Feature1", "description")}', 'Feature1', 'Feature2'),
            ('[[Feature1 (x)|alias]] [[Feature1 (x)|another alias]]', '[[Feature2|alias]] [[Feature2|another alias]]', 'Feature1 (x)', 'Feature2'),
            ('[[ASD$4|CHECK]] [ASD] [[XASD]] [[X ASD]]', '[[DEF$4|CHECK]] [ASD] [[XASD]] [[X ASD]]', 'ASD', 'DEF'),
            ('[[A$2|C]]', '[[A$2|C]]', 'A', 'A'),
            ('[[A$2|C]] [[A|C]]', '[[Z$2|C]] [[Z|C]]', 'A', 'Z'),
            ('[[A#2]]', '[[Z#2]]', 'A', 'Z'),
            ('[[A#2|alias]]', '[[Z#2|alias]]', 'A', 'Z'),
            ('[[A#1$3|alias]]', '[[Z#1$3|alias]]', 'A', 'Z'),
            ('[[A$Attribute]]', '[[Z$Attribute]]', 'A', 'Z'),
            ('[[A$Attribute|alias]]', '[[Z$Attribute|alias]]', 'A', 'Z'),
            ('[[3 Mana|x]] and [[3 Mana@description]]', '[[4 Mana|x]] and [[4 Mana@description]]', '3 Mana', '4 Mana'),
            ('[[Feature1@description]]', '[[Feature2@description]]', 'Feature1', 'Feature2'),
            ('[[fEature1@notes]]', '[[Feature2@notes]]', 'Feature1', 'Feature2'),
            ('[[Feature1$2@description]]', '[[Feature2$2@description]]', 'Feature1', 'Feature2'),
            ('[[Feature1$Attribute@sac step]] and [[Feature1]]', '[[Feature2$Attribute@sac step]] and [[Feature2]]', 'Feature1', 'Feature2'),
            ('[[Feature1@x]] [[Other@x]] {Feature1}', '[[Feature2@x]] [[Other@x]] {Feature1}', 'Feature1', 'Feature2'),
            (f'[[3]] and {format_line_reference(3)}', f'[[4]] and {format_line_reference(3)}', '3', '4'),
        ]:
            with self.subTest(test_text=test_text, old_name=old_name, new_name=new_name):
                self.assertEqual(rename_references(test_text, 'feature', old_name, new_name), verified_text)

    def test_replace_feature_references(self):
        feature = Feature.objects.create(name='Old Feature')
        combo = Combo.objects.create(
            status=Combo.Status.UTILITY,
            description='[[Old Feature]] does something',
            notes='[[Old Feature@notes]] was included',
            comment='[[Old Feature]]',
            easy_prerequisites='[[Old Feature]]',
            notable_prerequisites='[[Old Feature]]',
            mana_needed='{1} for [[Old Feature]]',
        )
        card_in_combo = CardInCombo.objects.create(
            combo=combo,
            card_id=self.c1_id,
            order=1,
            zone_locations=ZoneLocation.BATTLEFIELD,
            battlefield_card_state='next to [[Old Feature]]',
        )
        feature_in_combo = FeatureNeededInCombo.objects.create(
            combo=combo,
            feature=feature,
            order=1,
            zone_locations=ZoneLocation.GRAVEYARD,
            graveyard_card_state='below [[Old Feature]]',
        )
        produced = FeatureProducedInCombo.objects.create(combo=combo, feature=Feature.objects.create(name='Produced Feature'), description='Cast [[Old Feature]] for free')
        targets = FeatureAttribute.objects.create(name='targets')
        produced.attributes.add(targets, through_defaults={'value': '[[Old Feature$2]] or a creature'})
        removing_combo = Combo.objects.create(status=Combo.Status.UTILITY)
        FeatureRemovedInCombo.objects.create(combo=removing_combo, feature=feature)
        only_included = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Old Feature$Attribute@description]] only')
        untouched = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Other Feature]]')

        feature = Feature.objects.get(pk=feature.pk)
        feature.name = 'New Feature'
        feature.save()

        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[New Feature]] does something')
        self.assertEqual(combo.notes, '[[New Feature@notes]] was included')
        self.assertEqual(combo.comment, '[[New Feature]]')
        self.assertEqual(combo.easy_prerequisites, '[[New Feature]]')
        self.assertEqual(combo.notable_prerequisites, '[[New Feature]]')
        self.assertEqual(combo.mana_needed, '{1} for [[New Feature]]')
        self.assertIn('New Feature', combo.name)
        self.assertNotIn('Old Feature', combo.name)
        card_in_combo.refresh_from_db()
        self.assertEqual(card_in_combo.battlefield_card_state, 'next to [[New Feature]]')
        feature_in_combo.refresh_from_db()
        self.assertEqual(feature_in_combo.graveyard_card_state, 'below [[New Feature]]')
        produced.refresh_from_db()
        self.assertEqual(produced.description, 'Cast [[New Feature]] for free')
        self.assertEqual(produced.attributes.through.objects.get(producer=produced).value, '[[New Feature$2]] or a creature')
        removing_combo.refresh_from_db()
        self.assertIn('New Feature', removing_combo.name)
        only_included.refresh_from_db()
        self.assertEqual(only_included.description, '[[New Feature$Attribute@description]] only')
        untouched.refresh_from_db()
        self.assertEqual(untouched.description, '[[Other Feature]]')

    def test_replace_feature_references_ignores_relationships(self):
        feature = Feature.objects.create(name='Old Feature')
        unrelated_feature = Feature.objects.create(name='Unrelated Feature')
        unrelated_combo = Combo.objects.create(
            status=Combo.Status.UTILITY,
            description='[[Old Feature]] is only mentioned here',
        )
        card_in_unrelated_combo = CardInCombo.objects.create(
            combo=unrelated_combo,
            card_id=self.c1_id,
            order=1,
            zone_locations=ZoneLocation.BATTLEFIELD,
            battlefield_card_state='next to [[Old Feature]]',
        )
        feature_of_card = FeatureOfCard.objects.create(
            card_id=self.c2_id,
            feature=unrelated_feature,
            zone_locations=ZoneLocation.BATTLEFIELD,
            notable_prerequisites='needs [[Old Feature]]',
        )
        feature_of_card.attributes.add(FeatureAttribute.objects.create(name='effect'), through_defaults={'value': 'then [[Old Feature]] happens'})

        feature.name = 'New Feature'
        feature.save()

        unrelated_combo.refresh_from_db()
        self.assertEqual(unrelated_combo.description, '[[New Feature]] is only mentioned here')
        card_in_unrelated_combo.refresh_from_db()
        self.assertEqual(card_in_unrelated_combo.battlefield_card_state, 'next to [[New Feature]]')
        feature_of_card.refresh_from_db()
        self.assertEqual(feature_of_card.notable_prerequisites, 'needs [[New Feature]]')
        self.assertEqual(feature_of_card.attributes.through.objects.get(producer=feature_of_card).value, 'then [[New Feature]] happens')

    def test_merge_feature_updates_references(self):
        source = Feature.objects.create(name='Source Feature')
        target = Feature.objects.create(name='Target Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Source Feature]] does something')
        FeatureNeededInCombo.objects.create(combo=combo, feature=source, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureProducedInCombo.objects.create(combo=combo, feature=source)

        merge_feature(source, target)

        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Target Feature]] does something')
        self.assertIn('Target Feature', combo.name)
        self.assertNotIn('Source Feature', combo.name)

    def test_merge_feature_renames_combos(self):
        source = Feature.objects.create(name='Source Feature')
        target = Feature.objects.create(name='Target Feature')
        needing = Combo.objects.create(status=Combo.Status.UTILITY)
        FeatureNeededInCombo.objects.create(combo=needing, feature=source, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        producing = Combo.objects.create(status=Combo.Status.UTILITY)
        FeatureProducedInCombo.objects.create(combo=producing, feature=source)
        removing = Combo.objects.create(status=Combo.Status.UTILITY)
        FeatureRemovedInCombo.objects.create(combo=removing, feature=source)
        needing_both = Combo.objects.create(status=Combo.Status.UTILITY)
        FeatureNeededInCombo.objects.create(combo=needing_both, feature=source, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureNeededInCombo.objects.create(combo=needing_both, feature=target, order=2, zone_locations=ZoneLocation.BATTLEFIELD)
        for combo in (needing, producing, removing, needing_both):
            combo.refresh_from_db()
            self.assertIn('Source Feature', combo.name)

        merge_feature(source, target)

        for combo in (needing, producing, removing, needing_both):
            with self.subTest(combo=combo.pk):
                combo.refresh_from_db()
                self.assertNotIn('Source Feature', combo.name)
                self.assertIn('Target Feature', combo.name)

    def test_merge_feature_renames_variants(self):
        self.generate_variants()
        source = Feature.objects.get(id=self.f4_id)
        target = Feature.objects.get(id=self.f2_id)
        variant_ids = [variant.id for variant in Variant.objects.filter(produces=source) if source.name in variant.name]
        self.assertGreater(len(variant_ids), 0)

        merge_feature(source, target)

        for variant in Variant.objects.filter(id__in=variant_ids):
            with self.subTest(variant=variant.pk):
                self.assertNotIn(source.name, variant.name)

    def test_renaming_a_feature_updates_variant_and_combo_names(self):
        self.generate_variants()
        feature = Feature.objects.get(id=self.f4_id)
        old_name = feature.name
        variant_ids = [variant.id for variant in Variant.objects.filter(produces=feature) if old_name in variant.name]
        combo_ids = [combo.id for combo in Combo.objects.filter(produces=feature) if old_name in combo.name]
        self.assertGreater(len(variant_ids), 0)
        self.assertGreater(len(combo_ids), 0)

        feature.name = 'Renamed Feature'
        feature.save()

        for variant in Variant.objects.filter(id__in=variant_ids):
            self.assertIn('Renamed Feature', variant.name)
        for combo in Combo.objects.filter(id__in=combo_ids):
            self.assertIn('Renamed Feature', combo.name)

    def test_saving_a_feature_without_renaming_it_skips_updates(self):
        self.generate_variants()
        feature = Feature.objects.get(id=self.f1_id)
        feature.description = 'Another description'
        # only the update itself: the loaded name rules out a rename without any lookup
        with self.assertNumQueries(1):
            feature.save()

    def test_renaming_a_feature_twice_updates_names_both_times(self):
        self.generate_variants()
        feature = Feature.objects.get(id=self.f4_id)
        combo_ids = [combo.id for combo in Combo.objects.filter(produces=feature) if feature.name in combo.name]
        self.assertGreater(len(combo_ids), 0)

        feature.name = 'Renamed Once'
        feature.save()
        feature.name = 'Renamed Twice'
        feature.save()

        for combo in Combo.objects.filter(id__in=combo_ids):
            self.assertIn('Renamed Twice', combo.name)

    def test_merge_from_admin_deletes_the_merged_feature(self):
        self.client.force_login(self.admin)
        source = Feature.objects.create(name='Source Feature')
        target = Feature.objects.create(name='Target Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Source Feature]] does something')
        FeatureNeededInCombo.objects.create(combo=combo, feature=source, order=1, zone_locations=ZoneLocation.BATTLEFIELD)

        response = self.client.post(f'/admin/spellbook/feature/{source.id}/merge/', {'into': str(target.id)}, follow=True)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/admin/spellbook/feature/{source.id}/delete/?merge_into={target.id}', {'post': 'yes', 'merge_into': str(target.id)}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(Feature.objects.filter(pk=source.pk).exists())
        self.assertEqual(list(combo.needs.all()), [target])
        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Target Feature]] does something')

    def test_change_form_links_to_the_cards_producing_the_feature(self):
        self.client.force_login(self.admin)
        feature = Feature.objects.create(name='Linked Feature')
        producers = [curated_card(name=f'Linked Card {i}', type_line='Creature - Elf') for i in (1, 2)]
        for card in (*producers, producers[0]):
            FeatureOfCard.objects.create(card=card, feature=feature, zone_locations=ZoneLocation.BATTLEFIELD)

        response = self.client.get(f'/admin/spellbook/feature/{feature.id}/change/')
        self.assertContains(response, f'<a href="/admin/spellbook/card/?features__id={feature.id}">View all 2 cards that produce Linked Feature...</a>', html=True)

        response = self.client.get(f'/admin/spellbook/card/?features__id={feature.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({card.name for card in response.context['cl'].result_list}, {card.name for card in producers})

    def test_change_form_of_a_feature_no_card_produces_has_no_card_link(self):
        self.client.force_login(self.admin)
        feature = Feature.objects.create(name='Unproduced Feature')

        response = self.client.get(f'/admin/spellbook/feature/{feature.id}/change/')
        self.assertNotContains(response, '/admin/spellbook/card/?features__id=')

    def test_rename_from_admin_updates_references(self):
        self.client.force_login(self.admin)
        feature = Feature.objects.create(name='Old Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Old Feature]] does something')
        FeatureNeededInCombo.objects.create(combo=combo, feature=feature, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureProducedInCombo.objects.create(combo=combo, feature=feature)
        response = self.client.post(
            f'/admin/spellbook/feature/{feature.id}/change/',
            {
                'name': 'New Feature',
                'status': Feature.Status.HIDDEN_UTILITY,
                'description': '',
                'featureofcard_set-TOTAL_FORMS': '0',
                'featureofcard_set-INITIAL_FORMS': '0',
                'featureofcard_set-MIN_NUM_FORMS': '0',
                'featureofcard_set-MAX_NUM_FORMS': '1000',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        feature.refresh_from_db()
        self.assertEqual(feature.name, 'New Feature')
        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[New Feature]] does something')
        self.assertIn('New Feature', combo.name)
        self.assertNotIn('Old Feature', combo.name)

    def post_card_row(self, feature: Feature, attribute_texts: str, **fields: str):
        self.client.force_login(self.admin)
        return self.client.post(f'/admin/spellbook/feature/{feature.id}/change/', {
            'name': feature.name,
            'status': feature.status,
            'description': '',
            'featureofcard_set-TOTAL_FORMS': '1',
            'featureofcard_set-INITIAL_FORMS': '0',
            'featureofcard_set-MIN_NUM_FORMS': '0',
            'featureofcard_set-MAX_NUM_FORMS': '1000',
            'featureofcard_set-0-card': str(self.c1_id),
            'featureofcard_set-0-quantity': '1',
            'featureofcard_set-0-zone_locations': ZoneLocation.BATTLEFIELD,
            'featureofcard_set-0-is_mana_needed_an_accurate_minimum': 'on',
            'featureofcard_set-0-attribute_texts': attribute_texts,
            **{f'featureofcard_set-0-{field}': value for field, value in fields.items()},
        })

    def test_a_card_row_keeps_its_attributes_apart_from_its_texts(self):
        feature = Feature.objects.create(name='Attributed Feature', status=Feature.Status.HIDDEN_UTILITY)
        FeatureAttribute.objects.create(name='effect')

        response = self.post_card_row(feature, '{"effect": "adding {C}"}', mana_needed='{1}')

        self.assertEqual(response.status_code, 302)
        row = feature.featureofcard_set.get()
        self.assertEqual(row.mana_needed, '{1}')
        self.assertEqual(list(row.attributes.through.objects.filter(producer=row).values_list('attribute__name', 'value')), [('effect', 'adding {C}')])

    def test_an_error_of_a_hidden_text_shows_on_the_editor_of_its_row(self):
        feature = Feature.objects.create(name='Attributed Feature', status=Feature.Status.HIDDEN_UTILITY)

        response = self.post_card_row(feature, '{}', mana_needed='only words')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<li>Mana needed: Mana needed must be in the')
        self.assertFalse(feature.featureofcard_set.exists())

    def test_the_attributes_of_a_card_reference_no_feature(self):
        feature = Feature.objects.create(name='Attributed Feature', status=Feature.Status.HIDDEN_UTILITY)
        FeatureAttribute.objects.create(name='effect')

        response = self.post_card_row(feature, '{"effect": "untap [[Attributed Feature]]"}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A card feature cannot reference features, since it needs none: [[Attributed Feature]].')
        self.assertFalse(feature.featureofcard_set.exists())
