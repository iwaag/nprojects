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

For Job changes, verify discovery inside the same Nautobot environment:

```python
import nautobot_intent_catalog.jobs as j
print([job.__name__ for job in j.jobs])
```

If new Jobs are missing, check imports before UI permissions. Job modules should
use fully qualified Nautobot imports such as `nautobot.dcim.models`,
`nautobot.ipam.models`, and `nautobot.virtualization.models`; if Nautobot is
installed, broken imports should fail loudly instead of falling back to
`jobs = ()`. Register app Jobs with `register_jobs(*jobs)`, then run the normal
Nautobot upgrade/sync workflow and restart both web and worker processes.

## Nautobot UI Compatibility

When adding object views for app models, either create the expected
`{app_label}/{model_name}.html` template or set `template_name` explicitly.
Generic `ObjectView` redirects can otherwise fail after a successful database
write because the default detail template is missing.

On Nautobot 3.1.x, `ButtonsColumn` includes a changelog action by default. If a
model does not provide a changelog URL/view, pass an explicit button set such as
`buttons=("edit", "delete")`. Also check related `tables.LinkColumn()` fields:
linked models need working `get_absolute_url()` targets and detail templates.

## Nautobot Model Compatibility

Do not assume display properties are ORM fields. For example, Nautobot 3.1.x
`IPAddress` uses concrete fields such as `host` and `mask_length`, so ORM calls
should order or filter on those fields instead of `address`.

Keep cross-version object conversion at the boundary where Nautobot models are
turned into app facts. Prefer small compatibility helpers there over scattering
direct assumptions such as `IPAddress.address` through evaluation logic.

## Rename Cleanup Checks

Before completing a rename-oriented step, run searches for old implementation
names. The concrete cleanup search patterns and manual removal targets are
documented in `README.md` under `Manual Cleanup During Rename`.

```bash
rg "old implementation name pattern"
```

Only migration history notes or explicit manual cleanup documentation should
refer to removed names.
