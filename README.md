# Nautobot Service Catalog

Nautobot App for displaying, analyzing, and importing cluster service repository
catalog data.

The App still treats the existing `nauto/seed/service_repositories.yaml` file as
source data during the bootstrap phase. Repository rows can be imported into
App-owned Nautobot models so the GUI can use standard object views, change
logging, permissions, and future API integration.

## Install

Install the package into the same Python environment as Nautobot:

```bash
pip install -e /path/to/nprojects
```

Enable the App in `nautobot_config.py`:

```python
PLUGINS = [
    "nautobot_service_catalog",
]

PLUGINS_CONFIG = {
    "nautobot_service_catalog": {
        "service_repositories_file": "/path/to/nauto/seed/service_repositories.yaml",
    },
}
```

The `service_repositories_file` setting is the recommended way to point the App
at the existing catalog. If the setting is omitted, the App checks this
environment variable:

```bash
export NAUTOBOT_SERVICE_REPOSITORIES_FILE=/path/to/nauto/seed/service_repositories.yaml
```

If neither is set, the development fallback is:

```text
./nauto/seed/service_repositories.yaml
```

relative to Nautobot's current working directory.

After restarting Nautobot, open:

```text
/plugins/service-catalog/repositories/
```

Run migrations after installing or upgrading the App:

```bash
nautobot-server migrate nautobot_service_catalog
```

## Current Scope

- Imports repository input rows from YAML into `ServiceRepository`.
- Persists generated `DesiredServiceCandidate` records from repository analysis.
- Persists normalized `ServiceDependency` rows from Backstage `spec.dependsOn`.
- Keeps a diagnostic YAML source view at `/plugins/service-catalog/repositories/source-yaml/`.
- Provides a dry-run Nautobot Job named `Analyze Service Repositories`.
- Detects Backstage `Component` catalog entries for `service`, `website`, and `worker` candidates.
- Includes Backstage `spec.dependsOn` entries as normalized dependency metadata.
- Handles empty, missing, and malformed YAML without raising a server error from the view.
- Does not replace the Git YAML source of truth yet.
- Does not perform dependency readiness or placement review.

## Repository Analysis Preview

After enabling the App, open Nautobot's Jobs UI and run:

```text
Analyze Service Repositories
```

The Job reads the configured `service_repositories.yaml`, fetches only selected
catalog and basic files, and logs a dry-run analysis summary. It does not write
`desired_services.generated.yaml` and does not create database records.

Generated candidates include a `dependencies` list derived from Backstage
`spec.dependsOn`. Dependency refs are normalized into `raw_ref`, `kind`,
`namespace`, `name`, `dependency_type`, and `resolution_status`.

For local checks that do not require Nautobot:

```bash
python3 -m unittest discover -s nautobot_service_catalog/tests
```

## DB Import Workflow

Run these Jobs from Nautobot's Jobs UI:

```text
Import Service Repositories
```

This reads the configured YAML file and upserts `ServiceRepository` rows by URL.
It does not fetch remote repositories.

Then run:

```text
Analyze and Import Service Candidates
```

This reads enabled `ServiceRepository` rows, runs the same lightweight analyzer
used by the dry-run Job, and persists:

- `DesiredServiceCandidate`
- `ServiceDependency`
- repository `last_analysis_*` summary fields

Re-running the import Jobs is intended to be idempotent. Candidate dependencies
are replaced from the latest analysis output for that candidate.

## Dependency Handling

Backstage dependency refs are stored as unresolved metadata.

Examples:

```text
resource:default/minio-s3
resource:default/postgresql
component:default/keycloak
```

The App does not yet decide whether a `resource:*` dependency is external,
shared, or deployable. It also does not auto-resolve `component:*` refs to other
service candidates yet. Those decisions belong to later placement and readiness
work.
