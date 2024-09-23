from urllib.parse import quote_plus
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.models import User
from common.inspection import count_methods
from .testing import TestCaseMixinWithSeeding
from spellbook.models import merge_identities, Card, Feature, Template, Combo, Job, Variant, VariantSuggestion, CardUsedInVariantSuggestion, VariantAlias, PreSerializedSerializer, ZoneLocation
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH
from spellbook.models import id_from_cards_and_templates_ids, CardType
from spellbook.models.utils import auto_fix_missing_braces_to_oracle_symbols, upper_oracle_symbols, sanitize_mana, sanitize_scryfall_query
from django.core.exceptions import ValidationError
from spellbook.serializers import VariantSerializer


class TestAddCurlyBracketsToOracleSymbols(TestCase):
    def test_empty_string(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(''), '')

    def test_no_oracle_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'? *'), r'? *')

    def test_one_oracle_symbol(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'W'), r'{W}')
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'w'), r'{w}')

    def test_one_oracle_symbol_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{W}'), r'{W}')
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{w}'), r'{w}')

    def test_multiple_oracle_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'WUBRG'), r'{W}{U}{B}{R}{G}')
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'wubrg'), r'{w}{u}{b}{r}{g}')

    def test_multiple_oracle_symbols_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{W}{U}{B}{R}{G}'), r'{W}{U}{B}{R}{G}')

    def test_hybrid_manas(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'2/W'), r'{2/W}')

    def test_hybrid_manas_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{2/W}'), r'{2/W}')

    def test_hybrid_mana_with_multiple_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'2/W/PU12BR/PG'), r'{2/W/P}{U}{12}{B}{R/P}{G}')

    def test_hybrid_mana_with_multiple_symbols_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'11}2/W/PU{12}{B}{1}2R/P{G}'), r'11}2/W/PU{12}{B}{1}2R/P{G}')

    def test_with_following_text(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'WUBRG mana'), r'WUBRG mana')


class TestUpperOracleSymbols(TestCase):
    def test_empty_string(self):
        self.assertEqual(upper_oracle_symbols(''), '')

    def test_no_oracle_symbols(self):
        self.assertEqual(upper_oracle_symbols(r'aaa eee oo u ? *'), r'aaa eee oo u ? *')

    def test_one_oracle_symbol(self):
        self.assertEqual(upper_oracle_symbols(r'{w}'), r'{W}')

    def test_multiple_oracle_symbols(self):
        self.assertEqual(upper_oracle_symbols(r'{w}{u}{b}{r}{g}'), r'{W}{U}{B}{R}{G}')

    def test_mixed_case_oracle_symbols(self):
        self.assertEqual(upper_oracle_symbols(r'{W}{u}{b}{R}{g}'), r'{W}{U}{B}{R}{G}')

    def test_hybrid_mana(self):
        self.assertEqual(upper_oracle_symbols(r'{2/w}'), r'{2/W}')

    def test_free_text(self):
        self.assertEqual(upper_oracle_symbols(r'ahm {w} yes u {2/w} r bg {2} {b/p} b/p'), r'ahm {W} yes u {2/W} r bg {2} {B/P} b/p')


class TestSanitizeMana(TestCase):
    def test_empty_string(self):
        self.assertEqual(sanitize_mana(''), '')

    def test_no_mana(self):
        self.assertEqual(sanitize_mana('aaa eee oo ? *'), 'aaa eee oo ? *')

    def test_one_mana(self):
        self.assertEqual(sanitize_mana('{w}'), '{W}')
        self.assertEqual(sanitize_mana('w'), '{W}')
        self.assertEqual(sanitize_mana('c'), '{C}')

    def test_multiple_mana(self):
        self.assertEqual(sanitize_mana('{w}{u}{b}{r}{g}{b/p}'), '{W}{U}{B}{R}{G}{B/P}')
        self.assertEqual(sanitize_mana('wubrgb/p'), '{W}{U}{B}{R}{G}{B/P}')

    def test_add_braces(self):
        self.assertEqual(sanitize_mana('W'), '{W}')
        self.assertEqual(sanitize_mana('WU'), '{W}{U}')
        self.assertEqual(sanitize_mana('w'), '{W}')
        self.assertEqual(sanitize_mana('wu'), '{W}{U}')

    def test_fix_phyrexian(self):
        self.assertEqual(sanitize_mana('WP'), '{W}{P}')
        self.assertEqual(sanitize_mana('W/P'), '{W/P}')
        self.assertEqual(sanitize_mana('{WP}'), '{W/P}')
        self.assertEqual(sanitize_mana('{wp}'), '{W/P}')


