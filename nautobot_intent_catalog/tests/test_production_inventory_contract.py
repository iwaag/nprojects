from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import yaml

from nautobot_intent_catalog.production_inventory_contract import (
    ACTUAL_MAX_AGE_HOURS,
    ContractError,
    actual_state_problem,
    canonical_json,
    canonical_json_digest,
    evaluate_platform_policy,
    map_placement_config,
    merge_host_variables,
    parse_profile_job_input,
    require_unique_reference,
    resolve_connection_variables,
    validate_deployment_profiles,
    validate_desired_service_reference,
    validate_endpoint_ownership,
    validate_endpoint_reference,
    validate_production_inventory_document,
    validate_production_report,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "production_inventory_contract_cases.yml"


class ProductionInventoryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.profiles = cls.fixture["profiles"]

    def test_canonical_json_bytes_and_digest_are_exact(self) -> None:
        value = {"z": [True, "日本語"], "a": {"n": 3}}
        expected = '{"a":{"n":3},"z":[true,"日本語"]}'

        self.assertEqual(canonical_json(value), expected)
        self.assertFalse(canonical_json(value).endswith("\n"))
        self.assertEqual(
            canonical_json_digest(value),
            hashlib.sha256(expected.encode("utf-8")).hexdigest(),
        )

    def test_profile_job_input_requires_canonical_bytes_and_digest(self) -> None:
        payload = canonical_json(self.profiles)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        self.assertEqual(parse_profile_job_input(payload, digest), self.profiles)
        self.assert_contract_error(
            "noncanonical_profile_json",
            parse_profile_job_input,
            json.dumps(self.profiles, sort_keys=True),
            digest,
        )
        self.assert_contract_error(
            "profile_digest_mismatch",
            parse_profile_job_input,
            payload,
            "0" * 64,
        )

    def test_profile_shape_is_closed_and_rejects_duplicate_ansible_variables(self) -> None:
        validate_deployment_profiles(self.profiles)
        bad = yaml.safe_load(yaml.safe_dump(self.profiles))
        bad["demo"]["extra"] = True
        self.assert_contract_error("invalid_contract_keys", validate_deployment_profiles, bad)

        duplicate = yaml.safe_load(yaml.safe_dump(self.profiles))
        duplicate["demo"]["variables"]["other"] = {
            "ansible_variable": "demo_enabled",
            "type": "boolean",
            "required": False,
        }
        self.assert_contract_error("duplicate_variable_assignment", validate_deployment_profiles, duplicate)

    def test_placement_config_is_allowlisted_and_typed(self) -> None:
        mapped = map_placement_config("demo", "1", {"enabled": True, "peers": ["a", "b"]}, self.profiles)
        self.assertEqual(mapped, {"demo_enabled": True, "demo_peers": ["a", "b"]})
        self.assert_contract_error(
            "unknown_config_key",
            map_placement_config,
            "demo",
            "1",
            {"secret": "must-not-pass"},
            self.profiles,
        )

    def test_qualified_reference_formats(self) -> None:
        service_ref = {
            "intent_source": "infrastructure",
            "catalog_namespace": "default",
            "catalog_metadata_name": "dnsmasq",
            "service_type": "service",
        }
        endpoint_ref = {"name": "primary", "endpoint_type": "primary"}

        self.assertEqual(validate_desired_service_reference(service_ref), service_ref)
        self.assertEqual(validate_endpoint_reference(endpoint_ref), endpoint_ref)
        self.assert_contract_error(
            "invalid_contract_keys",
            validate_desired_service_reference,
            {"intent_source": "infrastructure", "slug": "dnsmasq"},
        )
        self.assert_contract_error(
            "invalid_contract_keys",
            validate_endpoint_reference,
            {"name": "primary"},
        )

    def test_connection_resolution_and_shared_user_contract(self) -> None:
        local = resolve_connection_variables(
            inventory_hostname="node-a",
            actual_state_policy="required",
            connection_path="local",
            actual_local_ip="192.0.2.10/24",
            local_endpoint={"dns_name": "node-a.example.test", "mdns_name": "node-a.local"},
        )
        self.assertEqual(local["ansible_host"], "192.0.2.10")
        self.assertEqual(local["local_dns_hostname"], "node-a.example.test")
        self.assertNotIn("ansible_user", local)

        tailscale = resolve_connection_variables(
            inventory_hostname="node-a",
            actual_state_policy="required",
            connection_path="tailscale",
            tailscale_endpoint={"ip_address": "100.64.0.10/32"},
        )
        self.assertEqual(tailscale["ansible_host"], "100.64.0.10")
        self.assert_contract_error(
            "unresolved_connection_path",
            resolve_connection_variables,
            inventory_hostname="node-a",
            actual_state_policy="required",
            connection_path="tailscale",
        )

    def test_freshness_boundary_is_72_hours_inclusive(self) -> None:
        self.assertEqual(ACTUAL_MAX_AGE_HOURS, 72)
        self.assertIsNone(
            actual_state_problem(
                "2026-06-24T12:00:00+00:00",
                "2026-06-27T12:00:00+00:00",
            )
        )

    def test_production_inventory_and_report_schema_are_closed(self) -> None:
        generation_id = "12345678-1234-5678-9234-567812345678"
        digest = "a" * 64
        inventory = {
            "all": {
                "vars": {
                    "nintent_inventory_schema_version": "1.0",
                    "nintent_generation_id": generation_id,
                    "nintent_generated_at": "2026-06-27T12:00:00+00:00",
                    "nintent_report_path": f"production.reports/{generation_id}.json",
                    "nintent_deployment_profile_digest": digest,
                },
                "children": {
                    "ssh_hosts": {
                        "hosts": {
                            "node-a": {
                                "host_os": "linux",
                                "connection_path": "local",
                                "nintent_desired_node_id": "node-id",
                                "demo_enabled": True,
                            }
                        }
                    },
                    "linux": {"hosts": {"node-a": {}}},
                    "macos": {"hosts": {}},
                    "haos": {"hosts": {}},
                    "power_managed": {"hosts": {"node-a": {}}},
                    "demo_server": {"hosts": {"node-a": {}}},
                },
            }
        }
        report = {
            "schema_version": "1.0",
            "generation_id": generation_id,
            "generated_at": "2026-06-27T12:00:00+00:00",
            "report_path": f"production.reports/{generation_id}.json",
            "deployment_profile_digest": digest,
            "summary": {
                "eligible": 1,
                "included": 1,
                "skipped": 0,
                "placements": 1,
                "active_placements": 1,
                "inactive_placements": 0,
            },
            "hosts": [],
            "skipped": [],
            "drift": [],
            "errors": [],
        }

        self.assertIs(validate_production_inventory_document(inventory, self.profiles), inventory)
        self.assertIs(validate_production_report(report), report)

        inventory["all"]["children"]["ssh_hosts"]["hosts"]["node-a"]["package_manager"] = "apt"
        self.assert_contract_error(
            "unknown_host_variable",
            validate_production_inventory_document,
            inventory,
            self.profiles,
        )

        report["legacy"] = {}
        self.assert_contract_error("invalid_contract_keys", validate_production_report, report)

    def test_required_contract_scenario_fixtures(self) -> None:
        names = set()
        for case in self.fixture["cases"]:
            names.add(case["name"])
            expected_error = case.get("expected_error")
            if expected_error:
                with self.assertRaises(ContractError) as caught:
                    self._execute_case(case)
                self.assertEqual(caught.exception.code, expected_error, case["name"])
            else:
                self._execute_case(case)

        self.assertEqual(
            names,
            {
                "linux_actual_state",
                "macos_actual_state",
                "haos_declared_state",
                "missing_actual_data",
                "stale_actual_data",
                "endpoint_mismatch",
                "unknown_profile",
                "invalid_profile_value_type",
                "ambiguous_service_reference",
                "desired_actual_os_mismatch",
                "invalid_platform_power",
                "conflicting_placement_variables",
            },
        )

    def _execute_case(self, case: dict) -> None:
        action = case["action"]
        if action == "platform":
            host_os, drift = evaluate_platform_policy(**case["input"])
            self.assertEqual(host_os, case.get("expected_host_os"))
            if case.get("expected_drift"):
                self.assertEqual(drift[0]["code"], case["expected_drift"])
            else:
                self.assertEqual(drift, [])
        elif action == "freshness":
            self.assertEqual(
                actual_state_problem(case.get("collected_at"), case["generated_at"]),
                case["expected_reason"],
            )
        elif action == "endpoint_ownership":
            validate_endpoint_ownership(case["desired_node_slug"], case["endpoint_node_slug"])
        elif action == "placement_config":
            map_placement_config(
                case["profile"],
                case["config_schema_version"],
                case["config"],
                self.profiles,
            )
        elif action == "reference_count":
            require_unique_reference(case["kind"], case["match_count"])
        elif action == "merge_variables":
            merge_host_variables(
                (assignment["source"], assignment["variables"])
                for assignment in case["assignments"]
            )
        else:  # pragma: no cover - a malformed fixture should be obvious.
            self.fail(f"Unknown fixture action: {action}")

    def assert_contract_error(self, code: str, function, *args, **kwargs) -> None:
        with self.assertRaises(ContractError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
