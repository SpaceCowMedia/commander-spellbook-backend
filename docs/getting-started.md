# Getting Started

This page gets a contributor from a fresh clone to a running backend, a passing test suite, and a clean linter.

## Prerequisites

- **Python 3.14+** (the CI matrix pins 3.14; see [`.python-version`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/.python-version)).
- **[uv](https://docs.astral.sh/uv/)** — the Python package & environment manager used throughout the repo. Install it with `pip install uv`, or get it together with the shared dev tooling by running `pip install -r requirements.txt` from the repository root. See the [uv Vademecum](uv.md) for the full workflow.
- **Docker + Docker Compose** — required to run the full stack and to generate the API clients. Not needed for the SQLite-only inner loop below.
- **Git**.
- *(Optional)* **VS Code** with the Python extension — the repo ships a `.vscode/launch.json` with run/debug and `pytest` configurations.

## Two ways to run the backend

### Option A — Docker Compose (full stack)

Brings up PostgreSQL, the Django web server behind nginx, and the background worker exactly as they run in the demo environment:

```bash
docker compose up --build
```

The site is served on `http://localhost` (override the port with the `PORT` environment variable). The compose file uses a throwaway Postgres database with demo credentials — see [`docker-compose.yml`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/docker-compose.yml).

To also run one or all of the bots, enable their compose profiles:

```bash
docker compose --profile bot up      # all bots
docker compose --profile discord up  # just Discord
```

### Option B — `manage.py` with SQLite (backend only)

Fastest inner loop for backend work. **Local development uses a file-based SQLite database by default** (configured in `backend/backend/settings.py`), so you need **no Postgres and no Docker** — Django creates the database file on first `migrate`. This is enough for most day-to-day development.

```bash
cd backend
uv sync                       # create .venv and install the locked dependencies
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver
```

`uv run` keeps the project environment locked and synced automatically before each command, so there is no separate "activate the virtualenv" step. Then open:

- `http://localhost:8000/` — the browsable REST API and OpenAPI docs
- `http://localhost:8000/admin` — the Django admin panel (where editors author combos)

> **Note:** some features (full-text search, certain indexes) are Postgres-only and are skipped on SQLite. Use Option A, or point `SQL_*` environment variables at a Postgres instance, when you need production-faithful behaviour. See [Configuration](#configuration) below.

## Installing dependencies

The repository is a monorepo with several **independent [uv](https://docs.astral.sh/uv/) projects** — `backend/`, `client/python/`, and the three `bot/*` — each with its own `pyproject.toml` and a committed, platform-independent `uv.lock`. Install the one you are working on with `uv sync` from its folder:

```bash
# The Django backend
cd backend && uv sync

# A bot (installs its own dependency set)
cd bot/discord && uv sync
```

Dependencies are declared in each project's `pyproject.toml` and pinned in `uv.lock`. Add or change one with `uv add <package>` / `uv remove <package>` — these update `pyproject.toml` and `uv.lock` together. **Never edit `uv.lock` by hand**; the lockfiles are verified in CI with `uv lock --check`. The [uv Vademecum](uv.md) covers dependency groups, versioning, and the rest of the workflow.

The repository root keeps a plain `requirements.txt` for shared dev/test tooling (including uv itself); install it with `pip install -r requirements.txt`.

> **Interpreter selection (VS Code):** each project has its own `.venv`, and the backend one is the default. When working on a different project (a bot, the client), run **Python: Select Interpreter** and pick that project's `*/.venv`.

## Running the tests

Tests are standard Django tests. Run them from the `backend` folder; `common` must be on the Python path:

```bash
cd backend
uv run python -Wd manage.py test --no-input --parallel auto --pythonpath ../common
```

`pytest` also works (configuration lives in [`pytest.ini`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/pytest.ini)); run it inside the backend environment, whose `dev` group also carries what the client tests need:

```bash
uv run --project backend pytest backend client/python common
```

Every code change **must** ship with tests — the CI enforces the suite across Linux, Windows, and macOS.

## Linting

The project follows [PEP 8](https://pep8.org/), enforced by `flake8`. The CI lints three folders; run the same locally before pushing:

```bash
uvx flake8 backend
uvx flake8 common
uvx flake8 bot
```

A failing lint fails the build.

## Optional: Cython acceleration

The [variant generation](variant-generation.md) code ships with `.pxd` type stubs so it can be compiled with Cython for a large speed-up on big generation runs. It is pure Python by default; compile it only if you are profiling or running full generations locally:

```bash
cd backend
uv sync --group cython
uv run cythonize -i 'spellbook/variants/*.py'
```

The CI runs the test suite both with and without Cython to guarantee behaviour is identical.

## Generating the API clients (optional)

The Python and TypeScript SDKs are generated from the live OpenAPI schema. You need Docker running. See [API & Clients](api.md#generated-clients) for the scripts and details.

## Configuration

Settings are read from environment variables (with sensible development defaults in [`backend/backend/settings.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/backend/settings.py)). The ones you are most likely to touch:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Django secret key | insecure dev key |
| `SQL_ENGINE` / `SQL_DATABASE` / `SQL_USER` / `SQL_PASSWORD` / `SQL_HOST` / `SQL_PORT` | Database connection (production settings) | SQLite |
| `VERSION` | Version string shown in the admin/API | `dev` |
| `DISCORD_WEBHOOK_URL` | Webhook for notifications | unset |
| `MOXFIELD_USER_AGENT` | User agent for Moxfield deck imports | unset |
| `DISCORD_CLIENTID` / `DISCORD_CLIENTSECRET` | Discord social login (OAuth) | unset |

Local development uses `backend/backend/settings.py` (SQLite, `DEBUG = True`). Docker and production use `backend/backend/production_settings.py` (Postgres via the `SQL_*` variables); the background worker uses `worker_settings.py`, which adds a statement timeout on top of the production settings.

## Next steps

You have a running backend. Read the [Architecture](architecture.md) to learn how the pieces fit together, then the [Domain Model](domain-model.md) to learn the vocabulary.
