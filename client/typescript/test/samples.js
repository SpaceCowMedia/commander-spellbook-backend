// Responses shaped like the backend's, built from the OpenAPI schema the client was generated from.
//
// Every property of every object is filled, nullable ones included, so a sample reaches every nested model.
// With unexpectedFields, every object also carries fields the schema does not declare, as a newer
// backend would send them to an older client.
import { readFileSync } from 'node:fs';

export const openapiSchema = JSON.parse(readFileSync(new URL('../../openapi.json', import.meta.url), 'utf-8'));

export const UNEXPECTED_FIELDS = {
    unexpectedString: 'unexpected',
    unexpectedNumber: 42,
    unexpectedBoolean: true,
    unexpectedNull: null,
    unexpectedArray: [1, 'two', { three: 3 }],
    unexpectedObject: { nested: { deeper: ['value'] } },
};

const STRING_FORMATS = {
    'date': '2026-01-01',
    'date-time': '2026-01-01T00:00:00Z',
    'email': 'user@example.com',
    'uri': 'https://example.com/',
    'uuid': '00000000-0000-4000-8000-000000000000',
};

// tried in order, the first one satisfying the length and pattern constraints is used
const STRING_CANDIDATES = ['Sample', 'example.com', '1', ''];

export function objectSchemaNames() {
    return Object.entries(openapiSchema.components.schemas)
        .filter(([, schema]) => schema.type === 'object')
        .map(([name]) => name);
}

export function resolve(schema) {
    if (typeof schema === 'string') {
        return openapiSchema.components.schemas[schema];
    }
    if ('$ref' in schema) {
        return resolve(schema['$ref'].replace('#/components/schemas/', ''));
    }
    return schema;
}

export function sample(schema, unexpectedFields = false) {
    schema = resolve(schema);
    if ('allOf' in schema) {
        const parts = schema.allOf.map((part) => sample(part, unexpectedFields));
        if (parts.every((part) => typeof part === 'object' && part !== null && !Array.isArray(part))) {
            return Object.assign({}, ...parts);
        }
        return parts[0];
    }
    if ('enum' in schema) {
        return schema.enum[0];
    }
    switch (schema.type) {
        case 'object': {
            const properties = Object.entries(schema.properties ?? {});
            const result = Object.fromEntries(properties.map(([name, property]) => [name, sample(property, unexpectedFields)]));
            if (unexpectedFields && properties.length > 0) {
                Object.assign(result, structuredClone(UNEXPECTED_FIELDS));
            }
            return result;
        }
        case 'array':
            return Array.from({ length: Math.max(1, schema.minItems ?? 0) }, () => sample(schema.items, unexpectedFields));
        case 'string':
            return sampleString(schema);
        case 'integer':
            return clamp(1, schema);
        case 'number':
            return clamp(1.5, schema);
        case 'boolean':
            return true;
        case undefined:
            // an untyped schema, such as a JSON field, accepts any value
            return STRING_CANDIDATES[0];
    }
    throw new Error(`Cannot build a sample of ${JSON.stringify(schema)}`);
}

function sampleString(schema) {
    if (schema.format in STRING_FORMATS) {
        return STRING_FORMATS[schema.format];
    }
    for (const candidate of STRING_CANDIDATES) {
        if (candidate.length < (schema.minLength ?? 0) || candidate.length > (schema.maxLength ?? candidate.length)) {
            continue;
        }
        if ('pattern' in schema && !new RegExp(schema.pattern).test(candidate)) {
            continue;
        }
        return candidate;
    }
    throw new Error(`No sample string satisfies ${JSON.stringify(schema)}`);
}

function clamp(value, schema) {
    return Math.min(Math.max(value, schema.minimum ?? value), schema.maximum ?? value);
}
