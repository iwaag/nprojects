from __future__ import annotations

import dataclasses
import unittest

from nautobot_intent_catalog.actual_facts import (
    ACTUAL_FACT_FIELDS,
    ActualFacts,
    actual_type_problem,
    missing_required_facts,
    read_actual_facts,
)
from nautobot_intent_catalog.production_inventory_contract import (
    actual_state_problem,
    evaluate_platform_policy,
)


def custom_fields(**overrides):
    """A realistic nodeutils-ingested custom-field blob with derived noise."""

    data = {
        "host_system": "Linux",
        "primary_ip_address": "192.168.0.10",
        "primary_mac_address": "aa:bb:cc:dd:ee:ff",
        "network_interface": "eth0",
        "last_seen": "2026-06-26T00:00:00+00:00",
        "inventory_source": "nodeutils",
        # Derived / non-allowlisted noise that must never reach ActualFacts.
        "os_name": "Ubuntu",
        "architecture": "x86_64",
        "package_manager": "apt",
        "service_roles": ["ai-inference"],
        "observed_services": {"nomad": {"state": "running"}},
        "docker_engine_state": "active",
        "power_control": "wol",
        "inventory_raw_json": {"facts": {"network": {"primary_interface": {"name": "eth9"}}}},
    }
    data.update(overrides)
    return data


class ReadActualFactsTests(unittest.TestCase):
    def test_reads_only_allowlisted_facts(self) -> None:
        facts = read_actual_facts(custom_fields())

        self.assertEqual(facts.observed_system, "Linux")
        self.assertEqual(facts.local_ip, "192.168.0.10")
        self.assertEqual(facts.mac_address, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(facts.network_interface, "eth0")
        self.assertEqual(facts.collected_at, "2026-06-26T00:00:00+00:00")
        self.assertEqual(facts.inventory_source, "nodeutils")

    def test_structure_exposes_no_derived_operational_value(self) -> None:
        field_names = {field.name for field in dataclasses.fields(ActualFacts)}

        self.assertEqual(field_names, set(ACTUAL_FACT_FIELDS))
        for forbidden in ("package_manager", "service_roles", "observed_services", "power_control"):
            self.assertNotIn(forbidden, field_names)

    def test_network_interface_comes_from_dedicated_field_not_raw_json(self) -> None:
        # The raw blob carries a different interface; the allowlisted field wins.
        facts = read_actual_facts(custom_fields(network_interface="eth0"))

        self.assertEqual(facts.network_interface, "eth0")

    def test_blank_and_missing_values_become_none(self) -> None:
        facts = read_actual_facts({"host_system": "  ", "primary_ip_address": ""})

        self.assertIsNone(facts.observed_system)
        self.assertIsNone(facts.local_ip)
        self.assertIsNone(facts.mac_address)

    def test_none_custom_fields_is_safe(self) -> None:
        facts = read_actual_facts(None)

        self.assertIsNone(facts.observed_system)


class ActualTypeTests(unittest.TestCase):
    def test_device_is_supported(self) -> None:
        self.assertIsNone(actual_type_problem("device"))

    def test_virtual_machine_is_unsupported(self) -> None:
        self.assertEqual(actual_type_problem("virtual_machine"), "unsupported_actual_type")

    def test_unknown_type_is_unsupported(self) -> None:
        self.assertEqual(actual_type_problem("container"), "unsupported_actual_type")

    def test_missing_realized_object(self) -> None:
        self.assertEqual(actual_type_problem(None), "no_realized_device")
        self.assertEqual(actual_type_problem(""), "no_realized_device")


class RequiredFactTests(unittest.TestCase):
    def test_only_consumer_relevant_facts_are_required(self) -> None:
        facts = read_actual_facts({"host_system": "Linux"})

        # host_os consumer is satisfied by observed_system alone.
        self.assertEqual(missing_required_facts(facts, {"host_os"}), [])
        # WOL and interface consumers need facts this host does not report.
        self.assertEqual(
            missing_required_facts(facts, {"host_os", "wol", "network_interface"}),
            ["missing_mac_address", "missing_network_interface"],
        )

    def test_no_consumers_requires_nothing(self) -> None:
        facts = read_actual_facts({})

        self.assertEqual(missing_required_facts(facts, set()), [])

    def test_unknown_consumer_is_rejected(self) -> None:
        facts = read_actual_facts(custom_fields())

        with self.assertRaises(KeyError):
            missing_required_facts(facts, {"package_manager"})


class ContractIntegrationTests(unittest.TestCase):
    def test_reader_does_not_normalize_host_os(self) -> None:
        # The reader returns the raw system; normalization lives in the contract.
        facts = read_actual_facts(custom_fields(host_system="Linux"))
        self.assertEqual(facts.observed_system, "Linux")

        host_os, drift = evaluate_platform_policy(
            actual_state_policy="required",
            power_control="none",
            expected_host_os="linux",
            observed_system=facts.observed_system,
        )
        self.assertEqual(host_os, "linux")
        self.assertEqual(drift, [])

    def test_freshness_uses_collected_at_from_reader(self) -> None:
        facts = read_actual_facts(custom_fields())

        self.assertIsNone(
            actual_state_problem(facts.collected_at, "2026-06-26T01:00:00+00:00")
        )
        self.assertEqual(
            actual_state_problem(None, "2026-06-26T01:00:00+00:00"),
            "missing_actual_data",
        )


if __name__ == "__main__":
    unittest.main()
