"""Views for the Nautobot Service Catalog App."""

from django.conf import settings
from django.shortcuts import render

from .loaders import load_default_service_repositories


def repository_list(request):
    """Render the configured service repository input list."""

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


def _configured_repository_file():
    plugins_config = getattr(settings, "PLUGINS_CONFIG", {}) or {}
    app_config = plugins_config.get("nautobot_service_catalog", {}) or {}
    return app_config.get("service_repositories_file")
