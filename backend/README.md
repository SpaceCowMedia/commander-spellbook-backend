# Commander Spellbook backend
This folder contains the main `backend` project folder and the `spellbook` app folder that compose the Commander Spellbook backend api.

## Try it out on your machine

Dependencies are managed with [uv](https://docs.astral.sh/uv/), which also downloads a matching
Python for you. Install it from the repository root, then run the backend against the default local
SQLite database:
```bash
pip install -r requirements.txt   # uv + pre-commit
cd backend
uv sync
uv run manage.py migrate
uv run manage.py createsuperuser
uv run manage.py runserver
```
Then go to http://localhost:8000/ for the API documentation and http://localhost:8000/admin for the admin panel.

## Before you commit

Install the [pre-commit](https://pre-commit.com/) hooks once, from the repository root:
```bash
pre-commit install
```
They run the same checks as the CI — `flake8` on the files you staged, `mypy` on the backend, and
the lockfile check — before each commit, and the test suite before each push. Run
`pre-commit run --all-files` to check the whole tree. See
[Git hooks](https://spacecowmedia.github.io/commander-spellbook-backend/getting-started/#git-hooks)
for details.

The full setup guide, including Docker Compose and Postgres, lives in
[Getting Started](https://spacecowmedia.github.io/commander-spellbook-backend/getting-started/).
