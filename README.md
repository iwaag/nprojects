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
```

By default, the App looks for:

```text
../nauto/seed/service_repositories.yaml
```

relative to the `nprojects` repository root. Override this path when needed:

```bash
export NAUTOBOT_SERVICE_REPOSITORIES_FILE=/path/to/nauto/seed/service_repositories.yaml
```

After restarting Nautobot, open:

```text
/plugins/service-catalog/repositories/
```

## Current Scope

- Displays repository input rows from YAML.
- Handles empty, missing, and malformed YAML without raising a server error from the view.
- Does not create database models or migrations.
- Does not fetch or analyze remote repository contents.
