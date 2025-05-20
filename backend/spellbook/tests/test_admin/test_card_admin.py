from django.test import TestCase
from django.urls import reverse
from spellbook.models import Card
from ..testing import TestCaseMixinWithSeeding


class CardAdminTests(TestCaseMixinWithSeeding, TestCase):
    def test_changelist_view(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:spellbook_card_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'{Card.objects.get(id=self.c1_id).name}</a>', str(response.content))

    def test_changelist_view_with_facets(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:spellbook_card_changelist'), query_params={'_facets': 'True'})  # type: ignore
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'?_facets=True&amp;identity=C', response.content)
