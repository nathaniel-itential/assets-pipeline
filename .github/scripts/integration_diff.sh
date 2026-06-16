#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" != "--stg" ] && [ "${1:-}" != "--prod" ]; then
  echo "Usage: integration_diff.sh [--stg|--prod]"
  exit 1
fi

if [ "$1" = "--prod" ]; then
  PREV_TAG=$(git tag --sort=-creatordate \
    | grep -v "^${GITHUB_REF_NAME}$" \
    | grep -v "\-rc" \
    | head -1 || true)
else
  PREV_TAG=$(git tag --sort=-creatordate \
    | grep -v "^${GITHUB_REF_NAME}$" \
    | head -1 || true)
fi

if [ -z "$PREV_TAG" ]; then
  echo "No previous tag — processing all specs"
  find . -path "*/OpenAPIs/*.json" -type f > /tmp/specs.txt
else
  echo "Diffing against $PREV_TAG"
  # This gets the name of every changed file, and filters to json files inside an OpenAPI folder
  git diff --name-only --diff-filter=AM "$PREV_TAG" HEAD \
    | grep "OpenAPIs/.*\.json$" > /tmp/specs.txt || true
fi

#get count by counting number of lines in specs
count=$(wc -l < /tmp/specs.txt | tr -d ' ')
if [ "$count" -eq 0 ]; then
  echo "No integration changes detected — skipping"
  echo "has_changes=false" >> "$GITHUB_OUTPUT"
else
  echo "Found $count changed spec(s):"
  cat /tmp/specs.txt
  echo "has_changes=true" >> "$GITHUB_OUTPUT"
fi
