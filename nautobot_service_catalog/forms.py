"""Forms for Service Catalog models."""

from __future__ import annotations

try:
    from nautobot.apps.forms import NautobotModelForm

    from .models import DesiredServiceCandidate, ServiceDependency, ServiceRepository
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    pass
else:

    class ServiceRepositoryForm(NautobotModelForm):
        """Create/edit form for repository inputs."""

        class Meta:
            model = ServiceRepository
            fields = (
                "url",
                "enabled",
                "ref",
                "owner",
                "service_hint",
                "catalog_paths",
                "basic_file_paths",
                "raw_url_template",
                "last_analysis_status",
                "last_analysis_summary",
            )


    class DesiredServiceCandidateForm(NautobotModelForm):
        """Edit form for generated service candidates."""

        class Meta:
            model = DesiredServiceCandidate
            fields = (
                "name",
                "display_name",
                "role",
                "source_repository",
                "source_ref",
                "source_catalog_path",
                "catalog_kind",
                "catalog_namespace",
                "catalog_metadata_name",
                "catalog_owner",
                "catalog_lifecycle",
                "catalog_spec_type",
                "prefers_gpu",
                "min_memory_gb",
                "analysis_status",
                "analysis_confidence",
                "analysis_reasons",
                "analysis_warnings",
                "notes",
            )


    class ServiceDependencyForm(NautobotModelForm):
        """Edit form for dependency metadata."""

        class Meta:
            model = ServiceDependency
            fields = (
                "source_service",
                "kind",
                "namespace",
                "name",
                "raw_ref",
                "dependency_type",
                "resolution_status",
                "resolved_service",
                "notes",
            )
