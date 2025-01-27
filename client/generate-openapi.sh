#!/bin/sh
set -e

cd ../backend
python manage.py spectacular --file ../client/openapi.yaml --fail-on-warn --validate
