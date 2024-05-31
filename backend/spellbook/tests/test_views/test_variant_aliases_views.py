import json
from spellbook.models import VariantAlias
from ..abstract_test import AbstractTestCaseWithSeeding
from common.inspection import json_to_python_lambda


class VariantAliasesTests(AbstractTestCaseWithSeeding):
    def variant_alias_assertions(self, alias_result):
        a = VariantAlias.objects.get(id=alias_result.id)
        self.assertEqual(a.id, alias_result.id)
        self.assertEqual(a.variant, alias_result.variant)

    def test_variant_aliases_list_view(self):
        response = self.client.get('/variant-aliases/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        alias_count = VariantAlias.objects.count()
        self.assertEqual(len(result.results), alias_count)
        for alias_result in result.results:
            self.variant_alias_assertions(alias_result)

    def test_variant_alias_detail_view(self):
        response = self.client.get(f'/variant-aliases/{self.a1_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        alias_result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.variant_alias_assertions(alias_result)
