---
name: run-backend
description: Run, start, seed and drive the Commander Spellbook backend (Django admin and API) on a throwaway database, take screenshots of the admin in a real browser, generate variants and read what they render. Use when asked to run or start the backend, open or screenshot the admin, click through a change view, try the dictionary editor, or check variant texts on live data.
---

Launches the Django backend on a database of its own with `.claude/skills/run-backend/serve.py`
(a `manage.py` that needs no PYTHONPATH and never touches `db.sqlite3`), then drives the admin in a
real Chromium-family browser with `.claude/skills/run-backend/driver.mjs`, a command runner over
Playwright that reads one command per line on stdin.

All paths below are relative to `backend/`. Verified on Windows 11 with Git Bash, uv 0.12, Node 24
and the installed Edge.

## Prerequisites

- `backend/.venv`, made by `uv sync` (see `docs/getting-started.md`).
- Node (24 here) and a Chromium-family browser: Edge, which Windows has, is found by itself.

```bash
npm install --prefix .claude/skills/run-backend --no-audit --no-fund
```

## Start the backend

```bash
uv run --no-sync python .claude/skills/run-backend/serve.py migrate --no-input
uv run --no-sync python .claude/skills/run-backend/serve.py seed
uv run --no-sync python .claude/skills/run-backend/serve.py runserver 127.0.0.1:8765 --noreload &
timeout 60 bash -c 'until curl -sf -o /dev/null http://127.0.0.1:8765/admin/login/; do sleep 1; done' && echo up
```

The database is `spellbook-run-backend.sqlite3` in the temp folder, or whatever `RUN_BACKEND_DB`
names; migrating a fresh one takes about 20 s. `seed` prints the superuser (`agent` /
`agent-password`) and the change views of what it made: a feature produced by two cards, one giving
it two attributes and the other a mana cost, and a generator combo needing it out of replacements.

For the real data, point `RUN_BACKEND_DB` at a copy of the developer's snapshot and migrate the copy
(the 2 GB snapshot copied in a second and migrated from 0081 in 9 s); never migrate `db.sqlite3`
itself. On it, `seed` reuses the existing Free Sacrifice Outlet, so its ids differ: read them from its
output.

```bash
export RUN_BACKEND_DB="$TEMP/spellbook-snapshot.sqlite3"
cp db.sqlite3 "$RUN_BACKEND_DB"
uv run --no-sync python .claude/skills/run-backend/serve.py migrate --no-input
uv run --no-sync python .claude/skills/run-backend/serve.py seed
```

## Drive the admin (agent path)

Pipe commands to the driver; screenshots land in `.claude/skills/run-backend/screenshots/`. Look at
them: the Read tool shows a PNG.

```bash
node .claude/skills/run-backend/driver.mjs <<'EOF'
login
nav /admin/spellbook/combo/1/change/
wait .dictionary-summary
scroll #featureproducedincombo_set-group
shot combo-rows
click #featureproducedincombo_set-group .dictionary-summary
wait dialog.dictionary-dialog
shot attributes dialog.dictionary-dialog
click .dictionary-tab-yaml
fill .dictionary-yaml sac activation: Sacrifice it\n
click .dictionary-apply
submit input[name=_continue]
text #featureproducedincombo_set-group .dictionary-summary
nav /admin/spellbook/feature/1/change/
scroll .dictionary-summary
shot feature-card-rows
errors
EOF
```

Commands: `login [user] [password]`, `nav <path>`, `wait <selector>`, `click <selector>`,
`submit <selector>` (click and wait for the next page), `fill <selector> <text>` (`\n` for new lines),
`hover`, `scroll <selector>`, `shot <name> [selector]`, `text <selector>`, `eval <expression>`,
`scheme light|dark`, `errors`. Selectors are Playwright's. The first failing command prints
`failed: ...` and ends the run with exit code 1. `RUN_BACKEND_URL` and `BROWSER_PATH` override the
server and the browser.

## Generate variants and read them

Most changes touch generation rather than the admin. On the running database:

```bash
uv run --no-sync python .claude/skills/run-backend/serve.py shell -c "from spellbook.variants.variants_generator import generate_variants; print('added, restored, removed:', generate_variants())"
uv run --no-sync python .claude/skills/run-backend/serve.py shell -c "from spellbook.models import Variant; [print(v.id, repr(v.mana_needed), repr(v.description), repr(v.notes)) for v in Variant.objects.all()]"
```

The seed gives two variants; Viscera Seer gives no attribute the combo's text asks for, so those
references are deleted, and the needed row out of replacements keeps the card's `{B}` out of it.

## Test

```bash
uv run --no-sync python manage.py test --no-input --parallel auto --pythonpath ../common
```

## Stop

```bash
pid=$(netstat -ano | grep "127.0.0.1:8765" | grep LISTENING | awk '{print $NF}' | head -1); taskkill //PID $pid //F
```

`--noreload` keeps the server in one process, so that PID is all there is to stop.

## Gotchas

- `uv run --no-sync` runs the existing `.venv` as it is; without the flag, uv syncs it first.
- `manage.py` alone cannot import `constants`: it lives in the repo's `common/`, which `serve.py` puts
  on the path (with plain `manage.py`, pass `--pythonpath ../common`, as the tests do).
- The default tasks backend stores tasks for a worker that is not running, so anything the admin or a
  command enqueues does nothing. The run settings use the immediate backend, as the tests do.
- `manage.py update_variants` is not generation: it refreshes EDHREC data and legalities, and fetches
  the public EDHREC dataset. Generation is `generate_variants()`, as above.
- Edge may be installed only as its `EdgeCore/<version>/msedge.exe` runtime, with no `Edge/Application`
  folder; the driver looks there first, newest version first.
- The attributes editor is a native `<dialog>`: while it is open it covers the page, so a click on the
  page behind it times out. It stays open whenever it refuses its input, which an unquoted YAML value
  holding `: ` or starting with `{` triggers; quote such values in `fill`.
- Inline rows are wider than the viewport and scroll sideways; `scroll <selector>` brings a row up
  before a `shot` of the whole page.
- Run the test suite with `manage.py test --pythonpath ../common`, not through `serve.py`: under the run
  settings two `backend.tests.test_admin` tests of the task results admin fail with `KeyError: 'task_name'`.

## Troubleshooting

- `ModuleNotFoundError: No module named 'constants'`: the command ran through `manage.py` without
  `--pythonpath ../common`; run it through `serve.py`.
- `.venv/Scripts/python: No such file or directory`: the shell is not in `backend/`.
- `failed: submit input[name=_continue]` with a navigation timeout: the dialog refused the text and is
  still open; `shot` it to read its error, and quote the YAML.
- `updated 0 variants` and no variants in the database: that was `update_variants`; call
  `generate_variants()`.
