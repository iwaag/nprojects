"""Table definitions for Intent Catalog models."""

from __future__ import annotations

try:
    import django_tables2 as tables
    from nautobot.apps.tables import BaseTable, ButtonsColumn, ToggleColumn

    from .models import DesiredDependency, DesiredService, IntentSource
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    pass
else:

    class IntentSourceTable(BaseTable):
        """Intent source list table."""

        pk = ToggleColumn()
        name = tables.LinkColumn()
        actions = ButtonsColumn(IntentSource)

        class Meta(BaseTable.Meta):
            model = IntentSource
            fields = (
                "pk",
                "name",
                "source_type",
                "url",
                "enabled",
                "owner",
                "last_import_status",
                "last_imported_at",
                "actions",
            )
            default_columns = (
                "pk",
                "name",
                "source_type",
                "url",
                "enabled",
                "owner",
                "last_import_status",
                "last_imported_at",
                "actions",
            )


    class DesiredServiceTable(BaseTable):
        """Desired service list table."""

        pk = ToggleColumn()
        name = tables.LinkColumn()
        intent_source = tables.LinkColumn()
        dependency_count = tables.Column(empty_values=(), verbose_name="Dependencies")
        actions = ButtonsColumn(DesiredService)

        def render_dependency_count(self, record):
            """Return dependency count for display."""

            return record.dependencies.count()

        class Meta(BaseTable.Meta):
            model = DesiredService
            fields = (
                "pk",
                "name",
                "display_name",
                "service_type",
                "lifecycle",
                "intent_source",
                "catalog_owner",
                "dependency_count",
                "actions",
            )
            default_columns = (
                "pk",
                "name",
                "display_name",
                "service_type",
                "lifecycle",
                "intent_source",
                "catalog_owner",
                "dependency_count",
                "actions",
            )


    class DesiredDependencyTable(BaseTable):
        """Desired dependency list table."""

        pk = ToggleColumn()
        source_service = tables.LinkColumn()
        resolved_service = tables.LinkColumn()
        actions = ButtonsColumn(DesiredDependency)

        class Meta(BaseTable.Meta):
            model = DesiredDependency
            fields = (
                "pk",
                "source_service",
                "dependency_kind",
                "namespace",
                "name",
                "resolution_status",
                "resolved_service",
                "actions",
            )
            default_columns = (
                "pk",
                "source_service",
                "dependency_kind",
                "namespace",
                "name",
                "resolution_status",
                "resolved_service",
                "actions",
            )
