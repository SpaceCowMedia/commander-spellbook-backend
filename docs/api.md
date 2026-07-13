# API & Clients

The backend exposes a REST API built with [Django REST Framework](https://www.django-rest-framework.org/). This page covers the endpoints, authentication, the OpenAPI schema, and the generated SDKs.

## Exploring the API

With the server running (see [Getting Started](getting-started.md)):

- `http://localhost:8000/` — the browsable API root
- `http://localhost:8000/schema/swagger/` — Swagger UI
- `http://localhost:8000/schema/redoc/` — ReDoc
- `http://localhost:8000/schema/` — the raw OpenAPI document

Responses use **camelCase** keys (a middleware converts Django's snake_case), which is what the generated clients and the frontend expect.

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

## OpenAPI schema

The schema is generated from the code by [`drf-spectacular`](https://drf-spectacular.readthedocs.io/). It is the **contract** the clients and frontend depend on, so keep it accurate: add [serializer](https://github.com/SpaceCowMedia/commander-spellbook-backend/tree/master/backend/spellbook/serializers) annotations and `@extend_schema` hints when you add or change an endpoint.

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
