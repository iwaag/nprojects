from __future__ import annotations

import unittest
from types import SimpleNamespace

import yaml

from nautobot_intent_catalog.ansible_inventory import (
    export_hosts_intent,
    hosts_intent_payload,
    render_hosts_intent_json,
    render_hosts_intent_yml,
)


def node(
    name: str,
    slug: str,
    *,
    lifecycle: str = "planned",
    node_type: str = "device",
    endpoints=None,
):
    return SimpleNamespace(
        pk=f"node-{slug}",
        name=name,
        slug=slug,
        lifecycle=lifecycle,
        node_type=node_type,
        desired_endpoints=endpoints or [],
    )


def endpoint(
    name: str,
    *,
    endpoint_type: str = "primary",
    mdns_name: str | None = None,
):
    return SimpleNamespace(
        pk=f"endpoint-{name}",
        name=name,
        endpoint_type=endpoint_type,
        mdns_name=mdns_name,
    )


class RelatedEndpoints:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class HostsIntentExportTests(unittest.TestCase):
    def test_primary_endpoint_with_mdns_exports_ssh_host(self) -> None:
        desired = node(
            "ag Nomad",
            "agnomad",
            endpoints=[endpoint("primary", mdns_name="agnomad.local")],
        )

        export = export_hosts_intent([desired])

        self.assertEqual(export.summary["exported_hosts"], 1)
        self.assertEqual(export.summary["groups"], ["ssh_hosts"])
        self.assertEqual(export.skipped, [])
        ssh_hosts = export.inventory["all"]["children"]["ssh_hosts"]["hosts"]
        self.assertEqual(ssh_hosts["agnomad"]["mdns_hostname"], "agnomad.local")
        self.assertEqual(ssh_hosts["agnomad"]["nintent_inventory_stage"], "reserved_name")
        self.assertTrue(ssh_hosts["agnomad"]["name_reserved_only"])
        self.assertNotIn("host_os", ssh_hosts["agnomad"])

    def test_bootstrap_export_contains_no_service_groups(self) -> None:
        desired = node(
            "ag Nomad",
            "agnomad",
            endpoints=[endpoint("primary", mdns_name="agnomad.local")],
        )

        export = export_hosts_intent([desired])

        groups = list(export.inventory["all"]["children"].keys())
        self.assertEqual(groups, ["ssh_hosts"])

    def test_export_does_not_require_mdns_endpoint_type(self) -> None:
        desired = node(
            "ag Grafana",
            "aggrafana",
            endpoints=[endpoint("primary", endpoint_type="primary", mdns_name="aggrafana.local")],
        )

        export = export_hosts_intent([desired])

        self.assertEqual(export.summary["exported_hosts"], 1)
        self.assertEqual(export.hosts[0]["desired_endpoint"], "primary")
        self.assertEqual(export.hosts[0]["mdns_hostname"], "aggrafana.local")

    def test_service_host_exports_for_bootstrap_discovery(self) -> None:
        desired = node(
            "DNS service host",
            "agdns",
            node_type="service_host",
            endpoints=[endpoint("primary", mdns_name="agdns.local")],
        )

        export = export_hosts_intent([desired])

        self.assertEqual(export.summary["exported_hosts"], 1)
        self.assertEqual(export.skipped, [])
        self.assertIn("agdns", export.inventory["all"]["children"]["ssh_hosts"]["hosts"])

    def test_endpoint_selection_prefers_primary_then_management_then_fallback(self) -> None:
        management_only = node(
            "Management Only",
            "management-only",
            endpoints=[
                endpoint("svc", endpoint_type="service", mdns_name="svc.local"),
                endpoint("mgmt", endpoint_type="management", mdns_name="mgmt.local"),
            ],
        )
        fallback = node(
            "Fallback",
            "fallback",
            endpoints=[
                endpoint("zeta", endpoint_type="vpn", mdns_name="zeta.local"),
                endpoint("alpha", endpoint_type="service", mdns_name="alpha.local"),
            ],
        )

        export = export_hosts_intent([fallback, management_only])
        hosts = {host["inventory_hostname"]: host for host in export.hosts}

        self.assertEqual(hosts["management-only"]["desired_endpoint"], "mgmt")
        self.assertEqual(hosts["fallback"]["desired_endpoint"], "alpha")

    def test_related_manager_style_endpoints_are_supported(self) -> None:
        desired = node("Related", "related")
        desired.desired_endpoints = RelatedEndpoints([endpoint("primary", mdns_name="related.local")])

        export = export_hosts_intent([desired])

        self.assertEqual(export.summary["exported_hosts"], 1)

    def test_node_without_mdns_endpoint_is_skipped(self) -> None:
        desired = node("No mDNS", "no-mdns", endpoints=[endpoint("primary")])

        export = export_hosts_intent([desired])

        self.assertEqual(export.summary["exported_hosts"], 0)
        self.assertEqual(export.summary["skipped_nodes"], 1)
        self.assertEqual(export.skipped[0]["reasons"], ["missing_mdns_name"])

    def test_ineligible_lifecycle_and_node_type_are_skipped(self) -> None:
        retired = node(
            "Retired",
            "retired",
            lifecycle="retired",
            endpoints=[endpoint("primary", mdns_name="retired.local")],
        )
        container = node(
            "Container",
            "container",
            node_type="container",
            endpoints=[endpoint("primary", mdns_name="container.local")],
        )

        export = export_hosts_intent([retired, container])
        reasons = {entry["desired_node_slug"]: entry["reasons"] for entry in export.skipped}

        self.assertEqual(reasons["retired"], ["node_lifecycle_not_exportable"])
        self.assertEqual(reasons["container"], ["node_type_not_exportable"])

    def test_rendered_yaml_is_parseable_inventory(self) -> None:
        desired = node(
            "ag Nomad",
            "agnomad",
            endpoints=[endpoint("primary", mdns_name="agnomad.local")],
        )
        export = export_hosts_intent([desired])

        rendered = render_hosts_intent_yml(
            export,
            generated_at="2026-06-26T00:00:00+00:00",
            job_result_id="job-123",
        )
        loaded = yaml.safe_load(rendered)

        self.assertIn("# schema_version: 2.0\n", rendered)
        self.assertEqual(loaded["all"]["children"]["ssh_hosts"]["hosts"]["agnomad"]["mdns_hostname"], "agnomad.local")

    def test_rendered_yaml_contains_no_host_os(self) -> None:
        desired = node(
            "ag Nomad",
            "agnomad",
            endpoints=[endpoint("primary", mdns_name="agnomad.local")],
        )
        export = export_hosts_intent([desired])

        rendered = render_hosts_intent_yml(
            export,
            generated_at="2026-06-26T00:00:00+00:00",
        )

        self.assertNotIn("host_os", rendered)

    def test_json_payload_contains_inventory_hosts_and_skipped(self) -> None:
        desired = node("ag Node", "agnode", endpoints=[endpoint("primary", mdns_name="agnode.local")])
        export = export_hosts_intent([desired])

        payload = hosts_intent_payload(
            export,
            generated_at="2026-06-26T00:00:00+00:00",
            job_result_id="job-123",
        )

        self.assertEqual(payload["schema_version"], "2.0")
        self.assertEqual(payload["job_result_id"], "job-123")
        self.assertEqual(payload["hosts"][0]["inventory_hostname"], "agnode")
        self.assertIn("ssh_hosts", payload["inventory"]["all"]["children"])
        self.assertTrue(render_hosts_intent_json(export, generated_at="2026-06-26T00:00:00+00:00").endswith("\n"))

    def test_summary_has_no_skipped_groups_field(self) -> None:
        desired = node("ag Node", "agnode", endpoints=[endpoint("primary", mdns_name="agnode.local")])
        export = export_hosts_intent([desired])

        self.assertNotIn("skipped_groups", export.summary)


if __name__ == "__main__":
    unittest.main()
