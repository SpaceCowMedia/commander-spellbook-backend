'''A newer backend can send fields an older client does not know about: the client must ignore them.'''
import json
import re
from contextlib import asynccontextmanager
from django.test import SimpleTestCase
import spellbook_client
from spellbook_client import ApiClient, ApiException, Configuration, FindMyCombosApi
from spellbook_client.extensions import find_my_combos_create_plain
from .fake_backend import FakeBackend
from .samples import object_schema_names, openapi_schema, sample, variant_sample, paginated_sample


def api_class_name(operation: dict) -> str:
    tags = operation.get('tags')
    if not tags:
        return 'DefaultApi'
    return ''.join(word.capitalize() for word in re.split(r'[^a-zA-Z0-9]', tags[0])) + 'Api'


def snake_case(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def request_body_argument(request_body: dict) -> tuple[str, object]:
    schema = next(iter(request_body['content'].values()))['schema']
    if '$ref' not in schema:
        return 'body', sample(schema)
    schema_name = schema['$ref'].split('/')[-1]
    return snake_case(schema_name), getattr(spellbook_client, schema_name).from_dict(sample(schema_name))


@asynccontextmanager
async def fake_backend_client():
    async with FakeBackend() as backend, ApiClient(Configuration(host=backend.url)) as api_client:
        yield backend, api_client


class TestModelsIgnoreUnexpectedFields(SimpleTestCase):
    def test_every_model(self):
        for name in object_schema_names():
            with self.subTest(model=name):
                model = getattr(spellbook_client, name)
                self.assertEqual(
                    model.from_json(json.dumps(sample(name))),
                    model.from_json(json.dumps(sample(name, unexpected_fields=True))),
                )


class TestOperationsIgnoreUnexpectedFields(SimpleTestCase):
    async def fetch(self, call, status: int):
        if 200 <= status < 300:
            return await call()
        with self.assertRaises(ApiException) as context:
            await call()
        self.assertEqual(context.exception.status, status)
        return context.exception.data

    async def test_every_documented_response(self):
        async with fake_backend_client() as (backend, api_client):
            for path, path_item in openapi_schema()['paths'].items():
                for method, operation in path_item.items():
                    parameters = {
                        parameter['name']: sample(parameter['schema'])
                        for parameter in operation.get('parameters', [])
                        if parameter['in'] == 'path'
                    }
                    arguments = dict(parameters)
                    if 'requestBody' in operation:
                        name, value = request_body_argument(operation['requestBody'])
                        arguments[name] = value
                    api = getattr(spellbook_client, api_class_name(operation))(api_client)
                    call = getattr(api, operation['operationId'])
                    for status, response in operation['responses'].items():
                        if 'application/json' not in response.get('content', {}):
                            continue
                        response_schema = response['content']['application/json']['schema']
                        with self.subTest(operation=operation['operationId'], status=status):
                            backend.respond(method, path.format(**parameters), sample(response_schema), int(status))
                            expected = await self.fetch(lambda: call(**arguments), int(status))
                            self.assertIsNotNone(expected)
                            backend.respond(method, path.format(**parameters), sample(response_schema, unexpected_fields=True), int(status))
                            actual = await self.fetch(lambda: call(**arguments), int(status))
                            self.assertEqual(expected, actual)

    async def test_find_my_combos_with_plain_text_decklist(self):
        response = sample('PaginatedFindMyCombosResponseList', unexpected_fields=True)
        response['results']['included'] = [variant_sample(id='1-2', cards=['A', 'B'])]
        async with fake_backend_client() as (backend, api_client):
            backend.respond('POST', '/find-my-combos', response)
            result = await find_my_combos_create_plain(FindMyCombosApi(api_client), '1 A\n1 B')
        self.assertEqual(['1-2'], [variant.id for variant in result.results.included])
        self.assertEqual('1 A\n1 B', backend.requests[-1].body)

    async def test_paginated_variants(self):
        async with fake_backend_client() as (backend, api_client):
            backend.respond('GET', '/variants/', paginated_sample([variant_sample(id='1-2'), variant_sample(id='3-4')], count=10))
            result = await spellbook_client.VariantsApi(api_client).variants_list(q='A', count=True)
        self.assertEqual(10, result.count)
        self.assertEqual(['1-2', '3-4'], [variant.id for variant in result.results])
        self.assertNotIn('unexpectedString', result.to_dict())
        self.assertNotIn('unexpectedString', result.results[0].to_dict())
