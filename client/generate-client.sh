#!/bin/sh
set -e

kiota generate -l python -c SpellbookClient -d openapi.yaml -o python/spellbook_client --exclude-backward-compatible
mv python/spellbook_client/spellbook_client.py python/spellbook_client/__init__.py
