from io import StringIO
from django.core.management import call_command
from spellbook.management.commands.report_text_features import text_features
from spellbook.models import CardInCombo, Combo, Feature, FeatureNeededInCombo, FeatureOfCard, ZoneLocation
from .testing import SpellbookTestCase, curated_card


class ReportTextFeaturesTests(SpellbookTestCase):
    '''The shape of FSO step and FSO mana: features produced only by the cards producing Free Sacrifice
    Outlet, needed only by combos needing it too, which exist for their texts alone.'''

    def setUp(self):
        super().setUp()
        self.outlet = Feature.objects.create(name='Free Sacrifice Outlet', status=Feature.Status.PUBLIC_UTILITY)
        self.mana = Feature.objects.create(name='FSO mana', status=Feature.Status.HIDDEN_UTILITY)
        self.unrelated = Feature.objects.create(name='Untapper', status=Feature.Status.HIDDEN_UTILITY)
        for name, mana_text in (('Phyrexian Altar', ', adding one mana of any color'), ('Ashnod Altar', ', adding two colorless mana')):
            card = curated_card(name=name, type_line='Artifact')
            FeatureOfCard.objects.create(card=card, feature=self.outlet, zone_locations=ZoneLocation.BATTLEFIELD)
            FeatureOfCard.objects.create(card=card, feature=self.mana, zone_locations=ZoneLocation.BATTLEFIELD, dictionary={'description': mana_text})
        self.combo = Combo.objects.create(status=Combo.Status.GENERATOR, description='Sacrifice it[[FSO mana@description]].')
        CardInCombo.objects.create(combo=self.combo, card=curated_card(name='Protean Hulk', type_line='Creature'), order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureNeededInCombo.objects.create(combo=self.combo, feature=self.outlet, order=1)
        FeatureNeededInCombo.objects.create(combo=self.combo, feature=self.mana, order=2)
        # needed alone by another combo, so it carries more than text
        untapper_card = curated_card(name='Untapper Card', type_line='Creature')
        FeatureOfCard.objects.create(card=untapper_card, feature=self.unrelated, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureNeededInCombo.objects.create(combo=self.combo, feature=self.unrelated, order=3)
        other = Combo.objects.create(status=Combo.Status.GENERATOR)
        CardInCombo.objects.create(combo=other, card=untapper_card, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureNeededInCombo.objects.create(combo=other, feature=self.unrelated, order=1)

    def test_a_companion_feature_is_found(self):
        found = text_features()
        self.assertEqual([(f.feature.name, [c.name for c in f.companions]) for f in found], [('FSO mana', ['Free Sacrifice Outlet'])])
        self.assertEqual([p.card.name for p in found[0].producers], ['Ashnod Altar', 'Phyrexian Altar'])
        self.assertEqual(found[0].needed_by, [self.combo])

    def test_a_feature_produced_by_a_card_without_the_companion_is_not(self):
        lone = curated_card(name='Lone Mana Card', type_line='Artifact')
        FeatureOfCard.objects.create(card=lone, feature=self.mana, zone_locations=ZoneLocation.BATTLEFIELD)
        self.assertEqual(text_features(), [])

    def test_the_report_names_the_texts_and_the_references(self):
        output = StringIO()
        call_command('report_text_features', stdout=output)
        report = output.getvalue()
        self.assertIn('FSO mana', report)
        self.assertIn('carries text for Free Sacrifice Outlet', report)
        self.assertIn("produced by Phyrexian Altar: {'description': ', adding one mana of any color'}", report)
        self.assertIn(f'needed by combo {self.combo.id}: [[FSO mana@description]]', report)
        self.assertIn('1 feature only carrying text.', report)
