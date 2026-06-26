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
  echo "deleted_files=[]" >> "$GITHUB_OUTPUT"
else
  echo "Diffing assets against $PREV_TAG"
  # core.quotePath=false prevents git from quoting paths that contain spaces
  CHANGED_FILES=$(git -c core.quotePath=false diff --name-only --diff-filter=AM "$PREV_TAG" HEAD \
    | grep -E "(${ASSET_DIRS})/.*\.json$" | jq -R . | jq -sc . || echo "[]")
  {
    echo "changed_files<<EOF"
    echo "$CHANGED_FILES"
    echo "EOF"
  } >> "$GITHUB_OUTPUT"
  count=$(echo "$CHANGED_FILES" | jq 'length')
  if [ "$count" -gt 0 ]; then
    echo "Asset changes detected"
    echo "has_asset_changes=true" >> "$GITHUB_OUTPUT"
  else
    echo "No asset changes detected — skipping asset deploy"
    echo "has_asset_changes=false" >> "$GITHUB_OUTPUT"
  fi

  DELETED_FILES=$(git -c core.quotePath=false diff --name-only --diff-filter=D "$PREV_TAG" HEAD \
    | grep -E "(${ASSET_DIRS})/.*\.json$" | jq -R . | jq -sc . || echo "[]")
  {
    echo "deleted_files<<EOF"
    echo "$DELETED_FILES"
    echo "EOF"
  } >> "$GITHUB_OUTPUT"
  echo "Deleted assets: $(echo "$DELETED_FILES" | jq 'length')"
fi

# ── Integration spec diff ─────────────────────────────────────────────────────
if [ -z "$PREV_TAG" ]; then
  echo "No previous tag — all integration specs will be deployed"
  CHANGED_SPECS=$(find . -path "*/${INTEGRATION_MODELS_DIR}/*.json" -type f | jq -R . | jq -sc .)
  echo "deleted_specs=[]" >> "$GITHUB_OUTPUT"
else
  echo "Diffing integration specs against $PREV_TAG"
  CHANGED_SPECS=$(git -c core.quotePath=false diff --name-only --diff-filter=AM "$PREV_TAG" HEAD \
    | grep "${INTEGRATION_MODELS_DIR}/.*\.json$" | jq -R . | jq -sc . || echo "[]")

  DELETED_SPECS=$(git -c core.quotePath=false diff --name-only --diff-filter=D "$PREV_TAG" HEAD \
    | grep "${INTEGRATION_MODELS_DIR}/.*\.json$" | jq -R . | jq -sc . || echo "[]")
  {
    echo "deleted_specs<<EOF"
    echo "$DELETED_SPECS"
    echo "EOF"
  } >> "$GITHUB_OUTPUT"
  echo "Deleted specs: $(echo "$DELETED_SPECS" | jq 'length')"
fi

# Use heredoc format — GitHub Actions rejects bare JSON arrays as output values
{
  echo "changed_specs<<EOF"
  echo "$CHANGED_SPECS"
  echo "EOF"
} >> "$GITHUB_OUTPUT"
count=$(echo "$CHANGED_SPECS" | jq 'length')
if [ "$count" -gt 0 ]; then
  echo "Found $count changed spec(s)"
  echo "has_spec_changes=true" >> "$GITHUB_OUTPUT"
else
  echo "No integration spec changes detected — skipping integration deploy"
  echo "has_spec_changes=false" >> "$GITHUB_OUTPUT"
fi
