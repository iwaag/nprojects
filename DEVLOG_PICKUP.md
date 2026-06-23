# Devlog Pickup

## Nautobot 3.1.3 UI compatibility notes

Date: 2026-06-23

### Symptoms

After adding Quick Host Add, object creation succeeded in the database, but UI
pages failed while rendering node/endpoint views.

Observed errors:

- `TemplateDoesNotExist: nautobot_intent_catalog/desirednode.html`
- `NoReverseMatch: Reverse for 'desiredendpoint_changelog' not found`
- Desired Endpoints list showed: `Failed to load table content. The server responded with status: 500`

### Cause

Nautobot generic object views and tables assume more UI plumbing than this app
had implemented.

`ObjectView` resolves its template from the model app label and model name when
`template_name` is not set. For `DesiredNode`, that means:

```text
nautobot_intent_catalog/desirednode.html
```

If the template is missing, redirecting to the object detail page after create
will fail even though the database write succeeded.

Nautobot 3.1.3 `ButtonsColumn` also renders a changelog action by default. The
default button set is effectively:

```text
changelog, edit, delete
```

For app models that only define detail/edit/delete URLs, this causes reverse
lookups such as the following to fail during table rendering:

```text
plugins:nautobot_intent_catalog:desiredendpoint_changelog
```

This is especially easy to hit with older plugin-style code because list tables
may have worked before a Nautobot upgrade, then start failing once the default
action column expects changelog routes.

### Fix applied here

- Added `nautobot_intent_catalog/templates/nautobot_intent_catalog/desirednode.html`.
- Added `nautobot_intent_catalog/templates/nautobot_intent_catalog/desiredendpoint.html`.
- Changed all app `ButtonsColumn(...)` usages to explicitly use only:

```python
("edit", "delete")
```

### Future checklist

When adding a Nautobot `ObjectView` for an app model, do one of the following:

- create the expected `{app_label}/{model_name}.html` template, or
- set `template_name` explicitly on the view.

When using `ButtonsColumn` on Nautobot 3.1.x or later, either:

- define the expected changelog URL/view for the model, or
- pass an explicit button set such as `buttons=("edit", "delete")`.

Also check related table columns using `tables.LinkColumn()`. They rely on the
related object's `get_absolute_url()`, so the target detail route and template
must exist if users can click through.

## Nautobot 2.x/3.x Job registration notes

Date: 2026-06-23

### Symptoms

After adding `Export dnsmasq Records`, the Job class existed in
`nautobot_intent_catalog/jobs.py`, but the job did not appear in the Nautobot
Jobs list after reload/post-upgrade.

### Cause

Defining Job classes and a module-level `jobs = (...)` tuple is not sufficient
for current Nautobot job discovery. Nautobot 2.x/3.x apps should register jobs
from the jobs module with `register_jobs()`.

This can be confusing because older Job records may still be present in the
database and visible in the UI, while newly added Job classes do not get
created unless they are registered during module import.

### Fix applied here

Import `register_jobs` from `nautobot.apps.jobs` and call it after all Job
classes are defined:

```python
jobs = (PreviewIntentSourceAnalysis, ImportIntentSources, AnalyzeIntentSources, ExportDnsmasqRecords)
register_jobs(*jobs)
```

After changing job registration, run Nautobot's normal upgrade/sync workflow
and restart both web and worker processes.
