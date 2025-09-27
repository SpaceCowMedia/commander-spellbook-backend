import uuid
import re
from functools import reduce
from collections import defaultdict
from django.db.models import Q, Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User
from website.tests.testing import BaseTestCase
from spellbook.variants.multiset import FrozenMultiset
from spellbook.models import Card, Feature, Combo, CardInCombo, Job, Template, TemplateInCombo
from spellbook.models import CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion
from spellbook.models import VariantSuggestion, VariantAlias, Variant, ZoneLocation
from spellbook.models import FeatureOfCard, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo, FeatureAttribute
from spellbook.utils import launch_job_command
from spellbook.serializers import VariantSerializer


class SpellbookTestCase(BaseTestCase):
    def assertMultisetEqual(self, a, b):
        if isinstance(a, FrozenMultiset):
            a = {k: v for k, v in a.items()}
        if isinstance(b, FrozenMultiset):
            b = {k: v for k, v in b.items()}
        self.assertDictEqual(a, b)

    @classmethod
    def generate_variants(cls):
        job = launch_job_command('generate_variants', background=False)
        assert job is not None
        if job.status == Job.Status.FAILURE:
            raise Exception(job.message)
        assert job.status == Job.Status.SUCCESS, f'{job} status was {job.status}'

    @classmethod
    def bulk_serialize_variants(cls, q=None, extra_fields=[]):
        if q is None:
            q = Variant.objects.all()
        Variant.objects.bulk_serialize(q, serializer=VariantSerializer, fields=extra_fields)

    @classmethod
    def update_variants(cls):
        Card.objects.update(
            variant_count=Coalesce(
                Subquery(
                    Variant
                    .objects
                    .filter(uses=OuterRef('pk'), status__in=Variant.public_statuses())
                    .values('uses')
                    .annotate(total=Count('pk', distinct=True))
                    .values('total'),
                ),
                0,
            ),
        )
        Combo.objects.update(
            variant_count=Coalesce(
                Subquery(
                    Variant
                    .objects
                    .filter(of=OuterRef('pk'), status__in=Variant.public_statuses())
                    .values('of')
                    .annotate(total=Count('pk', distinct=True))
                    .values('total'),
                ),
                0,
            ),
        )
        variants = list(Variant.objects.only('id').annotate(
            variant_count_updated=Count('of__variants', distinct=True, filter=Q(of__variants__status__in=Variant.public_statuses()))
        ))
        for variant in variants:
            variant.variant_count = variant.variant_count_updated
            variant.update_variant()
            variant.pre_save = lambda: None
        Variant.objects.bulk_update(variants, Variant.computed_fields() + ['variant_count'])

    @classmethod
    def generate_and_publish_variants(cls):
        cls.generate_variants()
        cls.bulk_serialize_variants()
        Variant.objects.update(status=Variant.Status.OK)
        cls.update_variants()

    @classmethod
    def setup_combo_graph(cls, model: dict[tuple[str, ...] | str, tuple[str, ...]]):
        card_ids_by_name: dict[str, int] = {}
        feature_ids_by_name: dict[str, int] = {}
        template_ids_by_name: dict[str, int] = {}
        attribute_ids_by_name: dict[str, int] = {}
        combo_id = 1
        feature_of_card_id = 1
        for recipe, result in model.items():
            cards = defaultdict[str, int](int)
            templates = defaultdict[str, int](int)
            features = list[tuple[str, int]]()
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
                for r in result:
                    feature, attributes = r.split('/') if '/' in r else (r, '')
                    feature = feature.strip()
                    assert not feature.startswith('-')
                    attributes = [a.strip() for a in attributes.split(',') if a.strip()]
                    feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                    f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', status=Feature.Status.HIDDEN_UTILITY if feature.startswith('u') else Feature.Status.STANDALONE)
                    foc = FeatureOfCard.objects.create(pk=feature_of_card_id, card=c, feature=f, zone_locations=ZoneLocation.BATTLEFIELD, quantity=quantity)
                    for attribute in attributes:
                        attribute_id = attribute_ids_by_name.setdefault(attribute, reduce(lambda x, y: max(x, y), attribute_ids_by_name.values(), 0) + 1)
                        a, _ = FeatureAttribute.objects.get_or_create(pk=attribute_id, name=attribute)
                        foc.attributes.add(a)
                    feature_of_card_id += 1
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
                        features.append((element, quantity))
                    elif element[0] == 'T':
                        templates[element] += quantity
                    else:
                        cards[element] += quantity
                combo = Combo.objects.create(pk=combo_id, mana_needed='', easy_prerequisites='Test Easy Prerequisites', notable_prerequisites='Test Notable Prerequisites', description='Test Description', status=Combo.Status.GENERATOR)
                for i, (card, quantity) in enumerate(cards.items(), start=1):
                    card_id = card_ids_by_name.setdefault(card, reduce(lambda x, y: max(x, y), card_ids_by_name.values(), 0) + 1)
                    c, _ = Card.objects.get_or_create(pk=card_id, name=card, identity='W', legal_commander=True, spoiler=False, type_line='Test Card')
                    CardInCombo.objects.create(card=c, combo=combo, order=i, zone_locations=ZoneLocation.BATTLEFIELD, quantity=quantity)
                for i, (template, quantity) in enumerate(templates.items(), start=1):
                    template_id = template_ids_by_name.setdefault(template, reduce(lambda x, y: max(x, y), template_ids_by_name.values(), 0) + 1)
                    t, _ = Template.objects.get_or_create(pk=template_id, name=template, scryfall_query='o:test', description='Test Template')
                    TemplateInCombo.objects.create(template=t, combo=combo, order=i, zone_locations=ZoneLocation.BATTLEFIELD, quantity=quantity)
                for r, quantity in features:
                    r = re.match(r'([^?!-]+)(\?[^?!-]+)?(![^?!-]+)?(-[^?!-]+)?', r)
                    assert r is not None
                    feature, any_of_attributes, all_of_attributes, none_of_attributes = r.groups()
                    feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                    f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', status=Feature.Status.HIDDEN_UTILITY if feature.startswith('u') else Feature.Status.STANDALONE)
                    fnc = FeatureNeededInCombo.objects.create(feature=f, combo=combo, quantity=quantity)
                    for attribute in (any_of_attributes or '').removeprefix('?').split(','):
                        attribute = attribute.strip()
                        if attribute:
                            attribute_id = attribute_ids_by_name.setdefault(attribute, reduce(lambda x, y: max(x, y), attribute_ids_by_name.values(), 0) + 1)
                            a, _ = FeatureAttribute.objects.get_or_create(pk=attribute_id, name=attribute)
                            fnc.any_of_attributes.add(a)
                    for attribute in (all_of_attributes or '').removeprefix('!').split(','):
                        attribute = attribute.strip()
                        if attribute:
                            attribute_id = attribute_ids_by_name.setdefault(attribute, reduce(lambda x, y: max(x, y), attribute_ids_by_name.values(), 0) + 1)
                            a, _ = FeatureAttribute.objects.get_or_create(pk=attribute_id, name=attribute)
                            fnc.all_of_attributes.add(a)
                    for attribute in (none_of_attributes or '').removeprefix('-').split(','):
                        attribute = attribute.strip()
                        if attribute:
                            attribute_id = attribute_ids_by_name.setdefault(attribute, reduce(lambda x, y: max(x, y), attribute_ids_by_name.values(), 0) + 1)
                            a, _ = FeatureAttribute.objects.get_or_create(pk=attribute_id, name=attribute)
                            fnc.none_of_attributes.add(a)
                for r in result:
                    feature, attributes = r.split('/') if '/' in r else (r, '')
                    feature = feature.strip()
                    attributes = [a.strip() for a in attributes.split(',') if a.strip()]
                    if feature.startswith('-'):
                        assert not attributes
                        feature = feature[1:]
                        feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                        f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', status=Feature.Status.HIDDEN_UTILITY if feature.startswith('u') else Feature.Status.STANDALONE)
                        FeatureRemovedInCombo.objects.create(feature=f, combo=combo)
                    else:
                        feature_id = feature_ids_by_name.setdefault(feature, reduce(lambda x, y: max(x, y), feature_ids_by_name.values(), 0) + 1)
                        f, _ = Feature.objects.get_or_create(pk=feature_id, name=feature, description='Test Feature', status=Feature.Status.HIDDEN_UTILITY if feature.startswith('u') else Feature.Status.STANDALONE)
                        fpc = FeatureProducedInCombo.objects.create(feature=f, combo=combo)
                        for attribute in attributes:
                            attribute_id = attribute_ids_by_name.setdefault(attribute, reduce(lambda x, y: max(x, y), attribute_ids_by_name.values(), 0) + 1)
                            a, _ = FeatureAttribute.objects.get_or_create(pk=attribute_id, name=attribute)
                            fpc.attributes.add(a)
                combo_id += 1


