from django.core.exceptions import ValidationError
from spellbook.admin.feature_attribute_admin import merge_feature_attribute
from spellbook.models import CardInCombo, Combo, Feature, FeatureAttribute, FeatureNeededInCombo, FeatureOfCard, FeatureProducedInCombo, ZoneLocation
from spellbook.models.references import replace_attribute_reference
from ..testing import SpellbookTestCaseWithSeeding


class FeatureAttributeAdminTests(SpellbookTestCaseWithSeeding):
    def test_reserved_characters_are_rejected(self):
        for name in ('With$Dollar', 'With|Pipe'):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    FeatureAttribute(name=name).full_clean()
        FeatureAttribute(name='With Spaces').full_clean()

    def test_replace_attribute_reference(self):
        for test_text, verified_text, old_name, new_name in [
            ('[[Feature$Attr]]', '[[Feature$Other]]', 'Attr', 'Other'),
            ('[[Feature$attr]]', '[[Feature$Other]]', 'Attr', 'Other'),
            ('[[Feature$Attr]] and [[Feature$Attr]]', '[[Feature$Other]] and [[Feature$Other]]', 'Attr', 'Other'),
            ('[[Feature$Attr]] and [[Feature$Untouched]]', '[[Feature$Other]] and [[Feature$Untouched]]', 'Attr', 'Other'),
            ('[[Attr$Attr]]', '[[Attr$Other]]', 'Attr', 'Other'),
            ('[[Feature$Attr|post]]', '[[Feature$Other|post]]', 'Attr', 'Other'),
            ('[[Feature#2|alias$Attr|post]]', '[[Feature#2|alias$Other|post]]', 'Attr', 'Other'),
            # attribute names with spaces, on both ends of the rename
            ('[[Feature$Old Attribute]]', '[[Feature$New Attribute]]', 'Old Attribute', 'New Attribute'),
            ('[[Feature$old attribute|post]]', '[[Feature$New Attribute|post]]', 'Old Attribute', 'New Attribute'),
            ('[[Feature$Old]] [[Feature$Old Attribute]]', '[[Feature$Old]] [[Feature$New]]', 'Old Attribute', 'New'),
            # a positional selector is never an attribute name
            ('[[Feature$2]]', '[[Feature$2]]', '2', 'Other'),
            ('[[Feature]]', '[[Feature]]', 'Attr', 'Other'),
        ]:
            with self.subTest(test_text=test_text, old_name=old_name, new_name=new_name):
                self.assertEqual(replace_attribute_reference(old_name, new_name, test_text), verified_text)

    def test_replace_attribute_references(self):
        attribute = FeatureAttribute.objects.create(name='Old Attribute')
        feature = Feature.objects.create(name='Renaming Feature')
        combo = Combo.objects.create(
            status=Combo.Status.UTILITY,
            description='[[Renaming Feature$Old Attribute]] does something',
            notes='[[Renaming Feature$Old Attribute]]',
            comment='[[Renaming Feature$Old Attribute]]',
            easy_prerequisites='[[Renaming Feature$Old Attribute]]',
            notable_prerequisites='[[Renaming Feature$Old Attribute]]',
            mana_needed='{1} for [[Renaming Feature$Old Attribute]]',
        )
        card_in_combo = CardInCombo.objects.create(
            combo=combo,
            card_id=self.c1_id,
            order=1,
            zone_locations=ZoneLocation.BATTLEFIELD,
            battlefield_card_state='next to [[Renaming Feature$Old Attribute]]',
        )
        feature_in_combo = FeatureNeededInCombo.objects.create(
            combo=combo,
            feature=feature,
            order=1,
            zone_locations=ZoneLocation.GRAVEYARD,
            graveyard_card_state='below [[Renaming Feature$Old Attribute]]',
        )
        feature_in_combo.any_of_attributes.add(attribute)
        feature_of_card = FeatureOfCard.objects.create(
            card_id=self.c2_id,
            feature=feature,
            zone_locations=ZoneLocation.BATTLEFIELD,
            notable_prerequisites='needs [[Renaming Feature$Old Attribute]]',
        )
        feature_of_card.attributes.add(attribute)
        untouched = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Renaming Feature$Other Attribute]]')

        attribute.name = 'New Attribute'
        attribute.save()

        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Renaming Feature$New Attribute]] does something')
        self.assertEqual(combo.notes, '[[Renaming Feature$New Attribute]]')
        self.assertEqual(combo.comment, '[[Renaming Feature$New Attribute]]')
        self.assertEqual(combo.easy_prerequisites, '[[Renaming Feature$New Attribute]]')
        self.assertEqual(combo.notable_prerequisites, '[[Renaming Feature$New Attribute]]')
        self.assertEqual(combo.mana_needed, '{1} for [[Renaming Feature$New Attribute]]')
        card_in_combo.refresh_from_db()
        self.assertEqual(card_in_combo.battlefield_card_state, 'next to [[Renaming Feature$New Attribute]]')
        feature_in_combo.refresh_from_db()
        self.assertEqual(feature_in_combo.graveyard_card_state, 'below [[Renaming Feature$New Attribute]]')
        feature_of_card.refresh_from_db()
        self.assertEqual(feature_of_card.notable_prerequisites, 'needs [[Renaming Feature$New Attribute]]')
        untouched.refresh_from_db()
        self.assertEqual(untouched.description, '[[Renaming Feature$Other Attribute]]')

    def test_replace_attribute_references_ignores_relationships(self):
        attribute = FeatureAttribute.objects.create(name='Old Attribute')
        feature = Feature.objects.create(name='Some Feature')
        unrelated_combo = Combo.objects.create(
            status=Combo.Status.UTILITY,
            description='[[Some Feature$Old Attribute]] is only mentioned here',
        )
        card_in_unrelated_combo = CardInCombo.objects.create(
            combo=unrelated_combo,
            card_id=self.c1_id,
            order=1,
            zone_locations=ZoneLocation.BATTLEFIELD,
            battlefield_card_state='next to [[Some Feature$Old Attribute]]',
        )
        feature_of_card = FeatureOfCard.objects.create(
            card_id=self.c2_id,
            feature=feature,
            zone_locations=ZoneLocation.BATTLEFIELD,
            notable_prerequisites='needs [[Some Feature$Old Attribute]]',
        )

        attribute.name = 'New Attribute'
        attribute.save()

        unrelated_combo.refresh_from_db()
        self.assertEqual(unrelated_combo.description, '[[Some Feature$New Attribute]] is only mentioned here')
        card_in_unrelated_combo.refresh_from_db()
        self.assertEqual(card_in_unrelated_combo.battlefield_card_state, 'next to [[Some Feature$New Attribute]]')
        feature_of_card.refresh_from_db()
        self.assertEqual(feature_of_card.notable_prerequisites, 'needs [[Some Feature$New Attribute]]')

    def test_rename_from_admin_updates_references(self):
        self.client.force_login(self.admin)
        attribute = FeatureAttribute.objects.create(name='Old Attribute')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Some Feature$Old Attribute]]')
        feature = Feature.objects.create(name='Some Feature')
        feature_in_combo = FeatureNeededInCombo.objects.create(combo=combo, feature=feature, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        feature_in_combo.any_of_attributes.add(attribute)
        response = self.client.post(
            f'/admin/spellbook/featureattribute/{attribute.id}/change/',
            {'name': 'New Attribute'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        attribute.refresh_from_db()
        self.assertEqual(attribute.name, 'New Attribute')
        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Some Feature$New Attribute]]')

    def test_merge_feature_attribute_moves_every_relationship(self):
        source = FeatureAttribute.objects.create(name='Source Attribute')
        target = FeatureAttribute.objects.create(name='Target Attribute')
        feature = Feature.objects.create(name='Merging Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY)
        needed = FeatureNeededInCombo.objects.create(combo=combo, feature=feature, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        needed.any_of_attributes.add(source)
        needed.all_of_attributes.add(source)
        needed.none_of_attributes.add(source)
        produced = FeatureProducedInCombo.objects.create(combo=combo, feature=feature)
        produced.attributes.add(source)
        feature_of_card = FeatureOfCard.objects.create(card_id=self.c1_id, feature=feature, zone_locations=ZoneLocation.BATTLEFIELD)
        feature_of_card.attributes.add(source)

        merge_feature_attribute(source, target)

        self.assertEqual(list(needed.any_of_attributes.all()), [target])
        self.assertEqual(list(needed.all_of_attributes.all()), [target])
        self.assertEqual(list(needed.none_of_attributes.all()), [target])
        self.assertEqual(list(produced.attributes.all()), [target])
        self.assertEqual(list(feature_of_card.attributes.all()), [target])

    def test_merge_feature_attribute_drops_duplicate_relationships(self):
        source = FeatureAttribute.objects.create(name='Source Attribute')
        target = FeatureAttribute.objects.create(name='Target Attribute')
        other = FeatureAttribute.objects.create(name='Other Attribute')
        feature = Feature.objects.create(name='Merging Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY)
        needed = FeatureNeededInCombo.objects.create(combo=combo, feature=feature, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        needed.any_of_attributes.add(source, target, other)
        feature_of_card = FeatureOfCard.objects.create(card_id=self.c1_id, feature=feature, zone_locations=ZoneLocation.BATTLEFIELD)
        feature_of_card.attributes.add(source, target)

        merge_feature_attribute(source, target)

        self.assertCountEqual(needed.any_of_attributes.all(), [target, other])
        self.assertCountEqual(feature_of_card.attributes.all(), [target])

    def test_merge_feature_attribute_updates_references(self):
        source = FeatureAttribute.objects.create(name='Source Attribute')
        target = FeatureAttribute.objects.create(name='Target Attribute')
        feature = Feature.objects.create(name='Merging Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Merging Feature$Source Attribute]] does something')
        needed = FeatureNeededInCombo.objects.create(combo=combo, feature=feature, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        needed.any_of_attributes.add(source)

        merge_feature_attribute(source, target)

        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Merging Feature$Target Attribute]] does something')

    def test_merge_from_admin_deletes_the_merged_attribute(self):
        self.client.force_login(self.admin)
        source = FeatureAttribute.objects.create(name='Source Attribute')
        target = FeatureAttribute.objects.create(name='Target Attribute')
        feature = Feature.objects.create(name='Merging Feature')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Merging Feature$Source Attribute]]')
        needed = FeatureNeededInCombo.objects.create(combo=combo, feature=feature, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        needed.any_of_attributes.add(source)

        response = self.client.post(f'/admin/spellbook/featureattribute/{source.id}/merge/', {'into': str(target.id)}, follow=True)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/admin/spellbook/featureattribute/{source.id}/delete/?merge_into={target.id}', {'post': 'yes', 'merge_into': str(target.id)}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(FeatureAttribute.objects.filter(pk=source.pk).exists())
        self.assertEqual(list(needed.any_of_attributes.all()), [target])
        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Merging Feature$Target Attribute]]')

    def test_change_form_offers_the_merge_button(self):
        self.client.force_login(self.admin)
        attribute = FeatureAttribute.objects.create(name='Some Attribute')

        response = self.client.get(f'/admin/spellbook/featureattribute/{attribute.id}/change/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'/admin/spellbook/featureattribute/{attribute.id}/merge/')

    def test_merge_from_admin_rejects_merging_into_itself(self):
        self.client.force_login(self.admin)
        attribute = FeatureAttribute.objects.create(name='Some Attribute')

        response = self.client.post(f'/admin/spellbook/featureattribute/{attribute.id}/merge/', {'into': str(attribute.id)}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(FeatureAttribute.objects.filter(pk=attribute.pk).exists())
        self.assertContains(response, 'Cannot merge a feature attribute into itself.')
