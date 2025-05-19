import json
import logging
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import VariantSuggestion
from spellbook.models.utils import strip_accents
from ..testing import TestCaseMixinWithSeeding


POST_DATA = {
    "uses": [
        {
            "card": "A card àèéìòù",
            "quantity": 2,
            "zoneLocations": list("HBGEL"),
            "battlefieldCardState": "bstate",
            "exileCardState": "estate",
            "libraryCardState": "lstate",
            "graveyardCardState": "gstate",
            "mustBeCommander": False
        },
        {
            "card": "Another card",
            "quantity": 1,
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
            "quantity": 1,
            "zoneLocations": list("H"),
            "battlefieldCardState": "",
            "exileCardState": "",
            "libraryCardState": "",
            "graveyardCardState": "",
            "mustBeCommander": False
        },
        {
            "template": "Another template",
            "quantity": 4,
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
    "easyPrerequisites": "easy prereqs",
    "notablePrerequisites": "notable prereqs",
    "description": "a description",
    "spoiler": False,
    "comment": "a comment",
}


class VariantSuggestionsTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self) -> None:
        """Reduce the log level to avoid errors like 'not found'"""
        super().setUp()
        logger = logging.getLogger("django.request")
        self.previous_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)
        self.user = User.objects.create_user(username='testuser', password='12345')

    def tearDown(self) -> None:
        """Reset the log level back to normal"""
        super().tearDown()
        logger = logging.getLogger("django.request")
        logger.setLevel(self.previous_level)

    def suggestion_assertions(self, suggestion_result):
        vs = VariantSuggestion.objects.get(id=suggestion_result.id)
        self.assertEqual(suggestion_result.id, vs.id)
        self.assertEqual(suggestion_result.status, vs.status)
        self.assertEqual(suggestion_result.comment, vs.comment)
        for i, uses in enumerate(vs.uses.all()):
            self.assertEqual(uses.card, suggestion_result.uses[i].card)
            self.assertEqual(uses.quantity, suggestion_result.uses[i].quantity)
            self.assertEqual(set(uses.zone_locations), set(suggestion_result.uses[i].zone_locations))
            self.assertEqual(uses.battlefield_card_state, suggestion_result.uses[i].battlefield_card_state)
            self.assertEqual(uses.exile_card_state, suggestion_result.uses[i].exile_card_state)
            self.assertEqual(uses.library_card_state, suggestion_result.uses[i].library_card_state)
            self.assertEqual(uses.graveyard_card_state, suggestion_result.uses[i].graveyard_card_state)
            self.assertEqual(uses.must_be_commander, suggestion_result.uses[i].must_be_commander)
            self.assertEqual(uses.card_unaccented, strip_accents(uses.card))
        for i, requires in enumerate(vs.requires.all()):
            self.assertEqual(requires.template, suggestion_result.requires[i].template)
            self.assertEqual(requires.quantity, suggestion_result.requires[i].quantity)
            self.assertEqual(set(requires.zone_locations), set(suggestion_result.requires[i].zone_locations))
            self.assertEqual(requires.battlefield_card_state, suggestion_result.requires[i].battlefield_card_state)
            self.assertEqual(requires.exile_card_state, suggestion_result.requires[i].exile_card_state)
            self.assertEqual(requires.library_card_state, suggestion_result.requires[i].library_card_state)
            self.assertEqual(requires.graveyard_card_state, suggestion_result.requires[i].graveyard_card_state)
            self.assertEqual(requires.must_be_commander, suggestion_result.requires[i].must_be_commander)
        for i, produces in enumerate(vs.produces.all()):
            self.assertEqual(produces.feature, suggestion_result.produces[i].feature)
        self.assertEqual(suggestion_result.mana_needed, vs.mana_needed)
        self.assertEqual(suggestion_result.easy_prerequisites, vs.easy_prerequisites)
        self.assertEqual(suggestion_result.notable_prerequisites, vs.notable_prerequisites)
        self.assertEqual(suggestion_result.description, vs.description)
        self.assertEqual(suggestion_result.spoiler, vs.spoiler)
        self.assertEqual(suggestion_result.notes, vs.notes)
        if suggestion_result.suggested_by is not None:
            self.assertEqual(suggestion_result.suggested_by.id, vs.suggested_by.id)  # type: ignore
            self.assertEqual(suggestion_result.suggested_by.username, vs.suggested_by.username)  # type: ignore

    def test_suggestions_list_view(self):
        response = self.client.get('/variant-suggestions/', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        suggestion_count = VariantSuggestion.objects.count()
        self.assertEqual(len(result.results), suggestion_count)
        for suggestion_result in result.results:
            self.suggestion_assertions(suggestion_result)

    def test_suggestion_detail_view(self):
        response = self.client.get(f'/variant-suggestions/{self.s1_id}', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.s1_id)
        self.suggestion_assertions(result)

    def test_new_suggestion(self):
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        self.assertEqual(result.status, 'N')
        self.assertTrue(VariantSuggestion.objects.filter(id=result.id).exists())
        self.suggestion_assertions(result)

    def test_duplicate_suggestion(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.get('Content-Type'), 'application/json')

    def test_duplicate_suggestion_on_update(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post_data_2 = POST_DATA.copy()
        post_data_2['uses'][0]['card'] = 'A different card'
        response_2 = self.client.post(
            '/variant-suggestions/',
            post_data_2,
            content_type='application/json',
            follow=True)
        self.assertEqual(response_2.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        response = self.client.put(
            f'/variant-suggestions/{result.id}/',
            post_data_2,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_suggestion(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        put_data = POST_DATA.copy()
        put_data['comment'] = 'new comment'
        put_data['requires'][0]['scryfall_query'] = None
        put_data['produces'].append({
            "feature": "Third produced feature",
        })
        response = self.client.put(
            f'/variant-suggestions/{result.id}/',
            put_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.comment, 'new comment')
        self.assertIsNone(result.requires[0].scryfall_query)

    def test_delete_suggestion(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        response = self.client.delete(
            f'/variant-suggestions/{result.id}/',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(VariantSuggestion.objects.filter(id=result.id).exists())

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
            "easyPrerequisites": "",
            "notablePrerequisites": "",
            "description": "1"
        }
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'uses'))
        self.assertGreaterEqual(len(result.uses), 2)

    def test_validate_view(self):
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
            "easyPrerequisites": "",
            "notablePrerequisites": "",
            "description": ""
        }
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/validate/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'uses'))
        self.assertGreaterEqual(len(result.uses), 2)
        suggestion_count_before = VariantSuggestion.objects.count()
        response = self.client.post(
            '/variant-suggestions/validate/',
            POST_DATA,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'uses'))
        self.assertGreaterEqual(len(result.uses), 2)
        suggestion_count_after = VariantSuggestion.objects.count()
        self.assertEqual(suggestion_count_before, suggestion_count_after)

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
                    "scryfall_query": None,
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
            "easyPrerequisites": "Easy prereqs with some apostrophes: `'ʼ and quotes: \"“ˮ",
            "notablePrerequisites": "Notable prereqs with some apostrophes: `'ʼ and quotes: \"“ˮ",
            "description": "A description with some apostrophes: `'ʼ and quotes: \"“ˮ and CRLF \r\n and LF \n and CR \r"
        }
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
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
        for c in result.uses:
            assertStringSanity(c.card)
            assertStringSanity(c.battlefield_card_state)
            assertStringSanity(c.exile_card_state)
            assertStringSanity(c.library_card_state)
            assertStringSanity(c.graveyard_card_state)
        for r in result.requires:
            assertStringSanity(r.template)
            assertStringSanity(r.battlefield_card_state)
            assertStringSanity(r.exile_card_state)
            assertStringSanity(r.library_card_state)
            assertStringSanity(r.graveyard_card_state)
        for p in result.produces:
            assertStringSanity(p.feature)
        assertStringSanity(result.comment)
        assertStringSanity(result.mana_needed)
        assertStringSanity(result.easy_prerequisites)
        assertStringSanity(result.notable_prerequisites)
        assertStringSanity(result.description)
