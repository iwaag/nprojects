"""Navigation items for the Nautobot Service Catalog App."""

try:
    from nautobot.apps.ui import NavMenuGroup, NavMenuItem, NavMenuTab
except ImportError:  # pragma: no cover - allows loader-only tests without Nautobot.
    menu_items = ()
else:
    menu_items = (
        NavMenuTab(
            name="Service Catalog",
            groups=(
                NavMenuGroup(
                    name="Service Catalog",
                    items=(
                        NavMenuItem(
                            link="plugins:nautobot_service_catalog:servicerepository_list",
                            name="Service Repositories",
                        ),
                        NavMenuItem(
                            link="plugins:nautobot_service_catalog:desiredservicecandidate_list",
                            name="Desired Service Candidates",
                        ),
                        NavMenuItem(
                            link="plugins:nautobot_service_catalog:servicedependency_list",
                            name="Service Dependencies",
                        ),
                        NavMenuItem(
                            link="plugins:nautobot_service_catalog:repository_source_yaml_list",
                            name="Source YAML",
                        ),
                    ),
                ),
            ),
        ),
    )
