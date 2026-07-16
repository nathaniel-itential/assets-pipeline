#!/usr/bin/env bash
set -euo pipefail

BASE_SHA="${BASE_SHA:-}"
ASSET_DIRS="Studio Projects|Agent Projects|Automations|LCM Resource Models|Golden Configs"
INTEGRATION_MODELS_DIR="OpenAPIs"

# ── Asset diff ────────────────────────────────────────────────────────────────
if [ -z "$BASE_SHA" ]; then
  echo "No base SHA — all assets will be deployed"
  echo "changed_files=" >> "$GITHUB_OUTPUT"
  echo "has_asset_changes=true" >> "$GITHUB_OUTPUT"
  echo "deleted_files=[]" >> "$GITHUB_OUTPUT"
else
  echo "Diffing assets against $BASE_SHA"
  # core.quotePath=false prevents git from quoting paths that contain spaces
  CHANGED_FILES=$(git -c core.quotePath=false diff --name-only --diff-filter=AM "$BASE_SHA" HEAD \
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

  DELETED_FILES=$(git -c core.quotePath=false diff --name-only --diff-filter=D "$BASE_SHA" HEAD \
    | grep -E "(${ASSET_DIRS})/.*\.json$" | jq -R . | jq -sc . || echo "[]")
  {
    echo "deleted_files<<EOF"
    echo "$DELETED_FILES"
    echo "EOF"
  } >> "$GITHUB_OUTPUT"
  echo "Deleted assets: $(echo "$DELETED_FILES" | jq 'length')"
fi

# ── Integration spec diff ─────────────────────────────────────────────────────
if [ -z "$BASE_SHA" ]; then
  echo "No base SHA — all integration specs will be deployed"
  CHANGED_SPECS=$(find . -path "*/${INTEGRATION_MODELS_DIR}/*-latest.json" -type f | jq -R . | jq -sc .)
  echo "deleted_specs=[]" >> "$GITHUB_OUTPUT"
else
  echo "Diffing integration specs against $BASE_SHA"
  CHANGED_SPECS=$(git -c core.quotePath=false diff --name-only --diff-filter=AM "$BASE_SHA" HEAD \
    | grep "${INTEGRATION_MODELS_DIR}/.*-latest\.json$" | jq -R . | jq -sc . || echo "[]")

  DELETED_SPECS=$(git -c core.quotePath=false diff --name-only --diff-filter=D "$BASE_SHA" HEAD \
    | grep "${INTEGRATION_MODELS_DIR}/.*-latest\.json$" | jq -R . | jq -sc . || echo "[]")
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
