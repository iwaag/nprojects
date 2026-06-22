"""Database models for the Nautobot Intent Catalog App."""

from __future__ import annotations

try:
    from django.db import models
    from django.urls import reverse
    from nautobot.apps.models import PrimaryModel
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    PrimaryModel = object  # type: ignore[assignment]
else:

    class IntentSource(PrimaryModel):
        """Input source record used for intent import and analysis."""

        SOURCE_GIT_REPOSITORY = "git_repository"
        SOURCE_YAML_FILE = "yaml_file"
        SOURCE_MANUAL = "manual"
        SOURCE_API = "api"
        SOURCE_GENERATED = "generated"
        SOURCE_TYPE_CHOICES = (
            (SOURCE_GIT_REPOSITORY, "Git repository"),
            (SOURCE_YAML_FILE, "YAML file"),
            (SOURCE_MANUAL, "Manual"),
            (SOURCE_API, "API"),
            (SOURCE_GENERATED, "Generated"),
        )

        name = models.CharField(max_length=255)
        slug = models.SlugField(max_length=255, unique=True)
        source_type = models.CharField(
            max_length=64,
            choices=SOURCE_TYPE_CHOICES,
            default=SOURCE_GIT_REPOSITORY,
        )
        url = models.URLField(unique=True, blank=True, null=True)
        ref = models.CharField(max_length=255, blank=True, null=True)
        enabled = models.BooleanField(default=True)
        owner = models.CharField(max_length=255, blank=True, null=True)
        description = models.TextField(blank=True, null=True)
        source_config = models.JSONField(default=dict, blank=True)
        last_import_status = models.CharField(max_length=64, blank=True, null=True)
        last_imported_at = models.DateTimeField(blank=True, null=True)
        last_import_summary = models.JSONField(default=dict, blank=True)

        class Meta:
            ordering = ("name",)
            verbose_name = "intent source"
            verbose_name_plural = "intent sources"

        def __str__(self) -> str:
            return self.name

        def get_absolute_url(self) -> str:
            return reverse("plugins:nautobot_intent_catalog:intentsource", args=[self.pk])


    class DesiredService(PrimaryModel):
        """Desired service generated from source metadata."""

        SERVICE_TYPE_SERVICE = "service"
        SERVICE_TYPE_WEBSITE = "website"
        SERVICE_TYPE_WORKER = "worker"
        SERVICE_TYPE_DATABASE = "database"
        SERVICE_TYPE_QUEUE = "queue"
        SERVICE_TYPE_STORAGE = "storage"
        SERVICE_TYPE_AGENT = "agent"
        SERVICE_TYPE_OTHER = "other"
        SERVICE_TYPE_CHOICES = (
            (SERVICE_TYPE_SERVICE, "Service"),
            (SERVICE_TYPE_WEBSITE, "Website"),
            (SERVICE_TYPE_WORKER, "Worker"),
            (SERVICE_TYPE_DATABASE, "Database"),
            (SERVICE_TYPE_QUEUE, "Queue"),
            (SERVICE_TYPE_STORAGE, "Storage"),
            (SERVICE_TYPE_AGENT, "Agent"),
            (SERVICE_TYPE_OTHER, "Other"),
        )

        LIFECYCLE_PROPOSED = "proposed"
        LIFECYCLE_PLANNED = "planned"
        LIFECYCLE_APPROVED = "approved"
        LIFECYCLE_ACTIVE = "active"
        LIFECYCLE_DEPRECATED = "deprecated"
        LIFECYCLE_RETIRED = "retired"
        LIFECYCLE_CHOICES = (
            (LIFECYCLE_PROPOSED, "Proposed"),
            (LIFECYCLE_PLANNED, "Planned"),
            (LIFECYCLE_APPROVED, "Approved"),
            (LIFECYCLE_ACTIVE, "Active"),
            (LIFECYCLE_DEPRECATED, "Deprecated"),
            (LIFECYCLE_RETIRED, "Retired"),
        )

        name = models.SlugField(max_length=255)
        slug = models.SlugField(max_length=255)
        display_name = models.CharField(max_length=255)
        service_type = models.CharField(
            max_length=64,
            choices=SERVICE_TYPE_CHOICES,
            default=SERVICE_TYPE_SERVICE,
        )
        lifecycle = models.CharField(
            max_length=64,
            choices=LIFECYCLE_CHOICES,
            default=LIFECYCLE_PROPOSED,
        )
        intent_source = models.ForeignKey(
            IntentSource,
            on_delete=models.CASCADE,
            related_name="desired_services",
        )
        source_ref = models.CharField(max_length=255, blank=True, null=True)
        source_catalog_path = models.CharField(max_length=512, blank=True, null=True)
        catalog_kind = models.CharField(max_length=64, blank=True, null=True)
        catalog_namespace = models.CharField(max_length=255, default="default")
        catalog_metadata_name = models.CharField(max_length=255)
        catalog_owner = models.CharField(max_length=255, blank=True, null=True)
        catalog_lifecycle = models.CharField(max_length=64, blank=True, null=True)
        prefers_gpu = models.BooleanField(default=False)
        min_memory_gb = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
        requirements = models.JSONField(default=dict, blank=True)
        placement_policy = models.JSONField(default=dict, blank=True)
        notes = models.TextField(blank=True, null=True)
        last_analyzed_at = models.DateTimeField(blank=True, null=True)

        class Meta:
            ordering = ("name",)
            verbose_name = "desired service"
            verbose_name_plural = "desired services"
            constraints = (
                models.UniqueConstraint(
                    fields=(
                        "intent_source",
                        "catalog_namespace",
                        "catalog_metadata_name",
                        "service_type",
                    ),
                    name="nic_unique_service_catalog_entity",
                ),
            )

        def __str__(self) -> str:
            return self.display_name or self.name

        def get_absolute_url(self) -> str:
            return reverse("plugins:nautobot_intent_catalog:desiredservice", args=[self.pk])


    class DesiredDependency(PrimaryModel):
        """Dependency metadata attached to a desired service."""

        RESOLUTION_UNRESOLVED = "unresolved"
        RESOLUTION_RESOLVED = "resolved"
        RESOLUTION_EXTERNAL = "external"
        RESOLUTION_IGNORED = "ignored"
        RESOLUTION_STATUS_CHOICES = (
            (RESOLUTION_UNRESOLVED, "Unresolved"),
            (RESOLUTION_RESOLVED, "Resolved"),
            (RESOLUTION_EXTERNAL, "External"),
            (RESOLUTION_IGNORED, "Ignored"),
        )

        source_service = models.ForeignKey(
            DesiredService,
            on_delete=models.CASCADE,
            related_name="dependencies",
        )
        dependency_kind = models.CharField(max_length=64)
        namespace = models.CharField(max_length=255, default="default")
        name = models.CharField(max_length=255)
        raw_ref = models.CharField(max_length=512)
        dependency_type = models.CharField(max_length=64)
        resolution_status = models.CharField(
            max_length=64,
            choices=RESOLUTION_STATUS_CHOICES,
            default=RESOLUTION_UNRESOLVED,
        )
        resolved_service = models.ForeignKey(
            DesiredService,
            on_delete=models.SET_NULL,
            blank=True,
            null=True,
            related_name="resolved_by_dependencies",
        )
        notes = models.TextField(blank=True, null=True)

        class Meta:
            ordering = ("source_service__name", "dependency_kind", "namespace", "name")
            verbose_name = "desired dependency"
            verbose_name_plural = "desired dependencies"
            constraints = (
                models.UniqueConstraint(
                    fields=("source_service", "dependency_kind", "namespace", "name"),
                    name="nic_unique_dependency_ref",
                ),
            )

        def __str__(self) -> str:
            return f"{self.dependency_kind}:{self.namespace}/{self.name}"

        def get_absolute_url(self) -> str:
            return reverse("plugins:nautobot_intent_catalog:desireddependency", args=[self.pk])
