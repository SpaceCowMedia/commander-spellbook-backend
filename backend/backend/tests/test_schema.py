from django.test import SimpleTestCase
from rest_framework import status
from django.conf import settings


class SchemaTestCase(SimpleTestCase):
    def test_yaml(self):
        response = self.client.get('/schema', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/vnd.oai.openapi; charset=utf-8')
        text = response.content.decode()
        self.assertIn('openapi: 3', text)

    def test_swagger(self):
        response = self.client.get('/schema/swagger', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'text/html; charset=utf-8')
        text = response.content.decode()
        self.assertIn(settings.SPECTACULAR_SETTINGS['TITLE'], text)

    def test_redoc(self):
        response = self.client.get('/schema/redoc', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'text/html; charset=utf-8')
        text = response.content.decode()
        self.assertIn(settings.SPECTACULAR_SETTINGS['TITLE'], text)
