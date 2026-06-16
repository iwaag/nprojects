"""Nautobot Jobs for repository analysis preview."""

from __future__ import annotations

import json
from pathlib import Path

from .analysis import analyze_repositories
from .importers import candidate_defaults, candidate_identity, candidate_dependencies, repository_defaults
from .loaders import RepositoryEntry
from .loaders import load_default_service_repositories, load_service_repositories

try:
    from django.conf import settings
    from django.utils import timezone
    from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, StringVar

    from .models import DesiredServiceCandidate, ServiceDependency, ServiceRepository
except ImportError:  # pragma: no cover - Nautobot is not available in local unit tests.
    jobs = ()
else:

    class AnalyzeServiceRepositories(Job):
        """Dry-run analyze configured service repositories."""

        repository_file = StringVar(
            default="",
            description="Optional path to service_repositories.yaml. Empty uses App configuration.",
        )
        fetch_timeout = IntegerVar(
            default=10,
            description="HTTP timeout in seconds for each lightweight file request.",
        )
        include_candidate_preview = BooleanVar(
            default=True,
            description="Log generated desired service candidates as JSON.",
        )

        class Meta:
            name = "Analyze Service Repositories"
            description = "Dry-run Backstage catalog detection for configured service repositories."
            has_sensitive_variables = False

        def run(self, repository_file: str, fetch_timeout: int, include_candidate_preview: bool) -> None:
            if repository_file:
                load_result = load_service_repositories(Path(repository_file))
            else:
                load_result = load_default_service_repositories(_configured_repository_file())

            for error in load_result.errors:
                self.logger.warning(error)

            if load_result.errors and not load_result.repositories:
                raise ValueError("Repository catalog could not be loaded; see Job logs for details.")

            result = analyze_repositories(
                load_result.repositories,
                fetch_timeout=float(fetch_timeout),
            )
            summary = {
                "source_path": str(load_result.source_path),
                "repositories": len(load_result.repositories),
                "repository_analyses": len(result.repository_analysis),
                "desired_services": len(result.desired_services),
                "analysis_errors": len(result.errors),
                "generated_at": result.generated_at,
            }

            self.logger.info("Repository analysis summary: %s", _json(summary))
            self.logger.info("Repository analysis detail: %s", _json(result.repository_analysis))
            for error in result.errors:
                self.logger.warning(error)

            if include_candidate_preview:
                self.logger.info("Desired service candidate preview: %s", _json(result.desired_services))


    class ImportServiceRepositories(Job):
        """Import service repository inputs from configured YAML into DB models."""

        repository_file = StringVar(
            default="",
            description="Optional path to service_repositories.yaml. Empty uses App configuration.",
        )
        disable_missing = BooleanVar(
            default=False,
            description="Disable existing DB repositories that are not present in the YAML input.",
        )

        class Meta:
            name = "Import Service Repositories"
            description = "Import service repository YAML rows into ServiceRepository records."
            has_sensitive_variables = False

        def run(self, repository_file: str, disable_missing: bool) -> None:
            if repository_file:
                load_result = load_service_repositories(Path(repository_file))
            else:
                load_result = load_default_service_repositories(_configured_repository_file())

            for error in load_result.errors:
                self.logger.warning(error)
            if load_result.errors and not load_result.repositories:
                raise ValueError("Repository catalog could not be loaded; see Job logs for details.")

            seen_urls = set()
            counts = {"created": 0, "updated": 0, "unchanged": 0, "disabled": 0}
            for repository in load_result.repositories:
                seen_urls.add(repository.url)
                defaults = repository_defaults(repository)
                obj, created = ServiceRepository.objects.get_or_create(url=repository.url, defaults=defaults)
                if created:
                    counts["created"] += 1
                elif _repository_matches_defaults(obj, defaults):
                    counts["unchanged"] += 1
                else:
                    for key, value in defaults.items():
                        setattr(obj, key, value)
                    obj.save(update_fields=tuple(defaults.keys()))
                    counts["updated"] += 1

            if disable_missing:
                missing = ServiceRepository.objects.exclude(url__in=seen_urls).filter(enabled=True)
                counts["disabled"] = missing.update(enabled=False)

            self.logger.info(
                "Service repository import summary: %s",
                _json(
                    {
                        "source_path": str(load_result.source_path),
                        "repositories": len(load_result.repositories),
                        **counts,
                    }
                ),
            )


    class AnalyzeAndImportServiceCandidates(Job):
        """Analyze DB-backed repositories and persist candidates plus dependencies."""

        fetch_timeout = IntegerVar(
            default=10,
            description="HTTP timeout in seconds for each lightweight file request.",
        )
        include_disabled = BooleanVar(
            default=False,
            description="Include disabled ServiceRepository rows in analysis.",
        )

        class Meta:
            name = "Analyze and Import Service Candidates"
            description = "Analyze ServiceRepository records and persist candidates plus dependencies."
            has_sensitive_variables = False

        def run(self, fetch_timeout: int, include_disabled: bool) -> None:
            queryset = ServiceRepository.objects.all()
            if not include_disabled:
                queryset = queryset.filter(enabled=True)
            repositories = list(queryset.order_by("url"))
            entries = [_repository_entry_from_model(repository) for repository in repositories]
            repository_by_url = {repository.url: repository for repository in repositories}

            result = analyze_repositories(entries, fetch_timeout=float(fetch_timeout))
            now = timezone.now()
            counts = {
                "repositories": len(repositories),
                "repository_analyses": len(result.repository_analysis),
                "candidates_created": 0,
                "candidates_updated": 0,
                "dependencies_created": 0,
                "dependencies_replaced": 0,
                "analysis_errors": len(result.errors),
            }

            for analysis in result.repository_analysis:
                repository = repository_by_url.get(analysis.get("url"))
                if repository is None:
                    continue
                repository.last_analysis_status = analysis.get("status")
                repository.last_analyzed_at = now
                repository.last_analysis_summary = analysis
                repository.save(
                    update_fields=("last_analysis_status", "last_analyzed_at", "last_analysis_summary")
                )

            for candidate in result.desired_services:
                source = candidate.get("source_repository") if isinstance(candidate.get("source_repository"), dict) else {}
                repository = repository_by_url.get(source.get("url"))
                if repository is None:
                    self.logger.warning("Skipping candidate without matching repository: %s", _json(candidate))
                    continue

                identity = candidate_identity(candidate)
                defaults = candidate_defaults(candidate)
                defaults["last_analyzed_at"] = now
                candidate_obj, created = DesiredServiceCandidate.objects.update_or_create(
                    source_repository=repository,
                    catalog_namespace=identity["catalog_namespace"],
                    catalog_metadata_name=identity["catalog_metadata_name"],
                    catalog_spec_type=identity["catalog_spec_type"],
                    defaults=defaults,
                )
                if created:
                    counts["candidates_created"] += 1
                else:
                    counts["candidates_updated"] += 1

                old_dependency_count = candidate_obj.dependencies.count()
                candidate_obj.dependencies.all().delete()
                counts["dependencies_replaced"] += old_dependency_count
                dependencies = [
                    ServiceDependency(source_service=candidate_obj, **dependency)
                    for dependency in candidate_dependencies(candidate)
                ]
                ServiceDependency.objects.bulk_create(dependencies)
                counts["dependencies_created"] += len(dependencies)

            for error in result.errors:
                self.logger.warning(error)

            self.logger.info("Service candidate import summary: %s", _json(counts))

    jobs = (AnalyzeServiceRepositories, ImportServiceRepositories, AnalyzeAndImportServiceCandidates)


def _configured_repository_file():
    plugins_config = getattr(settings, "PLUGINS_CONFIG", {}) or {}
    app_config = plugins_config.get("nautobot_service_catalog", {}) or {}
    return app_config.get("service_repositories_file")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _repository_entry_from_model(repository) -> RepositoryEntry:
    return RepositoryEntry(
        url=repository.url,
        enabled=repository.enabled,
        ref=repository.ref,
        owner=repository.owner,
        service_hint=repository.service_hint,
        catalog_paths=list(repository.catalog_paths or []),
        basic_file_paths=list(repository.basic_file_paths or []),
        raw_url_template=repository.raw_url_template,
    )


def _repository_matches_defaults(repository, defaults: dict) -> bool:
    return all(getattr(repository, key) == value for key, value in defaults.items())
