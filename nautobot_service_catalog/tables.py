"""Table definitions for Service Catalog models."""

from __future__ import annotations

try:
    import django_tables2 as tables
    from nautobot.apps.tables import BaseTable, ButtonsColumn, ToggleColumn

    from .models import DesiredServiceCandidate, ServiceDependency, ServiceRepository
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    pass
else:

    class ServiceRepositoryTable(BaseTable):
        """Repository list table."""

        pk = ToggleColumn()
        url = tables.LinkColumn()
        actions = ButtonsColumn(ServiceRepository)

        class Meta(BaseTable.Meta):
            model = ServiceRepository
            fields = (
                "pk",
                "url",
                "enabled",
                "owner",
                "service_hint",
                "last_analysis_status",
                "last_analyzed_at",
                "actions",
            )
            default_columns = (
                "pk",
                "url",
                "enabled",
                "owner",
                "service_hint",
                "last_analysis_status",
                "last_analyzed_at",
                "actions",
            )


    class DesiredServiceCandidateTable(BaseTable):
        """Desired service candidate list table."""

        pk = ToggleColumn()
        name = tables.LinkColumn()
        source_repository = tables.LinkColumn()
        dependency_count = tables.Column(empty_values=(), verbose_name="Dependencies")
        actions = ButtonsColumn(DesiredServiceCandidate)

        def render_dependency_count(self, record):
            """Return dependency count for display."""

            return record.dependencies.count()

        class Meta(BaseTable.Meta):
            model = DesiredServiceCandidate
            fields = (
                "pk",
                "name",
                "display_name",
                "role",
                "source_repository",
                "catalog_owner",
                "analysis_status",
                "dependency_count",
                "actions",
            )
            default_columns = (
                "pk",
                "name",
                "display_name",
                "role",
                "source_repository",
                "catalog_owner",
                "analysis_status",
                "dependency_count",
                "actions",
            )


    class ServiceDependencyTable(BaseTable):
        """Service dependency list table."""

        pk = ToggleColumn()
        source_service = tables.LinkColumn()
        resolved_service = tables.LinkColumn()
        actions = ButtonsColumn(ServiceDependency)

        class Meta(BaseTable.Meta):
            model = ServiceDependency
            fields = (
                "pk",
                "source_service",
                "kind",
                "namespace",
                "name",
                "resolution_status",
                "resolved_service",
                "actions",
            )
            default_columns = (
                "pk",
                "source_service",
                "kind",
                "namespace",
                "name",
                "resolution_status",
                "resolved_service",
                "actions",
            )
