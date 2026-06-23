from __future__ import annotations

import unittest
from types import SimpleNamespace

from nautobot_intent_catalog.dnsmasq import (
    dnsmasq_export_payload,
    export_dnsmasq_records,
    render_dnsmasq_export_json,
    render_dnsmasq_records_conf,
)


def node(name: str, slug: str, lifecycle: str):
    return SimpleNamespace(name=name, slug=slug, lifecycle=lifecycle)


def endpoint(
    *,
    name: str,
    dns_name: str | None,
    ip_address: str | None,
    desired_node,
    endpoint_type: str = "primary",
    generate_dnsmasq: bool = True,
    dnsmasq_record_type: str = "host_record",
    mdns_name: str | None = None,
    vpn_dns_name: str | None = None,
):
    return SimpleNamespace(
        name=name,
        desired_node=desired_node,
        endpoint_type=endpoint_type,
        ip_address=ip_address,
        dns_name=dns_name,
        mdns_name=mdns_name,
        vpn_dns_name=vpn_dns_name,
        generate_dnsmasq=generate_dnsmasq,
        dnsmasq_record_type=dnsmasq_record_type,
    )


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

        self.assertEqual(export.summary["eligible_endpoints"], 1)
        self.assertEqual(export.summary["skipped_endpoints"], 4)
        self.assertEqual(export.records[0]["line"], "host-record=edge-1.example.test,192.0.2.10")
        self.assertEqual(export.records[0]["mdns_name"], "edge-1.local")
        skipped_reasons = {entry["endpoint_name"]: entry["reasons"] for entry in export.skipped}
        self.assertEqual(skipped_reasons["off"], ["generate_dnsmasq_false"])
        self.assertEqual(skipped_reasons["mdns"], ["endpoint_type_not_exportable"])
        self.assertEqual(skipped_reasons["old"], ["node_lifecycle_not_exportable"])
        self.assertEqual(skipped_reasons["nameless"], ["missing_dns_name"])

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
        self.assertEqual(export.summary["skipped_endpoints"], 0)
        self.assertEqual(export.summary["skipped_endpoint_details"], 0)
        self.assertEqual(
            [record["line"] for record in export.records],
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

        self.assertEqual(export.records, [])
        self.assertEqual(export.skipped[0]["reasons"], ["missing_cname_alias"])

    def test_render_outputs_for_ansible_consumption(self) -> None:
        active = node("Edge 1", "edge-1", "active")
        export = export_dnsmasq_records(
            [
                endpoint(
                    name="primary",
                    desired_node=active,
                    dns_name="edge-1.example.test",
                    ip_address="192.0.2.10/32",
                )
            ]
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
                    "# schema_version: 1.0",
                    "# generated_at: 2026-06-23T00:00:00+00:00",
                    "# job_result_id: job-123",
                    "host-record=edge-1.example.test,192.0.2.10",
                    "",
                ]
            ),
        )

        payload = dnsmasq_export_payload(
            export,
            generated_at="2026-06-23T00:00:00+00:00",
            job_result_id="job-123",
        )
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["job_result_id"], "job-123")
        self.assertEqual(payload["records"][0]["line"], "host-record=edge-1.example.test,192.0.2.10")
        self.assertTrue(render_dnsmasq_export_json(export, generated_at="2026-06-23T00:00:00+00:00").endswith("\n"))


if __name__ == "__main__":
    unittest.main()
