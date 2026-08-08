import json
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.transformers.query_parsing import MAX_QUERY_LENGTH, MAX_QUERY_PARAMETERS
from spellbook.transformers.variants_query_explanation_transformer import variants_query_explainer
from ..testing import SpellbookTestCase


class QueryExplanationTests(SpellbookTestCase):
    def assertExplanation(self, query: str, expected: str):
        with self.subTest(query):
            self.assertEqual(variants_query_explainer(query), expected)

    def assertInvalid(self, query: str, expected_message: str):
        with self.subTest(query):
            with self.assertRaises(ValidationError) as context:
                variants_query_explainer(query)
            self.assertEqual(context.exception.messages, [expected_message])

    def test_empty_query(self):
        for query in ['', '   ']:
            self.assertExplanation(query, 'All combos.')

    def test_card_terms(self):
        self.assertExplanation('Basalt', 'Combos that use a card with “Basalt” in the name.')
        self.assertExplanation('"Basalt Monolith"', 'Combos that use a card with “Basalt Monolith” in the name.')
        self.assertExplanation('card:Basalt', 'Combos that use a card with “Basalt” in the name.')
        self.assertExplanation('card="Basalt Monolith"', 'Combos that use a card named exactly “Basalt Monolith”.')
        self.assertExplanation('@card:Monolith', 'Combos that use only cards with “Monolith” in the name.')
        self.assertExplanation('cards>2', 'Combos that use more than 2 cards.')
        self.assertExplanation('cards=1', 'Combos that use exactly 1 card.')
        self.assertExplanation('cards<=4', 'Combos that use at most 4 cards.')

    def test_template_terms(self):
        self.assertExplanation('template:"Draw outlet"', 'Combos that use a card template with “Draw outlet” in the name.')
        self.assertExplanation('@template:"Draw outlet"', 'Combos that use only templates with “Draw outlet” in the name.')
        self.assertExplanation('templates>=2', 'Combos that use at least 2 templates.')

    def test_card_attribute_terms(self):
        self.assertExplanation('type:artifact', 'Combos that use a card with “artifact” in the type line.')
        self.assertExplanation('@type:creature', 'Combos that use only cards with “creature” in the type line.')
        self.assertExplanation('oracle:"draw a card"', 'Combos that use a card with “draw a card” in the oracle text.')
        self.assertExplanation('oracle:"{T}: Add"', 'Combos that use a card with “{T}: Add” in the oracle text.')
        self.assertExplanation('keyword:flying', 'Combos that use a card with the “flying” keyword.')
        self.assertExplanation('mv<=2', 'Combos that use a card with mana value 2 or less.')
        self.assertExplanation('cardcolor:wu', 'Combos that use a card whose colors are exactly white and blue.')
        self.assertExplanation('cardcolor:c', 'Combos that use a colorless card.')
        self.assertExplanation('@cardcolor:c', 'Combos that use only colorless cards.')
        self.assertExplanation('cardcolor>=r', 'Combos that use a card whose colors include red.')
        self.assertExplanation('cardcolor=2', 'Combos that use a card with exactly 2 colors.')

    def test_identity_terms(self):
        self.assertExplanation('ci:temur', 'Combos that have a color identity within green, blue, and red.')
        self.assertExplanation('ci=wu', 'Combos that have a color identity of exactly white and blue.')
        self.assertExplanation('ci>=b', 'Combos that have a color identity that includes black.')
        self.assertExplanation('ci:c', 'Combos that have a colorless color identity.')
        self.assertExplanation('ci>2', 'Combos that have more than 2 colors in their color identity.')

    def test_recipe_terms(self):
        self.assertExplanation('prerequisites:"on the battlefield"', 'Combos that have a prerequisite containing “on the battlefield”.')
        self.assertExplanation('prereq<3', 'Combos that have fewer than 3 prerequisites.')
        self.assertExplanation('steps:"tap"', 'Combos that have a description containing “tap”.')
        self.assertExplanation('steps>4', 'Combos that have more than 4 steps.')
        self.assertExplanation('results:"infinite mana"', 'Combos that produce a result with “infinite mana” in the name.')
        self.assertExplanation('@results:infinite', 'Combos that produce only results with “infinite” in the name.')
        self.assertExplanation('results=2', 'Combos that produce exactly 2 results.')

    def test_variant_terms(self):
        self.assertExplanation('sid:abc-123', 'Combos that have the id or alias “abc-123”.')
        self.assertExplanation('commander:Kenrith', 'Combos that require a commander whose name contains “Kenrith”.')
        self.assertExplanation('legal:modern', 'Combos that are legal in Modern.')
        self.assertExplanation('banned:vintage', 'Combos that are banned in Vintage.')
        self.assertExplanation('price<=10', 'Combos that cost $10 or less on Card Kingdom.')
        self.assertExplanation('eur>5', 'Combos that cost more than €5 on Cardmarket.')
        self.assertExplanation('tcgplayer:20', 'Combos that cost exactly $20 on TCGPlayer.')
        self.assertExplanation('popularity>1000', 'Combos that are in more than 1000 decks.')
        self.assertExplanation('variants<=2', 'Combos that have at most 2 variants.')
        self.assertExplanation('bracket<=3', 'Combos that are in bracket 3 or lower.')
        self.assertExplanation('bracket:spicy', 'Combos that are tagged as “Spicy”.')

    def test_tag_terms(self):
        self.assertExplanation('is:infinite', 'Combos that produce an infinite loop.')
        self.assertExplanation('is:lock', 'Combos that produce a lock.')
        self.assertExplanation('is:commander', 'Combos that require a specific commander.')
        self.assertExplanation('is:reserved', 'Combos that use a card on the Reserved List.')
        self.assertExplanation('is:example', 'Combos that are an example combo.')
        self.assertExplanation('is:featured-1', 'Combos that are featured in home page tab 1.')

    def test_negation(self):
        self.assertExplanation('-card:Basalt', 'Combos that do not use a card with “Basalt” in the name.')
        self.assertExplanation('-is:example', 'Combos that are not an example combo.')
        self.assertExplanation('-price>10', 'Combos that do not cost more than $10 on Card Kingdom.')

    def test_shared_verbs_are_said_once(self):
        self.assertExplanation(
            'card:a card:b',
            'Combos that use a card with “a” in the name and a card with “b” in the name.',
        )
        self.assertExplanation(
            'card:a OR card:b OR card:c',
            'Combos that use a card with “a” in the name, a card with “b” in the name, or a card with “c” in the name.',
        )
        self.assertExplanation(
            '-card:a -card:b',
            'Combos that use neither a card with “a” in the name nor a card with “b” in the name.',
        )
        self.assertExplanation(
            '-card:a OR -card:b',
            'Combos that do not use a card with “a” in the name or do not use a card with “b” in the name.',
        )
        self.assertExplanation(
            'card:a results:b',
            'Combos that use a card with “a” in the name and produce a result with “b” in the name.',
        )

    def test_terms_for_every_related_row_stand_alone(self):
        self.assertExplanation(
            '@card:a cards>=3',
            'Combos that use only cards with “a” in the name and use at least 3 cards.',
        )

    def test_groups(self):
        self.assertExplanation(
            'card:a (results:x OR results:y)',
            'Combos that use a card with “a” in the name, and produce either a result with “x” in the name or a result with “y” in the name.',
        )
        self.assertExplanation(
            'card:a (results:x OR is:lock)',
            'Combos that use a card with “a” in the name, and produce either a result with “x” in the name or a lock.',
        )
        self.assertExplanation(
            'card:a (results:x OR ci:w)',
            'Combos that use a card with “a” in the name, and either produce a result with “x” in the name or have a color identity within white.',
        )
        self.assertExplanation(
            '(card:a card:b) OR ci=wu',
            'Combos that use both a card with “a” in the name and a card with “b” in the name, or have a color identity of exactly white and blue.',
        )
        self.assertExplanation(
            'card:d OR (card:a card:b card:c)',
            'Combos that use a card with “d” in the name, or use all of a card with “a” in the name, a card with “b” in the name, and a card with “c” in the name.',
        )
        self.assertExplanation(
            'card:d OR (card:a results:b ci:w)',
            'Combos that use a card with “d” in the name, or (use a card with “a” in the name, produce a result with “b” in the name, and have a color identity within white).',
        )

    def test_negated_groups(self):
        self.assertExplanation(
            '-(card:a OR card:b)',
            'Combos that use neither a card with “a” in the name nor a card with “b” in the name.',
        )
        self.assertExplanation(
            '-(card:a card:b)',
            'Combos that do not use a card with “a” in the name or do not use a card with “b” in the name.',
        )

    def test_invalid_queries(self):
        self.assertInvalid('card:a OR', 'Invalid search query: something is missing after character 8.')
        self.assertInvalid(')', 'Invalid search query: something is wrong at character 2.')
        self.assertInvalid('foo:bar', 'Invalid search query: unexpected character : at position 4.')
        self.assertInvalid('is:nope', 'Value "nope" is not supported for tag search.')
        self.assertInvalid('legal:frog', 'Format frog is not supported for legality search.')
        self.assertInvalid('ci:xyz', 'Invalid color identity: xyz')
        self.assertInvalid('bracket:9', 'Value 9 is not supported for bracket search. Choose a value between 1 and 5.')
        self.assertInvalid('@cards>2', 'Prefix @ is not supported for card search with numbers.')
        self.assertInvalid('a' * (MAX_QUERY_LENGTH + 1), 'Search query is too long.')
        self.assertInvalid('card:a ' * (MAX_QUERY_PARAMETERS + 1), 'Too many search parameters.')


class QueryExplanationViewTests(SpellbookTestCase):
    def test_explain_query_view(self):
        response = self.client.get(reverse('explain-query'), {'q': 'ci:temur is:infinite'}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.q, 'ci:temur is:infinite')
        self.assertEqual(result.explanation, 'Combos that have a color identity within green, blue, and red and produce an infinite loop.')

    def test_explain_query_view_without_query(self):
        response = self.client.get(reverse('explain-query'), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.q, '')
        self.assertEqual(result.explanation, 'All combos.')

    def test_explain_query_view_with_invalid_query(self):
        response = self.client.get(reverse('explain-query'), {'q': 'card:a OR'}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.q, ['Invalid search query: something is missing after character 8.'])