class TestSanitizeScryfallQuery(TestCase):
    def test_empty_string(self):
        self.assertEqual(sanitize_scryfall_query(''), '')

    def test_no_parameters(self):
        self.assertEqual(sanitize_scryfall_query('aaa eee oo ? *'), 'aaa eee oo ? *')

    def test_mana_parameters(self):
        self.assertEqual(sanitize_scryfall_query('mana={w}'), 'mana={W}')
        self.assertEqual(sanitize_scryfall_query('tou:5   mana={w}   pow:2'), 'tou:5   mana={W}   pow:2')
        self.assertEqual(sanitize_scryfall_query('mana=w'), 'mana={W}')
        self.assertEqual(sanitize_scryfall_query('mana=c'), 'mana={C}')
        self.assertEqual(sanitize_scryfall_query('mana={w}{u}{b}{r}{g}{b/p}'), 'mana={W}{U}{B}{R}{G}{B/P}')
        self.assertEqual(sanitize_scryfall_query('mana=wubrgb/p'), 'mana={W}{U}{B}{R}{G}{B/P}')
        self.assertEqual(sanitize_scryfall_query('mana=WU'), 'mana={W}{U}')
        self.assertEqual(sanitize_scryfall_query('mana=wu'), 'mana={W}{U}')
        self.assertEqual(sanitize_scryfall_query('mana={WP}'), 'mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana={wp}'), 'mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana=WP'), 'mana={W}{P}')
        self.assertEqual(sanitize_scryfall_query('mana=W/P'), 'mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('a mana={WP}'), 'a mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b'), 'mana={W/P} b')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP}'), 'mana={W/P} b mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP} c'), 'mana={W/P} b mana={W/P} c')
        self.assertEqual(sanitize_scryfall_query('-mana:{w} -mana:{u} -mana:{b} -mana:{r} -mana:{g} -mana:{b/p}'), '-mana:{W} -mana:{U} -mana:{B} -mana:{R} -mana:{G} -mana:{B/P}')

    def test_removal_of_format(self):
        self.assertEqual(sanitize_scryfall_query('format:standard'), '')
        self.assertEqual(sanitize_scryfall_query('format:modern'), '')
        self.assertEqual(sanitize_scryfall_query('tou>5 format:edh format:commander'), 'tou>5')
        self.assertEqual(sanitize_scryfall_query('legal:standard f:modern'), '')
        self.assertEqual(sanitize_scryfall_query('-legal:edh tou=3 format:commander'), 'tou=3')
        self.assertEqual(sanitize_scryfall_query('pow:2   format:standard      tou:5'), 'pow:2      tou:5')
        self.assertEqual(sanitize_scryfall_query('f:brawl   format:standard      tou:5'), 'tou:5')
        self.assertEqual(sanitize_scryfall_query('pow:2   format:standard      f:edh'), 'pow:2')
        self.assertEqual(sanitize_scryfall_query('format:vintage   format:standard      legal:brawl'), '')

    def test_combined_transform(self):
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP} c format:modern'), 'mana={W/P} b mana={W/P} c')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP} c format:modern f:edh'), 'mana={W/P} b mana={W/P} c')


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


