// A newer backend can send fields an older client does not know about: the client must ignore them.
import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import * as client from '../dist/index.js';
import { objectSchemaNames, openapiSchema, sample } from './samples.js';

const BASE_PATH = 'http://backend.test';

function pascalCase(name) {
    return name.split(/[^a-zA-Z0-9]/).map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join('');
}

function camelCase(name) {
    const pascal = pascalCase(name);
    return pascal.charAt(0).toLowerCase() + pascal.slice(1);
}

function requestBodyArgument(requestBody) {
    const schema = Object.values(requestBody.content)[0].schema;
    if (!('$ref' in schema)) {
        return ['body', sample(schema)];
    }
    const schemaName = schema['$ref'].split('/').pop();
    return [camelCase(schemaName), client[`${schemaName}FromJSON`](sample(schemaName))];
}

// An API whose every request is answered with the given body and status, after checking its method and path.
function apiAnswering(apiClass, method, path, body, status) {
    return new apiClass(new client.Configuration({
        basePath: BASE_PATH,
        fetchApi: async (url, init) => {
            assert.equal(init.method, method.toUpperCase());
            assert.equal(new URL(url).pathname, path);
            return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
        },
    }));
}

describe('models ignore unexpected fields', () => {
    for (const name of objectSchemaNames()) {
        test(name, () => {
            const fromJSON = client[`${name}FromJSON`];
            assert.deepEqual(fromJSON(sample(name, true)), fromJSON(sample(name)));
        });
    }
});

describe('operations ignore unexpected fields', () => {
    for (const [path, pathItem] of Object.entries(openapiSchema.paths)) {
        for (const [method, operation] of Object.entries(pathItem)) {
            const parameters = Object.fromEntries(
                (operation.parameters ?? [])
                    .filter((parameter) => parameter.in === 'path')
                    .map((parameter) => [parameter.name, sample(parameter.schema)]),
            );
            const urlPath = path.replace(/\{([^}]+)\}/g, (_, name) => encodeURIComponent(String(parameters[name])));
            const requestParameters = { ...parameters };
            if (operation.requestBody) {
                const [name, value] = requestBodyArgument(operation.requestBody);
                requestParameters[name] = value;
            }
            const apiClass = client[operation.tags ? `${pascalCase(operation.tags[0])}Api` : 'DefaultApi'];
            const methodName = camelCase(operation.operationId);
            // the generated client throws a ResponseError on any other status, without reading the body
            const statuses = Object.keys(operation.responses).filter((status) => status.startsWith('2'));
            for (const status of statuses) {
                const response = operation.responses[status];
                if (!response.content?.['application/json']) {
                    continue;
                }
                const responseSchema = response.content['application/json'].schema;
                test(`${operation.operationId} ${status}`, async () => {
                    const call = (body) => apiAnswering(apiClass, method, urlPath, body, Number(status))[methodName](requestParameters);
                    assert.deepEqual(await call(sample(responseSchema, true)), await call(sample(responseSchema)));
                });
            }
        }
    }
});
