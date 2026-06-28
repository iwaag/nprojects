"""Forms for Intent Catalog models."""

from __future__ import annotations

try:
    from django import forms
    from django.utils.text import slugify
    from nautobot.apps.forms import NautobotModelForm

    from .models import (
        DesiredDependency,
        DesiredEndpoint,
        DesiredIPRange,
        DesiredNode,
        DesiredNodeOperationalConfig,
        DesiredService,
        DesiredServicePlacement,
        IntentEvaluation,
        IntentSource,
    )
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    pass
else:

    class DesiredHostQuickAddForm(forms.Form):
        """Quick-add form for one desired node and its primary endpoint."""

        name = forms.CharField(max_length=255)
        slug = forms.SlugField(max_length=255, required=False)
        node_type = forms.ChoiceField(
            choices=DesiredNode.NODE_TYPE_CHOICES,
            initial=DesiredNode.NODE_TYPE_VIRTUAL_MACHINE,
        )
        accepted_actual_types = forms.JSONField(required=False, widget=forms.HiddenInput)
        lifecycle = forms.ChoiceField(
            choices=DesiredNode.LIFECYCLE_CHOICES,
            initial=DesiredNode.LIFECYCLE_PLANNED,
        )
        role = forms.CharField(max_length=255, required=False)
        description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
        intent_source = forms.ModelChoiceField(queryset=IntentSource.objects.all(), required=False)
        ip_address = forms.CharField(max_length=128, required=False)
        dns_name = forms.CharField(max_length=255, required=False)
        mdns_name = forms.CharField(max_length=255, required=False)
        vpn_dns_name = forms.CharField(max_length=255, required=False)
        protocol = forms.CharField(max_length=64, required=False)
        port = forms.IntegerField(required=False, min_value=1, max_value=65535)
        generate_dnsmasq = forms.BooleanField(required=False, initial=True)
        ip_policy = forms.ChoiceField(
            choices=DesiredEndpoint.IP_POLICY_CHOICES,
            initial=DesiredEndpoint.IP_POLICY_DHCP_RESERVED,
        )
        dnsmasq_record_type = forms.ChoiceField(
            choices=DesiredEndpoint.DNSMASQ_RECORD_TYPE_CHOICES,
            initial=DesiredEndpoint.DNSMASQ_HOST_RECORD,
        )
        endpoint_name = forms.CharField(
            max_length=255,
            initial=DesiredEndpoint.ENDPOINT_TYPE_PRIMARY,
            widget=forms.HiddenInput,
        )
        endpoint_type = forms.ChoiceField(
            choices=DesiredEndpoint.ENDPOINT_TYPE_CHOICES,
            initial=DesiredEndpoint.ENDPOINT_TYPE_PRIMARY,
            widget=forms.HiddenInput,
        )

        def clean_slug(self):
            """Generate a slug from name when omitted."""

            slug = self.cleaned_data.get("slug")
            if slug:
                return slug

            generated_slug = slugify(self.cleaned_data.get("name") or "")
            if not generated_slug:
                raise forms.ValidationError("Enter a slug or a name that can be converted to a slug.")
            return generated_slug

        def node_data(self):
            """Return cleaned values for DesiredNode creation."""

            return {
                "name": self.cleaned_data["name"],
                "slug": self.cleaned_data["slug"],
                "node_type": self.cleaned_data["node_type"],
                "accepted_actual_types": self.cleaned_data.get("accepted_actual_types"),
                "lifecycle": self.cleaned_data["lifecycle"],
                "role": self.cleaned_data.get("role"),
                "description": self.cleaned_data.get("description"),
                "intent_source": self.cleaned_data.get("intent_source"),
            }

        def endpoint_data(self):
            """Return cleaned values for DesiredEndpoint creation."""

            return {
                "ip_address": self.cleaned_data.get("ip_address"),
                "dns_name": self.cleaned_data.get("dns_name"),
                "mdns_name": self.cleaned_data.get("mdns_name"),
                "vpn_dns_name": self.cleaned_data.get("vpn_dns_name"),
                "protocol": self.cleaned_data.get("protocol"),
                "port": self.cleaned_data.get("port"),
                "generate_dnsmasq": self.cleaned_data.get("generate_dnsmasq"),
                "ip_policy": self.cleaned_data["ip_policy"],
                "dnsmasq_record_type": self.cleaned_data["dnsmasq_record_type"],
                "endpoint_name": self.cleaned_data["endpoint_name"],
                "endpoint_type": self.cleaned_data["endpoint_type"],
            }

        def operation_kwargs(self):
            """Return operation-ready keyword arguments."""

            return {**self.node_data(), **self.endpoint_data()}


    class DesiredServicePlacementQuickAddForm(forms.Form):
        """Quick-add form for one desired service placement.

        Operators only choose what they actually decide: the service, the node,
        the deployment profile, and the profile's config values.  Derived values
        (``config_schema_version``, ``assignment_source``) are never shown; the
        operation derives/fixes them.  ``deployment_profile`` choices and the
        dynamic ``config`` fields come from the synced deployment_profiles
        projection passed in as ``profiles``.
        """

        desired_service = forms.ModelChoiceField(queryset=DesiredService.objects.all())
        desired_node = forms.ModelChoiceField(queryset=DesiredNode.objects.all())
        deployment_profile = forms.ChoiceField(choices=())
        instance_name = forms.SlugField(max_length=255, required=False)
        desired_endpoint = forms.ModelChoiceField(
            queryset=DesiredEndpoint.objects.none(),
            required=False,
        )
        desired_state = forms.ChoiceField(
            choices=DesiredServicePlacement.DESIRED_STATE_CHOICES,
            initial=DesiredServicePlacement.STATE_ACTIVE,
        )
        instance_role = forms.CharField(max_length=64, required=False)
        reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

        def __init__(self, *args, profiles=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.profiles = dict(profiles or {})
            self._config_field_map: dict[str, str] = {}

            self.fields["deployment_profile"].choices = [("", "---------")] + [
                (name, name) for name in sorted(self.profiles)
            ]

            node = self._raw_value("desired_node")
            if node:
                self.fields["desired_endpoint"].queryset = DesiredEndpoint.objects.filter(
                    desired_node=node
                )

            profile_name = self._raw_value("deployment_profile")
            if profile_name and profile_name in self.profiles:
                self._build_config_fields(self.profiles[profile_name])

        def clean(self):
            cleaned = super().clean()
            if not self.profiles:
                # Never silently present an empty profile picker; tell the operator
                # to sync, using the same input as production inventory export.
                raise forms.ValidationError(
                    "No deployment profiles are synced. Run the Sync Deployment Profiles "
                    "Job with the same input used for production inventory export, then retry."
                )
            return cleaned

        def config_fields(self):
            """Yield the dynamically generated bound config fields for templates."""

            return [self[field_name] for field_name in self._config_field_map]

        def config_data(self):
            """Assemble the placement config dict from generated profile fields."""

            config: dict = {}
            for field_name, key in self._config_field_map.items():
                if field_name not in self.cleaned_data:
                    continue
                value = self.cleaned_data.get(field_name)
                if isinstance(self.fields[field_name], forms.BooleanField):
                    config[key] = bool(value)
                elif value is not None and value != "":
                    config[key] = value
            return config

        def operation_kwargs(self):
            """Return operation-ready keyword arguments for the placement operation."""

            cleaned = self.cleaned_data
            return {
                "desired_service": cleaned["desired_service"],
                "desired_node": cleaned["desired_node"],
                "deployment_profile": cleaned["deployment_profile"],
                "profiles": self.profiles,
                "instance_name": cleaned.get("instance_name") or None,
                "desired_endpoint": cleaned.get("desired_endpoint"),
                "desired_state": cleaned.get("desired_state") or DesiredServicePlacement.STATE_ACTIVE,
                "instance_role": cleaned.get("instance_role") or None,
                "config": self.config_data(),
                "reason": cleaned.get("reason") or None,
            }

        def _build_config_fields(self, profile):
            for key in sorted(profile.get("variables", {})):
                field_name = self._config_field_name(key)
                self.fields[field_name] = self._config_field(key, profile["variables"][key])
                self._config_field_map[field_name] = key

        def _config_field(self, key, definition):
            value_type = definition.get("type")
            required = bool(definition.get("required"))
            common = {
                "label": key,
                "help_text": f"{value_type} ({'required' if required else 'optional'})",
            }
            if value_type == "integer":
                return forms.IntegerField(required=required, **common)
            if value_type == "number":
                return forms.FloatField(required=required, **common)
            if value_type == "boolean":
                # Presence-by-value: a boolean key is always present, so required
                # is satisfied without forcing the checkbox to be ticked.
                return forms.BooleanField(required=False, **common)
            if value_type == "list":
                return forms.JSONField(required=required, **common)
            return forms.CharField(required=required, **common)

        @staticmethod
        def _config_field_name(key):
            return f"config__{key}"

        def _raw_value(self, field_name):
            if self.is_bound:
                return self.data.get(self.add_prefix(field_name))
            value = self.initial.get(field_name)
            if value is None:
                value = self.fields[field_name].initial
            return value


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
                "accepted_actual_types",
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
                "ip_policy",
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


    class DesiredServicePlacementForm(NautobotModelForm):
        """Create or edit an explicit desired service placement.

        ``config_schema_version`` and ``assignment_source`` are intentionally not
        operator inputs: the contract only supports a single config schema version
        (the model default), and manual CRUD always means ``assignment_source``
        ``manual`` (the model default).  Keeping them off the form matches the
        Quick Add path, which derives/fixes the same two values in the operation.
        """

        class Meta:
            model = DesiredServicePlacement
            fields = (
                "desired_service",
                "instance_name",
                "desired_node",
                "desired_endpoint",
                "desired_state",
                "instance_role",
                "deployment_profile",
                "config",
                "reason",
            )


    class DesiredNodeOperationalConfigForm(NautobotModelForm):
        """Create or edit desired node execution policy."""

        class Meta:
            model = DesiredNodeOperationalConfig
            fields = (
                "desired_node",
                "actual_state_policy",
                "expected_host_os",
                "declared_host_os",
                "connection_path",
                "local_endpoint",
                "tailscale_endpoint",
                "ansible_port",
                "power_control",
                "is_laptop",
            )


    class DesiredIPRangeForm(NautobotModelForm):
        """Edit form for desired IP ranges."""

        class Meta:
            model = DesiredIPRange
            fields = (
                "name",
                "slug",
                "start_address",
                "end_address",
                "range_policy",
                "lifecycle",
                "generate_dnsmasq",
                "dnsmasq_options",
                "description",
            )


    class IntentEvaluationForm(NautobotModelForm):
        """Edit form for persisted intent evaluations."""

        class Meta:
            model = IntentEvaluation
            fields = (
                "target_type",
                "target_id",
                "status",
                "deterministic_summary",
                "actual_refs",
                "observed_facts",
                "expected_facts",
                "gap_summary",
                "ai_review",
                "recommended_actions",
                "review_model",
                "source_hash",
                "reviewed_at",
            )
