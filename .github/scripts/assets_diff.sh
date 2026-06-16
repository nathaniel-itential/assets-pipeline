#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" != "--stg" ] && [ "${1:-}" != "--prod" ]; then
  echo "Usage: assets_diff.sh [--stg|--prod]"
  exit 1
fi

CURRENT_TAG=$(git tag --points-at HEAD | head -1 || true)

if [ "$1" = "--prod" ]; then
  PREV_TAG=$(git tag --sort=-creatordate \
    | grep -v "^${CURRENT_TAG}$" \
    | grep -v "\-rc" \
    | head -1 || true)
else
  PREV_TAG=$(git tag --sort=-creatordate \
    | grep -v "^${CURRENT_TAG}$" \
    | head -1 || true)
fi

if [ -z "$PREV_TAG" ]; then
  echo "No previous tag — processing all assets"
  echo "changed_files=" >> "$GITHUB_OUTPUT"
  echo "has_changes=true" >> "$GITHUB_OUTPUT"
else
  echo "Diffing against $PREV_TAG"
  # Get all added/modified files between the previous tag and HEAD, output as a JSON array
  CHANGED=$(git diff --name-only --diff-filter=AM "$PREV_TAG" HEAD \
    | jq -R . | jq -sc .)
  echo "changed_files=$CHANGED" >> "$GITHUB_OUTPUT"

  # Check if any changed files are actual asset files
  if echo "$CHANGED" | jq -r '.[]' \
    | grep -qE "(Projects|Automations|LCM Resource Models|Golden Configurations)/.*\.json$"; then
    echo "has_changes=true" >> "$GITHUB_OUTPUT"
  else
    echo "No asset changes detected — skipping"
    echo "has_changes=false" >> "$GITHUB_OUTPUT"
  fi
fi
