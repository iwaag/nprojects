"""Nautobot Jobs for repository analysis preview."""

from __future__ import annotations

import json
from pathlib import Path

from .analysis import analyze_repositories
from .loaders import load_default_service_repositories, load_service_repositories

try:
    from django.conf import settings
    from nautobot.apps.jobs import BooleanVar, IntegerVar, Job, StringVar
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

    jobs = (AnalyzeServiceRepositories,)


def _configured_repository_file():
    plugins_config = getattr(settings, "PLUGINS_CONFIG", {}) or {}
    app_config = plugins_config.get("nautobot_service_catalog", {}) or {}
    return app_config.get("service_repositories_file")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)
