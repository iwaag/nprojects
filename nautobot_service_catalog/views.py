"""Views for the Nautobot Service Catalog App."""

from django.shortcuts import render

from .loaders import load_default_service_repositories


def repository_list(request):
    """Render the configured service repository input list."""

    result = load_default_service_repositories()
    return render(
        request,
        "nautobot_service_catalog/repository_list.html",
        {
            "source_path": result.source_path,
            "repositories": result.repositories,
            "errors": result.errors,
        },
    )
