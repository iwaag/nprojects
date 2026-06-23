# Nautobot Intent Catalog

Nautobot App for importing and analyzing cluster intent. The current code
supports intent sources, desired services, desired dependencies, desired nodes,
desired endpoints, and deterministic dnsmasq export. Planned work will add
evaluation jobs and remediation review.

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
- Persists `DesiredNode` and `DesiredEndpoint` rows from YAML.
- Provides `Quick Host Add` for creating one desired node and one primary endpoint from one Nautobot form.
- Persists `IntentEvaluation` rows for desired-vs-actual gap data.
- Exports deterministic dnsmasq records from eligible desired endpoints.
- Keeps a diagnostic YAML source view at `/plugins/intent-catalog/sources/source-yaml/`.
- Provides dry-run and import Nautobot Jobs for intent source analysis.
- Detects Backstage `Component` catalog entries for `service`, `website`, and `worker` desired services.
- Does not run automated gap evaluation or remediation review yet.

For the model intent and design boundaries behind `IntentSource`,
`DesiredService`, `DesiredDependency`, `DesiredNode`, `DesiredEndpoint`, and
`IntentEvaluation`, see [CONCEPT.md](CONCEPT.md).

## Intent Source YAML

The loader accepts only the current `intent_sources`, `desired_nodes`, and
`desired_endpoints` roots. Older input roots are not loaded by compatibility
code.

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

desired_nodes:
  - name: Edge Router 1
    slug: edge-router-1
    node_type: virtual_machine
    lifecycle: approved
    role: edge
    intent_source: service
    expected_spec:
      cpu: 2
      memory_gb: 4

desired_endpoints:
  - name: mgmt
    desired_node: edge-router-1
    endpoint_type: management
    ip_address: 192.0.2.10/32
    dns_name: edge-router-1.example.test
    protocol: https
    port: 443
    generate_dnsmasq: true
    dnsmasq_record_type: host_record
```

Manual conversion from an older YAML shape is intentionally mechanical: rename
the top-level list key to `intent_sources` and keep each item field that still
applies. Fields such as `catalog_paths`, `basic_file_paths`, and
`raw_url_template` are stored in `IntentSource.source_config` after import.

Desired endpoints must reference an existing desired node by node slug or name
in the same YAML input. Missing node references are reported as deterministic
validation errors. `DesiredEndpoint.ip_address` is stored as text so unrealized
intent can be captured before a Nautobot `IPAddress` exists; actual state is
linked separately through `realized_ip_address`.

## Quick Host Add

Use `Quick Host Add` for the common case where one host needs one primary DNS
name and one IP address. It is available from the `Intent Catalog` navigation
near `Desired Nodes`, and directly at:

```text
/plugins/intent-catalog/nodes/quick-add/
```

Quick Host Add does not create a separate host model. It writes the same
canonical records used everywhere else:

- one `DesiredNode`
- one primary `DesiredEndpoint`

Use the normal `DesiredNode` and `DesiredEndpoint` CRUD screens when a host
needs multiple endpoints, non-primary endpoint types, realized object links, or
fine-grained endpoint edits. Use YAML import when the desired state should be
managed from a source file or reviewed as a batch.

## dnsmasq Export

Run the `Export dnsmasq Records` Job to create deterministic JobResult output
files for automation:

- `dnsmasq-records.conf`: dnsmasq-ready configuration lines.
- `dnsmasq-export.json`: machine-readable export metadata, records, and skipped
  endpoint details for Ansible, audit, and troubleshooting.

The Python API is `nautobot_intent_catalog.dnsmasq.export_dnsmasq_records()`;
it returns a dictionary-friendly structure with `summary`, `records`, and
`skipped` entries.

Initial export selection requires:

- `generate_dnsmasq: true`
- both `ip_address` and `dns_name`
- desired node lifecycle of `planned`, `approved`, or `active`
- endpoint type of `primary`, `management`, `service`, or `vpn`

Supported `dnsmasq_record_type` values are:

- `host_record`: `host-record=<dns_name>,<ip>`
- `address`: `address=/<dns_name>/<ip>`
- `cname`: `cname=<vpn_dns_name>,<dns_name>`

`cname` records require `vpn_dns_name` as the alias target. `mdns_name` is kept
as endpoint metadata and is intentionally not exported as a dnsmasq record.

## Intent Evaluations

`IntentEvaluation` stores durable desired-vs-actual review data for UI, API,
and future agent workflows. It intentionally uses `target_type` and `target_id`
instead of a generic relation so external automation can address targets with a
small stable key.

The initial upsert key is:

```text
target_type, target_id, source_hash
```

Structured deterministic fields are kept separate from optional AI review:

- deterministic fields: `deterministic_summary`, `actual_refs`,
  `observed_facts`, `expected_facts`, `gap_summary`, `recommended_actions`
- AI fields: `ai_review`, `review_model`, `reviewed_at`

`ai_review` may be empty. Deterministic evaluations and recommended actions are
valid without any model-generated review.

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
