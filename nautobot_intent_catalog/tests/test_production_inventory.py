from __future__ import annotations

import json
import unittest

import yaml

from nautobot_intent_catalog.actual_facts import ActualFacts
from nautobot_intent_catalog.production_inventory_contract import ContractError
from nautobot_intent_catalog.production_inventory import (
    EndpointInput,
    NodeInput,
    OperationalConfigInput,
    PlacementInput,
    ProductionComposition,
    RealizedState,
    compose_production_inventory,
    render_production_inventory_yml,
    render_production_report_json,
)


GENERATION_ID = "12345678-1234-5678-9234-567812345678"
GENERATED_AT = "2026-06-27T12:00:00+00:00"
DIGEST = "a" * 64
FRESH = "2026-06-27T00:00:00+00:00"

PROFILES = {
    "web": {
        "group": "web_server",
        "config_schema_version": "1",
        "variables": {
            "enabled": {"ansible_variable": "web_enabled", "type": "boolean", "required": False},
            "peers": {"ansible_variable": "web_peers", "type": "list", "items": "string", "required": False},
        },
    },
    "db": {
        "group": "db_server",
        "config_schema_version": "1",
        "variables": {
            "port": {"ansible_variable": "db_port", "type": "integer", "required": False},
        },
    },
    "home_assistant": {
        "group": "haos_server",
        "config_schema_version": "1",
        "variables": {},
    },
}


def linux_facts(*, collected_at=FRESH, mac="aa:bb:cc:dd:ee:ff", iface="eth0", local_ip="192.168.0.10", system="Linux"):
    return ActualFacts(
        observed_system=system,
        local_ip=local_ip,
        mac_address=mac,
        network_interface=iface,
        collected_at=collected_at,
        inventory_source="nodeutils",
    )


def linux_node(slug, *, placements=(), power="none", expected="linux", facts=None, realized_type="device", device_id=None):
    op = OperationalConfigInput(
        id=f"op-{slug}",
        actual_state_policy="required",
        connection_path="local",
        power_control=power,
        expected_host_os=expected,
    )
    realized = None
    if realized_type is not None:
        realized = RealizedState(
            realized_type=realized_type,
            facts=facts if facts is not None else linux_facts(),
            nautobot_device_id=device_id or f"dev-{slug}",
        )
    return NodeInput(
        id=f"node-{slug}",
        slug=slug,
        name=slug,
        lifecycle="active",
        node_type="device",
        operational_config=op,
        placements=tuple(placements),
        realized=realized,
    )


def haos_node(slug="aghaos", *, placements=()):
    endpoint = EndpointInput(
        name="primary",
        endpoint_type="primary",
        node_slug=slug,
        ip_address="192.168.0.20/24",
        dns_name="aghaos.example.test",
    )
    op = OperationalConfigInput(
        id="op-haos",
        actual_state_policy="declared",
        connection_path="local",
        power_control="none",
        declared_host_os="haos",
        local_endpoint=endpoint,
        ansible_port=2222,
    )
    return NodeInput(
        id="node-haos",
        slug=slug,
        name="HAOS",
        lifecycle="active",
        node_type="device",
        operational_config=op,
        placements=tuple(placements),
        realized=None,
    )


def compose(nodes):
    return compose_production_inventory(
        nodes,
        PROFILES,
        generation_id=GENERATION_ID,
        generated_at=GENERATED_AT,
        deployment_profile_digest=DIGEST,
    )


def ssh_host(composition: ProductionComposition, slug):
    return composition.inventory["all"]["children"]["ssh_hosts"]["hosts"][slug]


def group_hosts(composition: ProductionComposition, group):
    children = composition.inventory["all"]["children"]
    return set(children.get(group, {"hosts": {}})["hosts"])


