from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
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

    def test_change_view_renders_datetimes_for_localization(self):
        self.generate_variants()
        variant: Variant = Variant.objects.first()  # type: ignore
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:spellbook_variant_change', args=[variant.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for value in (variant.created, variant.updated):
            self.assertIn(f'data-iso="{value.isoformat()}"', content)

    def test_changelist_sorts_by_creation_date(self):
        self.generate_variants()
        now = timezone.now()
        # generation stamps every variant within the same instant: spreading the dates apart makes
        # the creation order differ from the primary key order the changelist falls back on
        for days, variant_id in enumerate(Variant.objects.order_by('pk').values_list('pk', flat=True)):
            Variant.objects.filter(pk=variant_id).update(created=now - timedelta(days=days))
        self.client.force_login(self.admin)
        url = reverse('admin:spellbook_variant_changelist')
        # the index the o parameter counts in, which includes the action checkbox when the admin has actions
        column = self.client.get(url).context['cl'].list_display.index('created_local')
        for ordering, expected in ((column, 'created'), (-column, '-created')):
            with self.subTest(ordering=ordering):
                response = self.client.get(url, query_params={'o': str(ordering)})  # type: ignore
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [variant.pk for variant in response.context['cl'].result_list],
                    list(Variant.objects.order_by(expected).values_list('pk', flat=True)),
                )

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
