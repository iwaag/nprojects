"""Load service repository input data for display."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SERVICE_REPOSITORIES_ENV = "NAUTOBOT_SERVICE_REPOSITORIES_FILE"
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
class RepositoryEntry:
    """One row from service_repositories.yaml normalized for display."""

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
class RepositoryLoadResult:
    """Result object returned by the YAML loader."""

    source_path: Path
    repositories: list[RepositoryEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def default_repository_file(configured_path: str | Path | None = None) -> Path:
    """Return the default service_repositories.yaml path."""

    if configured_path:
        return _resolve_configured_path(configured_path)

    override = os.environ.get(DEFAULT_SERVICE_REPOSITORIES_ENV)
    if override:
        return _resolve_configured_path(override)

    return Path.cwd() / "nauto" / "seed" / "service_repositories.yaml"


def load_default_service_repositories(configured_path: str | Path | None = None) -> RepositoryLoadResult:
    """Load repository data from the configured default path."""

    return load_service_repositories(default_repository_file(configured_path))


def load_service_repositories(path: Path) -> RepositoryLoadResult:
    """Load and normalize repository entries from a YAML file."""

    source_path = path.expanduser()
    try:
        text = source_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return RepositoryLoadResult(
            source_path=source_path,
            errors=[f"Repository catalog file not found: {source_path}"],
        )
    except OSError as exc:
        return RepositoryLoadResult(
            source_path=source_path,
            errors=[f"Repository catalog file could not be read: {exc}"],
        )

    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        return RepositoryLoadResult(
            source_path=source_path,
            errors=[f"Repository catalog YAML is invalid: {exc}"],
        )

    if not isinstance(data, dict):
        return RepositoryLoadResult(
            source_path=source_path,
            errors=["Repository catalog root must be a mapping."],
        )

    raw_items = data.get("service_repositories", [])
    if raw_items is None:
        raw_items = []
    if not isinstance(raw_items, list):
        return RepositoryLoadResult(
            source_path=source_path,
            errors=["service_repositories must be a list."],
        )

    repositories: list[RepositoryEntry] = []
    errors: list[str] = []
    for index, item in enumerate(raw_items, start=1):
        entry, entry_errors = _normalize_repository_entry(item, index)
        if entry is not None:
            repositories.append(entry)
        errors.extend(entry_errors)

    return RepositoryLoadResult(
        source_path=source_path,
        repositories=repositories,
        errors=errors,
    )


def _normalize_repository_entry(item: Any, index: int) -> tuple[RepositoryEntry | None, list[str]]:
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
        RepositoryEntry(
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


def _resolve_configured_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return Path.cwd() / path
