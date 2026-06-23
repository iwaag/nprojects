from __future__ import annotations

from types import SimpleNamespace
import unittest

from nautobot_intent_catalog.evaluations import (
    evaluate_endpoint_intent,
    evaluate_node_intent,
    evaluate_service_intent,
)


def obj(**kwargs):
    return SimpleNamespace(**kwargs)


def node(**overrides):
    data = {
        "pk": "11111111-1111-1111-1111-111111111111",
        "name": "edge-1",
        "slug": "edge-1",
        "node_type": "device",
        "lifecycle": "active",
        "role": "edge",
        "expected_spec": {},
        "realized_device": None,
        "realized_vm": None,
    }
    data.update(overrides)
    return obj(**data)


def endpoint(**overrides):
    data = {
        "pk": "22222222-2222-2222-2222-222222222222",
        "name": "primary",
        "endpoint_type": "primary",
        "ip_address": "192.0.2.10/32",
        "dns_name": "edge-1.example.test",
        "generate_dnsmasq": True,
        "dnsmasq_record_type": "host_record",
        "desired_node": node(),
        "realized_ip_address": None,
    }
    data.update(overrides)
    return obj(**data)


def actual_node(**overrides):
    data = {
        "pk": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "name": "edge-1",
        "serial": "SER123",
        "uuid": "NODE-UUID-1",
        "platform": obj(name="ubuntu"),
        "_custom_field_data": {},
        "interfaces": [],
    }
    data.update(overrides)
    return obj(**data)


def actual_ip(**overrides):
    data = {
        "pk": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "address": "192.0.2.10/32",
        "dns_name": "edge-1.example.test",
    }
    data.update(overrides)
    return obj(**data)


def interface(**overrides):
    data = {
        "pk": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "name": "eth0",
        "mac_address": "AA-BB-CC-DD-EE-FF",
        "enabled": True,
    }
    data.update(overrides)
    return obj(**data)


def service(**overrides):
    data = {
        "pk": "33333333-3333-3333-3333-333333333333",
        "name": "api-service",
        "slug": "api-service",
        "display_name": "API Service",
        "service_type": "service",
        "lifecycle": "active",
        "catalog_namespace": "default",
        "catalog_metadata_name": "api",
        "catalog_owner": "platform",
        "requirements": {"memory_gb": 2},
        "placement_policy": {},
        "dependencies": [],
    }
    data.update(overrides)
    return obj(**data)


def dependency(**overrides):
    data = {
        "dependency_kind": "component",
        "namespace": "default",
        "name": "database",
        "raw_ref": "component:default/database",
        "dependency_type": "component",
        "resolution_status": "unresolved",
        "resolved_service": None,
    }
    data.update(overrides)
    return obj(**data)


class NodeEvaluationTests(unittest.TestCase):
    def test_explicit_realized_link_is_satisfied_and_skips_candidate_adoption(self) -> None:
        realized = actual_node(name="edge-real", serial="SER123")
        desired = node(
            name="edge-1",
            realized_device=realized,
            expected_spec={"serial": "SER123"},
        )
        conflicting_candidate = actual_node(
            pk="dddddddd-dddd-dddd-dddd-dddddddddddd",
            name="edge-1",
            serial="OTHER",
        )

        payload = evaluate_node_intent(desired, device_candidates=[conflicting_candidate])

        self.assertEqual(payload.status, "satisfied")
        self.assertEqual(payload.actual_refs[0]["id"], realized.pk)
        self.assertEqual(payload.observed_facts["candidates"], [])

    def test_missing_node_records_missing_evaluation_instead_of_raising(self) -> None:
        payload = evaluate_node_intent(node(name="unknown", slug="unknown"))

        self.assertEqual(payload.status, "missing")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "missing_actual_node")
        self.assertEqual(payload.recommended_actions[0]["action"], "link_desired_node_to_actual")

    def test_unique_candidate_is_partial_and_requires_review(self) -> None:
        payload = evaluate_node_intent(
            node(name="edge-1", slug="edge-1"),
            device_candidates=[actual_node(name="edge-1")],
        )

        self.assertEqual(payload.status, "partial")
        self.assertEqual(payload.actual_refs[0]["object_type"], "dcim.device")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "actual_node_not_linked")
        self.assertTrue(payload.recommended_actions[0]["requires_review"])

    def test_explicit_link_mismatch_is_conflict(self) -> None:
        payload = evaluate_node_intent(
            node(realized_device=actual_node(serial="ACTUAL"), expected_spec={"serial": "EXPECTED"})
        )

        self.assertEqual(payload.status, "conflict")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "serial_mismatch")

    def test_ambiguous_candidates_are_conflict(self) -> None:
        desired = node(expected_spec={"serial": "SER123"})
        payload = evaluate_node_intent(
            desired,
            device_candidates=[
                actual_node(pk="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", name="node-a", serial="SER123"),
                actual_node(pk="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", name="node-b", serial="SER123"),
            ],
        )

        self.assertEqual(payload.status, "conflict")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "ambiguous_actual_node_candidates")


