import json
from pathlib import Path
from datetime import datetime
from django.conf import settings
from spellbook.models import Job, Variant
from spellbook.utils import launch_job_command
from .abstract_test import AbstractModelTests

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

    def test_generate_variants(self):
        pass  # TODO: Implement

    def test_export_variants(self):
        launch_job_command('generate_variants', None)
        file_path = Path(settings.STATIC_BULK_FOLDER) / 'export_variants.json'
        launch_job_command('export_variants', None, ['--file', file_path])
        self.assertTrue(file_path.exists())
        with open(file_path) as f:
            data = json.load(f)
        self.assertEqual(len(data['variants']), 0)
        Variant.objects.update(status=Variant.Status.OK)
        launch_job_command('export_variants', None, ['--file', file_path])
        with open(file_path) as f:
            data = json.load(f)
        self.assertEqual(len(data['variants']), 4)
