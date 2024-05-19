import json
import logging
from spellbook.models import VariantSuggestion
from spellbook.models.utils import apply_recursively_to_strings, strip_accents
from ..abstract_test import AbstractTestCaseWithSeeding
from common.inspection import json_to_python_lambda
from django.contrib.auth.models import User, Permission


class VariantSuggestionsTests(AbstractTestCaseWithSeeding):
    def suggestion_assertions(self, suggestion_result):
        vs = VariantSuggestion.objects.get(id=suggestion_result.id)
        self.assertEqual(suggestion_result.id, vs.id)
        self.assertEqual(suggestion_result.status, vs.status)
        self.assertEqual(suggestion_result.comment, vs.comment)
        for i, uses in enumerate(vs.uses.all()):
            self.assertEqual(uses.card, suggestion_result.uses[i].card)
            self.assertEqual(set(uses.zone_locations), set(suggestion_result.uses[i].zone_locations))
            self.assertEqual(uses.battlefield_card_state, suggestion_result.uses[i].battlefield_card_state)
            self.assertEqual(uses.exile_card_state, suggestion_result.uses[i].exile_card_state)
            self.assertEqual(uses.library_card_state, suggestion_result.uses[i].library_card_state)
            self.assertEqual(uses.graveyard_card_state, suggestion_result.uses[i].graveyard_card_state)
            self.assertEqual(uses.must_be_commander, suggestion_result.uses[i].must_be_commander)
            self.assertEqual(uses.card_unaccented, strip_accents(uses.card))
        for i, requires in enumerate(vs.requires.all()):
            self.assertEqual(requires.template, suggestion_result.requires[i].template)
            self.assertEqual(set(requires.zone_locations), set(suggestion_result.requires[i].zone_locations))
            self.assertEqual(requires.battlefield_card_state, suggestion_result.requires[i].battlefield_card_state)
            self.assertEqual(requires.exile_card_state, suggestion_result.requires[i].exile_card_state)
            self.assertEqual(requires.library_card_state, suggestion_result.requires[i].library_card_state)
            self.assertEqual(requires.graveyard_card_state, suggestion_result.requires[i].graveyard_card_state)
            self.assertEqual(requires.must_be_commander, suggestion_result.requires[i].must_be_commander)
        for i, produces in enumerate(vs.produces.all()):
            self.assertEqual(produces.feature, suggestion_result.produces[i].feature)
        self.assertEqual(suggestion_result.mana_needed, vs.mana_needed)
        self.assertEqual(suggestion_result.other_prerequisites, vs.other_prerequisites)
        self.assertEqual(suggestion_result.description, vs.description)
        self.assertEqual(suggestion_result.spoiler, vs.spoiler)
        if suggestion_result.suggested_by is not None:
            self.assertEqual(suggestion_result.suggested_by.id, vs.suggested_by.id)  # type: ignore
            self.assertEqual(suggestion_result.suggested_by.username, vs.suggested_by.username)  # type: ignore

    def test_suggestions_list_view(self):
        response = self.client.get('/variant-suggestions/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        suggestions_count = VariantSuggestion.objects.count()
        self.assertEqual(len(result.results), suggestions_count)
        for suggestion_result in result.results:
            self.suggestion_assertions(suggestion_result)

    def test_suggestion_detail_view(self):
        response = self.client.get(f'/variant-suggestions/{self.s1_id}', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.s1_id)
        self.suggestion_assertions(result)

    def test_new_suggestion(self):
        post_data = {
            "uses": [
                {
                    "card": "A card àèéìòù",
                    "zoneLocations": list("HBGEL"),
                    "battlefieldCardState": "bstate",
                    "exileCardState": "estate",
                    "libraryCardState": "lstate",
                    "graveyardCardState": "gstate",
                    "mustBeCommander": False
                },
                {
                    "card": "Another card",
                    "zoneLocations": list("HC"),
                    "battlefieldCardState": "",
                    "exileCardState": "",
                    "libraryCardState": "",
                    "graveyardCardState": "",
                    "mustBeCommander": True
                },
            ],
            "requires": [
                {
                    "template": "A template i.e. a card type",
                    "zoneLocations": list("H"),
                    "battlefieldCardState": "",
                    "exileCardState": "",
                    "libraryCardState": "",
                    "graveyardCardState": "",
                    "mustBeCommander": False
                },
                {
                    "template": "Another template",
                    "scryfall_query": "pow=2",
                    "zoneLocations": list("GL"),
                    "battlefieldCardState": "",
                    "exileCardState": "",
                    "libraryCardState": "in library",
                    "graveyardCardState": "",
                    "mustBeCommander": False
                }
            ],
            "produces": [
                {
                    "feature": "First produced feature"
                },
                {
                    "feature": "Second produced feature"
                }
            ],
            "manaNeeded": "{1}{W}{U}{B}{R}{G}",
            "otherPrerequisites": "other prereqs",
            "description": "a description",
            "spoiler": False,
            "comment": "a comment",
        }
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, 401)
        self.user = User.objects.create_user(username='testuser', password='12345')
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, 403)
        permissions = Permission.objects.filter(codename__in=['view_variantsuggestion', 'add_variantsuggestion', 'change_variantsuggestion'])
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        self.assertEqual(result.status, 'N')
        self.assertTrue(VariantSuggestion.objects.filter(id=result.id).exists())
        self.suggestion_assertions(result)

    def test_new_suggestion_with_wrong_fields(self):
        post_data = {
            "uses": [
                {
                    "card": "A card",
                    "zoneLocations": list("H"),
                    "battlefieldCardState": "asd",
                    "exileCardState": "",
                    "libraryCardState": "",
                    "graveyardCardState": "",
                    "mustBeCommander": False
                },
                {
                    "card": "Another card",
                    "zoneLocations": list("C"),
                    "battlefieldCardState": "",
                    "exileCardState": "",
                    "libraryCardState": "",
                    "graveyardCardState": "",
                    "mustBeCommander": False
                },
            ],
            "requires": [],
            "produces": [
                {
                    "feature": "first produced feature"
                },
            ],
            "manaNeeded": "",
            "otherPrerequisites": "",
            "description": "1"
        }
        self.user = User.objects.create_user(username='testuser', password='12345')
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(codename__in=['view_variantsuggestion', 'add_variantsuggestion', 'change_variantsuggestion'])
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'uses'))
        self.assertGreaterEqual(len(result.uses), 2)

    def test_new_suggestion_sanitization(self):
        post_data = {
            "uses": [
                {
                    "card": "A card with some apostrophes: `'ʼ and quotes: \"“ˮ and àccènts",
                    "zoneLocations": list("HBGEL"),
                    "battlefieldCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "exileCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "libraryCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "graveyardCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "mustBeCommander": False
                },
                {
                    "card": "Another card with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "zoneLocations": list("HBGELC"),
                    "battlefieldCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "exileCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "libraryCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "graveyardCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "mustBeCommander": True
                },
            ],
            "requires": [
                {
                    "template": "A template with some apostrophes: `'ʼ and quotes: \"“ˮ ok",
                    "zoneLocations": list("HBELG"),
                    "battlefieldCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "exileCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "libraryCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "graveyardCardState": "state with some apostrophes: `'ʼ and quotes: \"“ˮ",
                    "mustBeCommander": False
                },
                {
                    "template": "Another template with some apostrophes: `'ʼ and quotes: \"“ˮ ok",
                    "scryfall_query": "pow=2",
                    "zoneLocations": list("GL"),
                    "battlefieldCardState": "",
                    "exileCardState": "",
                    "libraryCardState": "in library",
                    "graveyardCardState": "",
                    "mustBeCommander": False
                }
            ],
            "produces": [
                {
                    "feature": "First produced feature with some apostrophes: `'ʼ and quotes: \"“ˮ ok"
                },
                {
                    "feature": "Second produced feature with some apostrophes: `'ʼ and quotes: \"“ˮ ok"
                }
            ],
            "comment": "A comment with some apostrophes: `'ʼ and quotes: \"“ˮ and newlines \r\n and \n and \r",
            "manaNeeded": "{1}{W}{U}{B}{R}{G} correct mana {U/P} wrong mana {BP} with some apostrophes: `'ʼ and quotes: \"“ˮ",
            "otherPrerequisites": "Other prereqs with some apostrophes: `'ʼ and quotes: \"“ˮ",
            "description": "A description with some apostrophes: `'ʼ and quotes: \"“ˮ and CRLF \r\n and LF \n and CR \r"
        }
        self.user = User.objects.create_user(username='testuser', password='12345')
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(codename__in=['view_variantsuggestion', 'add_variantsuggestion', 'change_variantsuggestion'])
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        self.assertEqual(result.status, 'N')
        self.assertTrue(VariantSuggestion.objects.filter(id=result.id).exists())
        self.suggestion_assertions(result)

        def assertStringSanity(s: str):
            self.assertNotIn('ʹ', s)
            self.assertNotIn('ʻ', s)
            self.assertNotIn('ʼ', s)
            self.assertNotIn('\r', s)
            for color in 'WUBRG':
                self.assertNotIn(f'{{{color}P}}', s)
            return s
        apply_recursively_to_strings(json.loads(response.content), assertStringSanity)

    def setUp(self) -> None:
        """Reduce the log level to avoid errors like 'not found'"""
        super().setUp()
        logger = logging.getLogger("django.request")
        self.previous_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)

    def tearDown(self) -> None:
        """Reset the log level back to normal"""
        super().tearDown()
        logger = logging.getLogger("django.request")
        logger.setLevel(self.previous_level)
