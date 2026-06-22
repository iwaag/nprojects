"""Table definitions for Intent Catalog models."""

from __future__ import annotations

try:
    import django_tables2 as tables
    from nautobot.apps.tables import BaseTable, ButtonsColumn, ToggleColumn

    from .models import DesiredDependency, DesiredEndpoint, DesiredNode, DesiredService, IntentSource
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


    class DesiredNodeTable(BaseTable):
        """Desired node list table."""

        pk = ToggleColumn()
        name = tables.LinkColumn()
        intent_source = tables.LinkColumn()
        realized_device = tables.LinkColumn()
        realized_vm = tables.LinkColumn()
        endpoint_count = tables.Column(empty_values=(), verbose_name="Endpoints")
        actions = ButtonsColumn(DesiredNode)

        def render_endpoint_count(self, record):
            """Return endpoint count for display."""

            return record.desired_endpoints.count()

        class Meta(BaseTable.Meta):
            model = DesiredNode
            fields = (
                "pk",
                "name",
                "node_type",
                "lifecycle",
                "role",
                "intent_source",
                "realized_device",
                "realized_vm",
                "endpoint_count",
                "actions",
            )
            default_columns = (
                "pk",
                "name",
                "node_type",
                "lifecycle",
                "role",
                "intent_source",
                "endpoint_count",
                "actions",
            )


    class DesiredEndpointTable(BaseTable):
        """Desired endpoint list table."""

        pk = ToggleColumn()
        name = tables.LinkColumn()
        desired_node = tables.LinkColumn()
        realized_ip_address = tables.LinkColumn()
        actions = ButtonsColumn(DesiredEndpoint)

        class Meta(BaseTable.Meta):
            model = DesiredEndpoint
            fields = (
                "pk",
                "name",
                "desired_node",
                "endpoint_type",
                "ip_address",
                "dns_name",
                "protocol",
                "port",
                "generate_dnsmasq",
                "dnsmasq_record_type",
                "realized_ip_address",
                "actions",
            )
            default_columns = (
                "pk",
                "name",
                "desired_node",
                "endpoint_type",
                "ip_address",
                "dns_name",
                "protocol",
                "port",
                "generate_dnsmasq",
                "actions",
            )
