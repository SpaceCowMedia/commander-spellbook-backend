import json
from django.db import connection
from django.db.models.functions import Lower
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from spellbook.models import Card
from ..testing import SpellbookTestCaseWithSeeding, curated_card


class DeckNameCaseTests(SpellbookTestCaseWithSeeding):
    '''How a decklist naming a card in a different case is resolved.

    The database folds the case, not Python, so that only the names a list holds are ever read instead
    of the whole card table. PostgreSQL folds the whole alphabet; SQLite leaves an uppercase letter
    outside ASCII alone, so the handful of cards printed with one are the difference between the two.
    The tests below spell that out, so it stays a decision rather than a surprise.'''

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ascii_card = curated_card(name='Plain Ascii Card', type_line='Instant', identity='W')
        cls.ligature_card = curated_card(name='Æther Test Card', type_line='Instant', identity='U')
        cls.dashed_card = curated_card(name='Human—Test Lord', type_line='Instant', identity='B')

    def _classified(self, *names: str) -> set[str]:
        response = self.client.post(
            reverse('estimate-bracket'),
            json.dumps({'main': [{'card': name, 'quantity': 1} for name in names]}),
            follow=True,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {card['card']['name'] for card in json.loads(response.content)['cards']}

    def test_a_name_written_as_printed_always_resolves(self):
        self.assertEqual(self._classified('Plain Ascii Card'), {'Plain Ascii Card'})
        self.assertEqual(self._classified('Æther Test Card'), {'Æther Test Card'})

    def test_an_ascii_name_resolves_in_any_case_on_every_backend(self):
        self.assertEqual(self._classified('plain ascii card'), {'Plain Ascii Card'})
        self.assertEqual(self._classified('PLAIN ASCII CARD'), {'Plain Ascii Card'})

    def test_an_uppercase_letter_outside_ascii_resolves_on_every_backend(self):
        # not because the database folds it, but because the normalized name holds no such letter
        self.assertEqual(self._classified('æther test card'), {'Æther Test Card'})
        self.assertEqual(self._classified('HUMAN—TEST LORD'), {'Human—Test Lord'})

    def test_the_databases_fold_the_printed_name_differently(self):
        '''The difference the normalized name covers over, pinned where it actually is.

        Nothing reaches it through a deck list any more, since a normalized name is plain ASCII and
        every backend folds that alike. It is still what the printed name is matched by first.'''
        folded = Card.objects.annotate(k=Lower('name')).filter(pk=self.ligature_card.pk).values_list('k', flat=True).first()
        if connection.vendor == 'postgresql':
            self.assertEqual(folded, 'æther test card')
        else:
            self.assertEqual(folded, 'Æther test card')

    def test_a_name_that_names_nothing_resolves_to_nothing(self):
        self.assertEqual(self._classified('Notacard Xyzzy'), set())


class DeckReadsOnlyWhatItNamesTests(SpellbookTestCaseWithSeeding):
    def test_no_query_reads_the_card_table_unfiltered(self):
        '''The card table holds every card Scryfall knows, so a deck must never read all of it.'''
        Card.objects.bulk_create([Card(name=f'Filler Card {index}', type_line='Instant') for index in range(50)])
        body = json.dumps({'main': [{'card': 'A A', 'quantity': 1}, {'card': 'B B', 'quantity': 1}]})
        with CaptureQueriesContext(connection) as queries:
            response = self.client.post(reverse('estimate-bracket'), body, follow=True, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        unfiltered = [
            query['sql'] for query in queries.captured_queries
            if 'FROM "spellbook_card"' in query['sql'] and 'WHERE' not in query['sql']
        ]
        self.assertEqual(unfiltered, [])


class DeckLigatureTests(SpellbookTestCaseWithSeeding):
    '''A name written with the letters a keyboard carries finds the card printed with the ones it does not.'''

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ligature = curated_card(name='Æther Vial Test', type_line='Artifact', identity='C')
        cls.plain = curated_card(name='Aether Hub Test', type_line='Land', identity='C')

    def _classified(self, *names: str) -> set[str]:
        response = self.client.post(
            reverse('estimate-bracket'),
            json.dumps({'main': [{'card': name, 'quantity': 1} for name in names]}),
            follow=True,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {card['card']['name'] for card in json.loads(response.content)['cards']}

    def test_a_ligature_is_reachable_by_its_plain_spelling(self):
        self.assertEqual(self._classified('Aether Vial Test'), {'Æther Vial Test'})
        self.assertEqual(self._classified('aether vial test'), {'Æther Vial Test'})

    def test_a_plain_name_is_reachable_by_the_ligature(self):
        self.assertEqual(self._classified('Æther Hub Test'), {'Aether Hub Test'})

    def test_the_card_is_still_reachable_as_it_is_printed(self):
        self.assertEqual(self._classified('Æther Vial Test'), {'Æther Vial Test'})
        self.assertEqual(self._classified('Aether Hub Test'), {'Aether Hub Test'})

    def test_a_dash_a_keyboard_does_not_carry_is_typed_as_a_hyphen(self):
        card = curated_card(name='Human—Time Test', type_line='Creature', identity='R')
        self.assertEqual(card.name_unaccented, 'Human-Time Test')
        self.assertEqual(self._classified('Human-Time Test'), {'Human—Time Test'})

    def test_a_list_names_a_card_by_the_ids_the_api_publishes(self):
        '''A card can be named by either id the API gives it, and never by the key behind them.'''
        card = Card.objects.create(
            name='Published Card',
            number=900,
            oracle_id='00000000-0000-0000-0000-0000000000ee',
            type_line='Instant',
            identity='W',
        )
        self.assertNotEqual(card.pk, card.number)
        self.assertFalse(Card.objects.filter(number=card.pk).exists())
        self.assertEqual(self._classified(str(card.number)), {'Published Card'})
        self.assertEqual(self._classified(str(card.oracle_id)), {'Published Card'})
        self.assertEqual(self._classified(str(card.pk)), set())

    def test_a_list_names_a_card_nobody_curated_by_its_oracle_id(self):
        '''The oracle id is the only id such a card has, and the deck still has to hold it.'''
        uncurated = Card.objects.create(
            name='Uncurated Deck Card',
            oracle_id='00000000-0000-0000-0000-0000000000ef',
            type_line='Instant',
            identity='U',
        )
        self.assertIsNone(uncurated.number)
        self.assertEqual(self._classified(str(uncurated.oracle_id)), {'Uncurated Deck Card'})
