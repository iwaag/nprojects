# Nautobot Service Catalog

Minimal Nautobot App for displaying the cluster service repository input catalog.

The first implementation is intentionally read-only. It loads `service_repositories`
from the existing `nauto/seed/service_repositories.yaml` file and renders the entries
in Nautobot's GUI.

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

## Current Scope

- Displays repository input rows from YAML.
- Provides a dry-run Nautobot Job named `Analyze Service Repositories`.
- Detects Backstage `Component` catalog entries for `service`, `website`, and `worker` candidates.
- Includes Backstage `spec.dependsOn` entries as normalized dependency metadata.
- Handles empty, missing, and malformed YAML without raising a server error from the view.
- Does not create database models or migrations.
- Does not persist analysis results.

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
