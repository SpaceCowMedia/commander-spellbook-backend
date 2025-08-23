#!/bin/sh
set -e

MSYS_NO_PATHCONV=1 docker run --rm --pull=always \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/openapi.yaml \
  -g python \
  -o /local/python \
  --additional-properties=generateSourceCodeOnly=true,library=asyncio,packageName=spellbook_client
