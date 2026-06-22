# Asset Pipeline

A repository based off of the Itential asset repository template that manages a library of itential assets using Git and automatic promotion through CI/CD pipelines.

> **Currently supported:** GitHub Actions, GitLab CI/CD

## How It Works

This repository uses a tag-based promotion model. CI/CD pipelines execute the shared scripts in `pipelines/scripts/` to automatically version, tag, and deploy assets across environments.

> **Note:** Throughout this documentation, `main` is used as the default branch name. If your repository uses `master`, substitute `master` wherever `main` appears.

```text
 develop branch       main/master branch           Staging                Production
 ──────────────       ──────────────────           ───────                ──────────
       |                       |                      |                       |
   commit work                 |                      |                       |
       |                       |                      |                       |
   open PR ──── merge ────►    |                      |                       |
       |                   auto-rc-tag                |                       |
       |                   creates v1.1.0-rc.1        |                       |
       |                       |                      |                       |
       |                  tag push triggers           |                       |
       |                  asset-promotion ────────► deploy to staging         |
       |                       |                      |                       |
       |                       |                  validate & test             |
       |                       |                      |                       |
       |  ◄───── fix in develop ◄──────────── issues found                   |
       |                       |                      |                       |
   open PR ──── merge ────►    |                      |                       |
       |                   auto-rc-tag                |                       |
       |                   creates v1.1.0-rc.2        |                       |
       |                       |                      |                       |
       |                  tag push triggers           |                       |
       |                  asset-promotion ────────► re-deploy to staging      |
       |                       |                      |                       |
       |                       |                  validate & test             |
       |                       |                      |                       |
       |                  manual tag push              |                       |
       |                     v1.1.0                    |                       |
       |                       |                      |                       |
       |                  asset-promotion ─────────────────────────► deploy to prod
```

### Automatic Versioning

The `auto-rc-tag` step in the diagram above uses [Conventional Commits](https://www.conventionalcommits.org/) to determine the next semantic version. The script scans all commit messages since the last production tag and picks the highest-priority bump:

| Bump Type | Commit Prefix | Example | Version Change |
| --- | --- | --- | --- |
| **Major** | `feat!:` or `feat(scope)!:` or `BREAKING CHANGE:` | `feat!: redesign asset schema` | `v1.2.3` → `v2.0.0` |
| **Minor** | `feat:` or `feat(scope):` | `feat: add lifecycle manager support` | `v1.2.3` → `v1.3.0` |
| **Patch** | Anything else (`fix:`, `chore:`, `docs:`, etc.) | `fix: correct automation import` | `v1.2.3` → `v1.2.4` |

If any commit in the range is a breaking change, the bump is **major** regardless of other commits. If no `feat` or breaking change commits are found, the bump defaults to **patch**.

Once the version is determined, the script creates a release candidate tag (e.g., `v1.3.0-rc.1`). If an RC tag for that version already exists then the RC number is incremented (e.g., `v1.3.0-rc.2`).

Tags are used by this pipeline to determine what to import into the platform. For staging, the last 2 tags with `-rc` are git diffed. For production, the last 2 tags without `-rc` are git diffed. 

## Repository Structure

```text
.
├── Asset Bundle/              # Current asset bundle structure
|   ├── configuration_manager/
|   ├── integration_models/
|   ├── lifecycle_manager/
|   ├── operations_manager/
|   └── studio/
│
├── github/                # GitHub Actions pipeline definitions
|   ├── scripts/               # Shared deployment scripts
│   │    ├── deploy.py
│   │    ├── bump-version.sh
|   │    ├── deploy_integrations.sh      # uses ipctl to deploy integrations
|   │    └── diff.sh                     # git diff logic for stg/prod for integrations and assets
|   └── workflows/
│       ├── promotion.yaml               # central deployment script for both integrations and assets
│       └── auto-rc-tag.yaml
| 
└──  workflows             # yaml files to determine github actions
     ├── integration-promotion.yaml      # runs first, triggered by tag (-rc means stg, else prod)
     ├── asset-promotion.yaml            # runs after successful completion of integration promotion, tag decides env (-rc means stg, else prod)
     └── auto-rc-tag.yaml             

└── README.md
```

### `Asset Bundle/`

An asset bundle that holds the assets to be imported. It is organized by vendor:

```text
└── Asset Bundle/              # Current asset bundle structure
    ├── configuration_manager/
    ├── integration_models/
    ├── lifecycle_manager/
    ├── operations_manager/
    └── studio/
```

You can add multiple bundles at the repo root and the deploy script will auto-discover them.

### `pipelines/`

Contains CI/CD pipeline definitions organized by platform, along with shared scripts that are called by each pipeline.

**`pipelines/scripts/`** — Shared scripts used across all platforms:

- **`deploy.py`** — Connects to an Itential Platform instance and imports all added or modified assets from the repository. Currently supports Studio projects, Operations Manager automations, Lifecycle Manager, and Configuration Manager assets.
- **`bump-version.sh`** — Calculates the next semantic version based on commit messages and creates release candidate tags
- **`deploy_integrations.sh`** — Connects to the Itential Platform instance and imports all added or modified assets from the repository. Uses IPCTL.
- **`diff.py`** — Calculates added/modified integration and asset files based on two most recent tags. (-rc for stg, else prod)


## Adding a New Asset Bundle

1. Create a new directory at the repo root — not nested inside other directories — (e.g., `My Use Case Bundle/`)
2. Add subdirectories for each asset type and place your exported JSON files inside
3. Commit and push to your develop branch

```text
My Use Case Bundle/
└── Asset Bundle/              # Current asset bundle structure
    ├── configuration_manager/
    ├── integration_models/
    ├── lifecycle_manager/
    ├── operations_manager/
    └── studio/
```

The deploy script auto-discovers any bundles matching this structure. No additional configuration is needed.

## License

Copyright 2026 Itential, LLC

This project is licensed under the GNU General Public License v3.0 — see the [LICENSE](LICENSE) file for details.v
