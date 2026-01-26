import json
import datetime
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.tasks import TaskResult, TaskResultStatus
from spellbook.models import Variant
from spellbook.tasks import combo_of_the_day_task, generate_variants_task, export_variants_task, DEFAULT_VARIANTS_FILE_NAME
from website.models import COMBO_OF_THE_DAY_PROPERTY, WebsiteProperty
from .testing import SpellbookTestCaseWithSeeding
from spellbook.models import id_from_cards_and_templates_ids


class TasksTest(SpellbookTestCaseWithSeeding):
    def test_generate_variants(self):
        u = User.objects.create(username='test', password='test')
        result: TaskResult = generate_variants_task.enqueue(started_by_user_id=u.pk)
        self.assertTrue(result.is_finished)
        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v2_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [self.t1_id])
        v3_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [self.t1_id])
        v4_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [])
        v5_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [])
        v6_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [])
        v7_id = id_from_cards_and_templates_ids([self.c1_id, self.c2_id, self.c3_id, self.c4_id, self.c5_id, self.c6_id], [])
        v8_id = id_from_cards_and_templates_ids([self.c1_id, self.c2_id], [self.t1_id, self.t2_id])
        self.assertEqual(Variant.objects.count(), self.expected_variant_count)
        for v in Variant.objects.all():
            self.assertEqual(v.status, Variant.Status.NEW)
        variant_ids = {v.id for v in Variant.objects.all()}
        self.assertSetEqual(variant_ids, {v1_id, v2_id, v3_id, v4_id, v5_id, v6_id, v7_id, v8_id})
        single_combo_generator = Variant.objects.get(id=v1_id).of.first()
        expected_variants_ids = set(single_combo_generator.variants.values_list('id', flat=True))
        Variant.objects.all().delete()
        result: TaskResult = generate_variants_task.enqueue(started_by_user_id=u.pk, combo=single_combo_generator.id)
        self.assertTrue(result.is_finished)
        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        self.assertSetEqual(set(Variant.objects.values_list('id', flat=True)), expected_variants_ids)

    def test_export_variants(self):
        super().generate_variants()
        with self.settings(VERSION='abc'):
            file_path = settings.STATIC_BULK_FOLDER / DEFAULT_VARIANTS_FILE_NAME
            result: TaskResult = export_variants_task.enqueue(file=True, s3=False)
            self.assertTrue(result.is_finished)
            self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
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
                    result: TaskResult = export_variants_task.enqueue(file=True, s3=False)
                    self.assertTrue(result.is_finished)
                    self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
                    with open(file_path) as f:
                        data = json.load(f)
                    self.assertEqual(len(data['variants']), Variant.objects.count())

    def test_notify(self):
        # The only meaningful test is to check that discord utils are available
        import text_utils
        text_utils.discord_chunk('test')

    def test_combo_of_the_day(self):
        super().generate_and_publish_variants()
        result: TaskResult = combo_of_the_day_task.enqueue()
        self.assertTrue(result.is_finished)
        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        check = WebsiteProperty.objects.get(key=COMBO_OF_THE_DAY_PROPERTY).value
        self.assertTrue(Variant.objects.filter(pk=check).exists())
