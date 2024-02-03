from urllib.parse import quote_plus
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from common.inspection import count_methods
from .abstract_test import AbstractModelTests
from spellbook.models import merge_identities, Card, Feature, Template, Combo, Job, IngredientInCombination, Variant, VariantSuggestion, CardUsedInVariantSuggestion, VariantAlias, PreSerializedSerializer
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH
from spellbook.models import id_from_cards_and_templates_ids
from django.core.exceptions import ValidationError
from spellbook.serializers import VariantSerializer


class UtilsTests(TestCase):
    def test_merge_identities(self):
        self.assertEqual(merge_identities(['', '']), 'C')
        for c in 'CWUBRG':
            self.assertEqual(merge_identities([c, '']), c)
            self.assertEqual(merge_identities(['', c]), c)
            self.assertEqual(merge_identities([c, c]), c)
        self.assertSetEqual(set(merge_identities(['W', 'U'])), set('WU'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B'])), set('WUB'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B', 'R'])), set('WUBR'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B', 'R', 'G'])), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(sorted(['W', 'U', 'B', 'R', 'G']))), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B', 'R', 'G', 'W'])), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(['WU', 'BR', 'G', 'WG'])), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(['S'])), set('C'))
        self.assertSetEqual(set(merge_identities(['S', 'R'])), set('R'))
        self.assertSetEqual(set(merge_identities(['r', 'g'])), set('RG'))
        self.assertSetEqual(set(merge_identities(['g', 'r'])), set('RG'))


