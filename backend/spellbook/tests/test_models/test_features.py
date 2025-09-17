from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import Feature


class FeatureTests(TestCaseMixinWithSeeding, TestCase):
    def test_feature_fields(self):
        f = Feature.objects.get(id=self.f1_id)
        self.assertEqual(f.name, 'FA')
        self.assertEqual(f.description, 'Feature A')
        self.assertEqual(f.cards.count(), 2)  # type: ignore
        self.assertEqual(f.cards.distinct().count(), 1)  # type: ignore
        self.assertEqual(f.status, Feature.Status.HIDDEN_UTILITY)
        self.assertFalse(f.uncountable)
        f = Feature.objects.get(id=self.f2_id)
        self.assertEqual(f.status, Feature.Status.CONTEXTUAL)
        f = Feature.objects.get(id=self.f5_id)
        self.assertTrue(f.uncountable)

    def test_method_count(self):
        self.assertEqual(count_methods(Feature), 1)