class ActualBackedTests(unittest.TestCase):
    def test_linux_node_joins_actual_facts_and_service_group(self) -> None:
        node = linux_node("agweb", placements=[PlacementInput("p1", "primary", "web", "1", config={"enabled": True})])
        result = compose([node])

        host = ssh_host(result, "agweb")
        self.assertEqual(host["host_os"], "linux")
        self.assertEqual(host["local_ip"], "192.168.0.10")
        self.assertEqual(host["mac_address"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(host["network_interface"], "eth0")
        self.assertEqual(host["nautobot_device_id"], "dev-agweb")
        self.assertEqual(host["web_enabled"], True)
        self.assertEqual(host["nintent_active_placement_ids"], ["p1"])
        self.assertIn("agweb", group_hosts(result, "linux"))
        self.assertIn("agweb", group_hosts(result, "web_server"))
        self.assertEqual(result.report["summary"]["active_placements"], 1)
        self.assertEqual(result.report["summary"]["included"], 1)

    def test_selector_groups_use_observed_system_not_expected(self) -> None:
        # expected linux, observed Darwin -> exported macos with drift, in macos group.
        node = linux_node("agmac", power="none", expected="linux", facts=linux_facts(system="Darwin"))
        result = compose([node])

        self.assertEqual(ssh_host(result, "agmac")["host_os"], "macos")
        self.assertIn("agmac", group_hosts(result, "macos"))
        self.assertEqual(group_hosts(result, "linux"), set())
        self.assertEqual(result.report["drift"][0]["code"], "desired_actual_os_mismatch")
        self.assertEqual(result.report["drift"][0]["desired_node_slug"], "agmac")

    def test_wol_power_marks_power_managed(self) -> None:
        result = compose([linux_node("agwol", power="wol")])

        self.assertIn("agwol", group_hosts(result, "power_managed"))
        self.assertEqual(ssh_host(result, "agwol")["power_control"], "wol")

    def test_tailscale_connection_exports_tailscale_ip(self) -> None:
        op = OperationalConfigInput(
            id="op-ts",
            actual_state_policy="required",
            connection_path="tailscale",
            expected_host_os="linux",
            tailscale_endpoint=EndpointInput("ts", "vpn", "agts", ip_address="100.64.0.10/32"),
        )
        node = NodeInput("node-ts", "agts", "agts", "active", "device", op, (), RealizedState("device", linux_facts(), "dev-ts"))
        result = compose([node])

        host = ssh_host(result, "agts")
        self.assertEqual(host["connection_path"], "tailscale")
        self.assertEqual(host["tailscale_ip"], "100.64.0.10")


class DeclaredHaosTests(unittest.TestCase):
    def test_haos_composed_without_realized_object(self) -> None:
        result = compose([haos_node()])

        host = ssh_host(result, "aghaos")
        self.assertEqual(host["host_os"], "haos")
        self.assertEqual(host["local_ip"], "192.168.0.20")
        self.assertEqual(host["ansible_port"], 2222)
        self.assertNotIn("mac_address", host)
        self.assertNotIn("network_interface", host)
        self.assertNotIn("nautobot_device_id", host)
        self.assertIn("aghaos", group_hosts(result, "haos"))
        self.assertEqual(group_hosts(result, "power_managed"), set())

    def test_haos_declared_node_joins_service_group(self) -> None:
        # The declared-node path must still place HAOS into its service group so
        # the home-assistant deployment play can target it without nodeutils data.
        node = haos_node(placements=[PlacementInput("p1", "primary", "home_assistant", "1", config={})])
        result = compose([node])

        self.assertIn("aghaos", group_hosts(result, "haos_server"))
        self.assertEqual(ssh_host(result, "aghaos")["nintent_active_placement_ids"], ["p1"])
        self.assertEqual(result.report["summary"]["active_placements"], 1)


class MixedPlatformPipelineTests(unittest.TestCase):
    def test_linux_macos_and_declared_haos_compose_together(self) -> None:
        nodes = [
            linux_node(
                "aglinux",
                placements=[PlacementInput("p-linux", "primary", "web", "1", config={"enabled": True})],
            ),
            linux_node(
                "agmac",
                expected="macos",
                facts=linux_facts(
                    system="Darwin",
                    local_ip="192.168.0.11",
                    mac="11:22:33:44:55:66",
                    iface="en0",
                ),
            ),
            haos_node(
                placements=[PlacementInput("p-haos", "primary", "home_assistant", "1", config={})],
            ),
        ]

        result = compose(nodes)

        self.assertEqual(result.report["summary"]["included"], 3)
        self.assertEqual(group_hosts(result, "ssh_hosts"), {"aglinux", "agmac", "aghaos"})
        self.assertEqual(group_hosts(result, "linux"), {"aglinux"})
        self.assertEqual(group_hosts(result, "macos"), {"agmac"})
        self.assertEqual(group_hosts(result, "haos"), {"aghaos"})
        self.assertEqual(group_hosts(result, "web_server"), {"aglinux"})
        self.assertEqual(group_hosts(result, "haos_server"), {"aghaos"})
        for hostname in group_hosts(result, "ssh_hosts"):
            self.assertNotIn("package_manager", ssh_host(result, hostname))


class SkipTaxonomyTests(unittest.TestCase):
    def test_missing_realized_device_is_skipped(self) -> None:
        result = compose([linux_node("agnodev", realized_type=None)])

        self.assertEqual(result.inventory["all"]["children"]["ssh_hosts"]["hosts"], {})
        self.assertEqual(result.report["skipped"][0]["reasons"], ["no_realized_device"])

    def test_virtual_machine_is_unsupported(self) -> None:
        result = compose([linux_node("agvm", realized_type="virtual_machine")])

        self.assertEqual(result.report["skipped"][0]["reasons"], ["unsupported_actual_type"])

    def test_stale_actual_data_is_skipped(self) -> None:
        node = linux_node("agstale", facts=linux_facts(collected_at="2026-06-20T00:00:00+00:00"))
        result = compose([node])

        self.assertEqual(result.report["skipped"][0]["reasons"], ["stale_actual_data"])

    def test_wol_without_mac_is_skipped(self) -> None:
        node = linux_node("agnomac", power="wol", facts=linux_facts(mac=None))
        result = compose([node])

        self.assertEqual(result.report["skipped"][0]["reasons"], ["missing_mac_address"])

    def test_skipped_host_placement_does_not_create_dangling_group(self) -> None:
        node = linux_node(
            "agskip",
            realized_type=None,
            placements=[PlacementInput("p1", "primary", "web", "1", config={"enabled": True})],
        )
        result = compose([node])

        self.assertEqual(group_hosts(result, "web_server"), set())
        self.assertEqual(result.report["summary"]["inactive_placements"], 1)
        self.assertEqual(result.report["summary"]["active_placements"], 0)


class GlobalFailureTests(unittest.TestCase):
    def test_missing_operational_config_fails_whole_job(self) -> None:
        node = NodeInput("node-x", "agx", "agx", "active", "device", None, (), None)
        with self.assertRaises(ContractError) as caught:
            compose([node])
        self.assertEqual(caught.exception.code, "missing_operational_config")

    def test_invalid_platform_power_fails_whole_job(self) -> None:
        with self.assertRaises(ContractError) as caught:
            compose([linux_node("agbad", power="macos_sleep")])
        self.assertEqual(caught.exception.code, "invalid_platform_power")

    def test_conflicting_placement_variables_fail_whole_job(self) -> None:
        node = linux_node(
            "agconf",
            placements=[
                PlacementInput("p1", "primary", "web", "1", config={"enabled": True}),
                PlacementInput("p2", "secondary", "web", "1", config={"enabled": False}),
            ],
        )
        with self.assertRaises(ContractError) as caught:
            compose([node])
        self.assertEqual(caught.exception.code, "conflicting_host_variable")

    def test_unknown_profile_fails_whole_job(self) -> None:
        node = linux_node("agunk", placements=[PlacementInput("p1", "primary", "missing", "1", config={})])
        with self.assertRaises(ContractError) as caught:
            compose([node])
        self.assertEqual(caught.exception.code, "unknown_profile")


class MultiplicityTests(unittest.TestCase):
    def test_multiple_services_on_one_node(self) -> None:
        node = linux_node(
            "agmulti",
            placements=[
                PlacementInput("p1", "web", "web", "1", config={"enabled": True}),
                PlacementInput("p2", "db", "db", "1", config={"port": 5432}),
            ],
        )
        result = compose([node])

        host = ssh_host(result, "agmulti")
        self.assertEqual(host["web_enabled"], True)
        self.assertEqual(host["db_port"], 5432)
        self.assertIn("agmulti", group_hosts(result, "web_server"))
        self.assertIn("agmulti", group_hosts(result, "db_server"))
        self.assertEqual(result.report["summary"]["active_placements"], 2)

    def test_multiple_instances_of_one_service(self) -> None:
        node = linux_node(
            "aginst",
            placements=[
                PlacementInput("p-b", "replica", "web", "1", config={"enabled": True}),
                PlacementInput("p-a", "primary", "web", "1", config={"enabled": True}),
            ],
        )
        result = compose([node])

        self.assertEqual(ssh_host(result, "aginst")["nintent_active_placement_ids"], ["p-a", "p-b"])
        self.assertEqual(group_hosts(result, "web_server"), {"aginst"})
        self.assertEqual(result.report["summary"]["active_placements"], 2)

    def test_disabled_placement_is_inactive(self) -> None:
        node = linux_node(
            "agdis",
            placements=[PlacementInput("p1", "primary", "web", "1", desired_state="disabled", config={"enabled": True})],
        )
        result = compose([node])

        self.assertNotIn("web_enabled", ssh_host(result, "agdis"))
        self.assertEqual(group_hosts(result, "web_server"), set())
        self.assertEqual(result.report["summary"]["active_placements"], 0)
        self.assertEqual(result.report["summary"]["inactive_placements"], 1)


class EligibilityAndDeterminismTests(unittest.TestCase):
    def test_ineligible_nodes_are_out_of_scope(self) -> None:
        planned = linux_node("agplanned")
        planned = NodeInput(**{**planned.__dict__, "lifecycle": "planned"})
        container = linux_node("agcontainer")
        container = NodeInput(**{**container.__dict__, "node_type": "container"})
        included = linux_node("agok")

        result = compose([planned, container, included])

        self.assertEqual(set(result.inventory["all"]["children"]["ssh_hosts"]["hosts"]), {"agok"})
        self.assertEqual(result.report["summary"]["eligible"], 1)

    def test_output_is_byte_stable(self) -> None:
        nodes = [
            linux_node("agweb", placements=[PlacementInput("p1", "primary", "web", "1", config={"enabled": True})]),
            haos_node(),
            linux_node("agwol", power="wol"),
        ]
        first = compose(list(nodes))
        second = compose(list(nodes))

        self.assertEqual(render_production_inventory_yml(first), render_production_inventory_yml(second))
        self.assertEqual(render_production_report_json(first), render_production_report_json(second))

    def test_renderers_are_schema_versioned_and_parseable(self) -> None:
        result = compose([linux_node("agweb")])

        rendered_yaml = render_production_inventory_yml(result)
        self.assertIn("# schema_version: 1.0\n", rendered_yaml)
        loaded = yaml.safe_load(rendered_yaml)
        self.assertEqual(loaded["all"]["vars"]["nintent_inventory_schema_version"], "1.0")

        rendered_json = render_production_report_json(result)
        self.assertTrue(rendered_json.endswith("\n"))
        self.assertEqual(json.loads(rendered_json)["schema_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