class CardTests(AbstractModelTests):
    def test_card_fields(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(c.name, 'A A')
        self.assertEqual(str(c.oracle_id), '00000000-0000-0000-0000-000000000001')
        self.assertEqual(c.features.count(), 1)
        self.assertEqual(c.identity, 'W')
        self.assertTrue(c.legal_commander)
        self.assertFalse(c.spoiler)
        self.assertEqual(c.oracle_text, 'x1')
        self.assertEqual(c.keywords, [])
        self.assertEqual(c.mana_value, 0)
        self.assertFalse(c.reserved)
        self.assertEqual(c.latest_printing_set, '')
        self.assertFalse(c.reprinted)

    def test_query_string(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(f'q=%21%22{quote_plus(c.name)}%22', c.query_string())

    def test_scryfall_link(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, c.scryfall_link())
        self.assertIn(c.query_string(), c.scryfall_link())
        self.assertIn('<a', c.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Card), 4)

    def test_name_unaccented(self):
        c = Card.objects.create(name='à, è, ì, ò, ù, y, À, È, Ì, Ò, Ù, Y, á, é, í, ó, ú, ý, Á, É, Í, Ó, Ú, Ý, â, ê, î, ô, û, y, Â, Ê, Î, Ô, Û, Y, ä, ë, ï, ö, ü, ÿ, Ä, Ë, Ï, Ö, Ü, Ÿ', oracle_id='47d6f04b-a6fe-4274-bd27-888475158e82')
        self.assertEqual(c.name_unaccented, ', '.join('aeiouyAEIOUY' * 4))
        c.name = 'àààèèèìììòòòùùù'
        c.save()
        self.assertEqual(c.name_unaccented, 'aaaeeeiiiooouuu')
        c.name = 'ààèèììòòùù'
        Card.objects.bulk_update([c], ['name', 'name_unaccented'])
        c.refresh_from_db()
        self.assertEqual(c.name_unaccented, 'aaeeiioouu')
        c.delete()
        Card.objects.bulk_create([Card(name='àààèèèìììòòòùùù', oracle_id='47d6f04b-a6fe-4274-bd27-888475158e82')])
        c = Card.objects.get(name='àààèèèìììòòòùùù')
        self.assertEqual(c.name_unaccented, 'aaaeeeiiiooouuu')


class FeatureTests(AbstractModelTests):
    def test_feature_fields(self):
        f = Feature.objects.get(id=self.f1_id)
        self.assertEqual(f.name, 'FA')
        self.assertEqual(f.description, 'Feature A')
        self.assertEqual(f.cards.count(), 1)
        self.assertTrue(f.utility)
        f = Feature.objects.get(id=self.f2_id)
        self.assertFalse(f.utility)

    def test_method_count(self):
        self.assertEqual(count_methods(Feature), 1)


class TemplateTests(AbstractModelTests):
    def test_template_fields(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')

    def test_query_string(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn('q=tou%3E5', t.query_string())
        self.assertTrue(t.query_string().startswith('q='))

    def test_scryfall_api_url(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_API_ROOT, t.scryfall_api())
        self.assertIn(t.query_string(), t.scryfall_api())

    def test_scryfall_link(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link())
        self.assertIn(t.query_string(), t.scryfall_link())
        self.assertIn('<a', t.scryfall_link())
        self.assertIn('target="_blank"', t.scryfall_link())

        t.scryfall_query = ''
        self.assertNotIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link())
        self.assertNotIn(t.query_string(), t.scryfall_link())
        self.assertNotIn('<a', t.scryfall_link())
        self.assertNotIn('target="_blank"', t.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Template), 4)


class ComboTests(AbstractModelTests):
    def test_combo_fields(self):
        c = Combo.objects.get(id=self.b1_id)
        self.assertEqual(c.description, '1')
        self.assertEqual(c.uses.count(), 2)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 0)
        self.assertEqual(c.produces.count(), 2)
        self.assertEqual(c.removes.count(), 0)
        self.assertEqual(c.mana_needed, '{W}{W}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertEqual(c.kind, Combo.Kind.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 2)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000002').zone_locations, IngredientInCombination.ZoneLocation.HAND)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000003').zone_locations, IngredientInCombination.ZoneLocation.BATTLEFIELD)
        self.assertEqual(c.templateincombo_set.count(), 0)
        c = Combo.objects.get(id=self.b2_id)
        self.assertEqual(c.description, '2')
        self.assertEqual(c.uses.count(), 0)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 1)
        self.assertEqual(c.produces.count(), 1)
        self.assertEqual(c.removes.count(), 1)
        self.assertEqual(c.mana_needed, '{U}{U}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertEqual(c.kind, Combo.Kind.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 0)
        self.assertEqual(c.templateincombo_set.count(), 1)
        self.assertEqual(c.templateincombo_set.get(template__name='TA').zone_locations, IngredientInCombination.ZoneLocation.GRAVEYARD)

    def test_ingredients(self):
        for c in Combo.objects.all():
            cic = sorted(c.cardincombo_set.all(), key=lambda x: x.order)
            self.assertEqual(c.cards(), list(map(lambda x: x.card, cic)))
            tic = sorted(c.templateincombo_set.all(), key=lambda x: x.order)
            self.assertEqual(c.templates(), list(map(lambda x: x.template, tic)))
            self.assertEqual(c.features_needed(), list(c.needs.all()))
            self.assertEqual(c.features_produced(), list(c.produces.all()))

    def test_query_string(self):
        c = Combo.objects.get(id=self.b1_id)
        for card in c.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', c.query_string())
        self.assertIn('+or+', c.query_string())
        self.assertTrue(c.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 4)


class JobTests(AbstractModelTests):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username='test', password='test', is_staff=True)

    def test_start(self):
        u = User.objects.get(username='test')
        j = Job.start('job name', timezone.timedelta(minutes=5), user=u)
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'job name')
        self.assertEqual(j.started_by, u)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)

    def test_start_without_duration(self):
        Job.objects.bulk_create([
            Job(
                name='a job name',
                status=Job.Status.SUCCESS,
                expected_termination=timezone.now() + timezone.timedelta(minutes=10),
                termination=timezone.now() + timezone.timedelta(minutes=5)
            ),
        ])
        j = Job.start('a job name')
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)
        self.assertGreater(j.expected_termination, timezone.now() + timezone.timedelta(minutes=5))

    def test_get_or_start(self):
        job = Job.objects.create(
            name='a job name',
            status=Job.Status.SUCCESS,
            expected_termination=timezone.now() + timezone.timedelta(minutes=10),
            termination=timezone.now() + timezone.timedelta(minutes=5)
        )
        j = Job.get_or_start('a job name', id=-1, duration=timezone.timedelta(minutes=5))
        self.assertIsNone(j)
        j = Job.get_or_start('a job name', id=job.id, duration=timezone.timedelta(minutes=5))
        self.assertEqual(j, job)
        j = Job.get_or_start('a job name', duration=timezone.timedelta(minutes=5))
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)

    def test_get_or_start_without_duration(self):
        job = Job.objects.create(
            name='a job name',
            status=Job.Status.SUCCESS,
            expected_termination=timezone.now() + timezone.timedelta(minutes=10),
            termination=timezone.now() + timezone.timedelta(minutes=5)
        )
        j = Job.get_or_start('a job name', id=-1)
        self.assertIsNone(j)
        j = Job.get_or_start('a job name', id=job.id)
        self.assertEqual(j, job)
        j = Job.get_or_start('a job name')
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)
        self.assertGreater(j.expected_termination, timezone.now() + timezone.timedelta(minutes=5))

    def test_method_count(self):
        self.assertEqual(count_methods(Job), 3)


