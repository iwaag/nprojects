# Development Notes

## Git Source of Truth and App Boundaries

The current service repository catalog is stored in the separate `nauto` repository:

```text
nauto/
├── jobs/
└── seed/
    ├── desired_services.yaml
    ├── home_cluster.yaml
    └── service_repositories.yaml
```

Using Git as the source of truth is intentional and useful. It keeps service intent reviewable, versioned, and easy to audit before the data model is stable enough to become a first-class Nautobot database model.

However, a Nautobot App should not permanently depend on knowing where another Git repository has been checked out on disk. After installation, this App normally lives under Python `site-packages`, while the `nauto` Git repository may be checked out by Nautobot's Git repository sync mechanism, by an operator, or by a deployment system. Those paths are environment-specific.

For that reason, direct file-path loading of `nauto/seed/service_repositories.yaml` is a temporary bootstrap mechanism, not the desired long-term architecture.

## Current Bootstrap Design

The first implementation reads the YAML file directly so the App can display repository input rows without introducing database models or migrations.

The path must be provided explicitly in Nautobot configuration:

```python
PLUGINS_CONFIG = {
    "nautobot_service_catalog": {
        "service_repositories_file": "/absolute/path/to/nauto/seed/service_repositories.yaml",
    },
}
```

This keeps the coupling visible and deployment-controlled. The App does not guess the `nauto` checkout location from its own package path.

The environment variable `NAUTOBOT_SERVICE_REPOSITORIES_FILE` is kept as a secondary override for simple local testing.

## Preferred Evolution

The target architecture should keep Git as the source of truth while avoiding direct path coupling from the App to the `nauto` repository.

Recommended progression:

1. Keep `nauto/seed/service_repositories.yaml` as the reviewed Git source of truth.
2. Add an App Job that imports that YAML into App-owned models such as `ServiceRepository`.
3. Render GUI pages from App models instead of directly rendering YAML.
4. Keep YAML import/export compatibility while the workflow is stabilizing.
5. Later, integrate with Nautobot's Git repository sync or datasource content lifecycle so Git sync can trigger App-managed imports.

Conceptually:

```text
Git source of truth
        |
        v
Nautobot Git sync / App import Job
        |
        v
App-owned Nautobot models
        |
        v
GUI, API, Jobs, placement analysis
```

This preserves the benefits of Git while letting the App own its UI, API, permissions, validation, and future analysis workflows.

## Design Rule

Treat `nauto/seed/*.yaml` as source data.

Treat `nprojects/nautobot_service_catalog` as the application layer that imports, displays, validates, and eventually analyzes that source data.

Avoid making the App's internal behavior depend on the physical checkout path of the `nauto` repository except during this initial bootstrap phase.

## Current Model Import Boundary

The DB-backed workflow is split into two Jobs:

```text
Import Service Repositories
Analyze and Import Service Candidates
```

The first Job only imports YAML rows into `ServiceRepository`. It does not fetch
remote repositories.

The second Job analyzes enabled `ServiceRepository` rows and persists
`DesiredServiceCandidate` and `ServiceDependency`. Dependencies are sourced from
the Phase 2.1 `dependencies` output and remain unresolved by default.

Repeated imports should not create duplicates:

```text
ServiceRepository      key: url
DesiredServiceCandidate key: source_repository + catalog namespace/name/type
ServiceDependency       key: source_service + kind + namespace + name
```

## Migration Verification

The initial migration is checked into the App, but this development workspace
does not include Nautobot or Django. After installing into the real Nautobot
environment, verify the checked-in migration against the installed Nautobot
version:

```bash
nautobot-server makemigrations nautobot_service_catalog --check --dry-run
nautobot-server migrate nautobot_service_catalog
```

If `makemigrations --check --dry-run` reports changes, regenerate the migration
inside that Nautobot environment and review only the App model differences.