class SpellbookTestCaseWithSeeding(SpellbookTestCase):
    expected_variant_count = 8
    admin: User
    user: User

    @classmethod
    def setUpTestData(cls):
        '''
        Populate the database with some test data.
        If used to generate variants, the expected generated variants are:
        - <Variant: A A + B B + C C + D' D + E É + F F ➜ 2 FB + 2 FC + FD> with id '1-2-3-4-5-6'
        - <Variant: H-H + A A ➜ FB> with id '1-8'
        - <Variant: B B + E É + C C + F F + TA ➜ FB + FD> with id '2-3-5-6--1'
        - <Variant: B B + C C + A A + TA ➜ FB + FD> with id '1-2-3--1'
        - <Variant: H-H + A A + TA ➜ FB + FD> with id '1-8--1'
        - <Variant: B B + C C + A A ➜ FB + FC> with id '1-2-3'
        - <Variant: B B + C C + E É + F F ➜ FB + FC> with id '2-3-5-6'
        - <Variant: A A + B B + TA + TB ➜ FD> with id '1-2--1-2'
        '''
        super().setUpTestData()
        fa1 = FeatureAttribute.objects.create(name='FA1')
        fa2 = FeatureAttribute.objects.create(name='FA2')
        c1 = Card.objects.create(name='A A', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000001'), identity='W', legal_commander=True, spoiler=False, type_line='Instant', oracle_text='x1', keywords=['keyword1', 'keyword2'], game_changer=True, extra_turn=True, image_uri_front_png='http://localhost/x.png', image_uri_back_normal='http://localhost/x.jpg')
        c2 = Card.objects.create(name='B B', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000002'), identity='U', legal_commander=True, spoiler=False, type_line='Sorcery', oracle_text='x2 x3', mana_value=3, game_changer=True)
        c3 = Card.objects.create(name='C C', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000003'), identity='B', legal_commander=False, spoiler=False, type_line='Creature', oracle_text='xx4', price_tcgplayer=2.71, price_cardkingdom=3.14, price_cardmarket=1.59)
        c4 = Card.objects.create(name='D\' D', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000004'), identity='R', legal_commander=True, spoiler=True, type_line='Battle', oracle_text='x5x', keywords=['keyword3'], price_tcgplayer=3.14, price_cardkingdom=1.59, price_cardmarket=2.65)
        c5 = Card.objects.create(name='E É', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000005'), identity='G', legal_commander=False, spoiler=True, type_line='Planeswalker', oracle_text='', price_tcgplayer=1.23, price_cardkingdom=4.56, price_cardmarket=7.89)
        c6 = Card.objects.create(name='F F', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000006'), identity='WU', legal_commander=True, spoiler=False, type_line='Enchantment', oracle_text='x6', mana_value=6, legal_brawl=False)
        c7 = Card.objects.create(name='G G _____', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000007'), identity='WB', legal_commander=True, spoiler=False, type_line='Artifact', oracle_text='x7x7')
        c8 = Card.objects.create(name='H-H', oracle_id=uuid.UUID('00000000-0000-0000-0000-000000000008'), identity='C', legal_commander=True, spoiler=False, type_line='Land', oracle_text='x8. x9.', mana_value=8)
        f1 = Feature.objects.create(name='FA', description='Feature A', status=Feature.Status.HIDDEN_UTILITY)
        f2 = Feature.objects.create(name='FB', description='Feature B', status=Feature.Status.CONTEXTUAL)
        f3 = Feature.objects.create(name='FC', description='Feature C', status=Feature.Status.HELPER)
        f4 = Feature.objects.create(name='FD', description='Feature D', status=Feature.Status.STANDALONE)
        f5 = Feature.objects.create(name='FE', description='Feature E', status=Feature.Status.STANDALONE, uncountable=True)
        f6 = Feature.objects.create(name='FF', description='Feature F', status=Feature.Status.PUBLIC_UTILITY)
        b1 = Combo.objects.create(mana_needed='{W}{W}', easy_prerequisites='Some easy requisites.', notable_prerequisites='Some notable requisites.', description='a1', status=Combo.Status.GENERATOR, notes='aa1', comment='***1')
        b2 = Combo.objects.create(mana_needed='{U}{U}', easy_prerequisites='Some easy requisites.', notable_prerequisites='Some notable requisites.', description='b2', status=Combo.Status.GENERATOR, notes='bb2', comment='***2')
        b3 = Combo.objects.create(mana_needed='{B}{B}', notable_prerequisites='Some requisites.', description='c3', status=Combo.Status.UTILITY, notes='cc3', comment='***3')
        b4 = Combo.objects.create(mana_needed='{R}{R}', notable_prerequisites='Some requisites.', description='d4', status=Combo.Status.GENERATOR, notes='dd4', comment='***4')
        b5 = Combo.objects.create(mana_needed='{G}{G}', notable_prerequisites='Some requisites.', description='e5', status=Combo.Status.UTILITY, notes='ee5', comment='***5')
        b6 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', notable_prerequisites='Some requisites.', description='f6', status=Combo.Status.GENERATOR, allow_many_cards=True, notes='ff6', comment='***6')
        b7 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', notable_prerequisites='Some requisites.', description='g7', status=Combo.Status.DRAFT, notes='gg7', comment='***7')
        b8 = Combo.objects.create(mana_needed='{W}{U}{B}{R}{G}', notable_prerequisites='Some requisites.', description='h8', status=Combo.Status.NEEDS_REVIEW, notes='hh8', comment='***8')
        b9 = Combo.objects.create(mana_needed='', easy_prerequisites='Some easy requisites.', notable_prerequisites='Some notable requisites.', description='i9', status=Combo.Status.GENERATOR, notes='ii9', comment='***9')
        t1 = Template.objects.create(name='TA', scryfall_query='tou>5', description='hello.')
        t2 = Template.objects.create(name='TB')
        t2.replacements.add(c3)
        fc1 = FeatureOfCard.objects.create(card=c1, feature=f1, zone_locations=ZoneLocation.BATTLEFIELD, quantity=1, notable_prerequisites='Some requisites for card.')
        fc1.attributes.add(fa2)
        FeatureOfCard.objects.create(card=c1, feature=f1, zone_locations=ZoneLocation.BATTLEFIELD, quantity=1, notable_prerequisites='Some requisites for card two.', easy_prerequisites='Some easy requisites for card two.')
        fn1 = FeatureNeededInCombo.objects.create(feature=f1, combo=b1, quantity=1)
        fn1.any_of_attributes.add(fa1, fa2)
        CardInCombo.objects.create(card=c2, combo=b1, order=1, zone_locations=ZoneLocation.HAND, quantity=1)
        CardInCombo.objects.create(card=c3, combo=b1, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped', quantity=1)
        fp1 = FeatureProducedInCombo.objects.create(feature=f2, combo=b1)
        fp1.attributes.add(fa1, fa2)
        FeatureProducedInCombo.objects.create(feature=f3, combo=b1)
        fn2 = FeatureNeededInCombo.objects.create(feature=f2, combo=b2, quantity=1)
        fn2.all_of_attributes.add(fa1, fa2)
        FeatureRemovedInCombo.objects.create(feature=f3, combo=b2)
        TemplateInCombo.objects.create(template=t1, combo=b2, order=1, zone_locations=ZoneLocation.GRAVEYARD, graveyard_card_state='on top')
        fp3 = FeatureProducedInCombo.objects.create(feature=f4, combo=b2)
        fp3.attributes.add(fa2)
        CardInCombo.objects.create(card=c4, combo=b3, order=1, zone_locations=ZoneLocation.HAND)
        CardInCombo.objects.create(card=c5, combo=b3, order=2, zone_locations=ZoneLocation.BATTLEFIELD + ZoneLocation.HAND + ZoneLocation.COMMAND_ZONE)
        CardInCombo.objects.create(card=c6, combo=b3, order=3, zone_locations=ZoneLocation.COMMAND_ZONE, must_be_commander=True)
        CardInCombo.objects.create(card=c7, combo=b3, order=4, zone_locations=ZoneLocation.LIBRARY, library_card_state='on top')
        fp4 = FeatureProducedInCombo.objects.create(feature=f1, combo=b3)
        fp4.attributes.add(fa1)
        CardInCombo.objects.create(card=c5, combo=b5, order=1, zone_locations=ZoneLocation.HAND)
        CardInCombo.objects.create(card=c6, combo=b5, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='attacking')
        fp5 = FeatureProducedInCombo.objects.create(feature=f1, combo=b5)
        fp5.attributes.add(fa2)
        fp6 = FeatureProducedInCombo.objects.create(feature=f2, combo=b4)
        fp6.attributes.add(fa1, fa2)
        FeatureProducedInCombo.objects.create(feature=f2, combo=b4)
        CardInCombo.objects.create(card=c8, combo=b4, order=1, zone_locations=ZoneLocation.HAND)
        CardInCombo.objects.create(card=c1, combo=b4, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='blocking')
        FeatureProducedInCombo.objects.create(feature=f4, combo=b6)
        CardInCombo.objects.create(card=c1, combo=b6, order=1, zone_locations=ZoneLocation.HAND)
        CardInCombo.objects.create(card=c2, combo=b6, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='face down')
        CardInCombo.objects.create(card=c3, combo=b6, order=3, zone_locations=ZoneLocation.GRAVEYARD, graveyard_card_state='with a sticker')
        CardInCombo.objects.create(card=c4, combo=b6, order=4, zone_locations=ZoneLocation.EXILE, exile_card_state='with a cage counter')
        CardInCombo.objects.create(card=c5, combo=b6, order=5, zone_locations=ZoneLocation.COMMAND_ZONE, must_be_commander=True)
        CardInCombo.objects.create(card=c6, combo=b6, order=6, zone_locations=ZoneLocation.LIBRARY, library_card_state='at the bottom')
        FeatureProducedInCombo.objects.create(feature=f5, combo=b7)
        fn3 = FeatureNeededInCombo.objects.create(feature=f4, combo=b7, quantity=1)
        fn3.none_of_attributes.add(fa1)
        FeatureProducedInCombo.objects.create(feature=f5, combo=b8)
        FeatureNeededInCombo.objects.create(feature=f4, combo=b8, quantity=1)
        CardInCombo.objects.create(card=c1, combo=b9, order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
        CardInCombo.objects.create(card=c2, combo=b9, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
        TemplateInCombo.objects.create(template=t1, combo=b9, order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
        TemplateInCombo.objects.create(template=t2, combo=b9, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
        FeatureProducedInCombo.objects.create(feature=f4, combo=b9)

        s1 = VariantSuggestion.objects.create(status=VariantSuggestion.Status.NEW, mana_needed='{W}{W}', easy_prerequisites='Some easy requisites.', notable_prerequisites='Some notable requisites.', description='1', spoiler=True, suggested_by=None)
        CardUsedInVariantSuggestion.objects.create(card=c1.name, variant=s1, order=1, zone_locations=ZoneLocation.HAND)
        CardUsedInVariantSuggestion.objects.create(card=c2.name, variant=s1, order=2, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='tapped')
        TemplateRequiredInVariantSuggestion.objects.create(template=t1.name, variant=s1, order=1, zone_locations=ZoneLocation.GRAVEYARD, graveyard_card_state='on top')
        FeatureProducedInVariantSuggestion.objects.create(feature=f1.name, variant=s1)

        a1 = VariantAlias.objects.create(id='1', description='a1')

        # Save ids
        cls.c1_id = c1.id
        cls.c2_id = c2.id
        cls.c3_id = c3.id
        cls.c4_id = c4.id
        cls.c5_id = c5.id
        cls.c6_id = c6.id
        cls.c7_id = c7.id
        cls.c8_id = c8.id
        cls.t1_id = t1.id
        cls.t2_id = t2.id
        cls.f1_id = f1.id
        cls.f2_id = f2.id
        cls.f3_id = f3.id
        cls.f4_id = f4.id
        cls.f5_id = f5.id
        cls.f6_id = f6.id
        cls.b1_id = b1.id
        cls.b2_id = b2.id
        cls.b3_id = b3.id
        cls.b4_id = b4.id
        cls.b5_id = b5.id
        cls.b6_id = b6.id
        cls.b7_id = b7.id
        cls.b8_id = b8.id
        cls.b9_id = b9.id
        cls.s1_id = s1.id
        cls.a1_id = a1.id

        cls.user = User.objects.create(username='user', password='user')
        cls.admin = User.objects.create(username='admin', password='admin', is_staff=True, is_superuser=True)
