import json
import logging
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import VariantUpdateSuggestion, Variant
from ..testing import TestCaseMixinWithSeeding


class VariantSuggestionsTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self) -> None:
        """Reduce the log level to avoid errors like 'not found'"""
        super().setUp()
        logger = logging.getLogger("django.request")
        self.previous_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR)
        # Setup
        super().generate_variants()
        Variant.objects.update(status=Variant.Status.OK)
        self.v1_id: int = Variant.objects.all()[0].id  # type: ignore
        self.v2_id: int = Variant.objects.all()[1].id  # type: ignore
        self.v3_id: int = Variant.objects.all()[2].id  # type: ignore
        self.update_variants()
        self.bulk_serialize_variants()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.us1 = VariantUpdateSuggestion.objects.create(
            status=VariantUpdateSuggestion.Status.NEW,
            comment='A comment',
            issue='An issue',
            solution='A solution',
            suggested_by=self.user,
        )
        self.us1.variants.create(
            variant_id=self.v1_id,
            issue='An issue',
        )
        self.post_data = {
            'comment': 'A comment',
            'issue': 'An issue',
            'solution': 'A solution',
            'variants': [
                {
                    'variant': self.v1_id,
                    'issue': 'An issue',
                },
                {
                    'variant': self.v2_id,
                    'issue': 'Another issue',
                }
            ],
        }

    def tearDown(self) -> None:
        """Reset the log level back to normal"""
        super().tearDown()
        logger = logging.getLogger("django.request")
        logger.setLevel(self.previous_level)

    def suggestion_assertions(self, suggestion_result):
        vs = VariantUpdateSuggestion.objects.get(id=suggestion_result.id)
        self.assertEqual(suggestion_result.id, vs.id)
        self.assertEqual(suggestion_result.status, vs.status)
        self.assertEqual(suggestion_result.comment, vs.comment)
        for i, variant in enumerate(vs.variants.all()):
            self.assertEqual(variant.variant_id, suggestion_result.variants[i].variant)
            self.assertEqual(variant.issue, suggestion_result.variants[i].issue)
        self.assertEqual(suggestion_result.issue, vs.issue)
        self.assertEqual(suggestion_result.solution, vs.solution)
        if suggestion_result.suggested_by is not None:
            self.assertEqual(suggestion_result.suggested_by.id, vs.suggested_by.id)  # type: ignore
            self.assertEqual(suggestion_result.suggested_by.username, vs.suggested_by.username)  # type: ignore

    def test_suggestions_list_view(self):
        response = self.client.get('/variant-update-suggestions/', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        suggestion_count = VariantUpdateSuggestion.objects.count()
        self.assertEqual(len(result.results), suggestion_count)
        for suggestion_result in result.results:
            self.suggestion_assertions(suggestion_result)

    def test_suggestion_detail_view(self):
        response = self.client.get(f'/variant-update-suggestions/{self.us1.id}', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.us1.id)
        self.suggestion_assertions(result)

    def test_new_suggestion(self):
        response = self.client.post(
            '/variant-update-suggestions/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        response = self.client.post(
            '/variant-update-suggestions/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        self.assertEqual(result.status, 'N')
        self.assertTrue(VariantUpdateSuggestion.objects.filter(id=result.id).exists())
        self.suggestion_assertions(result)

    def test_duplicate_variant_reference(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        put_data = self.post_data.copy()
        put_data['variants'].append({
            'variant': self.v2_id,
        })
        response = self.client.put(
            f'/variant-update-suggestions/{result.id}/',
            put_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_suggestion(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        put_data = self.post_data.copy()
        put_data['comment'] = 'new comment'
        put_data['variants'][0]['issue'] = ''
        put_data['variants'].append({
            'variant': self.v3_id,
            'issue': '',
        })
        response = self.client.put(
            f'/variant-update-suggestions/{result.id}/',
            put_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        self.assertEqual(result.status, 'N')
        self.suggestion_assertions(result)

    def test_delete_suggestion(self):
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        response = self.client.delete(
            f'/variant-update-suggestions/{result.id}/',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(VariantUpdateSuggestion.objects.filter(id=result.id).exists())

    def test_new_suggestion_with_wrong_fields(self):
        post_data = {
            'variants': [
                {
                    'variant': '',
                    'issue': 'An issue',
                },
                {
                    'variant': '1233213123241325332452354',
                    'issue': 'Another issue',
                },
            ],
        }
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'variants'))
        self.assertGreaterEqual(len(result.variants), 2)

    def test_validate_view(self):
        post_data = {
            'variants': [
                {
                    'variant': '',
                    'issue': 'An issue',
                },
                {
                    'variant': '1233213123241325332452354',
                    'issue': 'Another issue',
                },
            ],
        }
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/validate/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'variants'))
        self.assertGreaterEqual(len(result.variants), 2)
        suggestion_count_before = VariantUpdateSuggestion.objects.count()
        response = self.client.post(
            '/variant-update-suggestions/validate/',
            self.post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertTrue(hasattr(result, 'variants'))
        self.assertGreaterEqual(len(result.variants), 2)
        suggestion_count_after = VariantUpdateSuggestion.objects.count()
        self.assertEqual(suggestion_count_before, suggestion_count_after)

    def test_new_suggestion_sanitization(self):
        post_data = {
            "variants": [
                {
                    "variant": self.v1_id,
                    "issue": "An issue with some apostrophes: `'ʼ and quotes: \"“ˮ and newlines \r\n and \n and \r",
                },
            ],
            "comment": "A comment with some apostrophes: `'ʼ and quotes: \"“ˮ and newlines \r\n and \n and \r",
            "issue": "An issue with some apostrophes: `'ʼ and quotes: \"“ˮ and newlines \r\n and \n and \r",
            "solution": "A solution with some apostrophes: `'ʼ and quotes: \"“ˮ and newlines \r\n and \n and \r",
        }
        login = self.client.login(username='testuser', password='12345')
        self.assertTrue(login)
        permissions = Permission.objects.filter(content_type=ContentType.objects.get_for_model(VariantUpdateSuggestion))
        self.user.user_permissions.add(*permissions)
        response = self.client.post(
            '/variant-update-suggestions/',
            post_data,
            content_type='application/json',
            follow=True)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertGreater(result.id, 0)
        self.assertEqual(result.status, 'N')
        self.assertTrue(VariantUpdateSuggestion.objects.filter(id=result.id).exists())
        self.suggestion_assertions(result)

        def assertStringSanity(s: str):
            self.assertNotIn('ʹ', s)
            self.assertNotIn('ʻ', s)
            self.assertNotIn('ʼ', s)
            self.assertNotIn('\r', s)
            for color in 'WUBRG':
                self.assertNotIn(f'{{{color}P}}', s)
        for v in result.variants:
            assertStringSanity(v.issue)
        assertStringSanity(result.comment)
        assertStringSanity(result.issue)
        assertStringSanity(result.solution)
