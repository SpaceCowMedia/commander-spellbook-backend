from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import Job
from django.contrib.auth.models import User
from django.utils import timezone


class JobTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username='test', password='test', is_staff=True)

    def test_start(self):
        u = User.objects.get(username='test')
        j: Job = Job.start('job name', duration=timezone.timedelta(minutes=5), user=u)  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'job name')
        self.assertEqual(j.group, None)
        self.assertEqual(j.started_by, u)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertListEqual(j.args, [])
        self.assertIsNotNone(j.expected_termination)

    def test_start_without_duration(self):
        Job.objects.bulk_create([
            Job(
                name='a job name',
                args=['x'],
                group='abc',
                status=Job.Status.SUCCESS,
                expected_termination=timezone.now() + timezone.timedelta(minutes=10),
                termination=timezone.now() + timezone.timedelta(minutes=5)
            ),
        ] + [
            Job(
                name='a job name',
                args=['x'],
                group='another group',
                status=Job.Status.SUCCESS,
                expected_termination=timezone.now() + timezone.timedelta(minutes=1),
                termination=timezone.now() + timezone.timedelta(minutes=1)
            ) for _ in range(5)
        ])
        j: Job = Job.start('a job name', ['a'], group='abc')  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertEqual(j.group, 'abc')
        self.assertListEqual(j.args, ['a'])
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)
        self.assertGreater(j.expected_termination, timezone.now() + timezone.timedelta(minutes=5))

    def test_get_or_start(self):
        job = Job.objects.create(
            name='a job name',
            status=Job.Status.SUCCESS,
            expected_termination=timezone.now() + timezone.timedelta(minutes=10),
            termination=timezone.now() + timezone.timedelta(minutes=5)
        )
        j: Job = Job.get_or_start(-1, 'a job name', duration=timezone.timedelta(minutes=5))  # type: ignore
        self.assertIsNone(j)
        j = Job.get_or_start(job.id, 'a job name', duration=timezone.timedelta(minutes=5))  # type: ignore
        self.assertEqual(j, job)
        j = Job.get_or_start(None, 'a job name', duration=timezone.timedelta(minutes=5))  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)

    def test_get_or_start_without_duration(self):
        job = Job.objects.create(
            name='a job name',
            status=Job.Status.SUCCESS,
            expected_termination=timezone.now() + timezone.timedelta(minutes=10),
            termination=timezone.now() + timezone.timedelta(minutes=5)
        )
        j: Job = Job.get_or_start(-1, 'a job name')  # type: ignore
        self.assertIsNone(j)
        j = Job.get_or_start(job.id, 'a job name')  # type: ignore
        self.assertEqual(j, job)
        j = Job.get_or_start(None, 'a job name')  # type: ignore
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)
        self.assertGreater(j.expected_termination, timezone.now() + timezone.timedelta(minutes=5))

    def test_method_count(self):
        self.assertEqual(count_methods(Job), 3)
