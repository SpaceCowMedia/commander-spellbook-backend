from constants import BULK_VARIANTS_URL, BULK_VARIANTS_GZIP_URL, WEBSITE_URL

TYPESCRIPT_CLIENT_URL = 'https://www.npmjs.com/package/@space-cow-media/spellbook-client'
USER_AGENT_REFERENCE_URL = 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/User-Agent#library_and_net_tool_ua_strings'

BULK_DATA_SECTION = f'''## Bulk data

Please do not use this API to export the whole dataset: consuming hundreds of result pages every
time costs you time and us a ton of resources. Every variant, together with the variant aliases, is
published as a single JSON document, refreshed periodically:

* [{BULK_VARIANTS_GZIP_URL}]({BULK_VARIANTS_GZIP_URL}) — gzipped, prefer this one
* [{BULK_VARIANTS_URL}]({BULK_VARIANTS_URL}) — uncompressed

The document holds the `timestamp` it was built at, the `version` that built it, and the `variants`
and `aliases` arrays, whose items have the very same shape as the `/variants/` and
`/variant-aliases/` responses. Fetch it on a schedule of your own and read it locally.'''

USAGE_SECTION = f'''## Using this API

Make sparse, unauthenticated requests, with the general guideline of a few HTTP calls per user
interaction with your tool.

* Name your service, optionally with a version, in the [User-Agent]({USER_AGENT_REFERENCE_URL}) header.
* You may be rate limited: 80 requests per minute should be a safe rate, and clients should always
  handle `429 Too Many Requests` responses.
* Responses use camelCase keys.
* A TypeScript client is published on npm as [`@space-cow-media/spellbook-client`]({TYPESCRIPT_CLIENT_URL}).

Please credit us, and link back to [{WEBSITE_URL}]({WEBSITE_URL}) where applicable. Thanks!'''

API_DESCRIPTION = f'''API for Commander Spellbook, the combo database engine for Magic: The Gathering.

{BULK_DATA_SECTION}

{USAGE_SECTION}'''

API_ROOT_DESCRIPTION = f'''The Commander Spellbook API, the combo database engine for Magic: The Gathering.

Every endpoint is documented in the [OpenAPI schema](/schema/), browsable as
[Swagger](/schema/swagger/) or [ReDoc](/schema/redoc/).

{USAGE_SECTION}'''

VARIANTS_DESCRIPTION = f'''The combo variants the engine generated, searchable with the same query language the website uses.

{BULK_DATA_SECTION}'''
