# Intent Catalog Concepts

This document explains the design intent behind the core Intent Catalog models.
`README.md` focuses on installation and usage; this file explains what each
object is meant to represent.

## Big Picture

Intent Catalog separates desired state into a few layers:

- `IntentSource`: where desired state came from.
- `DesiredService`: a logical service or workload that should exist.
- `DesiredDependency`: another service or resource a desired service needs.
- `DesiredNode`: a desired host, VM, device, container, or other node.
- `DesiredEndpoint`: a desired IP/DNS/port-facing endpoint on a node.
- `IntentEvaluation`: persisted desired-vs-actual review data.

The current implementation stores desired state and deterministic exports. It
does not yet automatically prove that every desired service is running or that
every dependency is satisfied.

## IntentSource

`IntentSource` describes the source of truth or input channel for intent.

The most important current source type is `git_repository`. It is intended to
mean:

> A source repository that declares a desired service for this environment.
> Catalog metadata in the repository is analyzed into `DesiredService` rows, and
> declared dependencies are imported as `DesiredDependency` rows that should be
> satisfied by another desired service, desired node, endpoint, or external
> system.

In practice, a GitHub or GitLab repository containing Backstage catalog metadata
can become the source for one or more desired services.

Other source types are available as classification hooks:

- `git_repository`: a source repository analyzed for service intent.
- `yaml_file`: a YAML file used to declare intent directly.
- `manual`: intent entered or maintained by a person in Nautobot.
- `api`: intent synchronized from another system.
- `generated`: intent produced by an agent or automation tool.

The non-Git source types are currently lightweight classifications. The thickest
implemented paths are Git-backed service analysis and YAML import.

## DesiredService

`DesiredService` represents a logical service or workload that should exist in
the managed environment. It is not a VM, IP address, DNS record, or physical
device.

Examples:

- `auth-api`
- `web-frontend`
- `metrics-worker`
- `postgresql`
- `redis`

`DesiredService` is intended to answer:

- What service should exist?
- What type of service is it?
- Who owns it?
- What lifecycle state is intended?
- What requirements or placement hints were detected?
- When was it last analyzed from its source?

The current Git analysis path primarily creates `DesiredService` rows from
Backstage `Component` catalog entries.

## DesiredDependency

`DesiredDependency` represents something a `DesiredService` needs in order to be
complete.

It is usually derived from Backstage `spec.dependsOn` metadata. For example:

```yaml
spec:
  dependsOn:
    - component:default/auth-api
    - resource:default/postgresql
```

This can become dependency rows such as:

```text
web-frontend -> component:default/auth-api
web-frontend -> resource:default/postgresql
```

`DesiredDependency` is intended to preserve dependency intent even before the
dependency is resolved. A dependency can be:

- `unresolved`: known desired dependency, but no matching internal target yet.
- `resolved`: linked to another `DesiredService`.
- `external`: satisfied outside this app or outside this environment.
- `ignored`: intentionally excluded from evaluation.

The current implementation stores and replaces dependency rows deterministically
during service analysis. It does not yet automatically evaluate whether every
dependency is satisfied.

## DesiredNode

`DesiredNode` represents a desired node-level object: a physical device, VM,
container, service host, network object, or similar managed unit.

Examples:

- `proxmox-01`
- `vm-git-01`
- `vm-db-01`
- `nas-01`

For a simple DNS/DHCP inventory, this model can feel heavier than a single
`DesiredHost` table. The reason it exists separately is long-term flexibility:
one physical layer object may eventually host many logical nodes, and one node
may have several endpoints.

For example, a Proxmox host and its VMs can be represented as separate desired
nodes:

```yaml
desired_nodes:
  - name: proxmox-01
    slug: proxmox-01
    node_type: device
    lifecycle: active
    role: hypervisor

  - name: vm-git-01
    slug: vm-git-01
    node_type: virtual_machine
    lifecycle: active
    role: git
    expected_spec:
      hypervisor: proxmox-01
      vcpu: 2
      memory_gb: 4
```

The current schema does not yet have a typed `parent_node` or `placement_node`
relationship. Placement can be carried in `expected_spec` for now. A future
self-referential relationship would be a natural extension if placement becomes
important enough to query directly.

## DesiredEndpoint

`DesiredEndpoint` represents a desired network-facing endpoint on a
`DesiredNode`.

Examples:

- primary DNS/IP for a VM
- management IP for a device
- VPN DNS name for a host
- service endpoint with protocol and port metadata

This separation allows one node to have multiple endpoints:

```yaml
desired_nodes:
  - name: vm-01
    slug: vm-01
    node_type: virtual_machine
    lifecycle: active

desired_endpoints:
  - name: primary
    desired_node: vm-01
    endpoint_type: primary
    ip_address: 192.168.10.21/24
    dns_name: vm-01.example.lan
    generate_dnsmasq: true

  - name: management
    desired_node: vm-01
    endpoint_type: management
    ip_address: 192.168.20.21/24
    dns_name: vm-01-mgmt.example.lan
    generate_dnsmasq: true
```

For basic host inventory, using one `primary` endpoint per node is enough. More
endpoints can be added later without changing the node identity.

The dnsmasq export is generated from eligible `DesiredEndpoint` rows. mDNS names
are retained as metadata and are not exported as dnsmasq records.

## IntentEvaluation

`IntentEvaluation` stores persisted desired-vs-actual review data. It is the
place where deterministic checks and optional AI review can be saved for UI,
API, or future agent workflows.

The initial upsert key is:

```text
target_type, target_id, source_hash
```

The model deliberately separates deterministic fields from AI review fields.
Deterministic fields include:

- `deterministic_summary`
- `actual_refs`
- `observed_facts`
- `expected_facts`
- `gap_summary`
- `recommended_actions`

AI-related fields include:

- `ai_review`
- `review_model`
- `reviewed_at`

An evaluation can be useful even when `ai_review` is empty.

## Current Boundaries

These boundaries are intentional in the current implementation:

- `DesiredService` and `DesiredNode` are not yet directly linked.
- `DesiredDependency` rows are stored, but dependency satisfaction is not yet
  automatically evaluated.
- `DesiredNode` / `DesiredEndpoint` can be imported and exported to dnsmasq, but
  actual Nautobot object comparison is not yet automated.
- `IntentEvaluation` has CRUD and schema support, but node, endpoint, and service
  evaluation jobs are not yet implemented.
- The app does not preserve backward compatibility with the old package name,
  old URLs, old model names, old YAML root names, or old migrations.

This means the app is currently useful as an intent inventory, service/dependency
catalog, endpoint source for deterministic dnsmasq export, and storage surface
for evaluations produced manually or by external automation.