class EndpointEvaluationTests(unittest.TestCase):
    def test_realized_ip_and_single_mac_candidate_are_satisfied(self) -> None:
        desired_node = node(realized_device=actual_node(interfaces=[interface()]))
        payload = evaluate_endpoint_intent(
            endpoint(desired_node=desired_node, realized_ip_address=actual_ip())
        )

        self.assertEqual(payload.status, "satisfied")
        self.assertTrue(payload.deterministic_summary["dhcp_reservation_ready"])
        self.assertEqual(payload.observed_facts["dhcp_mac_candidates"][0]["mac_address"], "aa:bb:cc:dd:ee:ff")

    def test_ip_mismatch_is_conflict(self) -> None:
        payload = evaluate_endpoint_intent(
            endpoint(realized_ip_address=actual_ip(address="192.0.2.20/32"))
        )

        self.assertEqual(payload.status, "conflict")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "ip_address_mismatch")

    def test_nautobot_3_ip_host_and_mask_length_are_matched(self) -> None:
        desired_node = node(realized_device=actual_node(interfaces=[interface()]))
        realized_ip = actual_ip(address=None, host="192.0.2.10", mask_length=32)
        payload = evaluate_endpoint_intent(endpoint(desired_node=desired_node, realized_ip_address=realized_ip))

        self.assertEqual(payload.status, "satisfied")
        self.assertEqual(payload.actual_refs[0]["name"], "192.0.2.10/32")
        self.assertEqual(payload.observed_facts["actual_ip_address"]["address"], "192.0.2.10/32")

    def test_nautobot_3_ip_candidates_match_host_and_mask_length(self) -> None:
        matching_ip = actual_ip(address=None, host="192.0.2.10", mask_length=32)
        payload = evaluate_endpoint_intent(
            endpoint(realized_ip_address=None, generate_dnsmasq=False),
            ip_candidates=[matching_ip],
        )

        self.assertEqual(payload.status, "partial")
        self.assertEqual(payload.actual_refs[0]["name"], "192.0.2.10/32")
        self.assertEqual(payload.observed_facts["ip_candidates"][0]["facts"]["address"], "192.0.2.10/32")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "actual_ip_address_not_linked")

    def test_missing_ip_and_missing_mac_are_partial(self) -> None:
        desired_node = node(realized_device=actual_node(interfaces=[interface(mac_address=None)]))
        payload = evaluate_endpoint_intent(endpoint(desired_node=desired_node), ip_candidates=[])

        self.assertEqual(payload.status, "partial")
        gap_codes = [gap["code"] for gap in payload.gap_summary["gaps"]]
        self.assertIn("missing_actual_ip_address", gap_codes)
        self.assertIn("missing_mac_address", gap_codes)
        self.assertFalse(payload.deterministic_summary["dhcp_reservation_ready"])

    def test_multiple_mac_candidates_are_not_dhcp_ready(self) -> None:
        desired_node = node(
            realized_device=actual_node(
                interfaces=[
                    interface(name="eth0", mac_address="aa:bb:cc:dd:ee:ff"),
                    interface(
                        pk="dddddddd-dddd-dddd-dddd-dddddddddddd",
                        name="eth1",
                        mac_address="11:22:33:44:55:66",
                    ),
                ]
            )
        )
        payload = evaluate_endpoint_intent(
            endpoint(desired_node=desired_node, realized_ip_address=actual_ip())
        )

        self.assertEqual(payload.status, "partial")
        self.assertEqual(payload.gap_summary["gaps"][0]["code"], "ambiguous_interface")
        self.assertFalse(payload.deterministic_summary["dhcp_reservation_ready"])
        self.assertEqual(payload.recommended_actions[0]["action"], "select_dhcp_interface")


class ServiceEvaluationTests(unittest.TestCase):
    def test_unresolved_dependency_is_recorded_as_gap_and_action_without_ai_output(self) -> None:
        payload = evaluate_service_intent(
            service(dependencies=[dependency()]),
            ai_review_enabled=True,
        )

        self.assertEqual(payload.target_type, "desired_service")
        self.assertEqual(payload.status, "partial")
        self.assertEqual(payload.observed_facts["ai_review"], {"enabled": True, "executed": False})
        gap_codes = [gap["code"] for gap in payload.gap_summary["gaps"]]
        self.assertIn("unresolved_dependency", gap_codes)
        self.assertIn("service_observed_facts_unknown", gap_codes)
        self.assertEqual(payload.recommended_actions[0]["action"], "resolve_service_dependency")
        self.assertEqual(payload.recommended_actions[0]["dependency"]["raw_ref"], "component:default/database")

    def test_service_with_provided_observed_facts_and_resolved_dependencies_is_satisfied(self) -> None:
        payload = evaluate_service_intent(
            service(
                dependencies=[
                    dependency(
                        resolution_status="resolved",
                        resolved_service=service(
                            pk="44444444-4444-4444-4444-444444444444",
                            name="database",
                            slug="database",
                            display_name="Database",
                            catalog_metadata_name="database",
                        ),
                    )
                ],
            ),
            observed_facts={"monitoring": {"status": "ok"}},
        )

        self.assertEqual(payload.status, "satisfied")
        self.assertEqual(payload.observed_facts["service_observation_status"], "provided")
        self.assertEqual(payload.deterministic_summary["dependency_counts"]["resolved"], 1)
        self.assertEqual(payload.recommended_actions, [])


if __name__ == "__main__":
    unittest.main()
