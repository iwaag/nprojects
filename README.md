# Nautobot Intent Catalog

Nautobot App for importing and analyzing cluster intent. The current code
supports intent sources, desired services, and desired dependencies. Planned
work will add desired nodes, desired endpoints, evaluations, and deterministic
exports.

## Install

Install the package into the same Python environment as Nautobot:

```bash
pip install -e /path/to/nintent
```

Enable the App in `nautobot_config.py`:

```python
PLUGINS = [
    "nautobot_intent_catalog",
]

PLUGINS_CONFIG = {
    "nautobot_intent_catalog": {
        "intent_sources_file": "/path/to/nauto/seed/intent_sources.yaml",
    },
}
```

If `intent_sources_file` is omitted, the App checks:

```bash
export NAUTOBOT_INTENT_SOURCES_FILE=/path/to/nauto/seed/intent_sources.yaml
```

If neither is set, the development fallback is:

```text
./nauto/seed/intent_sources.yaml
```

relative to Nautobot's current working directory.

After restarting Nautobot, open:

```text
/plugins/intent-catalog/sources/
```

Run migrations after installing or upgrading the App:

```bash
nautobot-server migrate nautobot_intent_catalog
```

## Current Scope

- Imports `intent_sources` YAML rows into `IntentSource`.
- Persists generated `DesiredService` records from source analysis.
- Persists normalized `DesiredDependency` rows from Backstage `spec.dependsOn`.
- Keeps a diagnostic YAML source view at `/plugins/intent-catalog/sources/source-yaml/`.
- Provides dry-run and import Nautobot Jobs for intent source analysis.
- Detects Backstage `Component` catalog entries for `service`, `website`, and `worker` desired services.
- Does not perform desired-node, desired-endpoint, gap evaluation, or remediation review yet.

## Intent Source YAML

The loader accepts only the current `intent_sources` root. Older input roots are
not loaded by compatibility code.

```yaml
intent_sources:
  - url: https://github.com/example/service
    enabled: true
    ref: main
    owner: platform
    service_hint: service
    catalog_paths:
      - catalog-info.yaml
    basic_file_paths:
      - README.md
    raw_url_template: https://raw.example.test/{ref}/{path}
```

Manual conversion from an older YAML shape is intentionally mechanical: rename
the top-level list key to `intent_sources` and keep each item field that still
applies. Fields such as `catalog_paths`, `basic_file_paths`, and
`raw_url_template` are stored in `IntentSource.source_config` after import.

For local checks that do not require Nautobot:

```bash
python3 -m unittest discover -s nautobot_intent_catalog/tests
```

## Manual Cleanup During Rename

This App is intentionally moving without backward compatibility artifacts. It
does not provide old plugin names, old URL aliases, old settings fallbacks, or
automatic cleanup migrations.

When replacing an older installation, review your Nautobot environment and
manually remove obsolete data only after exporting anything you need to keep.
Typical cleanup items are:

- old plugin entries in `PLUGINS`
- old plugin configuration keys in `PLUGINS_CONFIG`
- old App database tables and migration history rows
- old package installations from the Python environment

The exact SQL or operational commands depend on the Nautobot deployment and
database backend, so perform cleanup from an environment-specific maintenance
plan and backup first.
