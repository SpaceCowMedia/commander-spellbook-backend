# uv Vademecum

All Python dependencies and environments in this repository are managed with
[uv](https://docs.astral.sh/uv/). This page is the quick reference: what lives where, the commands
you need day to day, and the conventions the CI enforces. For a first-time setup walkthrough see
[Getting Started](getting-started.md).

## Installing uv

uv is installed **through pip**, and it is listed in the repository-root `requirements.txt` together
with the shared dev tooling:

```bash
pip install -r requirements.txt   # uv + flake8, pytest-django, ...
```

CI and the Dockerfiles bootstrap it the same way (`pip install uv -c requirements.txt`), so if you
ever need to constrain uv's version, do it in that one file rather than hardcoding it elsewhere.

## The layout

This is a monorepo of **independent uv projects**. Each has its own `pyproject.toml`, its own
committed `uv.lock`, and its own `.venv` — there is no shared virtualenv.

| Project | Path | What it is |
|---|---|---|
| Backend | `backend/` | The Django backend, REST API and variant engine |
| Python client | `client/python/` | The OpenAPI-generated SDK (`spellbook_client`) |
| Discord bot | `bot/discord/` | Standalone bot service |
| Reddit bot | `bot/reddit/` | Standalone bot service |
| Telegram bot | `bot/telegram/` | Standalone bot service |

Two things are deliberately *not* uv projects:

- **`common/`** — shared source with no third-party dependencies. It is put on `PYTHONPATH`
  (`--pythonpath ../common`), not installed.
- **the repository root** — its `requirements.txt` is a plain pip file for dev tooling.

`spellbook_client` is likewise consumed *from source* (via `PYTHONPATH`, and copied into the bot
images), not installed as a package. That is why the bots — and the backend's `dev` group — repeat
the client's runtime dependencies.

## Everyday commands

Run these from inside a project folder, or from anywhere with `--directory <project>`.

| Command | What it does |
|---|---|
| `uv sync` | Create/update `.venv` to exactly match `uv.lock` |
| `uv run <cmd>` | Run a command in the project env, locking & syncing first |
| `uv add <pkg>` | Add a dependency (updates `pyproject.toml` **and** `uv.lock`) |
| `uv remove <pkg>` | Remove a dependency |
| `uv lock` | Re-resolve and refresh `uv.lock` |
| `uv lock --check` | Fail if `uv.lock` is stale (what CI runs) |
| `uv lock --upgrade-package <pkg>` | Bump a single package |
| `uvx <tool>` | Run a one-off tool without installing it (e.g. `uvx flake8 .`) |

The most common ones in this project:

```bash
cd backend
uv sync                                   # install the backend env
uv run manage.py migrate                  # any manage.py command
uv run manage.py runserver
uv run python -Wd manage.py test --no-input --parallel auto --pythonpath ../common
```

## Automatic environment upkeep

`uv run` locks and syncs the environment **before every command**, so the env is always current with
`pyproject.toml`/`uv.lock` — there is no "activate the virtualenv" step and no stale-dependency
class of bug. This is why the VS Code tasks and the OpenAPI script call `uv run` rather than
`python`.

To opt out (CI and Docker do, for reproducibility):

| Flag | Effect |
|---|---|
| `--locked` | Error instead of updating a stale lockfile |
| `--frozen` | Use the lockfile as-is, without checking it |
| `--no-sync` | Run without touching the environment |
| `--no-install-project` | Install only dependencies, not the project itself |

## Dependency groups

Dependencies default to the `dev` group being installed. The backend defines three groups:

| Group | Contents | Used by |
|---|---|---|
| `dev` (default) | `tblib`, `flake8`, `pytest-django`, `django-debug-toolbar`, plus the client's runtime deps | local dev, tests, CI |
| `prod` | `gunicorn`, `psycopg[binary]` | the Docker images only |
| `cython` | `cython`, `setuptools` | the Cython build |

```bash
uv sync --group cython        # dev + cython
uv sync --no-dev --group prod # what the Docker builder installs
```

## Lockfiles

`uv.lock` is **committed** and is a universal, platform-independent resolution: the same lockfile
serves Linux, macOS and Windows, so it replaces the old `pip-compile` output entirely.

- Never edit `uv.lock` by hand — change `pyproject.toml` (or use `uv add`) and re-lock.
- CI has a dedicated `lockfile` job running `uv lock --check` in every project; a stale lockfile
  fails the build. If it fails, run `uv lock` and commit the result.
- Dependabot updates `pyproject.toml` + `uv.lock` through its `uv` ecosystem.

## Versioning

Package versions are **not** written down anywhere — they are computed from the git tags described in
[Git Flow & Versioning](git-flow.md) by
[`uv-dynamic-versioning`](https://github.com/ninoseki/uv-dynamic-versioning), a hatchling plugin:

```toml
[build-system]
requires = ["hatchling", "uv-dynamic-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "uv-dynamic-versioning"
```

On the `v5.6.0` tag a build produces `5.6.0`; off-tag it produces a dev version, and with no tags at
all it falls back to `0.0.0`.

> `uv version` does **not** work here — it refuses dynamic versions. To see the computed version,
> run `uv build` and read the resulting wheel's filename.

The Django backend's *runtime* version string (shown in the admin and the API schema) is separate:
it comes from the `VERSION` environment variable, which the CI passes to the Docker build.

## Supply chain

Every project sets a resolution cutoff matching the Dependabot cooldown, so a freshly published
(potentially compromised) release is never picked up immediately:

```toml
[tool.uv]
exclude-newer = "1 day"
```

It only affects *new* resolutions (`uv lock`, `uv add`, upgrades). It does not make `uv lock --check`
time-dependent, because uv does not re-resolve when merely validating a lockfile.

## uv in Docker and CI

**Docker** — each image installs uv with pip, then installs *only dependencies* from the lockfile
into a virtualenv at the fixed path `/opt/venv` (fixed so it stays valid when copied between build
stages), which is then put on `PATH`:

```dockerfile
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

RUN uv sync --locked --no-install-project --no-dev --group prod
```

| Variable | Why |
|---|---|
| `UV_COMPILE_BYTECODE=1` | Write `.pyc` files at build time, so the first request does not pay for compilation. Worth it in an image, which is built once and started many times. |
| `UV_LINK_MODE=copy` | Copy files out of uv's cache instead of hardlinking. The cache and `/opt/venv` are on different layers, where hardlinks cannot be made; without this uv warns and falls back anyway. |
| `UV_PYTHON_DOWNLOADS=0` | Never fetch a managed interpreter — the image must use the `python:3.14-alpine` one it is built on. |
| `UV_PROJECT_ENVIRONMENT` | See the fixed-path note above. |

The applications run **from source** (`manage.py`, `spellbook_<bot>.py`), so the project itself is
never installed into the image, and `.git` is never needed at build time.

**CI** — installs uv with pip, then `uv sync --locked` + `uv run --no-sync`, so jobs can never
silently drift from the committed lockfile.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `VIRTUAL_ENV=... does not match the project environment` | A different virtualenv is active in your shell. Harmless — uv correctly uses the project's `.venv`. |
| `uv lock --check` fails in CI | The lockfile is stale. Run `uv lock` in that project and commit. |
| `ModuleNotFoundError` for `constants`, `text_utils`, … | Root `common/` is missing from the path; pass `--pythonpath ../common`. |
| `ModuleNotFoundError: spellbook_client` | You are in a project whose env lacks the client's deps, or `client/python` is not on `PYTHONPATH`. |
| VS Code uses the wrong interpreter | Each project has its own `.venv` (the backend's is the default). Run **Python: Select Interpreter**. |
| flake8 reports errors inside `.venv` | The project's `.flake8` must exclude `.venv`. |
