# Commander Spellbook Backend Development Docs

This is the home page of the developer documentation for the Commander Spellbook Backend project.

## Architecture

Commander Spellbook consists of three main components:
- the database, which by default is a PostgreSQL instance
- the backend, which is a single, self-contained Django project with multiple apps and dependencies
- the frontend, which is a separate React project that consumes the backend API

## Environment Setup for the Backend

You need:
- Python 3.9 or higher
- To install the dependencies in `requirements.txt` using `pip install -r requirements.txt`
- `pytest` and `pytest-django` for running the unit tests
- `flake8` for linting the code, which is mandatory for contributing otherwise the CI will fail
- [Optional] VS Code with the Python extension, for development and debugging exploiting the `launch.json` configuration
- [Optional] Docker and Docker Compose, for running the entire stack locally
- [Optional] `pip-tools` for managing the dependencies, in particular `requirements.in` is used to generate `requirements.txt` with the command `pip-compile`
