# Development Notes

## Current Boundary

`nautobot_intent_catalog` is the application layer for cluster intent. The code
currently analyzes Git-backed intent sources and persists desired service,
dependency, node, and endpoint records. Package, AppConfig, URL base, settings
key, Job names, and YAML loader names use Intent Catalog terminology.

The App should not depend on the physical checkout path of another repository.
When a YAML input file is needed during local development, provide it explicitly:

```python
PLUGINS_CONFIG = {
    "nautobot_intent_catalog": {
        "intent_sources_file": "/absolute/path/to/nauto/seed/intent_sources.yaml",
    },
}
```

For simple local testing, the equivalent environment variable is:

```bash
export NAUTOBOT_INTENT_SOURCES_FILE=/absolute/path/to/nauto/seed/intent_sources.yaml
```

No fallback to old plugin names, old setting keys, old import paths, or old URL
aliases should be added. If an implementation change leaves obsolete database
tables or configuration behind, document the manual cleanup in `README.md`
instead of adding automatic deletion code.

## Local Tests

This workspace does not include Nautobot or Django, so the fast checks focus on
loader, importer, and analysis code that can run without Nautobot:

```bash
python3 -m unittest discover -s nautobot_intent_catalog/tests
```

## Nautobot Verification

After installing into a real Nautobot environment, verify migrations there:

```bash
nautobot-server makemigrations nautobot_intent_catalog --check --dry-run
nautobot-server migrate nautobot_intent_catalog
```

If `makemigrations --check --dry-run` reports changes, regenerate the migration
inside that Nautobot environment and review only the App model differences.

## Rename Cleanup Checks

Before completing a rename-oriented step, run searches for old implementation
names. The concrete cleanup search patterns and manual removal targets are
documented in `README.md` under `Manual Cleanup During Rename`.

```bash
rg "old implementation name pattern"
```

Only migration history notes or explicit manual cleanup documentation should
refer to removed names.
