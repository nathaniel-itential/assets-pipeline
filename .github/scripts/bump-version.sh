#!/usr/bin/env bash
set -euo pipefail

# Color-coded logging
log_info()  { echo -e "\033[0;32m[INFO]\033[0m  $*"; }
log_warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*"; }
log_error() { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; }

# Usage
if [[ "${1:-}" == "--help" ]]; then
  echo "Usage: $0 [--help]"
  echo ""
  echo "Calculates the next semantic version based on Conventional Commits"
  echo "since the last production tag and creates a release candidate tag."
  exit 0
fi

# Find the latest production release tag (v* excluding -rc tags), default to v0.0.0
latest_tag=$(git tag --list 'v*' --sort=-v:refname | grep -v '\-rc' | head -n 1 || true)
if [ -z "$latest_tag" ]; then
  latest_tag="v0.0.0"
  log_warn "No previous production tag found. Defaulting to $latest_tag"
else
  log_info "Latest production tag: $latest_tag"
fi

# Parse current version numbers
version="${latest_tag#v}"
IFS='.' read -r major minor patch <<< "$version"

# Scan commit messages since the latest tag for conventional commit prefixes
if [ "$latest_tag" = "v0.0.0" ]; then
  commits=$(git log --pretty=format:"%s" 2>/dev/null || true)
else
  commits=$(git log "${latest_tag}..HEAD" --pretty=format:"%s" 2>/dev/null || true)
fi

log_info "Commits since $latest_tag:"
echo "$commits"
echo ""

# Determine the highest-priority bump type
bump="patch"
while IFS= read -r msg; do
  [ -z "$msg" ] && continue
  if echo "$msg" | grep -qE '^feat(\(.*\))?!:|BREAKING CHANGE:'; then
    bump="major"
    break
  elif echo "$msg" | grep -qE '^feat(\(.*\))?:'; then
    if [ "$bump" != "major" ]; then
      bump="minor"
    fi
  fi
done <<< "$commits"

log_info "Bump type: $bump"

# Calculate the next version
case "$bump" in
  major)
    major=$((major + 1))
    minor=0
    patch=0
    ;;
  minor)
    minor=$((minor + 1))
    patch=0
    ;;
  patch)
    patch=$((patch + 1))
    ;;
esac

next_version="v${major}.${minor}.${patch}"
log_info "Next version: $next_version"

# Check for existing RC tags for this version and determine RC number
existing_rcs=$(git tag --list "${next_version}-rc.*" --sort=-v:refname | head -n 1 || true)
if [ -z "$existing_rcs" ]; then
  rc_num=1
else
  rc_num=$(echo "$existing_rcs" | sed "s/${next_version}-rc\.\([0-9]*\)/\1/")
  rc_num=$((rc_num + 1))
fi

rc_tag="${next_version}-rc.${rc_num}"
log_info "Creating RC tag: $rc_tag"

# Create and push the annotated tag
git tag -a "$rc_tag" -m "Release candidate ${rc_tag}"
git push origin "$rc_tag"

log_info "Successfully pushed tag: $rc_tag"

# Write outputs for GitHub Actions
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "rc_tag=$rc_tag" >> "$GITHUB_OUTPUT"
  echo "version=$next_version" >> "$GITHUB_OUTPUT"
  echo "bump_type=$bump" >> "$GITHUB_OUTPUT"
fi