class VariantTests(AbstractModelTests):
    def setUp(self):
        super().setUp()
        self.generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        self.v2_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [self.t1_id])
        self.v3_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [self.t1_id])
        self.v4_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [])

    def test_variant_fields(self):
        v = Variant.objects.get(id=self.v1_id)
        self.assertSetEqual(set(v.uses.values_list('id', flat=True)), {self.c8_id, self.c1_id})
        self.assertSetEqual(set(c.id for c in v.cards()), {self.c8_id, self.c1_id})
        self.assertSetEqual(set(v.requires.values_list('id', flat=True)), {self.t1_id})
        self.assertSetEqual(set(t.id for t in v.templates()), {self.t1_id})
        self.assertSetEqual(set(v.produces.values_list('id', flat=True)), {self.f4_id, self.f2_id})
        self.assertSetEqual(set(v.includes.values_list('id', flat=True)), {self.b4_id, self.b2_id})
        self.assertSetEqual(set(v.of.values_list('id', flat=True)), {self.b2_id})
        self.assertEqual(v.status, Variant.Status.NEW)
        self.assertIn('{U}{U}', v.mana_needed)
        self.assertIn('{R}{R}', v.mana_needed)
        self.assertIn('Some requisites.', v.other_prerequisites)
        self.assertIn('2', v.description)
        self.assertIn('4', v.description)
        self.assertEqual(v.identity, 'W')
        self.assertEqual(v.generated_by.id, Job.objects.get(name='generate_variants').id)
        self.assertEqual(v.legal_commander, True)
        self.assertEqual(v.spoiler, False)
        self.assertEqual(v.description_line_count, v.description.count('\n') + 1)
        self.assertEqual(v.other_prerequisites_line_count, v.other_prerequisites.count('\n') + 1)
        self.assertEqual(v.mana_value_needed, 4)
        self.assertEqual(v.popularity, None)
        self.assertIn(v.id, v.spellbook_link())

    def test_ingredients(self):
        for v in Variant.objects.all():
            civ = sorted(v.cardinvariant_set.all(), key=lambda x: x.order)
            self.assertEqual(v.cards(), list(map(lambda x: x.card, civ)))
            tiv = sorted(v.templateinvariant_set.all(), key=lambda x: x.order)
            self.assertEqual(v.templates(), list(map(lambda x: x.template, tiv)))

    def test_query_string(self):
        v = Variant.objects.get(id=self.v1_id)
        for card in v.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', v.query_string())
        self.assertIn('+or+', v.query_string())
        self.assertTrue(v.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Variant), 7)

    def test_update(self):
        v = Variant.objects.get(id=self.v1_id)
        self.assertFalse(v.update(v.uses.all(), False))
        # TODO: test update

    def test_serialization(self):
        v = Variant.objects.get(id=self.v1_id)
        v.update_serialized(serializer=VariantSerializer)
        self.assertIsNotNone(v.serialized)
        self.assertIn('id', v.serialized)  # type: ignore
        self.assertFalse(Variant.serialized_objects.filter(id=self.v1_id).exists())
        v.save()
        self.assertTrue(Variant.serialized_objects.filter(id=self.v1_id).exists())
        v = Variant.serialized_objects.get(id=self.v1_id)
        self.assertIsNotNone(v.serialized)
        self.assertIn('id', v.serialized)  # type: ignore
        r = PreSerializedSerializer(v).data
        self.assertEqual(r, v.serialized)


