"""Load intent source input data for display."""

from __future__ import annotations

import os
import ipaddress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_INTENT_SOURCES_ENV = "NAUTOBOT_INTENT_SOURCES_FILE"
DEFAULT_CATALOG_PATHS = ("catalog-info.yaml", "backstage/catalog-info.yaml")
DEFAULT_BASIC_FILE_PATHS = (
    "README.md",
    "readme.md",
    "package.json",
    "docker-compose.yml",
    "compose.yaml",
    "Chart.yaml",
)


@dataclass(frozen=True)
class IntentSourceEntry:
    """One Git repository-style intent source row normalized for display."""

    url: str
    enabled: bool = True
    ref: str | None = None
    owner: str | None = None
    service_hint: str | None = None
    catalog_paths: list[str] = field(default_factory=list)
    basic_file_paths: list[str] = field(default_factory=list)
    catalog_paths_defaulted: bool = False
    basic_file_paths_defaulted: bool = False
    raw_url_template: str | None = None


@dataclass(frozen=True)
class DesiredNodeEntry:
    """One desired node row normalized from YAML."""

    name: str
    slug: str
    node_type: str = "device"
    accepted_actual_types: list[str] = field(default_factory=list)
    lifecycle: str = "planned"
    role: str | None = None
    description: str | None = None
    expected_spec: dict[str, Any] = field(default_factory=dict)
    intent_source: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class DesiredEndpointEntry:
    """One desired endpoint row normalized from YAML."""

    name: str
    desired_node: str
    endpoint_type: str = "primary"
    ip_address: str | None = None
    dns_name: str | None = None
    mdns_name: str | None = None
    vpn_dns_name: str | None = None
    protocol: str | None = None
    port: int | None = None
    generate_dnsmasq: bool = False
    ip_policy: str | None = None
    dnsmasq_record_type: str = "host_record"
    description: str | None = None


@dataclass(frozen=True)
class DesiredIPRangeEntry:
    """One desired IP range row normalized from YAML."""

    name: str
    slug: str
    start_address: str
    end_address: str
    range_policy: str
    lifecycle: str = "planned"
    generate_dnsmasq: bool = False
    dnsmasq_options: dict[str, Any] = field(default_factory=dict)
    description: str | None = None


