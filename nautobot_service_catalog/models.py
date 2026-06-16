"""Database models for the Nautobot Service Catalog App."""

from __future__ import annotations

try:
    from django.db import models
    from django.urls import reverse
    from nautobot.apps.models import PrimaryModel
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    PrimaryModel = object  # type: ignore[assignment]
else:

    class ServiceRepository(PrimaryModel):
        """Repository input record used for catalog analysis."""

        url = models.URLField(unique=True)
        enabled = models.BooleanField(default=True)
        ref = models.CharField(max_length=255, blank=True, null=True)
        owner = models.CharField(max_length=255, blank=True, null=True)
        service_hint = models.CharField(max_length=255, blank=True, null=True)
        catalog_paths = models.JSONField(default=list, blank=True)
        basic_file_paths = models.JSONField(default=list, blank=True)
        raw_url_template = models.CharField(max_length=1024, blank=True, null=True)
        last_analysis_status = models.CharField(max_length=64, blank=True, null=True)
        last_analyzed_at = models.DateTimeField(blank=True, null=True)
        last_analysis_summary = models.JSONField(default=dict, blank=True)

        class Meta:
            ordering = ("url",)
            verbose_name = "service repository"
            verbose_name_plural = "service repositories"

        def __str__(self) -> str:
            return self.service_hint or self.url

        def get_absolute_url(self) -> str:
            return reverse("plugins:nautobot_service_catalog:servicerepository", args=[self.pk])


    class DesiredServiceCandidate(PrimaryModel):
        """Service candidate generated from Backstage catalog metadata."""

        name = models.SlugField(max_length=255)
        display_name = models.CharField(max_length=255)
        role = models.CharField(max_length=64)
        source_repository = models.ForeignKey(
            ServiceRepository,
            on_delete=models.CASCADE,
            related_name="desired_service_candidates",
        )
        source_ref = models.CharField(max_length=255, blank=True, null=True)
        source_catalog_path = models.CharField(max_length=512, blank=True, null=True)
        catalog_kind = models.CharField(max_length=64, blank=True, null=True)
        catalog_namespace = models.CharField(max_length=255, default="default")
        catalog_metadata_name = models.CharField(max_length=255)
        catalog_owner = models.CharField(max_length=255, blank=True, null=True)
        catalog_lifecycle = models.CharField(max_length=64, blank=True, null=True)
        catalog_spec_type = models.CharField(max_length=64, blank=True, null=True)
        prefers_gpu = models.BooleanField(default=False)
        min_memory_gb = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
        analysis_status = models.CharField(max_length=64, blank=True, null=True)
        analysis_confidence = models.CharField(max_length=64, blank=True, null=True)
        analysis_reasons = models.JSONField(default=list, blank=True)
        analysis_warnings = models.JSONField(default=list, blank=True)
        notes = models.TextField(blank=True, null=True)
        last_analyzed_at = models.DateTimeField(blank=True, null=True)

        class Meta:
            ordering = ("name",)
            verbose_name = "desired service candidate"
            verbose_name_plural = "desired service candidates"
            constraints = (
                models.UniqueConstraint(
                    fields=(
                        "source_repository",
                        "catalog_namespace",
                        "catalog_metadata_name",
                        "catalog_spec_type",
                    ),
                    name="npsc_unique_candidate_catalog_entity",
                ),
            )

        def __str__(self) -> str:
            return self.display_name or self.name

        def get_absolute_url(self) -> str:
            return reverse("plugins:nautobot_service_catalog:desiredservicecandidate", args=[self.pk])


    class ServiceDependency(PrimaryModel):
        """Dependency metadata attached to a desired service candidate."""

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
            DesiredServiceCandidate,
            on_delete=models.CASCADE,
            related_name="dependencies",
        )
        kind = models.CharField(max_length=64)
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
            DesiredServiceCandidate,
            on_delete=models.SET_NULL,
            blank=True,
            null=True,
            related_name="resolved_by_dependencies",
        )
        notes = models.TextField(blank=True, null=True)

        class Meta:
            ordering = ("source_service__name", "kind", "namespace", "name")
            verbose_name = "service dependency"
            verbose_name_plural = "service dependencies"
            constraints = (
                models.UniqueConstraint(
                    fields=("source_service", "kind", "namespace", "name"),
                    name="npsc_unique_dependency_ref",
                ),
            )

        def __str__(self) -> str:
            return f"{self.kind}:{self.namespace}/{self.name}"

        def get_absolute_url(self) -> str:
            return reverse("plugins:nautobot_service_catalog:servicedependency", args=[self.pk])
