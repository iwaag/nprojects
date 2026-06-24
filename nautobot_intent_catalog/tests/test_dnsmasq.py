from __future__ import annotations

import unittest
from types import SimpleNamespace

from nautobot_intent_catalog.dnsmasq import (
    dnsmasq_export_payload,
    export_dnsmasq_records,
    render_dnsmasq_export_json,
    render_dnsmasq_records_conf,
    resolve_dhcp_reservation,
)


def node(name: str, slug: str, lifecycle: str):
    return SimpleNamespace(pk=f"node-{slug}", name=name, slug=slug, lifecycle=lifecycle)


def endpoint(
    *,
    name: str,
    dns_name: str | None,
    ip_address: str | None,
    desired_node,
    endpoint_type: str = "primary",
    generate_dnsmasq: bool = True,
    ip_policy: str = "dhcp_reserved",
    dnsmasq_record_type: str = "host_record",
    mdns_name: str | None = None,
    vpn_dns_name: str | None = None,
):
    return SimpleNamespace(
        pk=f"endpoint-{name}",
        name=name,
        desired_node=desired_node,
        endpoint_type=endpoint_type,
        ip_address=ip_address,
        dns_name=dns_name,
        mdns_name=mdns_name,
        vpn_dns_name=vpn_dns_name,
        generate_dnsmasq=generate_dnsmasq,
        ip_policy=ip_policy,
        dnsmasq_record_type=dnsmasq_record_type,
    )


def endpoint_evaluation(endpoint_obj, *, mac_candidates=None, ready=True):
    return {
        str(endpoint_obj.pk): {
            "deterministic_summary": {"dhcp_reservation_ready": ready},
            "observed_facts": {"dhcp_mac_candidates": mac_candidates or []},
        }
    }


def mac_candidate(*, mac_address="AA-BB-CC-DD-EE-FF", node_name="Edge 1", node_id="actual-node-1", interface_name="eth0"):
    return {
        "actual_node_ref": {
            "object_type": "dcim.device",
            "id": node_id,
            "name": node_name,
        },
        "interface_id": f"interface-{interface_name}",
        "interface_name": interface_name,
        "mac_address": mac_address,
    }


