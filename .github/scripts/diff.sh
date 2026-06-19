#!/usr/bin/env bash
set -euo pipefail

CURRENT_TAG="${GITHUB_REF_NAME}"
ASSET_DIRS="studio|operations_manager|lifecycle_manager|configuration_manager"
INTEGRATION_MODELS_DIR="integration_models"

# Pick PREV_TAG based on whether this is an RC or release tag.
# Deploy jobs determine environment via contains(github.ref, '-rc') in their if: conditions.
if echo "$CURRENT_TAG" | grep -q '\-rc'; then
  PREV_TAG=$(git tag --sort=-creatordate | grep '\-rc' | grep -v "^${CURRENT_TAG}$" | head -1 || true)
else
  PREV_TAG=$(git tag --sort=-creatordate | grep '^v' | grep -v '\-rc' | grep -v "^${CURRENT_TAG}$" | head -1 || true)
fi

# ── Asset diff ────────────────────────────────────────────────────────────────
if [ -z "$PREV_TAG" ]; then
  echo "No previous tag — all assets will be deployed"
  echo "changed_files=" >> "$GITHUB_OUTPUT"
  echo "has_asset_changes=true" >> "$GITHUB_OUTPUT"
else
  echo "Diffing assets against $PREV_TAG"
  CHANGED_FILES=$(git diff --name-only --diff-filter=AM "$PREV_TAG" HEAD | jq -R . | jq -sc .)
  echo "changed_files=$CHANGED_FILES" >> "$GITHUB_OUTPUT"
  if echo "$CHANGED_FILES" | jq -r '.[]' | grep -qE "(${ASSET_DIRS})/.*\.json$"; then
    echo "Asset changes detected"
    echo "has_asset_changes=true" >> "$GITHUB_OUTPUT"
  else
    echo "No asset changes detected — skipping asset deploy"
    echo "has_asset_changes=false" >> "$GITHUB_OUTPUT"
  fi
fi

# ── Integration spec diff ─────────────────────────────────────────────────────
if [ -z "$PREV_TAG" ]; then
  echo "No previous tag — all integration specs will be deployed"
  CHANGED_SPECS=$(find . -path "*/${INTEGRATION_MODELS_DIR}/*.json" -type f | jq -R . | jq -sc .)
else
  echo "Diffing integration specs against $PREV_TAG"
  CHANGED_SPECS=$(git diff --name-only --diff-filter=AM "$PREV_TAG" HEAD \
    | grep "${INTEGRATION_MODELS_DIR}/.*\.json$" | jq -R . | jq -sc . || echo "[]")
fi

echo "changed_specs=$CHANGED_SPECS" >> "$GITHUB_OUTPUT"
count=$(echo "$CHANGED_SPECS" | jq 'length')
if [ "$count" -gt 0 ]; then
  echo "Found $count changed spec(s)"
  echo "has_spec_changes=true" >> "$GITHUB_OUTPUT"
else
  echo "No integration spec changes detected — skipping integration deploy"
  echo "has_spec_changes=false" >> "$GITHUB_OUTPUT"
fi
