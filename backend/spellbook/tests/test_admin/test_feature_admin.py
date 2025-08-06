from django.test import TestCase
from ..testing import TestCaseMixinWithSeeding
from spellbook.admin.feature_admin import replace_feature_reference


class FeatureAdminTests(TestCaseMixinWithSeeding, TestCase):
    def test_replace_feature_reference(self):
        for test_text, verified_text, old_name, new_name in [
            ('[[Feature1]]', '[[Feature2]]', 'Feature1', 'Feature2'),
            ('[[fEature1]]', '[[Feature2]]', 'Feature1', 'Feature2'),
            ('[[Feature1|alias]]', '[[Feature2|alias]]', 'Feature1', 'Feature2'),
            ('[[Feature1|alias]] and [[Feature1]]', '[[Feature2|alias]] and [[Feature2]]', 'Feature1', 'Feature2'),
            ('[[Feature1|alias]] and [[Feature2|alias]]', '[[Feature2|alias]] and [[Feature2|alias]]', 'Feature1', 'Feature2'),
            ('[[feature1]] and [[feature2]]', '[[feature2]] and [[feature2]]', 'feature1', 'feature2'),
            ('[[Feature1|alias]] asd [[alias]]', '[[Feature2|alias]] asd [[alias]]', 'Feature1', 'Feature2'),
            ('[[Feature1 [x]|alias]] [[Feature1 [x]|another alias]]', '[[Feature2|alias]] [[Feature2|another alias]]', 'Feature1 [x]', 'Feature2'),
            ('[[ASD$4|CHECK]] [ASD] [[XASD]] [[X ASD]]', '[[DEF$4|CHECK]] [ASD] [[XASD]] [[X ASD]]', 'ASD', 'DEF'),
            ('[[A|B$2|C]]', '[[A|B$2|C]]', 'A', 'A'),
            ('[[A|B$2|C]] [[A|B|C]]', '[[Z|B$2|C]] [[A|B|C]]', 'A', 'Z'),
        ]:
            with self.subTest(test_text=test_text, old_name=old_name, new_name=new_name):
                result = replace_feature_reference(old_name, new_name, test_text)
                self.assertEqual(result, verified_text)