class DnsmasqExportTests(unittest.TestCase):
    def test_export_filters_eligible_endpoints_and_keeps_mdns_as_metadata(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        retired = node("Old Edge", "old-edge", "retired")
        endpoints = [
            endpoint(name="mgmt", desired_node=active, dns_name="edge-1.example.test", ip_address="192.0.2.10/32", mdns_name="edge-1.local"),
            endpoint(name="off", desired_node=active, dns_name="off.example.test", ip_address="192.0.2.11", generate_dnsmasq=False),
            endpoint(name="mdns", desired_node=active, dns_name="mdns.example.test", ip_address="192.0.2.12", endpoint_type="mdns"),
            endpoint(name="old", desired_node=retired, dns_name="old.example.test", ip_address="192.0.2.13"),
            endpoint(name="nameless", desired_node=active, dns_name=None, ip_address="192.0.2.14"),
        ]

        export = export_dnsmasq_records(endpoints)

        self.assertEqual(export.summary["dns_records"], 1)
        self.assertEqual(export.summary["skipped"]["dns_records"], 4)
        self.assertEqual(export.dns_records[0]["line"], "host-record=edge-1.example.test,192.0.2.10")
        self.assertEqual(export.dns_records[0]["mdns_name"], "edge-1.local")
        skipped_reasons = {
            (entry["item_type"], entry["endpoint_name"]): entry["reasons"]
            for entry in export.skipped
            if entry["item_type"] == "dns_record"
        }
        self.assertEqual(skipped_reasons[("dns_record", "off")], ["generate_dnsmasq_false"])
        self.assertEqual(skipped_reasons[("dns_record", "mdns")], ["endpoint_type_not_exportable"])
        self.assertEqual(skipped_reasons[("dns_record", "old")], ["node_lifecycle_not_exportable"])
        self.assertEqual(skipped_reasons[("dns_record", "nameless")], ["missing_dns_name"])
        dhcp_skipped_reasons = {
            entry["endpoint_name"]: entry["reasons"]
            for entry in export.skipped
            if entry["item_type"] == "dhcp_reservation"
        }
        self.assertIn("node_lifecycle_not_exportable", dhcp_skipped_reasons["old"])

    def test_export_formats_record_types_and_sort_order(self) -> None:
        approved = node("App 1", "app-1", "approved")
        planned = node("VPN 1", "vpn-1", "planned")
        endpoints = [
            endpoint(
                name="vpn",
                desired_node=planned,
                endpoint_type="vpn",
                dns_name="vpn-target.example.test",
                ip_address="198.51.100.10/32",
                dnsmasq_record_type="cname",
                vpn_dns_name="vpn.example.test",
            ),
            endpoint(
                name="svc",
                desired_node=approved,
                endpoint_type="service",
                dns_name="api.example.test",
                ip_address="198.51.100.20/32",
                dnsmasq_record_type="address",
            ),
            endpoint(
                name="primary",
                desired_node=approved,
                dns_name="app.example.test",
                ip_address="198.51.100.30/32",
                dnsmasq_record_type="host_record",
            ),
        ]

        export = export_dnsmasq_records(endpoints, include_skipped=False)

        self.assertEqual(export.skipped, [])
        self.assertEqual(export.summary["total_endpoints"], 3)
        self.assertEqual(export.summary["skipped"]["dns_records"], 0)
        self.assertEqual(export.summary["skipped_endpoint_details"], 0)
        self.assertEqual(
            [record["line"] for record in export.dns_records],
            [
                "address=/api.example.test/198.51.100.20",
                "host-record=app.example.test,198.51.100.30",
                "cname=vpn.example.test,vpn-target.example.test",
            ],
        )
        self.assertEqual(
            export.summary["record_types"],
            {"address": 1, "cname": 1, "host_record": 1},
        )

    def test_cname_requires_vpn_dns_alias(self) -> None:
        active = node("VPN 2", "vpn-2", "active")
        export = export_dnsmasq_records(
            [
                endpoint(
                    name="vpn",
                    desired_node=active,
                    endpoint_type="vpn",
                    dns_name="vpn-target.example.test",
                    ip_address="203.0.113.10",
                    dnsmasq_record_type="cname",
                )
            ]
        )

        self.assertEqual(export.dns_records, [])
        dns_skip = [entry for entry in export.skipped if entry["item_type"] == "dns_record"][0]
        self.assertEqual(dns_skip["reasons"], ["missing_cname_alias"])

    def test_dns_record_is_exported_without_mac_but_dhcp_is_skipped(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        primary = endpoint(
            name="primary",
            desired_node=active,
            dns_name="edge-1.example.test",
            ip_address="192.0.2.10/32",
        )

        export = export_dnsmasq_records([primary])

        self.assertEqual(export.dns_records[0]["line"], "host-record=edge-1.example.test,192.0.2.10")
        self.assertEqual(export.dhcp_reservations, [])
        dhcp_skip = [entry for entry in export.skipped if entry["item_type"] == "dhcp_reservation"][0]
        self.assertIn("missing_endpoint_evaluation", dhcp_skip["reasons"])
        self.assertIn("missing_actual_node", dhcp_skip["reasons"])
        self.assertIn("missing_mac_address", dhcp_skip["reasons"])

    def test_static_endpoint_exports_dns_but_not_dhcp_reservation(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        primary = endpoint(
            name="primary",
            desired_node=active,
            dns_name="edge-1.example.test",
            ip_address="192.0.2.10/32",
            ip_policy="static",
        )

        export = export_dnsmasq_records(
            [primary],
            endpoint_evaluations=endpoint_evaluation(primary, mac_candidates=[mac_candidate()]),
        )

        self.assertEqual(export.dns_records[0]["line"], "host-record=edge-1.example.test,192.0.2.10")
        self.assertEqual(export.dhcp_reservations, [])
        dhcp_skip = [entry for entry in export.skipped if entry["item_type"] == "dhcp_reservation"][0]
        self.assertEqual(dhcp_skip["reasons"], ["ip_policy_not_dhcp_reserved"])

    def test_dhcp_reservation_is_exported_when_mac_is_unique(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        primary = endpoint(
            name="primary",
            desired_node=active,
            dns_name="edge-1.example.test",
            ip_address="192.0.2.10/32",
        )
        export = export_dnsmasq_records(
            [primary],
            endpoint_evaluations=endpoint_evaluation(primary, mac_candidates=[mac_candidate()]),
        )

        self.assertEqual(export.summary["dhcp_reservations"], 1)
        self.assertEqual(
            export.dhcp_reservations[0]["line"],
            "dhcp-host=aa:bb:cc:dd:ee:ff,edge-1.example.test,192.0.2.10",
        )

    def test_dhcp_reservation_skips_ambiguous_or_invalid_mac(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        primary = endpoint(
            name="primary",
            desired_node=active,
            dns_name="edge-1.example.test",
            ip_address="192.0.2.10/32",
        )

        ambiguous = resolve_dhcp_reservation(
            primary,
            endpoint_evaluation={
                "deterministic_summary": {"dhcp_reservation_ready": False},
                "observed_facts": {
                    "dhcp_mac_candidates": [
                        mac_candidate(mac_address="aa:bb:cc:dd:ee:ff", interface_name="eth0"),
                        mac_candidate(mac_address="11:22:33:44:55:66", interface_name="eth1"),
                    ]
                },
            },
        )
        invalid = resolve_dhcp_reservation(
            primary,
            endpoint_evaluation={
                "deterministic_summary": {"dhcp_reservation_ready": True},
                "observed_facts": {"dhcp_mac_candidates": [mac_candidate(mac_address="not-a-mac")]},
            },
        )

        self.assertIn("ambiguous_interface", ambiguous["skip_reasons"])
        self.assertIn("invalid_mac_address", invalid["skip_reasons"])

    def test_render_outputs_for_ansible_consumption(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        primary = endpoint(
            name="primary",
            desired_node=active,
            dns_name="edge-1.example.test",
            ip_address="192.0.2.10/32",
        )
        export = export_dnsmasq_records(
            [primary],
            endpoint_evaluations=endpoint_evaluation(primary, mac_candidates=[mac_candidate()]),
        )

        conf = render_dnsmasq_records_conf(
            export,
            generated_at="2026-06-23T00:00:00+00:00",
            job_result_id="job-123",
        )
        self.assertEqual(
            conf,
            "\n".join(
                [
                    "# Generated by Nautobot Intent Catalog",
                    "# schema_version: 2.0",
                    "# generated_at: 2026-06-23T00:00:00+00:00",
                    "# job_result_id: job-123",
                    "host-record=edge-1.example.test,192.0.2.10",
                    "dhcp-host=aa:bb:cc:dd:ee:ff,edge-1.example.test,192.0.2.10",
                    "",
                ]
            ),
        )

        payload = dnsmasq_export_payload(
            export,
            generated_at="2026-06-23T00:00:00+00:00",
            job_result_id="job-123",
        )
        self.assertEqual(payload["schema_version"], "2.0")
        self.assertEqual(payload["job_result_id"], "job-123")
        self.assertEqual(payload["dns_records"][0]["line"], "host-record=edge-1.example.test,192.0.2.10")
        self.assertEqual(
            payload["dhcp_reservations"][0]["line"],
            "dhcp-host=aa:bb:cc:dd:ee:ff,edge-1.example.test,192.0.2.10",
        )
        self.assertTrue(render_dnsmasq_export_json(export, generated_at="2026-06-23T00:00:00+00:00").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
