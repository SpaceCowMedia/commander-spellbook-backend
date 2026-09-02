from datetime import timedelta
from unittest.mock import patch
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import router, transaction
from django.urls import reverse
from django.utils import timezone
from spellbook.admin import variant_admin
from spellbook.models import Variant, variant_counts
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


class RecordingTransactions:
    '''Stands in for django.db.transaction, remembering the database every block is opened on.'''

    def __init__(self):
        self.opened: list[str | None] = []

    def atomic(self, using=None, *args, **kwargs):
        self.opened.append(using)
        return transaction.atomic(using, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(transaction, name)


class VariantStatusActionTests(SpellbookTestCaseWithSeeding):
    def setUp(self):
        super().setUp()
        self.generate_variants()
        self.bulk_serialize_variants()
        self.client.force_login(self.admin)

    def selection(self, count: int) -> list[str]:
        return list(Variant.objects.order_by('pk').values_list('pk', flat=True)[:count])

    def set_status(self, action: str, ids: list[str]):
        return self.client.post(
            reverse('admin:spellbook_variant_changelist'),
            data={'action': action, ACTION_CHECKBOX_NAME: ids},
            follow=True,
        )

    def test_the_action_marks_every_selected_variant(self):
        ids = self.selection(3)
        response = self.set_status('set_ok', ids)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(Variant.objects.filter(status=Variant.Status.OK).values_list('pk', flat=True)),
            set(ids),
        )
        self.assertTrue(all(Variant.objects.filter(pk__in=ids).values_list('published', flat=True)))

    def test_the_action_names_the_database_it_works_on(self):
        '''The admin answers its requests on a connection of its own, so a block opened on the default
        alias leaves the row lock, and the writes it guards, outside any transaction. PostgreSQL then
        gets asked for a lock through a connection still in autocommit, refuses it, and the whole
        action comes back as a 500 however few or many variants were selected.'''
        recorder = RecordingTransactions()
        with patch.object(variant_admin, 'transaction', recorder), patch.object(variant_counts, 'transaction', recorder):
            response = self.set_status('set_ok', self.selection(3))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(None, recorder.opened, 'Every transaction has to name its database, leaving the choice to the router instead of to the default alias.')
        self.assertEqual(set(recorder.opened), {router.db_for_write(Variant)})
