import random
import uuid
from functools import reduce
from collections import defaultdict
from common.abstract_test_case import AbstractTestCase as TestCase
from django.conf import settings
from spellbook.models import Card, Feature, Combo, CardInCombo, Template, TemplateInCombo
from spellbook.models import CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion
from spellbook.models import VariantSuggestion, VariantAlias, IngredientInCombination, Variant
from spellbook.models import FeatureOfCard, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo
from spellbook.utils import launch_job_command
from spellbook.serializers import VariantSerializer


class AbstractTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        settings.ASYNC_GENERATION = False

    def generate_variants(self):
        launch_job_command('generate_variants', None)

    def bulk_serialize_variants(self, q=None, extra_fields=[]):
        if q is None:
            q = Variant.objects.all()
        Variant.objects.bulk_serialize(q, serializer=VariantSerializer, fields=extra_fields)  # type: ignore

    def save_combo_model(self, model: dict[tuple[str, ...] | str, tuple[str, ...]]):
        card_ids_by_name: dict[str, int] = {}
        feature_ids_by_name: dict[str, int] = {}
        template_ids_by_name: dict[str, int] = {}
        combo_id = 1
        for recipe, result in model.items():
            cards = defaultdict[str, int](int)
            features = defaultdict[str, int](int)
            templates = defaultdict[str, int](int)
            if isinstance(recipe, str):
                if '*' in recipe:
                    recipe, quantity = recipe.split('*')
                    recipe = recipe.strip()
                    quantity = quantity.strip()
                    if not quantity.isdigit():
                        recipe, quantity = quantity, recipe
                    quantity = int(quantity)
                else:
                    quantity = 1
                recipe = recipe.strip()
                assert len(recipe) > 0 and not recipe[0].islower() and recipe[0] != 'T'
                card_id = card_ids_by_name.setdefault(recipe, reduce(lambda x, y: max(x, y), card_ids_by_name.values(), 0) + 1)
                c, _ = Card.objects.get_or_create(pk=card_id, name=recipe, identity='W', legal_commander=True, spoiler=False, type_line='Test Card')
                for feature in result:
                    assert not feature.startswith('-')
                    feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                    f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', utility=feature.startswith('u'))
                    FeatureOfCard.objects.create(card=c, feature=f, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, quantity=quantity)
            else:
                for element in recipe:
                    if '*' in element:
                        element, quantity = element.split('*')
                        quantity = quantity.strip()
                        element = element.strip()
                        if not quantity.isdigit():
                            element, quantity = quantity, element
                        quantity = int(quantity)
                    else:
                        quantity = 1
                    element = element.strip()
                    if element[0].islower():
                        features[element] += quantity
                    elif element[0] == 'T':
                        templates[element] += quantity
                    else:
                        cards[element] += quantity
                combo = Combo.objects.create(pk=combo_id, mana_needed='', other_prerequisites='Test Prerequisites', description='Test Description', status=Combo.Status.GENERATOR)
                for i, (card, quantity) in enumerate(cards.items()):
                    card_id = card_ids_by_name.setdefault(card, reduce(lambda x, y: max(x, y), card_ids_by_name.values(), 0) + 1)
                    c, _ = Card.objects.get_or_create(pk=card_id, name=card, identity='W', legal_commander=True, spoiler=False, type_line='Test Card')
                    CardInCombo.objects.create(card=c, combo=combo, order=i, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, quantity=quantity)
                for feature, quantity in features.items():
                    feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                    f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', utility=feature.startswith('u'))
                    FeatureNeededInCombo.objects.create(feature=f, combo=combo, quantity=quantity)
                for i, (template, quantity) in enumerate(templates.items(), start=1):
                    template_id = template_ids_by_name.setdefault(template, reduce(lambda x, y: max(x, y), template_ids_by_name.values(), 0) + 1)
                    t, _ = Template.objects.get_or_create(pk=template_id, name=template, scryfall_query='o:test', description='Test Template')
                    TemplateInCombo.objects.create(template=t, combo=combo, order=i, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, quantity=quantity)
                for feature in result:
                    if feature.startswith('-'):
                        feature = feature[1:]
                        feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                        f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', utility=feature.startswith('u'))
                        FeatureRemovedInCombo.objects.create(feature=f, combo=combo)
                    else:
                        feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                        f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', utility=feature.startswith('u'))
                        FeatureProducedInCombo.objects.create(feature=f, combo=combo)
                combo_id += 1


