from datetime import datetime
from .abstract_test import AbstractModelTests
from spellbook.models import Job
from spellbook.utils import launch_job_command

class CleanJobsTest(AbstractModelTests):
    def clean_jobs_job(self):
        j = Job(
            name='test',
            expected_termination=datetime.fromtimestamp(1681126064),
            status=Job.Status.PENDING)
        j.save()
        j2 = Job(
            name='test2',
            expected_termination=datetime.fromtimestamp(1681126064),
            termination=datetime.fromtimestamp(1681126065),
            status=Job.Status.SUCCESS)
        j2.save()
        result = launch_job_command('clean_jobs', None)
        self.assertTrue(result)
        self.assertEqual(Job.objects.count(), 2)
        cleaned = Job.objects.get(name='test')
        self.assertEqual(cleaned.status, Job.Status.FAILURE)
        self.assertIsNotNone(cleaned.termination)
        self.assertEqual(Job.objects.get(name='test2').status, Job.Status.SUCCESS)

    def test_export_variants(self):
        pass  # TODO: Implement

    def test_generate_variants(self):
        pass  # TODO: Implement
