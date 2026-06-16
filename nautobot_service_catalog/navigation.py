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
                            link="plugins:nautobot_service_catalog:repository_list",
                            name="Repositories",
                        ),
                    ),
                ),
            ),
        ),
    )
