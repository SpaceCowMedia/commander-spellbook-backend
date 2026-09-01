# API & Clients

The backend exposes a REST API built with [Django REST Framework](https://www.django-rest-framework.org/). This page covers the endpoints, authentication, the OpenAPI schema, and the generated SDKs.

## Exploring the API

With the server running (see [Getting Started](getting-started.md)):

- `http://localhost:8000/` — the browsable API root
- `http://localhost:8000/schema/swagger/` — Swagger UI
- `http://localhost:8000/schema/redoc/` — ReDoc
- `http://localhost:8000/schema/` — the raw OpenAPI document

Responses use **camelCase** keys (a middleware converts Django's snake_case), which is what the generated clients and the frontend expect.

## Bulk data

**Do not use the HTTP API to export the whole dataset.** Consuming hundreds of result pages every time costs you time and us a ton of resources. Every variant, together with the variant aliases, is published as a single JSON document on S3, refreshed periodically:

| File | Description |
|------|-------------|
| <https://json.commanderspellbook.com/variants.json.gz> | Gzipped. Prefer this one. |
| <https://json.commanderspellbook.com/variants.json> | Uncompressed. |

The document holds the `timestamp` it was built at, the `version` that built it, and the `variants` and `aliases` arrays, whose items have the very same shape as the `/variants/` and `/variant-aliases/` responses. Fetch it on a schedule of your own and read it locally.

It is written by the `export_variants` task ([`spellbook/tasks/export_variants.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/spellbook/tasks/export_variants.py)), which the recurring update CronJob runs with `--s3` to upload to the bucket named by `AWS_S3_BUCKET`. The public base URL comes from `SPELLBOOK_FILES_URL`, set by every deployment alongside `SPELLBOOK_API_URL` and `SPELLBOOK_WEBSITE_URL` (see `backend/.env` and the Kubernetes manifests).

## Guidelines for API consumers

Use the HTTP API for sparse, unauthenticated requests, with the general guideline of a few HTTP calls per user interaction with your tool.

- Name your service, optionally with a version, in the [User-Agent](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/User-Agent#library_and_net_tool_ua_strings) header.
- You may be rate limited: 80 requests per minute should be a safe rate. **Always handle `429 Too Many Requests` responses** — back off and retry rather than hammering the endpoint.
- Please credit us and link back to [commanderspellbook.com](https://commanderspellbook.com/) where applicable.

## Endpoints

Routes are wired in [`backend/spellbook/urls.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/spellbook/urls.py), [`backend/website/urls.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/website/urls.py), and the project [`urls.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/backend/urls.py).

### Core (`spellbook`)

| Endpoint | Description |
|----------|-------------|
| `GET /variants/` | The generated [variants](domain-model.md#variant) — the main read endpoint. Supports the [search query language](#the-search-query-language). |
| `GET /cards/` | Cards. |
| `GET /features/` | Features. |
| `GET /templates/` | Templates. |
| `GET`/`POST /find-my-combos` | Given a decklist, returns the combos it can assemble (the engine's [up phase](variant-generation.md#up-phase--find-combos-from-a-hand-bfs-from-cards)). |
| `GET`/`POST /estimate-bracket` | Estimates the power bracket of a decklist. |
| `GET /explain-query` | Explains a [search query](#the-search-query-language) in plain English, or reports why it is invalid. |
| `… /variant-suggestions/` | Community-submitted combos awaiting review. |
| `… /variant-update-suggestions/` | Suggested edits to existing variants. |
| `… /variant-aliases/` | Redirects from alternative ids to canonical variants. |

### Site support (`website`)

| Endpoint | Description |
|----------|-------------|
| `GET /properties/` | Site-wide configurable properties. |
| `GET /card-list-from-url` | Parse a decklist from a supported deckbuilder URL (Moxfield, Archidekt, Deckstats, TappedOut). |
| `GET`/`POST /card-list-from-text` | Parse a decklist from pasted text. |

### Users & auth

`/users/`, plus the authentication endpoints below.

## Authentication

Two mechanisms, both configured in the project [`urls.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/backend/urls.py):

- **JWT** ([`simplejwt`](https://django-rest-framework-simplejwt.readthedocs.io/)):
  - `POST /token/` — obtain an access/refresh pair
  - `POST /token/refresh/` — refresh an access token
  - `POST /token/verify/` — verify a token

  Send the access token as `Authorization: Bearer <token>`.
- **Social login** (`social-auth`) — Discord OAuth, enabled when `DISCORD_CLIENTID` / `DISCORD_CLIENTSECRET` are set.

Most read endpoints are public; writing and reviewing require authentication and the appropriate permissions. Editors work primarily through the **admin panel** (`/admin`), not the API.

## The search query language

`variants` (and template matching) accept a **Scryfall-style search query** — e.g. `ci:temur mana result:"infinite mana"`. The grammar is defined with [Lark](https://github.com/lark-parser/lark) in [`spellbook/parsers/`](https://github.com/SpaceCowMedia/commander-spellbook-backend/tree/master/backend/spellbook/parsers) and turned into ORM filters by the transformers in [`spellbook/transformers/`](https://github.com/SpaceCowMedia/commander-spellbook-backend/tree/master/backend/spellbook/transformers). Extend the query language by editing the `.lark` grammar and its transformer together.

The same grammar drives a second transformer, which turns a query into an English sentence instead of a filter: `GET /explain-query?q=ci:temur mana` answers *"Combos that have a color identity within green, blue, and red and use a card whose name contains “mana”."* A new search term needs a phrase in [`variants_query_explanations/`](https://github.com/SpaceCowMedia/commander-spellbook-backend/tree/master/backend/spellbook/transformers/variants_query_explanations) alongside its filter, so that both endpoints accept and reject exactly the same queries.

## OpenAPI schema

The schema is generated from the code by [`drf-spectacular`](https://drf-spectacular.readthedocs.io/). It is the **contract** the clients and frontend depend on, so keep it accurate: add [serializer](https://github.com/SpaceCowMedia/commander-spellbook-backend/tree/master/backend/spellbook/serializers) annotations and `@extend_schema` hints when you add or change an endpoint.

The prose the schema and the browsable API show — the API description, the root page and the `/variants/` endpoint — lives in [`common/api_docs.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/common/api_docs.py). Edit it there and this page together, so the two keep saying the same thing.

Regenerate the committed schema with:

```bash
cd client
./generate-openapi.sh   # writes client/openapi.yaml
```

The script runs `manage.py spectacular … --fail-on-warn --validate`, so a schema warning is treated as an error — the CI does the same.

## Generated clients

The SDKs are generated from `openapi.yaml` with [openapi-generator](https://openapi-generator.tech/) (run via Docker, so Docker must be running):

```bash
cd client
./generate-openapi.sh              # 1. refresh the schema
./generate-client-python.sh        # 2a. Python client  -> client/python/
./generate-client-typescript.sh    # 2b. TypeScript client -> client/typescript/
```

- **Python** — package `spellbook_client` (async, `asyncio` library). Used by the [bots](architecture.md#repository-layout) and the Python integration tests.
- **TypeScript** — published to npm as [`@space-cow-media/spellbook-client`](https://www.npmjs.com/package/@space-cow-media/spellbook-client) and consumed by the [React frontend](https://github.com/SpaceCowMedia/commander-spellbook-site).

The CI regenerates and publishes both on release; you only need to run these locally when changing the API and testing a client against it.
