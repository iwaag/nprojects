"""Forms for Intent Catalog models."""

from __future__ import annotations

try:
    from nautobot.apps.forms import NautobotModelForm

    from .models import DesiredDependency, DesiredEndpoint, DesiredNode, DesiredService, IntentSource
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    pass
else:

    class IntentSourceForm(NautobotModelForm):
        """Create/edit form for intent sources."""

        class Meta:
            model = IntentSource
            fields = (
                "name",
                "slug",
                "source_type",
                "url",
                "ref",
                "enabled",
                "owner",
                "description",
                "source_config",
                "last_import_status",
                "last_import_summary",
            )


    class DesiredServiceForm(NautobotModelForm):
        """Edit form for desired services."""

        class Meta:
            model = DesiredService
            fields = (
                "name",
                "slug",
                "display_name",
                "service_type",
                "lifecycle",
                "intent_source",
                "source_ref",
                "source_catalog_path",
                "catalog_kind",
                "catalog_namespace",
                "catalog_metadata_name",
                "catalog_owner",
                "catalog_lifecycle",
                "prefers_gpu",
                "min_memory_gb",
                "requirements",
                "placement_policy",
                "notes",
            )


    class DesiredDependencyForm(NautobotModelForm):
        """Edit form for dependency metadata."""

        class Meta:
            model = DesiredDependency
            fields = (
                "source_service",
                "dependency_kind",
                "namespace",
                "name",
                "raw_ref",
                "dependency_type",
                "resolution_status",
                "resolved_service",
                "notes",
            )


    class DesiredNodeForm(NautobotModelForm):
        """Edit form for desired nodes."""

        class Meta:
            model = DesiredNode
            fields = (
                "name",
                "slug",
                "node_type",
                "lifecycle",
                "role",
                "description",
                "expected_spec",
                "intent_source",
                "realized_device",
                "realized_vm",
                "notes",
            )


    class DesiredEndpointForm(NautobotModelForm):
        """Edit form for desired endpoints."""

        class Meta:
            model = DesiredEndpoint
            fields = (
                "name",
                "desired_node",
                "endpoint_type",
                "ip_address",
                "dns_name",
                "mdns_name",
                "vpn_dns_name",
                "protocol",
                "port",
                "generate_dnsmasq",
                "dnsmasq_record_type",
                "realized_ip_address",
                "description",
            )
