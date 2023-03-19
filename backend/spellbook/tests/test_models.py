import uuid
from django.test import TestCase
from spellbook.models import Combo, CardInCombo, TemplateInCombo, Card, Feature, Template, IngredientInCombination


def populate_db():
    c1 = Card.objects.create(name='A', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000001'), identity='W', legal=True, spoiler=False)
    c2 = Card.objects.create(name='B', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000002'), identity='U', legal=True, spoiler=False)
    c3 = Card.objects.create(name='C', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000003'), identity='B', legal=False, spoiler=False)
    c4 = Card.objects.create(name='D', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000004'), identity='R', legal=True, spoiler=True)
    c5 = Card.objects.create(name='E', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000005'), identity='G', legal=False, spoiler=True)
    c6 = Card.objects.create(name='F', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000006'), identity='WU', legal=True, spoiler=False)
    c7 = Card.objects.create(name='G', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000007'), identity='WB', legal=True, spoiler=False)
    f1 = Feature.objects.create(name='FA', description='Feature A', utility=False)
    f2 = Feature.objects.create(name='FB', description='Feature B', utility=True)
    f3 = Feature.objects.create(name='FC', description='Feature C', utility=False)
    f4 = Feature.objects.create(name='FD', description='Feature D', utility=True)
    b1 = Combo.objects.create(mana_needed='{W}{W}', other_prerequisites='Some requisites.', description='Some description.', generator=False)
    b2 = Combo.objects.create(mana_needed='{U}{U}', other_prerequisites='Some requisites.', description='Some description.', generator=True)
    b3 = Combo.objects.create(mana_needed='{B}{B}', other_prerequisites='Some requisites.', description='Some description.', generator=False)
    t1 = Template.objects.create(name='TA', scryfall_query='tou>5')
    c1.features.add(f1)
    b1.needs.add(f1)
    CardInCombo.objects.create(card=c2, combo=b1, order=1, zone_location=IngredientInCombination.ZoneLocation.HAND, card_state='Some state.')
    CardInCombo.objects.create(card=c3, combo=b1, order=2, zone_location=IngredientInCombination.ZoneLocation.BATTLEFIELD, card_state='Some state.')
    b1.produces.add(f2)
    b1.produces.add(f3)
    b2.needs.add(f2)
    b2.removes.add(f3)
    TemplateInCombo.objects.create(template=t1, combo=b2, order=1, zone_location=IngredientInCombination.ZoneLocation.GRAVEYARD, card_state='Some state.')
    b2.produces.add(f4)
    CardInCombo.objects.create(card=c4, combo=b3, order=1, zone_location=IngredientInCombination.ZoneLocation.HAND, card_state='Some state.')
    CardInCombo.objects.create(card=c5, combo=b3, order=2, zone_location=IngredientInCombination.ZoneLocation.BATTLEFIELD, card_state='Some state.')
    CardInCombo.objects.create(card=c6, combo=b3, order=3, zone_location=IngredientInCombination.ZoneLocation.COMMAND_ZONE, card_state='Some state.')
    CardInCombo.objects.create(card=c7, combo=b3, order=4, zone_location=IngredientInCombination.ZoneLocation.LIBRARY, card_state='Some state.')


class CardTests(TestCase):

    def setUp(self) -> None:
        populate_db()

    def test_card(self):
        c = Card.objects.get(name='A')
        self.assertTrue(c.legal)
        self.assertFalse(c.spoiler)

    def test_card_query_string(self):
        c = Card.objects.get(name='A')
        self.assertEqual(c.query_string(), 'q=%21%22A%22')
