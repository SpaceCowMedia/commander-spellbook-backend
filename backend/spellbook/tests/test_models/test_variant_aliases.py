from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import VariantAlias


class VariantAliasTests(TestCaseMixinWithSeeding, TestCase):
    def test_variant_alias_fields(self):
        a = VariantAlias.objects.get(id=self.a1_id)
        self.assertEqual(a.id, '1')
        self.assertEqual(a.description, 'a1')
        self.assertEqual(a.variant, None)

    def test_method_count(self):
        self.assertEqual(count_methods(VariantAlias), 1)
