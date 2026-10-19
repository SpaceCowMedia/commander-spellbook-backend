#!/bin/sh
set -e

cd ../backend
PYTHONPATH=../common uv run python manage.py spectacular --file ../client/openapi.yaml --fail-on-warn --validate
# the clients' tests read the schema with a plain JSON parser
PYTHONPATH=../common uv run python manage.py spectacular --file ../client/openapi.json --format openapi-json --fail-on-warn
