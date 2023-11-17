import json
import logging
from spellbook.models import VariantSuggestion
from ..abstract_test import AbstractModelTests
from common.inspection import json_to_python_lambda
from django.contrib.auth.models import User, Permission


class VariantSuggestionsTests(AbstractModelTests):
    def suggestion_assertions(self, suggestion_result):
        vs = VariantSuggestion.objects.get(id=suggestion_result.id)
        self.assertEqual(suggestion_result.id, vs.id)
        self.assertEqual(suggestion_result.status, vs.status)
        for i, uses in enumerate(vs.uses.all()):
            self.assertEqual(uses.card, suggestion_result.uses[i].card)
            self.assertEqual(set(uses.zone_locations), set(suggestion_result.uses[i].zone_locations))
            self.assertEqual(uses.battlefield_card_state, suggestion_result.uses[i].battlefield_card_state)
            self.assertEqual(uses.exile_card_state, suggestion_result.uses[i].exile_card_state)
            self.assertEqual(uses.library_card_state, suggestion_result.uses[i].library_card_state)
            self.assertEqual(uses.graveyard_card_state, suggestion_result.uses[i].graveyard_card_state)
            self.assertEqual(uses.must_be_commander, suggestion_result.uses[i].must_be_commander)
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
        if suggestion_result.suggested_by is not None:
            self.assertEqual(suggestion_result.suggested_by.id, vs.suggested_by.id)
            self.assertEqual(suggestion_result.suggested_by.username, vs.suggested_by.username)

    def test_suggestions_list_view(self):
        response = self.client.get('/variant-suggestions/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        suggestions_count = VariantSuggestion.objects.count()
        self.assertEqual(len(result.results), suggestions_count)
        for i in range(suggestions_count):
            self.suggestion_assertions(result.results[i])

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
                    "card": "A card",
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
                    "template": "A template",
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
            "description": "a description"
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
                    "card": "A card",
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
                    "template": "A template",
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
            "otherPrerequisites": "Other prereqs with some apostrophes: `'ʼ and quotes: \"“ˮ",
            "description": "A description with some apostrophes: `'ʼ and quotes: \"“ˮ"
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
