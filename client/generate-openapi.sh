#!/bin/sh
set -e

cd ../backend
PYTHONPATH=../common python manage.py spectacular --file ../client/openapi.yaml --fail-on-warn --validate
