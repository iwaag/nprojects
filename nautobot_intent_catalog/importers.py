"""Helpers for importing catalog source and analysis output into models."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

from .loaders import DesiredEndpointEntry, DesiredNodeEntry, IntentSourceEntry
from .names import default_dns_name, default_mdns_name


SOURCE_CONFIG_FIELDS = (
    "service_hint",
    "catalog_paths",
    "basic_file_paths",
    "catalog_paths_defaulted",
    "basic_file_paths_defaulted",
    "raw_url_template",
)


def intent_source_defaults(source: IntentSourceEntry) -> dict[str, Any]:
    """Return model defaults for an intent source loader entry."""

    data = asdict(source)
    name = data.get("service_hint") or _name_from_url(source.url)
    return {
        "name": name,
        "slug": _slug_from_text(name or source.url),
        "source_type": "git_repository",
        "enabled": data["enabled"],
        "ref": data["ref"],
        "owner": data["owner"],
        "description": None,
        "source_config": {field: data[field] for field in SOURCE_CONFIG_FIELDS},
    }


def desired_service_identity(service: dict[str, Any], intent_source_id: Any | None = None) -> dict[str, Any]:
    """Return the stable identity fields for an analyzed desired service."""

    catalog = _mapping(service.get("catalog"))
    identity = {
        "catalog_namespace": str(catalog.get("namespace") or "default"),
        "catalog_metadata_name": str(catalog.get("metadata_name") or service.get("name") or ""),
        "service_type": _service_type(catalog.get("spec_type") or service.get("role")),
    }
    if intent_source_id is not None:
        identity["intent_source_id"] = intent_source_id
    return identity


def desired_service_defaults(service: dict[str, Any]) -> dict[str, Any]:
    """Return model defaults for an analyzed desired service."""

    catalog = _mapping(service.get("catalog"))
    source = _mapping(service.get("intent_source"))
    analysis = _mapping(service.get("analysis"))
    name = str(service.get("name") or "")
    service_type = _service_type(catalog.get("spec_type") or service.get("role"))
    return {
        "name": name,
        "slug": _slug_from_text(name),
        "display_name": str(service.get("display_name") or name),
        "service_type": service_type,
        "lifecycle": "proposed",
        "source_ref": _optional_str(source.get("ref")),
        "source_catalog_path": _optional_str(source.get("catalog_path")),
        "catalog_kind": _optional_str(catalog.get("kind")),
        "catalog_namespace": str(catalog.get("namespace") or "default"),
        "catalog_metadata_name": str(catalog.get("metadata_name") or name),
        "catalog_owner": _optional_str(catalog.get("owner")),
        "catalog_lifecycle": _optional_str(catalog.get("lifecycle")),
        "prefers_gpu": bool(service.get("prefers_gpu", False)),
        "min_memory_gb": service.get("min_memory_gb"),
        "requirements": {
            "analysis_status": _optional_str(analysis.get("status")),
            "analysis_confidence": _optional_str(analysis.get("confidence")),
            "analysis_reasons": _list(analysis.get("reasons")),
            "analysis_warnings": _analysis_warnings(analysis),
        },
        "placement_policy": {},
        "notes": _optional_str(service.get("notes")),
    }


def dependency_defaults(dependency: dict[str, Any]) -> dict[str, Any]:
    """Return model defaults for a normalized dependency."""

    dependency_kind = str(dependency.get("dependency_kind") or dependency.get("kind") or "")
    return {
        "dependency_kind": dependency_kind,
        "namespace": str(dependency.get("namespace") or "default"),
        "name": str(dependency.get("name") or ""),
        "raw_ref": str(dependency.get("raw_ref") or ""),
        "dependency_type": str(dependency.get("dependency_type") or dependency_kind),
        "resolution_status": str(dependency.get("resolution_status") or "unresolved"),
    }


def dependency_key(dependency: dict[str, Any]) -> tuple[str, str, str]:
    """Return the natural key for one dependency under a source service."""

    defaults = dependency_defaults(dependency)
    return defaults["dependency_kind"], defaults["namespace"], defaults["name"]


def desired_service_dependencies(service: dict[str, Any]) -> list[dict[str, Any]]:
    """Return dependency rows from an analyzed desired service, dropping malformed empty entries."""

    dependencies = service.get("dependencies")
    if not isinstance(dependencies, list):
        return []
    return [
        dependency_defaults(dependency)
        for dependency in dependencies
        if isinstance(dependency, dict)
        and dependency.get("kind")
        and dependency.get("namespace")
        and dependency.get("name")
    ]


def desired_node_identity(node: DesiredNodeEntry) -> dict[str, Any]:
    """Return the stable identity fields for a desired node."""

    return {"slug": node.slug}


def desired_node_defaults(node: DesiredNodeEntry, intent_source_id: Any | None = None) -> dict[str, Any]:
    """Return model defaults for a desired node loader entry."""

    defaults = {
        "name": node.name,
        "node_type": node.node_type,
        "lifecycle": node.lifecycle,
        "role": node.role,
        "description": node.description,
        "expected_spec": node.expected_spec,
        "notes": node.notes,
        "intent_source_id": intent_source_id,
    }
    return defaults


def desired_endpoint_identity(endpoint: DesiredEndpointEntry, desired_node_id: Any) -> dict[str, Any]:
    """Return the stable identity fields for a desired endpoint."""

    return {
        "desired_node_id": desired_node_id,
        "name": endpoint.name,
        "endpoint_type": endpoint.endpoint_type,
    }


def desired_endpoint_defaults(endpoint: DesiredEndpointEntry, desired_node: Any | None = None) -> dict[str, Any]:
    """Return model defaults for a desired endpoint loader entry."""

    dns_name = _optional_str(endpoint.dns_name)
    mdns_name = _optional_str(endpoint.mdns_name)
    if desired_node is not None and endpoint.name == "primary" and endpoint.endpoint_type == "primary":
        node_name = getattr(desired_node, "name", None)
        if dns_name is None:
            dns_name = default_dns_name(node_name)
        if mdns_name is None:
            mdns_name = default_mdns_name(node_name)

    return {
        "ip_address": endpoint.ip_address,
        "dns_name": dns_name,
        "mdns_name": mdns_name,
        "vpn_dns_name": endpoint.vpn_dns_name,
        "protocol": endpoint.protocol,
        "port": endpoint.port,
        "generate_dnsmasq": endpoint.generate_dnsmasq,
        "dnsmasq_record_type": endpoint.dnsmasq_record_type,
        "description": endpoint.description,
    }


def _analysis_warnings(analysis: dict[str, Any]) -> list[Any]:
    warnings = []
    raw_warnings = analysis.get("warnings")
    if isinstance(raw_warnings, list):
        warnings.extend(raw_warnings)
    malformed_dependencies = analysis.get("malformed_dependencies")
    if malformed_dependencies:
        warnings.append({"malformed_dependencies": malformed_dependencies})
    return warnings


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _service_type(value: Any) -> str:
    normalized = str(value or "service").strip().lower().replace("-", "_")
    return normalized if normalized in {"service", "website", "worker", "database", "queue", "storage", "agent"} else "other"


def _name_from_url(url: str) -> str:
    parsed = urlparse(url)
    path_name = parsed.path.rstrip("/").rsplit("/", maxsplit=1)[-1]
    if path_name:
        return path_name.removesuffix(".git")
    return parsed.netloc or url


def _slug_from_text(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "intent-source"
