# Commander Spellbook Backend Development Docs

This is the home page of the developer documentation for the Commander Spellbook Backend project.

## Architecture

Commander Spellbook consists of three main components:

- the database, which by default is a PostgreSQL instance
- the backend, which is a single, self-contained Django project with multiple apps and dependencies
- the frontend, which is a separate React project that consumes the backend API

## Environment Setup for the Backend

You need:

- Python 3.11 or higher
- Docker and Docker Compose, for running the entire stack locally and for running some scripts
- To install the dependencies:
  - In the root of the repository, install the dependencies for local development using `pip install -r requirements.txt`
  - In the backend folder, install the dependencies using `pip install -r requirements.txt`
  - In the client folder:
    - Generate the OpenAPI doc using the `generate-openapi.sh` script
    - [Optional] Generate the TypeScript/JavaScript client using the `generate-client-typescript.sh` script
    - Generate the python client using the `generate-client-python.sh` script
    - Inside the client/python folder:
        - Install the python client dependencies using `pip install -r requirements.txt`
- `flake8` for linting the code, which is mandatory for contributing otherwise the CI will fail
- [Optional] VS Code with the Python extension, for development and debugging exploiting the `launch.json` configuration
    - `pytest` to run the unit tests in VS Code
- [Optional] Cython for running long tasks faster (especially the variant generation code)
