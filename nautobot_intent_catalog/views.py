"""Views for the Nautobot Intent Catalog App."""

from django.conf import settings
from django.shortcuts import render

from .loaders import load_default_intent_sources

try:
    from nautobot.apps.views import ObjectDeleteView, ObjectEditView, ObjectListView, ObjectView

    from .filters import (
        DesiredDependencyFilterSet,
        DesiredEndpointFilterSet,
        DesiredNodeFilterSet,
        DesiredServiceFilterSet,
        IntentEvaluationFilterSet,
        IntentSourceFilterSet,
    )
    from .forms import (
        DesiredDependencyForm,
        DesiredEndpointForm,
        DesiredNodeForm,
        DesiredServiceForm,
        IntentEvaluationForm,
        IntentSourceForm,
    )
    from .models import DesiredDependency, DesiredEndpoint, DesiredNode, DesiredService, IntentEvaluation, IntentSource
    from .tables import (
        DesiredDependencyTable,
        DesiredEndpointTable,
        DesiredNodeTable,
        DesiredServiceTable,
        IntentEvaluationTable,
        IntentSourceTable,
    )
except ImportError:  # pragma: no cover - Nautobot is unavailable in local unit tests.
    pass
else:

    class IntentSourceListView(ObjectListView):
        """List DB-backed intent source records."""

        queryset = IntentSource.objects.all()
        filterset = IntentSourceFilterSet
        table = IntentSourceTable


    class IntentSourceView(ObjectView):
        """Show one intent source record."""

        queryset = IntentSource.objects.all()


    class IntentSourceEditView(ObjectEditView):
        """Create or edit an intent source record."""

        queryset = IntentSource.objects.all()
        model_form = IntentSourceForm


    class IntentSourceDeleteView(ObjectDeleteView):
        """Delete an intent source record."""

        queryset = IntentSource.objects.all()


    class DesiredServiceListView(ObjectListView):
        """List desired service records."""

        queryset = DesiredService.objects.select_related("intent_source")
        filterset = DesiredServiceFilterSet
        table = DesiredServiceTable


    class DesiredServiceView(ObjectView):
        """Show one desired service record."""

        queryset = DesiredService.objects.select_related("intent_source")


    class DesiredServiceEditView(ObjectEditView):
        """Edit a desired service record."""

        queryset = DesiredService.objects.all()
        model_form = DesiredServiceForm


    class DesiredServiceDeleteView(ObjectDeleteView):
        """Delete a desired service record."""

        queryset = DesiredService.objects.all()


    class DesiredDependencyListView(ObjectListView):
        """List desired dependency records."""

        queryset = DesiredDependency.objects.select_related("source_service", "resolved_service")
        filterset = DesiredDependencyFilterSet
        table = DesiredDependencyTable


    class DesiredDependencyView(ObjectView):
        """Show one desired dependency record."""

        queryset = DesiredDependency.objects.select_related("source_service", "resolved_service")


    class DesiredDependencyEditView(ObjectEditView):
        """Edit a desired dependency record."""

        queryset = DesiredDependency.objects.all()
        model_form = DesiredDependencyForm


    class DesiredDependencyDeleteView(ObjectDeleteView):
        """Delete a desired dependency record."""

        queryset = DesiredDependency.objects.all()


    class DesiredNodeListView(ObjectListView):
        """List desired node records."""

        queryset = DesiredNode.objects.select_related("intent_source", "realized_device", "realized_vm")
        filterset = DesiredNodeFilterSet
        table = DesiredNodeTable


    class DesiredNodeView(ObjectView):
        """Show one desired node record."""

        queryset = DesiredNode.objects.select_related("intent_source", "realized_device", "realized_vm")


    class DesiredNodeEditView(ObjectEditView):
        """Edit a desired node record."""

        queryset = DesiredNode.objects.all()
        model_form = DesiredNodeForm


    class DesiredNodeDeleteView(ObjectDeleteView):
        """Delete a desired node record."""

        queryset = DesiredNode.objects.all()


    class DesiredEndpointListView(ObjectListView):
        """List desired endpoint records."""

        queryset = DesiredEndpoint.objects.select_related("desired_node", "realized_ip_address")
        filterset = DesiredEndpointFilterSet
        table = DesiredEndpointTable


    class DesiredEndpointView(ObjectView):
        """Show one desired endpoint record."""

        queryset = DesiredEndpoint.objects.select_related("desired_node", "realized_ip_address")


    class DesiredEndpointEditView(ObjectEditView):
        """Edit a desired endpoint record."""

        queryset = DesiredEndpoint.objects.all()
        model_form = DesiredEndpointForm


    class DesiredEndpointDeleteView(ObjectDeleteView):
        """Delete a desired endpoint record."""

        queryset = DesiredEndpoint.objects.all()


    class IntentEvaluationListView(ObjectListView):
        """List intent evaluation records."""

        queryset = IntentEvaluation.objects.all()
        filterset = IntentEvaluationFilterSet
        table = IntentEvaluationTable


    class IntentEvaluationView(ObjectView):
        """Show one intent evaluation record."""

        queryset = IntentEvaluation.objects.all()


    class IntentEvaluationEditView(ObjectEditView):
        """Edit an intent evaluation record."""

        queryset = IntentEvaluation.objects.all()
        model_form = IntentEvaluationForm


    class IntentEvaluationDeleteView(ObjectDeleteView):
        """Delete an intent evaluation record."""

        queryset = IntentEvaluation.objects.all()


def source_yaml_intent_source_list(request):
    """Render the configured intent source input list directly from YAML."""

    result = load_default_intent_sources(_configured_source_file())
    return render(
        request,
        "nautobot_intent_catalog/source_yaml_list.html",
        {
            "source_path": result.source_path,
            "intent_sources": result.intent_sources,
            "desired_nodes": result.desired_nodes,
            "desired_endpoints": result.desired_endpoints,
            "errors": result.errors,
        },
    )


source_yaml_list = source_yaml_intent_source_list


def _configured_source_file():
    plugins_config = getattr(settings, "PLUGINS_CONFIG", {}) or {}
    app_config = plugins_config.get("nautobot_intent_catalog", {}) or {}
    return app_config.get("intent_sources_file")
