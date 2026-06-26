#!/usr/bin/env python3
"""
Incrementally updates README.md based on added, modified, and deleted
asset files in the PR diff.
"""

import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

SECTION_MAP = {
    'integration_models': 'Integration Models',
    'studio': 'Studio Projects',
    'operations_manager': 'Operations Manager',
    'lifecycle_manager': 'Lifecycle Manager',
    'configuration_manager': 'Configuration Manager',
}

SECTION_ORDER = [
    'Integration Models',
    'Studio Projects',
    'Operations Manager',
    'Lifecycle Manager',
    'Configuration Manager',
]


def is_asset_file(path: str) -> bool:
    return path.endswith('.json') and Path(path).parent.name in SECTION_MAP


def get_section(path: str) -> str | None:
    return SECTION_MAP.get(Path(path).parent.name)


def get_display_name(path: str) -> str:
    try:
        with open(path) as f:
            data = json.load(f)
        if 'integration_models' in path:
            return data.get('info', {}).get('title') or Path(path).stem
        return data.get('name') or Path(path).stem
    except Exception:
        return Path(path).stem


def make_url(repo: str, path: str) -> str:
    return f'https://github.com/{repo}/blob/main/{quote(path, safe="/")}'


def get_pr_diff(base_sha: str, head_sha: str) -> tuple[list, list, list]:
    result = subprocess.run(
        ['git', 'diff', '--name-status', '--no-renames', f'{base_sha}..{head_sha}'],
        capture_output=True, text=True, check=True,
    )
    added, modified, deleted = [], [], []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        status, path = parts
        if not is_asset_file(path):
            continue
        if status == 'A':
            added.append(path)
        elif status == 'M':
            modified.append(path)
        elif status == 'D':
            deleted.append(path)
    return added, modified, deleted


def parse_readme(content: str, repo: str) -> dict[str, dict[str, str]]:
    """Parse README into {section: {path: name}}."""
    entries: dict[str, dict[str, str]] = defaultdict(dict)
    current_section = None
    base_url = f'https://github.com/{repo}/blob/main/'

    for line in content.splitlines():
        if line.startswith('## '):
            current_section = line[3:].strip()
        elif current_section and line.startswith('- ['):
            match = re.match(
                r'- \['      # bullet + opening bracket
                r'([^\]]+)'  # capture: display name (anything except ])
                r'\]\('      # closing bracket + opening paren
                r'([^)]+)'   # capture: URL (anything except ))
                r'\)',        # closing paren
                line,
            )
            if match:
                name, url = match.group(1), match.group(2)
                if url.startswith(base_url):
                    path = url[len(base_url):].replace('%20', ' ')
                    entries[current_section][path] = name
    return entries


def generate_readme(entries: dict[str, dict[str, str]], repo: str) -> str:
    lines = []
    for section in SECTION_ORDER:
        section_entries = entries.get(section, {})
        if not section_entries:
            continue
        lines.append(f'## {section}')
        for path, name in sorted(section_entries.items(), key=lambda x: x[1].lower()):
            lines.append(f'- [{name}]({make_url(repo, path)})')
        lines.append('')
    return '\n'.join(lines).rstrip('\n') + '\n'


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    base_sha = os.environ['BASE_SHA']
    head_sha = os.environ['HEAD_SHA']

    readme_path = Path('README.md')
    existing = readme_path.read_text() if readme_path.exists() else ''
    entries = parse_readme(existing, repo)

    added, modified, deleted = get_pr_diff(base_sha, head_sha)

    for path in deleted:
        section = get_section(path)
        if section and path in entries.get(section, {}):
            del entries[section][path]
            print(f'  removed: {path}')

    for path in added + modified:
        section = get_section(path)
        if not section:
            continue
        name = get_display_name(path)
        entries[section][path] = name
        print(f'  {"added" if path in added else "updated"}: {path} → {name}')

    readme_path.write_text(generate_readme(entries, repo))
    print(f'README.md updated ({len(added)} added, {len(modified)} modified, {len(deleted)} deleted)')


if __name__ == '__main__':
    main()
