# Getting Started

This page gets a contributor from a fresh clone to a running backend, a passing
test suite, and a clean linter.

## Prerequisites

- **Python 3.14+** (the CI matrix pins 3.14; see [`.python-version`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/.python-version)).
- **Docker + Docker Compose** — required to run the full stack and to generate the
  API clients.
- **Git**.
- *(Optional)* **VS Code** with the Python extension — the repo ships a
  `.vscode/launch.json` with run/debug and `pytest` configurations.

## Two ways to run the backend

### Option A — Docker Compose (full stack)

Brings up PostgreSQL, the Django web server behind nginx, and the background
worker exactly as they run in the demo environment:

```bash
docker compose up --build
```

The site is served on `http://localhost` (override the port with the `PORT`
environment variable). The compose file uses a throwaway Postgres database with
demo credentials — see [`docker-compose.yml`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/docker-compose.yml).

To also run one or all of the bots, enable their compose profiles:

```bash
docker compose --profile bot up      # all bots
docker compose --profile discord up  # just Discord
```

### Option B — `manage.py` (backend only)

Fastest inner loop for backend work. Uses a local **SQLite** database by default
(no Postgres needed), which is enough for most development.

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then open:

- `http://localhost:8000/` — the browsable REST API and OpenAPI docs
- `http://localhost:8000/admin` — the Django admin panel (where editors author combos)

> **Note:** some features (full-text search, certain indexes) are Postgres-only and
> are skipped on SQLite. Use Option A, or point `SQL_*` environment variables at a
> Postgres instance, when you need production-faithful behaviour. See
> [Configuration](#configuration) below.

## Installing dependencies

The repository is a monorepo with several dependency sets. Install what you need:

```bash
# From the repository root — dev & test tooling (flake8, pytest-django, ...)
pip install -r requirements.txt

# From backend/ — the Django backend itself
pip install -r backend/requirements.txt
```

`requirements.txt` files are compiled from `requirements.in` with
[`pip-tools`](https://github.com/jazzband/pip-tools); edit the `.in` file and
recompile rather than editing the pinned file by hand.

## Running the tests

Tests are standard Django tests. Run them from the `backend` folder; `common` must
be on the Python path:

```bash
cd backend
python -Wd manage.py test --no-input --parallel auto --pythonpath ../common
```

`pytest` also works from the repository root (configuration lives in
[`pytest.ini`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/pytest.ini)):

```bash
pytest
```

Every code change **must** ship with tests — the CI enforces the suite across
Linux, Windows, and macOS.

## Linting

The project follows [PEP 8](https://pep8.org/), enforced by `flake8`. The CI lints
three folders; run the same locally before pushing:

```bash
flake8 backend
flake8 common
flake8 bot
```

A failing lint fails the build.

## Optional: Cython acceleration

The [variant generation](variant-generation.md) code ships with `.pxd` type stubs
so it can be compiled with Cython for a large speed-up on big generation runs. It
is pure Python by default; compile it only if you are profiling or running full
generations locally:

```bash
cd backend
pip install --upgrade cython setuptools
cythonize -i 'spellbook/variants/*.py'
```

The CI runs the test suite both with and without Cython to guarantee behaviour is
identical.

## Generating the API clients (optional)

The Python and TypeScript SDKs are generated from the live OpenAPI schema. You need
Docker running. See [API & Clients](api.md#generated-clients) for the scripts and
details.

## Configuration

Settings are read from environment variables (with sensible development defaults in
[`backend/backend/settings.py`](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/backend/settings.py)).
The ones you are most likely to touch:

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Django secret key | insecure dev key |
| `SQL_ENGINE` / `SQL_DATABASE` / `SQL_USER` / `SQL_PASSWORD` / `SQL_HOST` / `SQL_PORT` | Database connection (production settings) | SQLite |
| `VERSION` | Version string shown in the admin/API | `dev` |
| `DISCORD_WEBHOOK_URL` | Webhook for notifications | unset |
| `MOXFIELD_USER_AGENT` | User agent for Moxfield deck imports | unset |
| `DISCORD_CLIENTID` / `DISCORD_CLIENTSECRET` | Discord social login (OAuth) | unset |

Local development uses `backend/backend/settings.py` (SQLite, `DEBUG = True`).
Docker and production use `backend/backend/production_settings.py` (Postgres via the
`SQL_*` variables); the background worker uses `worker_settings.py`, which adds a
statement timeout on top of the production settings.

## Next steps

You have a running backend. Read the [Architecture](architecture.md) to learn how
the pieces fit together, then the [Domain Model](domain-model.md) to learn the
vocabulary.
