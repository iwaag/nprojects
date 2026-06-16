"""Filter sets for Service Catalog models."""

from __future__ import annotations

try:
    import django_filters
    from nautobot.apps.filters import NautobotFilterSet

    from .models import DesiredServiceCandidate, ServiceDependency, ServiceRepository
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    pass
else:

    class ServiceRepositoryFilterSet(NautobotFilterSet):
        """Filters for repository inputs."""

        q = django_filters.CharFilter(method="search", label="Search")

        class Meta:
            model = ServiceRepository
            fields = ("id", "url", "enabled", "owner", "service_hint", "last_analysis_status")

        def search(self, queryset, name, value):
            if not value.strip():
                return queryset
            return queryset.filter(url__icontains=value) | queryset.filter(service_hint__icontains=value)


    class DesiredServiceCandidateFilterSet(NautobotFilterSet):
        """Filters for desired service candidates."""

        q = django_filters.CharFilter(method="search", label="Search")

        class Meta:
            model = DesiredServiceCandidate
            fields = (
                "id",
                "name",
                "role",
                "source_repository",
                "catalog_owner",
                "analysis_status",
            )

        def search(self, queryset, name, value):
            if not value.strip():
                return queryset
            return queryset.filter(name__icontains=value) | queryset.filter(display_name__icontains=value)


    class ServiceDependencyFilterSet(NautobotFilterSet):
        """Filters for service dependencies."""

        q = django_filters.CharFilter(method="search", label="Search")

        class Meta:
            model = ServiceDependency
            fields = (
                "id",
                "source_service",
                "kind",
                "namespace",
                "name",
                "dependency_type",
                "resolution_status",
                "resolved_service",
            )

        def search(self, queryset, name, value):
            if not value.strip():
                return queryset
            return queryset.filter(name__icontains=value) | queryset.filter(raw_ref__icontains=value)
