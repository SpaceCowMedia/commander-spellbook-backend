import uuid
from django.contrib.auth.models import User
from spellbook.models import Combo, CardInCombo, TemplateInCombo, Card, Feature, Template, IngredientInCombination


def populate_db(self):
    c1 = Card.objects.create(name='A A', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000001'), identity='W', legal=True, spoiler=False)
    c2 = Card.objects.create(name='B B', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000002'), identity='U', legal=True, spoiler=False)
    c3 = Card.objects.create(name='C C', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000003'), identity='B', legal=False, spoiler=False)
    c4 = Card.objects.create(name='D D', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000004'), identity='R', legal=True, spoiler=True)
    c5 = Card.objects.create(name='E E', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000005'), identity='G', legal=False, spoiler=True)
    c6 = Card.objects.create(name='F F', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000006'), identity='WU', legal=True, spoiler=False)
    c7 = Card.objects.create(name='G G', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000007'), identity='WB', legal=True, spoiler=False)
    c8 = Card.objects.create(name='H H', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000008'), identity='C', legal=True, spoiler=False)
    f1 = Feature.objects.create(name='FA', description='Feature A', utility=True)
    f2 = Feature.objects.create(name='FB', description='Feature B', utility=False)
    f3 = Feature.objects.create(name='FC', description='Feature C', utility=False)
    f4 = Feature.objects.create(name='FD', description='Feature D', utility=False)
    b1 = Combo.objects.create(mana_needed='{W}{W}', other_prerequisites='Some requisites.', description='1', kind=Combo.Kind.GENERATOR)
    b2 = Combo.objects.create(mana_needed='{U}{U}', other_prerequisites='Some requisites.', description='2', kind=Combo.Kind.GENERATOR)
    b3 = Combo.objects.create(mana_needed='{B}{B}', other_prerequisites='Some requisites.', description='3', kind=Combo.Kind.UTILITY)
    b4 = Combo.objects.create(mana_needed='{R}{R}', other_prerequisites='Some requisites.', description='4', kind=Combo.Kind.GENERATOR)
    b5 = Combo.objects.create(mana_needed='{G}{G}', other_prerequisites='Some requisites.', description='5', kind=Combo.Kind.UTILITY)
    b6 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', other_prerequisites='Some requisites.', description='6', kind=Combo.Kind.GENERATOR_WITH_MANY_CARDS)
    t1 = Template.objects.create(name='TA', scryfall_query='tou>5')
    c1.features.add(f1)
    b1.needs.add(f1)
    CardInCombo.objects.create(card=c2, combo=b1, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
    CardInCombo.objects.create(card=c3, combo=b1, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
    b1.produces.add(f2)
    b1.produces.add(f3)
    b2.needs.add(f2)
    b2.removes.add(f3)
    TemplateInCombo.objects.create(template=t1, combo=b2, order=1, zone_locations=IngredientInCombination.ZoneLocation.GRAVEYARD, graveyard_card_state='on top')
    b2.produces.add(f4)
    CardInCombo.objects.create(card=c4, combo=b3, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
    CardInCombo.objects.create(card=c5, combo=b3, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD + IngredientInCombination.ZoneLocation.HAND + IngredientInCombination.ZoneLocation.COMMAND_ZONE)
    CardInCombo.objects.create(card=c6, combo=b3, order=3, zone_locations=IngredientInCombination.ZoneLocation.COMMAND_ZONE)
    CardInCombo.objects.create(card=c7, combo=b3, order=4, zone_locations=IngredientInCombination.ZoneLocation.LIBRARY, library_card_state='on top')
    b3.produces.add(f1)
    CardInCombo.objects.create(card=c5, combo=b5, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
    CardInCombo.objects.create(card=c6, combo=b5, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='attacking')
    b5.produces.add(f1)
    b4.produces.add(f2)
    CardInCombo.objects.create(card=c8, combo=b4, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
    CardInCombo.objects.create(card=c1, combo=b4, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='blocking')
    b6.produces.add(f4)
    CardInCombo.objects.create(card=c1, combo=b6, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
    CardInCombo.objects.create(card=c2, combo=b6, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='face down')
    CardInCombo.objects.create(card=c3, combo=b6, order=3, zone_locations=IngredientInCombination.ZoneLocation.GRAVEYARD, graveyard_card_state='with a sticker')
    CardInCombo.objects.create(card=c4, combo=b6, order=4, zone_locations=IngredientInCombination.ZoneLocation.EXILE, exile_card_state='with a cage counter')
    CardInCombo.objects.create(card=c5, combo=b6, order=5, zone_locations=IngredientInCombination.ZoneLocation.COMMAND_ZONE)
    CardInCombo.objects.create(card=c6, combo=b6, order=6, zone_locations=IngredientInCombination.ZoneLocation.LIBRARY, library_card_state='at the bottom')

    # Save ids
    self.c1_id = c1.id
    self.c2_id = c2.id
    self.c3_id = c3.id
    self.c4_id = c4.id
    self.c5_id = c5.id
    self.c6_id = c6.id
    self.c7_id = c7.id
    self.c8_id = c8.id
    self.t1_id = t1.id
    self.f1_id = f1.id
    self.f2_id = f2.id
    self.f3_id = f3.id
    self.f4_id = f4.id
    self.b1_id = b1.id
    self.b2_id = b2.id
    self.b3_id = b3.id
    self.b4_id = b4.id
    self.b5_id = b5.id
    self.b6_id = b6.id
