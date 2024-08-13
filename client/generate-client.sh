#!/bin/sh
set -e

kiota generate -l python -c SpellbookClient -n spellbook_client -d openapi.yaml -o python --exclude-backward-compatible
