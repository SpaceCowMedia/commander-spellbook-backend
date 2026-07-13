# Commander Spellbook Backend — Developer Docs

Welcome. This is the developer documentation for the **Commander Spellbook Backend**, the engine and REST API behind [commanderspellbook.com](https://commanderspellbook.com/) — a combo database, wiki, and search engine for [Magic: The Gathering](https://magic.wizards.com/en).

These pages are for **contributors**. If you read them top to bottom you should be able to set up the project, understand how it fits together, and open your first pull request. They complement (not replace) the [root README](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/README.md) and [`CONTRIBUTING.md`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/CONTRIBUTING.md).

## What this project does

Editors describe *combos* (small interactions between Magic cards that produce an effect). The backend then **automatically generates every concrete card combination — a _variant_ — that achieves a result**, by walking a graph of cards, features, and combos. Those variants are served through a REST API that the [React frontend](https://github.com/SpaceCowMedia/commander-spellbook-site), the chat bots, and third-party tools consume.

The heart of the project is therefore not CRUD — it is the [variant generation engine](variant-generation.md).

## The stack at a glance

| Component  | Technology | Role |
|------------|------------|------|
| Database   | PostgreSQL (SQLite for local dev) | Stores cards, combos, features, generated variants |
| Backend    | Django + Django REST Framework | Domain model, admin panel, REST API, variant engine |
| Worker     | `django-tasks` (`db_worker`) | Runs long jobs: variant generation, Scryfall card sync |
| Clients    | Generated from OpenAPI | Python & TypeScript SDKs published to PyPI / npm |
| Bots       | Discord, Reddit, Telegram | Standalone services that consume the API via the Python client |
| Frontend   | React (separate repo) | The website; not in this repository |

## Documentation map

Start here and follow the order:

1. **[Getting Started](getting-started.md)** — install dependencies, run the stack, run the tests and the linter.
2. **[Architecture](architecture.md)** — the repository layout and how the pieces (backend project, `spellbook` app, `website` app, `common`, clients, bots) connect.
3. **[Domain Model](domain-model.md)** — Cards, Features, Combos, Templates, Variants, and Suggestions: the vocabulary everything else is built on.
4. **[Variant Generation](variant-generation.md)** — the combo graph and the algorithm that turns editor-authored combos into concrete variants.
5. **[API & Clients](api.md)** — the REST endpoints, authentication, the OpenAPI schema, and the generated SDKs.
6. **[Git Flow & Versioning](git-flow.md)** — branching, semantic versioning, and how a release ships.

Reference material:

- **[The Minimal Set of Multisets ADT](minimal-set-of-multisets.md)** — the data structure behind the engine's minimality pruning.

## Getting help

Ask on the Commander Spellbook Discord — the [#website](https://discord.com/channels/673601282946236417/728339448558911508) channel is the best place for backend questions. Maintainers are happy to help you get started.
