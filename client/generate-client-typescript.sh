#!/bin/sh
set -e

MSYS_NO_PATHCONV=1 docker run --rm \
  -v ${PWD}:/local openapitools/openapi-generator-cli generate \
  -i /local/openapi.yaml \
  -g typescript-fetch \
  -o /local/typescript/spellbook-client \
  --additional-properties=fileNaming=camelCase,stringEnums=true