class CardTests(TestCaseMixinWithSeeding, TestCase):
    def test_card_fields(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(c.name, 'A A')
        self.assertEqual(str(c.oracle_id), '00000000-0000-0000-0000-000000000001')
        self.assertEqual(c.features.count(), 1)
        self.assertEqual(c.identity, 'W')
        self.assertTrue(c.legal_commander)
        self.assertFalse(c.spoiler)
        self.assertEqual(c.oracle_text, 'x1')
        self.assertEqual(c.keywords, ['keyword1', 'keyword2'])
        self.assertEqual(c.mana_value, 0)
        self.assertFalse(c.reserved)
        self.assertEqual(c.latest_printing_set, '')
        self.assertFalse(c.reprinted)

    def test_query_string(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(f'q=%21%22{quote_plus(c.name)}%22', c.query_string())

    def test_scryfall_link(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, c.scryfall_link())  # type: ignore
        self.assertIn(c.query_string(), c.scryfall_link())  # type: ignore
        self.assertIn('<a', c.scryfall_link())  # type: ignore
        self.assertTrue(c.scryfall_link().startswith('<a'))  # type: ignore
        self.assertTrue(c.scryfall_link(raw=True).startswith('http'))  # type: ignore
        self.assertIn(c.scryfall_link(raw=True), c.scryfall_link(raw=False))  # type: ignore

    def test_is_legendary(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertFalse(c.is_of_type(CardType.LEGENDARY))
        c.type_line = 'Legendary Creature - Human'
        c.save()
        self.assertTrue(c.is_of_type(CardType.LEGENDARY))
        c.type_line = 'Legendary Sorcery'
        self.assertTrue(c.is_of_type(CardType.LEGENDARY))
        c.type_line = 'Creature - Human'
        self.assertFalse(c.is_of_type(CardType.LEGENDARY))

    def test_is_creature(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertFalse(c.is_of_type(CardType.CREATURE))
        c.type_line = 'Creature - Human'
        c.save()
        self.assertTrue(c.is_of_type(CardType.CREATURE))
        c.type_line = 'Legendary Creature - Human'
        self.assertTrue(c.is_of_type(CardType.CREATURE))
        c.type_line = 'Legendary Sorcery'
        self.assertFalse(c.is_of_type(CardType.CREATURE))

    def test_is_instant(self):
        c = Card.objects.get(id=self.c2_id)
        self.assertFalse(c.is_of_type(CardType.INSTANT))
        c.type_line = 'Legendary Instant'
        c.save()
        self.assertTrue(c.is_of_type(CardType.INSTANT))
        c.type_line = 'Instant'
        self.assertTrue(c.is_of_type(CardType.INSTANT))
        c.type_line = 'Sorcery'
        self.assertFalse(c.is_of_type(CardType.INSTANT))

    def test_is_sorcery(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertFalse(c.is_of_type(CardType.SORCERY))
        c.type_line = 'Legendary Sorcery'
        c.save()
        self.assertTrue(c.is_of_type(CardType.SORCERY))
        c.type_line = 'Sorcery'
        self.assertTrue(c.is_of_type(CardType.SORCERY))
        c.type_line = 'Instant'
        self.assertFalse(c.is_of_type(CardType.SORCERY))

    def test_method_count(self):
        self.assertEqual(count_methods(Card), 8)

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


class FeatureTests(TestCaseMixinWithSeeding, TestCase):
    def test_feature_fields(self):
        f = Feature.objects.get(id=self.f1_id)
        self.assertEqual(f.name, 'FA')
        self.assertEqual(f.description, 'Feature A')
        self.assertEqual(f.cards.count(), 1)  # type: ignore
        self.assertTrue(f.utility)
        self.assertFalse(f.uncountable)
        f = Feature.objects.get(id=self.f2_id)
        self.assertFalse(f.utility)
        f = Feature.objects.get(id=self.f5_id)
        self.assertTrue(f.uncountable)

    def test_method_count(self):
        self.assertEqual(count_methods(Feature), 1)


class TemplateTests(TestCaseMixinWithSeeding, TestCase):
    def test_template_fields(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')
        self.assertEqual(t.description, 'hello.')

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
        self.assertTrue(t.scryfall_link(raw=True).startswith('http'))
        self.assertIn(t.scryfall_link(raw=True), t.scryfall_link(raw=False))

        t.scryfall_query = ''
        self.assertNotIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link())
        self.assertNotIn(t.query_string(), t.scryfall_link())
        self.assertNotIn('<a', t.scryfall_link())
        self.assertNotIn('target="_blank"', t.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Template), 4)


class ComboTests(TestCaseMixinWithSeeding, TestCase):
    def test_combo_fields(self):
        c = Combo.objects.get(id=self.b1_id)
        self.assertEqual(c.description, 'a1')
        self.assertEqual(c.notes, '***1')
        self.assertEqual(c.public_notes, 'aa1')
        self.assertEqual(c.uses.count(), 2)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 0)
        self.assertEqual(c.produces.count(), 2)
        self.assertEqual(c.removes.count(), 0)
        self.assertEqual(c.mana_needed, '{W}{W}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertEqual(c.status, Combo.Status.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 2)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000002').zone_locations, ZoneLocation.HAND)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000003').zone_locations, ZoneLocation.BATTLEFIELD)
        self.assertEqual(c.templateincombo_set.count(), 0)
        self.assertEqual(c.allow_many_cards, False)
        self.assertEqual(c.allow_multiple_copies, False)
        c = Combo.objects.get(id=self.b2_id)
        self.assertEqual(c.description, 'b2')
        self.assertEqual(c.notes, '***2')
        self.assertEqual(c.public_notes, 'bb2')
        self.assertEqual(c.uses.count(), 0)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 1)
        self.assertEqual(c.produces.count(), 1)
        self.assertEqual(c.removes.count(), 1)
        self.assertEqual(c.mana_needed, '{U}{U}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertEqual(c.status, Combo.Status.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 0)
        self.assertEqual(c.templateincombo_set.count(), 1)
        self.assertEqual(c.templateincombo_set.get(template__name='TA').zone_locations, ZoneLocation.GRAVEYARD)
        self.assertEqual(c.allow_many_cards, False)
        self.assertEqual(c.allow_multiple_copies, False)

    def test_ingredients(self):
        for c in Combo.objects.all():
            cic = sorted(c.cardincombo_set.all(), key=lambda x: x.order)
            self.assertDictEqual(c.cards(), {ci.card.name: ci.quantity for ci in cic})
            tic = sorted(c.templateincombo_set.all(), key=lambda x: x.order)
            self.assertDictEqual(c.templates(), {ti.template.name: ti.quantity for ti in tic})
            self.assertDictEqual(c.features_needed(), {f.feature.name: f.quantity for f in c.featureneededincombo_set.all()})
            self.assertDictEqual(c.features_produced(), {f.feature.name: 1 for f in c.featureproducedincombo_set.all()})

    def test_query_string(self):
        c = Combo.objects.get(id=self.b1_id)
        for card in c.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', c.query_string())
        self.assertIn('+or+', c.query_string())
        self.assertTrue(c.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 4)


class JobTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username='test', password='test', is_staff=True)

    def test_start(self):
        u = User.objects.get(username='test')
        j: Job = Job.start('job name', duration=timezone.timedelta(minutes=5), user=u)  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'job name')
        self.assertEqual(j.group, None)
        self.assertEqual(j.started_by, u)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertListEqual(j.args, [])
        self.assertIsNotNone(j.expected_termination)

    def test_start_without_duration(self):
        Job.objects.bulk_create([
            Job(
                name='a job name',
                args=['x'],
                group='abc',
                status=Job.Status.SUCCESS,
                expected_termination=timezone.now() + timezone.timedelta(minutes=10),
                termination=timezone.now() + timezone.timedelta(minutes=5)
            ),
        ] + [
            Job(
                name='a job name',
                args=['x'],
                group='another group',
                status=Job.Status.SUCCESS,
                expected_termination=timezone.now() + timezone.timedelta(minutes=1),
                termination=timezone.now() + timezone.timedelta(minutes=1)
            ) for _ in range(5)
        ])
        j: Job = Job.start('a job name', ['a'], group='abc')  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertEqual(j.group, 'abc')
        self.assertListEqual(j.args, ['a'])
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
        j: Job = Job.get_or_start(-1, 'a job name', duration=timezone.timedelta(minutes=5))  # type: ignore
        self.assertIsNone(j)
        j = Job.get_or_start(job.id, 'a job name', duration=timezone.timedelta(minutes=5))  # type: ignore
        self.assertEqual(j, job)
        j = Job.get_or_start(None, 'a job name', duration=timezone.timedelta(minutes=5))  # type: ignore
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
        j: Job = Job.get_or_start(-1, 'a job name')  # type: ignore
        self.assertIsNone(j)
        j = Job.get_or_start(job.id, 'a job name')  # type: ignore
        self.assertEqual(j, job)
        j = Job.get_or_start(None, 'a job name')  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)
        self.assertGreater(j.expected_termination, timezone.now() + timezone.timedelta(minutes=5))

    def test_method_count(self):
        self.assertEqual(count_methods(Job), 3)


class VariantTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self):
        super().setUp()
        self.generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        self.v2_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [self.t1_id])
        self.v3_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [self.t1_id])
        self.v4_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [])

    def test_variant_fields(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        self.assertSetEqual(set(v.uses.values_list('id', flat=True)), {self.c8_id, self.c1_id})
        self.assertDictEqual(v.cards(), {Card.objects.get(pk=self.c8_id).name: 1, Card.objects.get(pk=self.c1_id).name: 1})
        self.assertSetEqual(set(v.requires.values_list('id', flat=True)), {self.t1_id})
        self.assertDictEqual(v.templates(), {Template.objects.get(pk=self.t1_id).name: 1})
        self.assertSetEqual(set(v.produces.values_list('id', flat=True)), {self.f4_id, self.f2_id})
        self.assertSetEqual(set(v.includes.values_list('id', flat=True)), {self.b4_id, self.b2_id})
        self.assertSetEqual(set(v.of.values_list('id', flat=True)), {self.b2_id})
        self.assertEqual(v.status, Variant.Status.NEW)
        self.assertIn('{U}{U}', v.mana_needed)
        self.assertIn('{R}{R}', v.mana_needed)
        self.assertIn('Some requisites.', v.other_prerequisites)
        self.assertIn('2', v.description)
        self.assertIn('2', v.notes)
        self.assertIn('2', v.public_notes)
        self.assertIn('4', v.description)
        self.assertIn('4', v.notes)
        self.assertIn('4', v.public_notes)
        self.assertEqual(v.identity, 'W')
        self.assertEqual(v.generated_by.id, Job.objects.get(name='generate_variants').id)  # type: ignore
        self.assertEqual(v.legal_commander, True)
        self.assertEqual(v.spoiler, False)
        self.assertEqual(v.description_line_count, v.description.count('\n') + 1)
        self.assertEqual(v.other_prerequisites_line_count, v.other_prerequisites.count('\n') + 1)
        self.assertEqual(v.mana_value_needed, 4)
        self.assertEqual(v.popularity, None)
        self.assertIsNone(v.spellbook_link())

    def test_ingredients(self):
        for v in Variant.objects.all():
            civ = sorted(v.cardinvariant_set.all(), key=lambda x: x.order)
            self.assertDictEqual(v.cards(), {ci.card.name: ci.quantity for ci in civ})
            tiv = sorted(v.templateinvariant_set.all(), key=lambda x: x.order)
            self.assertDictEqual(v.templates(), {ti.template.name: ti.quantity for ti in tiv})

    def test_query_string(self):
        v = Variant.objects.get(id=self.v1_id)
        for card in v.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', v.query_string())
        self.assertIn('+or+', v.query_string())
        self.assertTrue(v.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Variant), 8)

    def test_update(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        cards = list(v.uses.all())
        self.assertFalse(v.update(cards, requires_commander=False))
        self.assertTrue(v.update(cards, requires_commander=True))
        non_commander_formats = (
            'vintage',
            'legacy',
            'modern',
            'pioneer',
            'standard',
            'pauper',
        )
        for f in non_commander_formats:
            self.assertFalse(getattr(v, f'legal_{f}'))
        self.assertTrue(v.legal_commander)
        self.assertTrue(v.update(cards, requires_commander=False))
        self.assertLess(len(v.identity), 5)
        c = Card(name='Extra card 1', oracle_id='00000000-0000-0000-0000-0000000000ff', identity='C')
        c.save()
        cards.append(c)
        self.assertFalse(v.update(cards, requires_commander=False))
        c.identity = 'WUBRG'
        c.save()
        self.assertTrue(v.update(cards, requires_commander=False))
        self.assertFalse(v.update(cards, requires_commander=False))
        c.spoiler = True
        c.save()
        self.assertTrue(v.update(cards, requires_commander=False))
        self.assertFalse(v.update(cards, requires_commander=False))
        c.legal_predh = False
        c.save()
        self.assertTrue(v.update(cards, requires_commander=False))
        self.assertFalse(v.update(cards, requires_commander=False))
        c.price_cardmarket = Decimal(100)
        c.save()
        self.assertTrue(v.update(cards, requires_commander=False))
        self.assertFalse(v.update(cards, requires_commander=False))

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


class VariantSuggestionTests(TestCaseMixinWithSeeding, TestCase):
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
            self.assertDictEqual(s.cards(), {ci.card: ci.quantity for ci in civ})
            tiv = sorted(s.requires.all(), key=lambda x: x.order)
            self.assertDictEqual(s.templates(), {ti.template: ti.quantity for ti in tiv})
            self.assertDictEqual(s.features_produced(), {f.feature: 1 for f in s.produces.all()})
            self.assertDictEqual(s.features_needed(), {})

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
        c = CardUsedInVariantSuggestion(card='A card', variant=s, order=1, zone_locations=ZoneLocation.COMMAND_ZONE)
        self.assertRaises(ValidationError, lambda: c.full_clean())


class VariantAliasTests(TestCaseMixinWithSeeding, TestCase):
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