class VariantSuggestionTests(AbstractModelTests):
    def test_variant_suggestion_fields(self):
        s = VariantSuggestion.objects.get(id=self.s1_id)
        card_names = {Card.objects.get(id=self.c1_id).name, Card.objects.get(id=self.c2_id).name}
        template_names = {Template.objects.get(id=self.t1_id).name}
        feature_names = {Feature.objects.get(id=self.f1_id).name}
        self.assertSetEqual(set(s.uses.values_list('card', flat=True)), card_names)
        self.assertSetEqual(set(s.requires.values_list('template', flat=True)), template_names)
        self.assertSetEqual(set(s.produces.values_list('feature', flat=True)), feature_names)
        self.assertEqual(s.status, VariantSuggestion.Status.NEW)
        self.assertEqual('{W}{W}', s.mana_needed)
        self.assertEqual('Some requisites.', s.other_prerequisites)
        self.assertEqual('1', s.description)
        self.assertEqual(s.suggested_by, None)
        self.assertTrue(s.spoiler)

    def test_ingredients(self):
        for s in VariantSuggestion.objects.all():
            civ = sorted(s.uses.all(), key=lambda x: x.order)
            self.assertEqual(s.cards(), civ)
            tiv = sorted(s.requires.all(), key=lambda x: x.order)
            self.assertEqual(s.templates(), tiv)
            self.assertEqual(s.features_produced(), list(s.produces.all()))
            self.assertEqual(s.features_needed(), [])

    def test_method_count(self):
        self.assertEqual(count_methods(VariantSuggestion), 4)

    def test_validate_against_redundancy(self):
        s1 = VariantSuggestion.objects.get(id=self.s1_id)
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            list(s1.uses.values_list('card', flat=True)),
            list(s1.requires.values_list('template', flat=True)),
            ['result']))

    def test_validate_against_already_present(self):
        super().generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            list(v1.uses.values_list('name', flat=True)),
            list(v1.requires.values_list('name', flat=True)),
            ['result']))

    def test_validate_against_empty_results(self):
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            ['a'],
            ['b'],
            []))

    def test_validate_against_empty_cards(self):
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            [],
            ['b'],
            ['result']))

    def test_validate_success(self):
        super().generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        VariantSuggestion.validate(
            list(v1.uses.values_list('name', flat=True)[:1]),
            list(v1.requires.values_list('name', flat=True)),
            ['result'])

    def test_card_in_variant_suggestion_validation(self):
        s = VariantSuggestion.objects.get(id=self.s1_id)
        c = CardUsedInVariantSuggestion(card='A card', variant=s, order=1, zone_locations=IngredientInCombination.ZoneLocation.COMMAND_ZONE)
        self.assertRaises(ValidationError, lambda: c.full_clean())


class VariantAliasTests(AbstractModelTests):
    def test_variant_alias_fields(self):
        a = VariantAlias.objects.get(id=self.a1_id)
        self.assertEqual(a.id, '1')
        self.assertEqual(a.description, 'a1')
        self.assertEqual(a.variant, None)

    def test_method_count(self):
        self.assertEqual(count_methods(VariantAlias), 1)


class KeywordsFieldTests(TestCase):
    def test_new_card_with_empty_keywords(self):
        c = Card(name='A', oracle_id='00000000-0000-0000-0000-000000000001')
        c.save()

    def test_new_card_with_some_keywords(self):
        c = Card(name='A', oracle_id='00000000-0000-0000-0000-000000000001', keywords=['A', 'B'])
        c.save()

    def test_new_card_with_wrong_keywords(self):
        c = Card(name='A', oracle_id='00000000-0000-0000-0000-000000000001', keywords=[{}, 1])
        c.save()
        self.assertRaises(ValidationError, lambda: c.full_clean())
