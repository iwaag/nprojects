# Nautobot Intent Catalog

Nautobot App for importing and analyzing cluster intent. The current code
supports intent sources, desired services, desired dependencies, desired nodes,
desired endpoints, and deterministic dnsmasq export. Planned work will add
evaluations and remediation review.

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
- Exports deterministic dnsmasq records from eligible desired endpoints.
- Keeps a diagnostic YAML source view at `/plugins/intent-catalog/sources/source-yaml/`.
- Provides dry-run and import Nautobot Jobs for intent source analysis.
- Detects Backstage `Component` catalog entries for `service`, `website`, and `worker` desired services.
- Does not perform gap evaluation or remediation review yet.

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

## dnsmasq Export

Run the `Export dnsmasq Records` Job to log a deterministic dry-run payload.
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
