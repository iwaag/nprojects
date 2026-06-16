"""Helpers for importing catalog source and analysis output into models."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .loaders import RepositoryEntry


REPOSITORY_FIELDS = (
    "enabled",
    "ref",
    "owner",
    "service_hint",
    "catalog_paths",
    "basic_file_paths",
    "raw_url_template",
)


def repository_defaults(repository: RepositoryEntry) -> dict[str, Any]:
    """Return model defaults for a repository loader entry."""

    data = asdict(repository)
    return {field: data[field] for field in REPOSITORY_FIELDS}


def candidate_identity(candidate: dict[str, Any], repository_id: Any | None = None) -> dict[str, Any]:
    """Return the stable identity fields for an analysis candidate."""

    catalog = _mapping(candidate.get("catalog"))
    identity = {
        "catalog_namespace": str(catalog.get("namespace") or "default"),
        "catalog_metadata_name": str(catalog.get("metadata_name") or candidate.get("name") or ""),
        "catalog_spec_type": str(catalog.get("spec_type") or candidate.get("role") or ""),
    }
    if repository_id is not None:
        identity["source_repository_id"] = repository_id
    return identity


def candidate_defaults(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return model defaults for an analysis candidate."""

    catalog = _mapping(candidate.get("catalog"))
    source_repository = _mapping(candidate.get("source_repository"))
    analysis = _mapping(candidate.get("analysis"))
    return {
        "name": str(candidate.get("name") or ""),
        "display_name": str(candidate.get("display_name") or candidate.get("name") or ""),
        "role": str(candidate.get("role") or ""),
        "source_ref": _optional_str(source_repository.get("ref")),
        "source_catalog_path": _optional_str(source_repository.get("catalog_path")),
        "catalog_kind": _optional_str(catalog.get("kind")),
        "catalog_namespace": str(catalog.get("namespace") or "default"),
        "catalog_metadata_name": str(catalog.get("metadata_name") or candidate.get("name") or ""),
        "catalog_owner": _optional_str(catalog.get("owner")),
        "catalog_lifecycle": _optional_str(catalog.get("lifecycle")),
        "catalog_spec_type": str(catalog.get("spec_type") or candidate.get("role") or ""),
        "prefers_gpu": bool(candidate.get("prefers_gpu", False)),
        "min_memory_gb": candidate.get("min_memory_gb"),
        "analysis_status": _optional_str(analysis.get("status")),
        "analysis_confidence": _optional_str(analysis.get("confidence")),
        "analysis_reasons": _list(analysis.get("reasons")),
        "analysis_warnings": _analysis_warnings(analysis),
        "notes": _optional_str(candidate.get("notes")),
    }


def dependency_defaults(dependency: dict[str, Any]) -> dict[str, Any]:
    """Return model defaults for a normalized dependency."""

    return {
        "kind": str(dependency.get("kind") or ""),
        "namespace": str(dependency.get("namespace") or "default"),
        "name": str(dependency.get("name") or ""),
        "raw_ref": str(dependency.get("raw_ref") or ""),
        "dependency_type": str(dependency.get("dependency_type") or dependency.get("kind") or ""),
        "resolution_status": str(dependency.get("resolution_status") or "unresolved"),
    }


def dependency_key(dependency: dict[str, Any]) -> tuple[str, str, str]:
    """Return the natural key for one dependency under a source service."""

    defaults = dependency_defaults(dependency)
    return defaults["kind"], defaults["namespace"], defaults["name"]


def candidate_dependencies(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    """Return dependency rows from a candidate, dropping malformed empty entries."""

    dependencies = candidate.get("dependencies")
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
    if value is None or value == "":
        return None
    return str(value)
