"""Add explicit service placement and desired node operational policy."""

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_intent_catalog", "0003_desired_node_actual_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="DesiredServicePlacement",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("instance_name", models.SlugField(max_length=255)),
                (
                    "desired_state",
                    models.CharField(
                        choices=[("active", "Active"), ("disabled", "Disabled")],
                        default="active",
                        max_length=32,
                    ),
                ),
                ("instance_role", models.CharField(blank=True, max_length=64, null=True)),
                ("deployment_profile", models.SlugField(max_length=255)),
                ("config_schema_version", models.CharField(max_length=64)),
                ("config", models.JSONField(blank=True, default=dict)),
                (
                    "assignment_source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("yaml", "YAML"),
                            ("policy", "Policy"),
                            ("generated", "Generated"),
                        ],
                        default="manual",
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField(blank=True, null=True)),
                (
                    "desired_endpoint",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="service_placements",
                        to="nautobot_intent_catalog.desiredendpoint",
                    ),
                ),
                (
                    "desired_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="service_placements",
                        to="nautobot_intent_catalog.desirednode",
                    ),
                ),
                (
                    "desired_service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="placements",
                        to="nautobot_intent_catalog.desiredservice",
                    ),
                ),
            ],
            options={
                "verbose_name": "desired service placement",
                "verbose_name_plural": "desired service placements",
                "ordering": ("desired_service__name", "instance_name"),
            },
        ),
        migrations.CreateModel(
            name="DesiredNodeOperationalConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                (
                    "actual_state_policy",
                    models.CharField(
                        choices=[("required", "Required"), ("declared", "Declared")],
                        max_length=32,
                    ),
                ),
                (
                    "expected_host_os",
                    models.CharField(
                        blank=True,
                        choices=[("linux", "Linux"), ("macos", "macOS")],
                        max_length=32,
                        null=True,
                    ),
                ),
                (
                    "declared_host_os",
                    models.CharField(
                        blank=True,
                        choices=[("haos", "Home Assistant OS")],
                        max_length=32,
                        null=True,
                    ),
                ),
                (
                    "connection_path",
                    models.CharField(
                        choices=[("local", "Local"), ("tailscale", "Tailscale")],
                        max_length=32,
                    ),
                ),
                ("ansible_port", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "power_control",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("wol", "Wake-on-LAN"),
                            ("macos_sleep", "macOS sleep"),
                        ],
                        default="none",
                        max_length=32,
                    ),
                ),
                ("is_laptop", models.BooleanField(default=False)),
                (
                    "desired_node",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="operational_config",
                        to="nautobot_intent_catalog.desirednode",
                    ),
                ),
                (
                    "local_endpoint",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="local_operational_configs",
                        to="nautobot_intent_catalog.desiredendpoint",
                    ),
                ),
                (
                    "tailscale_endpoint",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tailscale_operational_configs",
                        to="nautobot_intent_catalog.desiredendpoint",
                    ),
                ),
            ],
            options={
                "verbose_name": "desired node operational config",
                "verbose_name_plural": "desired node operational configs",
                "ordering": ("desired_node__name",),
            },
        ),
        migrations.AddConstraint(
            model_name="desiredserviceplacement",
            constraint=models.UniqueConstraint(
                fields=("desired_service", "instance_name"),
                name="nic_unique_service_instance",
            ),
        ),
        migrations.AddConstraint(
            model_name="desiredserviceplacement",
            constraint=models.CheckConstraint(
                check=~models.Q(deployment_profile=""),
                name="nic_placement_profile_nonempty",
            ),
        ),
        migrations.AddConstraint(
            model_name="desiredserviceplacement",
            constraint=models.CheckConstraint(
                check=~models.Q(config_schema_version=""),
                name="nic_placement_schema_nonempty",
            ),
        ),
        migrations.AddConstraint(
            model_name="desiredserviceplacement",
            constraint=models.CheckConstraint(
                check=models.expressions.RawSQL(
                    "jsonb_typeof(config) = 'object'",
                    (),
                    output_field=models.BooleanField(),
                ),
                name="nic_placement_config_object",
            ),
        ),
        migrations.AddConstraint(
            model_name="desirednodeoperationalconfig",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(
                        actual_state_policy="required",
                        expected_host_os__in=("linux", "macos"),
                        declared_host_os__isnull=True,
                    )
                    | models.Q(
                        actual_state_policy="declared",
                        expected_host_os__isnull=True,
                        declared_host_os="haos",
                    )
                ),
                name="nic_operational_host_os_policy",
            ),
        ),
    ]
