from django.urls import reverse
from spellbook.models import Variant
from ..testing import SpellbookTestCaseWithSeeding


class VariantAdminTests(SpellbookTestCaseWithSeeding):
    def test_changelist_view(self):
        self.generate_variants()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:spellbook_variant_changelist'))
        self.assertEqual(response.status_code, 200)
        content = str(response.content)
        self.assertIn('Generate variants', content)
        self.assertIn('name="full"', content)

    def test_generate_enqueues_incremental_generation_by_default(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:spellbook_variant_generate'))
        self.assertEqual(response.status_code, 302)
        # The test task backend runs the task immediately: without stored
        # fingerprints the incremental run falls back to a full generation
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)

    def test_generate_enqueues_full_generation_with_flag(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:spellbook_variant_generate'), data={'full': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
