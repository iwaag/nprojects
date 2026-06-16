# Generated manually for the initial Service Catalog models.

from __future__ import annotations

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ServiceRepository",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("url", models.URLField(unique=True)),
                ("enabled", models.BooleanField(default=True)),
                ("ref", models.CharField(blank=True, max_length=255, null=True)),
                ("owner", models.CharField(blank=True, max_length=255, null=True)),
                ("service_hint", models.CharField(blank=True, max_length=255, null=True)),
                ("catalog_paths", models.JSONField(blank=True, default=list)),
                ("basic_file_paths", models.JSONField(blank=True, default=list)),
                ("raw_url_template", models.CharField(blank=True, max_length=1024, null=True)),
                ("last_analysis_status", models.CharField(blank=True, max_length=64, null=True)),
                ("last_analyzed_at", models.DateTimeField(blank=True, null=True)),
                ("last_analysis_summary", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "service repository",
                "verbose_name_plural": "service repositories",
                "ordering": ("url",),
            },
        ),
        migrations.CreateModel(
            name="DesiredServiceCandidate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("name", models.SlugField(max_length=255)),
                ("display_name", models.CharField(max_length=255)),
                ("role", models.CharField(max_length=64)),
                ("source_ref", models.CharField(blank=True, max_length=255, null=True)),
                ("source_catalog_path", models.CharField(blank=True, max_length=512, null=True)),
                ("catalog_kind", models.CharField(blank=True, max_length=64, null=True)),
                ("catalog_namespace", models.CharField(default="default", max_length=255)),
                ("catalog_metadata_name", models.CharField(max_length=255)),
                ("catalog_owner", models.CharField(blank=True, max_length=255, null=True)),
                ("catalog_lifecycle", models.CharField(blank=True, max_length=64, null=True)),
                ("catalog_spec_type", models.CharField(blank=True, max_length=64, null=True)),
                ("prefers_gpu", models.BooleanField(default=False)),
                ("min_memory_gb", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("analysis_status", models.CharField(blank=True, max_length=64, null=True)),
                ("analysis_confidence", models.CharField(blank=True, max_length=64, null=True)),
                ("analysis_reasons", models.JSONField(blank=True, default=list)),
                ("analysis_warnings", models.JSONField(blank=True, default=list)),
                ("notes", models.TextField(blank=True, null=True)),
                ("last_analyzed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source_repository",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="desired_service_candidates",
                        to="nautobot_service_catalog.servicerepository",
                    ),
                ),
            ],
            options={
                "verbose_name": "desired service candidate",
                "verbose_name_plural": "desired service candidates",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="ServiceDependency",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("_custom_field_data", models.JSONField(blank=True, default=dict, editable=False)),
                ("kind", models.CharField(max_length=64)),
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
                        to="nautobot_service_catalog.desiredservicecandidate",
                    ),
                ),
                (
                    "source_service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dependencies",
                        to="nautobot_service_catalog.desiredservicecandidate",
                    ),
                ),
            ],
            options={
                "verbose_name": "service dependency",
                "verbose_name_plural": "service dependencies",
                "ordering": ("source_service__name", "kind", "namespace", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="desiredservicecandidate",
            constraint=models.UniqueConstraint(
                fields=("source_repository", "catalog_namespace", "catalog_metadata_name", "catalog_spec_type"),
                name="npsc_unique_candidate_catalog_entity",
            ),
        ),
        migrations.AddConstraint(
            model_name="servicedependency",
            constraint=models.UniqueConstraint(
                fields=("source_service", "kind", "namespace", "name"),
                name="npsc_unique_dependency_ref",
            ),
        ),
    ]
