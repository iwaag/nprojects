"""Views for the Nautobot Service Catalog App."""

from django.conf import settings
from django.shortcuts import render

from .loaders import load_default_service_repositories

try:
    from nautobot.apps.views import ObjectDeleteView, ObjectEditView, ObjectListView, ObjectView

    from .filters import DesiredServiceCandidateFilterSet, ServiceDependencyFilterSet, ServiceRepositoryFilterSet
    from .forms import DesiredServiceCandidateForm, ServiceDependencyForm, ServiceRepositoryForm
    from .models import DesiredServiceCandidate, ServiceDependency, ServiceRepository
    from .tables import DesiredServiceCandidateTable, ServiceDependencyTable, ServiceRepositoryTable
except ImportError:  # pragma: no cover - Nautobot is unavailable in local unit tests.
    pass
else:

    class ServiceRepositoryListView(ObjectListView):
        """List DB-backed service repository records."""

        queryset = ServiceRepository.objects.all()
        filterset = ServiceRepositoryFilterSet
        table = ServiceRepositoryTable


    class ServiceRepositoryView(ObjectView):
        """Show one service repository record."""

        queryset = ServiceRepository.objects.all()


    class ServiceRepositoryEditView(ObjectEditView):
        """Create or edit a service repository record."""

        queryset = ServiceRepository.objects.all()
        model_form = ServiceRepositoryForm


    class ServiceRepositoryDeleteView(ObjectDeleteView):
        """Delete a service repository record."""

        queryset = ServiceRepository.objects.all()


    class DesiredServiceCandidateListView(ObjectListView):
        """List desired service candidate records."""

        queryset = DesiredServiceCandidate.objects.select_related("source_repository")
        filterset = DesiredServiceCandidateFilterSet
        table = DesiredServiceCandidateTable


    class DesiredServiceCandidateView(ObjectView):
        """Show one desired service candidate record."""

        queryset = DesiredServiceCandidate.objects.select_related("source_repository")


    class DesiredServiceCandidateEditView(ObjectEditView):
        """Edit a desired service candidate record."""

        queryset = DesiredServiceCandidate.objects.all()
        model_form = DesiredServiceCandidateForm


    class DesiredServiceCandidateDeleteView(ObjectDeleteView):
        """Delete a desired service candidate record."""

        queryset = DesiredServiceCandidate.objects.all()


    class ServiceDependencyListView(ObjectListView):
        """List service dependency records."""

        queryset = ServiceDependency.objects.select_related("source_service", "resolved_service")
        filterset = ServiceDependencyFilterSet
        table = ServiceDependencyTable


    class ServiceDependencyView(ObjectView):
        """Show one service dependency record."""

        queryset = ServiceDependency.objects.select_related("source_service", "resolved_service")


    class ServiceDependencyEditView(ObjectEditView):
        """Edit a service dependency record."""

        queryset = ServiceDependency.objects.all()
        model_form = ServiceDependencyForm


    class ServiceDependencyDeleteView(ObjectDeleteView):
        """Delete a service dependency record."""

        queryset = ServiceDependency.objects.all()


def source_yaml_repository_list(request):
    """Render the configured service repository input list directly from YAML."""

    result = load_default_service_repositories(_configured_repository_file())
    return render(
        request,
        "nautobot_service_catalog/repository_list.html",
        {
            "source_path": result.source_path,
            "repositories": result.repositories,
            "errors": result.errors,
        },
    )


repository_list = source_yaml_repository_list


def _configured_repository_file():
    plugins_config = getattr(settings, "PLUGINS_CONFIG", {}) or {}
    app_config = plugins_config.get("nautobot_service_catalog", {}) or {}
    return app_config.get("service_repositories_file")
