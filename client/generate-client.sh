#!/bin/sh
set -e
VERSION=`python ../backend/manage.py shell -c 'from django.conf import settings; print(settings.VERSION)'`
MSYS_NO_PATHCONV=1 docker run --rm \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/openapi.yaml \
  -g python \
  -o /local/python \
  --additional-properties=generateSourceCodeOnly=true,library=asyncio,packageName=spellbook_client,packageVersion=${VERSION}