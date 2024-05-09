import json
from time import sleep
from pathlib import Path
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from spellbook.models import Job, Variant
from spellbook.utils import launch_job_command
from .abstract_test import AbstractTestCaseWithSeeding
from spellbook.models import id_from_cards_and_templates_ids


class CleanJobsTest(AbstractTestCaseWithSeeding):
    def test_clean_jobs(self):
        j = Job(
            name='test',
            expected_termination=timezone.now() + timedelta(seconds=5),
            status=Job.Status.PENDING)
        j.save()
        j2 = Job(
            name='test2',
            expected_termination=timezone.now() + timedelta(minutes=1),
            termination=timezone.now() + timedelta(minutes=1),
            status=Job.Status.SUCCESS)
        j2.save()
        j2 = Job(
            name='test3',
            expected_termination=timezone.now() + timedelta(days=1000),
            termination=timezone.now() + timedelta(minutes=1),
            status=Job.Status.PENDING)
        sleep(6)
        j2.save()
        result = launch_job_command('clean_jobs', None)
        self.assertTrue(result)
        self.assertEqual(Job.objects.count(), 4)
        cleaned = Job.objects.get(name='test')
        self.assertEqual(cleaned.status, Job.Status.FAILURE)
        self.assertIsNotNone(cleaned.termination)
        self.assertEqual(Job.objects.get(name='test2').status, Job.Status.SUCCESS)
        self.assertEqual(Job.objects.get(name='test3').status, Job.Status.PENDING)

    def test_generate_variants(self):
        u = User.objects.create(username='test', password='test')
        launch_job_command('generate_variants', u)
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        self.v2_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [self.t1_id])
        self.v3_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [self.t1_id])
        self.v4_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [])
        self.v5_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [])
        self.v6_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [])
        self.v7_id = id_from_cards_and_templates_ids([self.c1_id, self.c2_id, self.c3_id, self.c4_id, self.c5_id, self.c6_id], [])
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        for v in Variant.objects.all():
            self.assertEqual(v.status, Variant.Status.NEW)
        j = Job.objects.get(name='generate_variants')
        self.assertEqual(j.status, Job.Status.SUCCESS)
        self.assertEqual(j.started_by, u)
        variant_ids = {v.id for v in Variant.objects.all()}
        self.assertEqual(variant_ids, {self.v1_id, self.v2_id, self.v3_id, self.v4_id, self.v5_id, self.v6_id, self.v7_id})

    def test_export_variants(self):
        super().generate_variants()
        file_path = Path(settings.STATIC_BULK_FOLDER) / 'export_variants.json'
        launch_job_command('export_variants', None, ['--file', str(file_path)])
        self.assertTrue(file_path.exists())
        with open(file_path) as f:
            data = json.load(f)
        self.assertEqual(len(data['variants']), 0)
        for export_status in Variant.public_statuses():
            with self.subTest(export_status=export_status):
                Variant.objects.update(status=export_status)
                launch_job_command('export_variants', None, ['--file', str(file_path)])
                with open(file_path) as f:
                    data = json.load(f)
                self.assertEqual(len(data['variants']), 7)
