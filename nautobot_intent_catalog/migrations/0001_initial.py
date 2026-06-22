# Generated manually for the initial Intent Catalog models.

from __future__ import annotations

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="IntentSource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("name", models.CharField(max_length=255)),
                ("slug", models.SlugField(max_length=255, unique=True)),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("git_repository", "Git repository"),
                            ("yaml_file", "YAML file"),
                            ("manual", "Manual"),
                            ("api", "API"),
                            ("generated", "Generated"),
                        ],
                        default="git_repository",
                        max_length=64,
                    ),
                ),
                ("url", models.URLField(blank=True, null=True, unique=True)),
                ("ref", models.CharField(blank=True, max_length=255, null=True)),
                ("enabled", models.BooleanField(default=True)),
                ("owner", models.CharField(blank=True, max_length=255, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("source_config", models.JSONField(blank=True, default=dict)),
                ("last_import_status", models.CharField(blank=True, max_length=64, null=True)),
                ("last_imported_at", models.DateTimeField(blank=True, null=True)),
                ("last_import_summary", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "intent source",
                "verbose_name_plural": "intent sources",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="DesiredService",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("name", models.SlugField(max_length=255)),
                ("slug", models.SlugField(max_length=255)),
                ("display_name", models.CharField(max_length=255)),
                (
                    "service_type",
                    models.CharField(
                        choices=[
                            ("service", "Service"),
                            ("website", "Website"),
                            ("worker", "Worker"),
                            ("database", "Database"),
                            ("queue", "Queue"),
                            ("storage", "Storage"),
                            ("agent", "Agent"),
                            ("other", "Other"),
                        ],
                        default="service",
                        max_length=64,
                    ),
                ),
                (
                    "lifecycle",
                    models.CharField(
                        choices=[
                            ("proposed", "Proposed"),
                            ("planned", "Planned"),
                            ("approved", "Approved"),
                            ("active", "Active"),
                            ("deprecated", "Deprecated"),
                            ("retired", "Retired"),
                        ],
                        default="proposed",
                        max_length=64,
                    ),
                ),
                ("source_ref", models.CharField(blank=True, max_length=255, null=True)),
                ("source_catalog_path", models.CharField(blank=True, max_length=512, null=True)),
                ("catalog_kind", models.CharField(blank=True, max_length=64, null=True)),
                ("catalog_namespace", models.CharField(default="default", max_length=255)),
                ("catalog_metadata_name", models.CharField(max_length=255)),
                ("catalog_owner", models.CharField(blank=True, max_length=255, null=True)),
                ("catalog_lifecycle", models.CharField(blank=True, max_length=64, null=True)),
                ("prefers_gpu", models.BooleanField(default=False)),
                ("min_memory_gb", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("requirements", models.JSONField(blank=True, default=dict)),
                ("placement_policy", models.JSONField(blank=True, default=dict)),
                ("notes", models.TextField(blank=True, null=True)),
                ("last_analyzed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "intent_source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="desired_services",
                        to="nautobot_intent_catalog.intentsource",
                    ),
                ),
            ],
            options={
                "verbose_name": "desired service",
                "verbose_name_plural": "desired services",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="DesiredDependency",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("dependency_kind", models.CharField(max_length=64)),
                ("namespace", models.CharField(default="default", max_length=255)),
                ("name", models.CharField(max_length=255)),
                ("raw_ref", models.CharField(max_length=512)),
                ("dependency_type", models.CharField(max_length=64)),
                (
                    "resolution_status",
                    models.CharField(
                        choices=[
                            ("unresolved", "Unresolved"),
                            ("resolved", "Resolved"),
                            ("external", "External"),
                            ("ignored", "Ignored"),
                        ],
                        default="unresolved",
                        max_length=64,
                    ),
                ),
                ("notes", models.TextField(blank=True, null=True)),
                (
                    "resolved_service",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resolved_by_dependencies",
                        to="nautobot_intent_catalog.desiredservice",
                    ),
                ),
                (
                    "source_service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dependencies",
                        to="nautobot_intent_catalog.desiredservice",
                    ),
                ),
            ],
            options={
                "verbose_name": "desired dependency",
                "verbose_name_plural": "desired dependencies",
                "ordering": ("source_service__name", "dependency_kind", "namespace", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="desiredservice",
            constraint=models.UniqueConstraint(
                fields=("intent_source", "catalog_namespace", "catalog_metadata_name", "service_type"),
                name="nic_unique_service_catalog_entity",
            ),
        ),
        migrations.AddConstraint(
            model_name="desireddependency",
            constraint=models.UniqueConstraint(
                fields=("source_service", "dependency_kind", "namespace", "name"),
                name="nic_unique_dependency_ref",
            ),
        ),
    ]
