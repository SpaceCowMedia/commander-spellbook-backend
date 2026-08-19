from datetime import timedelta
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django_tasks.backends.database.models import DBTaskResult


def rendered_for_localization(value) -> str:
    return f'data-iso="{value.isoformat()}"'


def task_result(**kwargs) -> DBTaskResult:
    return DBTaskResult.objects.create(
        args_kwargs={'args': [], 'kwargs': {}},
        task_path='spellbook.tasks.export_variants.export_variants_task',
        backend_name='default',
        run_after=timezone.now(),
        **kwargs,
    )


class LocalDatetimeAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(username='admin', password='admin', email='admin@example.com')
        cls.task_result = task_result(started_at=timezone.now(), finished_at=timezone.now())
        cls.log_entry = LogEntry.objects.create(user=cls.admin, object_repr='Generated Variants', action_flag=ADDITION)

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def assertRendersForLocalization(self, url: str, *values):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('class="local-datetime"', content)
        for value in values:
            self.assertIn(rendered_for_localization(value), content)

    def test_task_result_datetimes_are_rendered_for_localization(self):
        self.task_result.refresh_from_db()
        datetimes = (self.task_result.enqueued_at, self.task_result.started_at, self.task_result.finished_at)
        for url in (
            reverse('admin:django_tasks_database_dbtaskresult_changelist'),
            reverse('admin:django_tasks_database_dbtaskresult_change', args=[self.task_result.pk]),
        ):
            with self.subTest(url=url):
                self.assertRendersForLocalization(url, *datetimes)

    def test_log_entry_action_time_is_rendered_for_localization(self):
        self.log_entry.refresh_from_db()
        for url in (
            reverse('admin:admin_logentry_changelist'),
            reverse('admin:admin_logentry_change', args=[self.log_entry.pk]),
        ):
            with self.subTest(url=url):
                self.assertRendersForLocalization(url, self.log_entry.action_time)

    def test_task_result_changelist_sorts_by_the_localized_column(self):
        older = task_result()
        DBTaskResult.objects.filter(pk=older.pk).update(enqueued_at=timezone.now() - timedelta(days=1))
        url = reverse('admin:django_tasks_database_dbtaskresult_changelist')
        # the index the o parameter counts in, which includes the action checkbox when the admin has actions
        column = self.client.get(url).context['cl'].list_display.index('enqueued_at_local')
        for ordering, expected in ((column, 'enqueued_at'), (-column, '-enqueued_at')):
            with self.subTest(ordering=ordering):
                response = self.client.get(url, query_params={'o': str(ordering)})  # type: ignore
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    [result.pk for result in response.context['cl'].result_list],
                    list(DBTaskResult.objects.order_by(expected).values_list('pk', flat=True)),
                )