@dataclass(frozen=True)
class IntentSourceLoadResult:
    """Result object returned by the YAML loader."""

    source_path: Path
    intent_sources: list[IntentSourceEntry] = field(default_factory=list)
    desired_nodes: list[DesiredNodeEntry] = field(default_factory=list)
    desired_ip_ranges: list[DesiredIPRangeEntry] = field(default_factory=list)
    desired_endpoints: list[DesiredEndpointEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def default_intent_sources_file(configured_path: str | Path | None = None) -> Path:
    """Return the default intent source YAML path."""

    if configured_path:
        return _resolve_configured_path(configured_path)

    override = os.environ.get(DEFAULT_INTENT_SOURCES_ENV)
    if override:
        return _resolve_configured_path(override)

    return Path.cwd() / "nauto" / "seed" / "intent_sources.yaml"


def load_default_intent_sources(configured_path: str | Path | None = None) -> IntentSourceLoadResult:
    """Load intent source data from the configured default path."""

    return load_intent_sources(default_intent_sources_file(configured_path))


def load_intent_sources(path: Path) -> IntentSourceLoadResult:
    """Load and normalize intent source entries from a YAML file."""

    source_path = path.expanduser()
    try:
        text = source_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return IntentSourceLoadResult(
            source_path=source_path,
            errors=[f"Intent source file not found: {source_path}"],
        )
    except OSError as exc:
        return IntentSourceLoadResult(
            source_path=source_path,
            errors=[f"Intent source file could not be read: {exc}"],
        )

    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        return IntentSourceLoadResult(
            source_path=source_path,
            errors=[f"Intent source YAML is invalid: {exc}"],
        )

    if not isinstance(data, dict):
        return IntentSourceLoadResult(
            source_path=source_path,
            errors=["Intent source root must be a mapping."],
        )

    if "service_repositories" in data:
        return IntentSourceLoadResult(
            source_path=source_path,
            errors=["service_repositories is not supported; rename the top-level key to intent_sources."],
        )

    intent_sources: list[IntentSourceEntry] = []
    desired_nodes: list[DesiredNodeEntry] = []
    desired_ip_ranges: list[DesiredIPRangeEntry] = []
    desired_endpoints: list[DesiredEndpointEntry] = []
    errors: list[str] = []

    raw_sources, source_errors = _list_section(data, "intent_sources")
    errors.extend(source_errors)
    for index, item in enumerate(raw_sources, start=1):
        entry, entry_errors = _normalize_intent_source_entry(item, index)
        if entry is not None:
            intent_sources.append(entry)
        errors.extend(entry_errors)

    raw_nodes, node_errors = _list_section(data, "desired_nodes")
    errors.extend(node_errors)
    for index, item in enumerate(raw_nodes, start=1):
        entry, entry_errors = _normalize_desired_node_entry(item, index)
        if entry is not None:
            desired_nodes.append(entry)
        errors.extend(entry_errors)

    raw_ip_ranges, ip_range_errors = _list_section(data, "desired_ip_ranges")
    errors.extend(ip_range_errors)
    for index, item in enumerate(raw_ip_ranges, start=1):
        entry, entry_errors = _normalize_desired_ip_range_entry(item, index)
        if entry is not None:
            desired_ip_ranges.append(entry)
        errors.extend(entry_errors)

    raw_endpoints, endpoint_errors = _list_section(data, "desired_endpoints")
    errors.extend(endpoint_errors)
    for index, item in enumerate(raw_endpoints, start=1):
        entry, entry_errors = _normalize_desired_endpoint_entry(item, index)
        if entry is not None:
            desired_endpoints.append(entry)
        errors.extend(entry_errors)

    errors.extend(_validate_endpoint_nodes(desired_nodes, desired_endpoints))

    return IntentSourceLoadResult(
        source_path=source_path,
        intent_sources=intent_sources,
        desired_nodes=desired_nodes,
        desired_ip_ranges=desired_ip_ranges,
        desired_endpoints=desired_endpoints,
        errors=errors,
    )


def _list_section(data: dict[Any, Any], key: str) -> tuple[list[Any], list[str]]:
    raw_items = data.get(key, [])
    if raw_items is None:
        return [], []
    if not isinstance(raw_items, list):
        return [], [f"{key} must be a list."]
    return raw_items, []


def _normalize_intent_source_entry(item: Any, index: int) -> tuple[IntentSourceEntry | None, list[str]]:
    """Normalize one raw YAML list item."""

    if isinstance(item, str):
        item = {"url": item}

    if not isinstance(item, dict):
        return None, [f"Entry {index} must be a URL string or mapping."]

    raw_url = item.get("url")
    if not raw_url:
        return None, [f"Entry {index} is missing required field: url."]

    catalog_paths, catalog_paths_defaulted = _string_list_with_default(
        item,
        "catalog_paths",
        DEFAULT_CATALOG_PATHS,
    )
    basic_file_paths, basic_file_paths_defaulted = _string_list_with_default(
        item,
        "basic_file_paths",
        DEFAULT_BASIC_FILE_PATHS,
    )

    return (
        IntentSourceEntry(
            url=str(raw_url),
            enabled=_as_bool(item.get("enabled", True)),
            ref=_optional_str(item.get("ref")),
            owner=_optional_str(item.get("owner")),
            service_hint=_optional_str(item.get("service_hint")),
            catalog_paths=catalog_paths,
            basic_file_paths=basic_file_paths,
            catalog_paths_defaulted=catalog_paths_defaulted,
            basic_file_paths_defaulted=basic_file_paths_defaulted,
            raw_url_template=_optional_str(item.get("raw_url_template")),
        ),
        [],
    )


def _normalize_desired_node_entry(item: Any, index: int) -> tuple[DesiredNodeEntry | None, list[str]]:
    """Normalize one desired node YAML item."""

    if not isinstance(item, dict):
        return None, [f"desired_nodes entry {index} must be a mapping."]

    name = _optional_str(item.get("name"))
    if not name:
        return None, [f"desired_nodes entry {index} is missing required field: name."]

    slug = _optional_str(item.get("slug")) or _slug_from_text(name, "desired-node")
    expected_spec = item.get("expected_spec") or {}
    if not isinstance(expected_spec, dict):
        return None, [f"desired_nodes entry {index} expected_spec must be a mapping."]

    node_type, node_type_error = _choice_with_default_or_error(
        item.get("node_type"),
        _NODE_TYPES,
        f"desired_nodes entry {index} node_type",
        "device",
    )
    accepted_actual_types, accepted_actual_types_error = _actual_types_or_error(
        item.get("accepted_actual_types"),
        node_type or "device",
        f"desired_nodes entry {index} accepted_actual_types",
    )
    errors = []
    if node_type_error:
        errors.append(node_type_error)
    if accepted_actual_types_error:
        errors.append(accepted_actual_types_error)
    if errors:
        return None, errors

    return (
        DesiredNodeEntry(
            name=name,
            slug=slug,
            node_type=node_type or "device",
            accepted_actual_types=accepted_actual_types,
            lifecycle=_choice(item.get("lifecycle"), _LIFECYCLES, "planned"),
            role=_optional_str(item.get("role")),
            description=_optional_str(item.get("description")),
            expected_spec=_plain_mapping(expected_spec),
            intent_source=_optional_str(item.get("intent_source")),
            notes=_optional_str(item.get("notes")),
        ),
        [],
    )


def _normalize_desired_endpoint_entry(item: Any, index: int) -> tuple[DesiredEndpointEntry | None, list[str]]:
    """Normalize one desired endpoint YAML item."""

    if not isinstance(item, dict):
        return None, [f"desired_endpoints entry {index} must be a mapping."]

    name = _optional_str(item.get("name"))
    desired_node = _optional_str(item.get("desired_node"))
    errors = []
    if not name:
        errors.append(f"desired_endpoints entry {index} is missing required field: name.")
    if not desired_node:
        errors.append(f"desired_endpoints entry {index} is missing required field: desired_node.")
    port, port_error = _optional_port(item.get("port"), index)
    if port_error:
        errors.append(port_error)
    ip_address = _optional_str(item.get("ip_address"))
    raw_ip_policy = item.get("ip_policy")
    ip_policy: str | None = None
    ip_policy_error: str | None = None
    if ip_address or raw_ip_policy is not None:
        ip_policy, ip_policy_error = _choice_or_error(
            raw_ip_policy,
            _IP_POLICIES,
            f"desired_endpoints entry {index} ip_policy",
        )
    if ip_address and raw_ip_policy is None:
        errors.append(f"desired_endpoints entry {index} is missing required field: ip_policy.")
    elif ip_policy_error:
        errors.append(ip_policy_error)
    if ip_policy is None and not ip_address:
        ip_policy = "external"
    if errors:
        return None, errors

    return (
        DesiredEndpointEntry(
            name=name or "",
            desired_node=desired_node or "",
            endpoint_type=_choice(item.get("endpoint_type"), _ENDPOINT_TYPES, "primary"),
            ip_address=ip_address,
            dns_name=_optional_str(item.get("dns_name")),
            mdns_name=_optional_str(item.get("mdns_name")),
            vpn_dns_name=_optional_str(item.get("vpn_dns_name")),
            protocol=_optional_str(item.get("protocol")),
            port=port,
            generate_dnsmasq=_as_bool(item.get("generate_dnsmasq", False)),
            ip_policy=ip_policy,
            dnsmasq_record_type=_choice(item.get("dnsmasq_record_type"), _DNSMASQ_RECORD_TYPES, "host_record"),
            description=_optional_str(item.get("description")),
        ),
        [],
    )


def _normalize_desired_ip_range_entry(item: Any, index: int) -> tuple[DesiredIPRangeEntry | None, list[str]]:
    """Normalize one desired IP range YAML item."""

    if not isinstance(item, dict):
        return None, [f"desired_ip_ranges entry {index} must be a mapping."]

    name = _optional_str(item.get("name"))
    slug = _optional_str(item.get("slug"))
    start_address = _optional_str(item.get("start_address"))
    end_address = _optional_str(item.get("end_address"))
    errors = []
    if not name:
        errors.append(f"desired_ip_ranges entry {index} is missing required field: name.")
    if not slug:
        errors.append(f"desired_ip_ranges entry {index} is missing required field: slug.")
    if not start_address:
        errors.append(f"desired_ip_ranges entry {index} is missing required field: start_address.")
    if not end_address:
        errors.append(f"desired_ip_ranges entry {index} is missing required field: end_address.")

    range_policy, range_policy_error = _choice_or_error(
        item.get("range_policy"),
        _RANGE_POLICIES,
        f"desired_ip_ranges entry {index} range_policy",
    )
    if range_policy_error:
        errors.append(range_policy_error)

    lifecycle, lifecycle_error = _choice_or_error(
        item.get("lifecycle", "planned"),
        _LIFECYCLES,
        f"desired_ip_ranges entry {index} lifecycle",
    )
    if lifecycle_error:
        errors.append(lifecycle_error)

    if start_address:
        errors.extend(_address_errors(start_address, f"desired_ip_ranges entry {index} start_address"))
    if end_address:
        errors.extend(_address_errors(end_address, f"desired_ip_ranges entry {index} end_address"))

    dnsmasq_options = item.get("dnsmasq_options") or {}
    if not isinstance(dnsmasq_options, dict):
        errors.append(f"desired_ip_ranges entry {index} dnsmasq_options must be a mapping.")

    if errors:
        return None, errors

    return (
        DesiredIPRangeEntry(
            name=name or "",
            slug=slug or "",
            start_address=start_address or "",
            end_address=end_address or "",
            range_policy=range_policy or "static_pool",
            lifecycle=lifecycle or "planned",
            generate_dnsmasq=_as_bool(item.get("generate_dnsmasq", False)),
            dnsmasq_options=_plain_mapping(dnsmasq_options),
            description=_optional_str(item.get("description")),
        ),
        [],
    )


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _string_list_with_default(item: dict[Any, Any], key: str, default: tuple[str, ...]) -> tuple[list[str], bool]:
    if key not in item or item.get(key) is None:
        return list(default), True
    return _string_list(item.get(key)), False


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _optional_port(value: Any, index: int) -> tuple[int | None, str | None]:
    if value is None or value == "":
        return None, None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None, f"desired_endpoints entry {index} port must be an integer."
    if port < 1 or port > 65535:
        return None, f"desired_endpoints entry {index} port must be between 1 and 65535."
    return port, None


def _choice(value: Any, allowed: set[str], default: str) -> str:
    normalized = str(value or default).strip().lower().replace("-", "_")
    return normalized if normalized in allowed else default


def _choice_or_error(value: Any, allowed: set[str], field_name: str) -> tuple[str | None, str | None]:
    if value is None or value == "":
        return None, f"{field_name} is missing required field."
    normalized = str(value).strip().lower().replace("-", "_")
    if normalized in allowed:
        return normalized, None
    return None, f"{field_name} must be one of: {', '.join(sorted(allowed))}."


def _choice_with_default_or_error(
    value: Any,
    allowed: set[str],
    field_name: str,
    default: str,
) -> tuple[str | None, str | None]:
    if value is None or value == "":
        return default, None
    return _choice_or_error(value, allowed, field_name)


def _actual_types_or_error(value: Any, node_type: str, field_name: str) -> tuple[list[str], str | None]:
    if value is None:
        return list(_ACTUAL_TYPE_DEFAULTS[node_type]), None
    if not isinstance(value, list):
        return [], f"{field_name} must be a list."

    actual_types = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return [], f"{field_name} must contain non-empty strings."
        normalized = item.strip().lower().replace("-", "_")
        if normalized not in _ACTUAL_TYPES:
            return [], f"{field_name} must be one of: {', '.join(sorted(_ACTUAL_TYPES))}."
        if normalized not in actual_types:
            actual_types.append(normalized)
    return actual_types, None


def _address_errors(value: str, field_name: str) -> list[str]:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return [f"{field_name} must be a valid IP address."]
    return []


def _plain_mapping(value: dict[Any, Any]) -> dict[str, Any]:
    return {str(key): item for key, item in value.items()}


def _validate_endpoint_nodes(nodes: list[DesiredNodeEntry], endpoints: list[DesiredEndpointEntry]) -> list[str]:
    node_keys = {node.slug for node in nodes} | {node.name for node in nodes}
    errors = []
    for endpoint in endpoints:
        if endpoint.desired_node not in node_keys:
            errors.append(
                f"desired_endpoints entry {endpoint.name} references missing desired_node: {endpoint.desired_node}."
            )
    return errors


def _slug_from_text(value: str, fallback: str) -> str:
    slug = "-".join(part for part in str(value).lower().replace("_", "-").split() if part)
    slug = "".join(char if char.isalnum() or char == "-" else "-" for char in slug).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or fallback


def _resolve_configured_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return Path.cwd() / path


_NODE_TYPES = {"device", "virtual_machine", "container", "service_host"}
_ACTUAL_TYPES = {"device", "virtual_machine", "container"}
_ACTUAL_TYPE_DEFAULTS = {
    "device": ("device",),
    "virtual_machine": ("virtual_machine",),
    "container": ("container",),
    "service_host": ("device", "virtual_machine", "container"),
}
_LIFECYCLES = {"planned", "approved", "active", "deprecated", "retired"}
_ENDPOINT_TYPES = {"primary", "management", "service", "vpn", "mdns", "other"}
_DNSMASQ_RECORD_TYPES = {"host_record", "address", "cname"}
_IP_POLICIES = {"static", "dhcp_reserved", "external"}
_RANGE_POLICIES = {"static_pool", "dhcp_reservable_pool", "dhcp_dynamic_pool", "excluded"}
