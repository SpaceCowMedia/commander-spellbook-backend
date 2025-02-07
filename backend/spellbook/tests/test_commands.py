import json
import datetime
from time import sleep
from pathlib import Path
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from spellbook.models import Job, Variant
from spellbook.utils import launch_job_command
from website.models import COMBO_OF_THE_DAY, WebsiteProperty
from .testing import TestCaseMixinWithSeeding
from spellbook.models import id_from_cards_and_templates_ids


class CleanJobsTest(TestCaseMixinWithSeeding, TestCase):
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
        self.assertSetEqual(variant_ids, {self.v1_id, self.v2_id, self.v3_id, self.v4_id, self.v5_id, self.v6_id, self.v7_id})
        single_combo_generator = Variant.objects.get(id=self.v1_id).of.first()
        expected_variants_ids = set(single_combo_generator.variants.values_list('id', flat=True))
        Variant.objects.all().delete()
        launch_job_command('generate_variants', u, ['--combo', single_combo_generator.id])
        self.assertSetEqual(set(Variant.objects.values_list('id', flat=True)), expected_variants_ids)

    def test_export_variants(self):
        super().generate_variants()
        with self.settings(VERSION='abc'):
            file_path = Path(settings.STATIC_BULK_FOLDER) / 'test_export_variants.json'
            launch_job_command('export_variants', None, ['--file', str(file_path)])
            self.assertTrue(file_path.exists())
            with open(file_path) as f:
                data = json.load(f)
            self.assertEqual(len(data['variants']), 0)
            self.assertEqual(len(data['aliases']), 1)
            self.assertEqual(data['version'], 'abc')
            self.assertLessEqual(datetime.datetime.fromisoformat(data['timestamp']), timezone.now())
            for export_status in Variant.public_statuses():
                with self.subTest(export_status=export_status):
                    Variant.objects.update(status=export_status)
                    launch_job_command('export_variants', None, ['--file', str(file_path)])
                    with open(file_path) as f:
                        data = json.load(f)
                    self.assertEqual(len(data['variants']), 7)

    def test_notify(self):
        # The only meaningful test is to check that discord utils are available
        import text_utils
        text_utils.discord_chunk('test')

    def test_combo_of_the_day(self):
        super().generate_and_publish_variants()
        launch_job_command('combo_of_the_day')
        result = WebsiteProperty.objects.get(key=COMBO_OF_THE_DAY).value
        self.assertTrue(Variant.objects.filter(pk=result).exists())