class AbstractTestCaseWithSeeding(AbstractTestCase):
    c1_id = 0
    c2_id = 0
    c3_id = 0
    c4_id = 0
    c5_id = 0
    c6_id = 0
    c7_id = 0
    c8_id = 0
    t1_id = 0
    f1_id = 0
    f2_id = 0
    f3_id = 0
    f4_id = 0
    f5_id = 0
    b1_id = 0
    b2_id = 0
    b3_id = 0
    b4_id = 0
    b5_id = 0
    b6_id = 0
    b7_id = 0
    s1_id = 0
    expected_variant_count = 7

    def setUp(self) -> None:
        super().setUp()
        self.populate_db()
        random.seed(42)

    def populate_db(self):
        c1 = Card.objects.create(name='A A', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000001'), identity='W', legal_commander=True, spoiler=False, type_line='Instant', oracle_text='x1', keywords=['keyword1', 'keyword2'])
        c2 = Card.objects.create(name='B B', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000002'), identity='U', legal_commander=True, spoiler=False, type_line='Sorcery', oracle_text='x2 x3', mana_value=3)
        c3 = Card.objects.create(name='C C', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000003'), identity='B', legal_commander=False, spoiler=False, type_line='Creature', oracle_text='xx4', price_tcgplayer=2.71, price_cardkingdom=3.14, price_cardmarket=1.59)
        c4 = Card.objects.create(name='D\' D', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000004'), identity='R', legal_commander=True, spoiler=True, type_line='Battle', oracle_text='x5x', keywords=['keyword3'], price_tcgplayer=3.14, price_cardkingdom=1.59, price_cardmarket=2.65)
        c5 = Card.objects.create(name='E É', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000005'), identity='G', legal_commander=False, spoiler=True, type_line='Planeswalker', oracle_text='', price_tcgplayer=1.23, price_cardkingdom=4.56, price_cardmarket=7.89)
        c6 = Card.objects.create(name='F F', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000006'), identity='WU', legal_commander=True, spoiler=False, type_line='Enchantment', oracle_text='x6', mana_value=6, legal_brawl=False)
        c7 = Card.objects.create(name='G G _____', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000007'), identity='WB', legal_commander=True, spoiler=False, type_line='Artifact', oracle_text='x7x7')
        c8 = Card.objects.create(name='H-H', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000008'), identity='C', legal_commander=True, spoiler=False, type_line='Land', oracle_text='x8. x9.')
        f1 = Feature.objects.create(name='FA', description='Feature A', utility=True)
        f2 = Feature.objects.create(name='FB', description='Feature B', utility=False)
        f3 = Feature.objects.create(name='FC', description='Feature C', utility=False)
        f4 = Feature.objects.create(name='FD', description='Feature D', utility=False)
        f5 = Feature.objects.create(name='FE', description='Feature E', utility=False, uncountable=True)
        b1 = Combo.objects.create(mana_needed='{W}{W}', other_prerequisites='Some requisites.', description='a1', status=Combo.Status.GENERATOR, notes='aa1')
        b2 = Combo.objects.create(mana_needed='{U}{U}', other_prerequisites='Some requisites.', description='b2', status=Combo.Status.GENERATOR, notes='bb2')
        b3 = Combo.objects.create(mana_needed='{B}{B}', other_prerequisites='Some requisites.', description='c3', status=Combo.Status.UTILITY, notes='cc3')
        b4 = Combo.objects.create(mana_needed='{R}{R}', other_prerequisites='Some requisites.', description='d4', status=Combo.Status.GENERATOR, notes='dd4')
        b5 = Combo.objects.create(mana_needed='{G}{G}', other_prerequisites='Some requisites.', description='e5', status=Combo.Status.UTILITY, notes='ee5')
        b6 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', other_prerequisites='Some requisites.', description='f6', status=Combo.Status.GENERATOR, allow_many_cards=True, notes='ff6')
        b7 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', other_prerequisites='Some requisites.', description='g7', status=Combo.Status.DRAFT, notes='gg7')
        b8 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', other_prerequisites='Some requisites.', description='g7', status=Combo.Status.NEEDS_REVIEW, notes='gg7')
        t1 = Template.objects.create(name='TA', scryfall_query='tou>5', description='hello.')
        t2 = Template.objects.create(name='TB', scryfall_query='o:/asd dsa*/')
        FeatureOfCard.objects.create(card=c1, feature=f1, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, quantity=1)
        FeatureNeededInCombo.objects.create(feature=f1, combo=b1, quantity=1)
        CardInCombo.objects.create(card=c2, combo=b1, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND, quantity=1)
        CardInCombo.objects.create(card=c3, combo=b1, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped', quantity=1)
        FeatureProducedInCombo.objects.create(feature=f2, combo=b1)
        FeatureProducedInCombo.objects.create(feature=f3, combo=b1)
        FeatureNeededInCombo.objects.create(feature=f2, combo=b2, quantity=1)
        FeatureRemovedInCombo.objects.create(feature=f3, combo=b2)
        TemplateInCombo.objects.create(template=t1, combo=b2, order=1, zone_locations=IngredientInCombination.ZoneLocation.GRAVEYARD, graveyard_card_state='on top')
        FeatureProducedInCombo.objects.create(feature=f4, combo=b2)
        CardInCombo.objects.create(card=c4, combo=b3, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
        CardInCombo.objects.create(card=c5, combo=b3, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD + IngredientInCombination.ZoneLocation.HAND + IngredientInCombination.ZoneLocation.COMMAND_ZONE)
        CardInCombo.objects.create(card=c6, combo=b3, order=3, zone_locations=IngredientInCombination.ZoneLocation.COMMAND_ZONE, must_be_commander=True)
        CardInCombo.objects.create(card=c7, combo=b3, order=4, zone_locations=IngredientInCombination.ZoneLocation.LIBRARY, library_card_state='on top')
        FeatureProducedInCombo.objects.create(feature=f1, combo=b3)
        CardInCombo.objects.create(card=c5, combo=b5, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
        CardInCombo.objects.create(card=c6, combo=b5, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='attacking')
        FeatureProducedInCombo.objects.create(feature=f1, combo=b5)
        FeatureProducedInCombo.objects.create(feature=f2, combo=b4)
        CardInCombo.objects.create(card=c8, combo=b4, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
        CardInCombo.objects.create(card=c1, combo=b4, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='blocking')
        FeatureProducedInCombo.objects.create(feature=f4, combo=b6)
        CardInCombo.objects.create(card=c1, combo=b6, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
        CardInCombo.objects.create(card=c2, combo=b6, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='face down')
        CardInCombo.objects.create(card=c3, combo=b6, order=3, zone_locations=IngredientInCombination.ZoneLocation.GRAVEYARD, graveyard_card_state='with a sticker')
        CardInCombo.objects.create(card=c4, combo=b6, order=4, zone_locations=IngredientInCombination.ZoneLocation.EXILE, exile_card_state='with a cage counter')
        CardInCombo.objects.create(card=c5, combo=b6, order=5, zone_locations=IngredientInCombination.ZoneLocation.COMMAND_ZONE, must_be_commander=True)
        CardInCombo.objects.create(card=c6, combo=b6, order=6, zone_locations=IngredientInCombination.ZoneLocation.LIBRARY, library_card_state='at the bottom')
        FeatureProducedInCombo.objects.create(feature=f5, combo=b7)
        FeatureNeededInCombo.objects.create(feature=f4, combo=b7, quantity=1)
        FeatureProducedInCombo.objects.create(feature=f5, combo=b8)
        FeatureNeededInCombo.objects.create(feature=f4, combo=b8, quantity=1)

        s1 = VariantSuggestion.objects.create(status=VariantSuggestion.Status.NEW, mana_needed='{W}{W}', other_prerequisites='Some requisites.', description='1', spoiler=True, suggested_by=None)
        CardUsedInVariantSuggestion.objects.create(card=c1.name, variant=s1, order=1, zone_locations=IngredientInCombination.ZoneLocation.HAND)
        CardUsedInVariantSuggestion.objects.create(card=c2.name, variant=s1, order=2, zone_locations=IngredientInCombination.ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
        TemplateRequiredInVariantSuggestion.objects.create(template=t1.name, variant=s1, order=1, zone_locations=IngredientInCombination.ZoneLocation.GRAVEYARD, graveyard_card_state='on top')
        FeatureProducedInVariantSuggestion.objects.create(feature=f1.name, variant=s1)

        a1 = VariantAlias.objects.create(id='1', description='a1')

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
        self.t2_id = t2.id
        self.f1_id = f1.id
        self.f2_id = f2.id
        self.f3_id = f3.id
        self.f4_id = f4.id
        self.f5_id = f5.id
        self.b1_id = b1.id
        self.b2_id = b2.id
        self.b3_id = b3.id
        self.b4_id = b4.id
        self.b5_id = b5.id
        self.b6_id = b6.id
        self.b7_id = b7.id
        self.b8_id = b8.id
        self.s1_id = s1.id
        self.a1_id = a1.id
