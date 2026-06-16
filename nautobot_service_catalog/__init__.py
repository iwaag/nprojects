"""Nautobot Service Catalog App."""

try:
    from nautobot.apps import NautobotAppConfig
except ImportError:  # pragma: no cover - supports loader-only local smoke tests.
    class NautobotAppConfig:  # type: ignore[no-redef]
        """Fallback base when Nautobot is not installed."""


class ServiceCatalogConfig(NautobotAppConfig):
    """App configuration for the service repository catalog."""

    name = "nautobot_service_catalog"
    verbose_name = "Service Catalog"
    description = "Display and analyze cluster service repositories."
    version = "0.1.0"
    author = ""
    author_email = ""
    base_url = "service-catalog"
    required_settings = []
    default_settings = {}
    home_view_name = "plugins:nautobot_service_catalog:repository_list"


config = ServiceCatalogConfig
