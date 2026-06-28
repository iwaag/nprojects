from __future__ import annotations

import unittest

from nautobot_intent_catalog.deployment_profiles import (
    DeploymentProfilesUnavailable,
    project_deployment_profiles,
    select_projection_profiles,
)
from nautobot_intent_catalog.production_inventory_contract import (
    ContractError,
    canonical_json,
    canonical_json_digest,
)


def _valid_profiles() -> dict:
    return {
        "web": {
            "group": "web_servers",
            "config_schema_version": "1",
            "variables": {
                "service_port": {
                    "ansible_variable": "service_port",
                    "type": "integer",
                    "required": True,
                },
            },
        },
    }


class FakeProjection:
    def __init__(self, profiles):
        self.profiles = profiles


class ProjectDeploymentProfilesTests(unittest.TestCase):
    def test_valid_export_input_returns_validated_map(self) -> None:
        profiles = _valid_profiles()
        payload = canonical_json(profiles)
        digest = canonical_json_digest(profiles)

        result = project_deployment_profiles(payload, digest)

        self.assertEqual(result, profiles)

    def test_digest_mismatch_is_rejected(self) -> None:
        payload = canonical_json(_valid_profiles())
        with self.assertRaises(ContractError) as ctx:
            project_deployment_profiles(payload, "0" * 64)
        self.assertEqual(ctx.exception.code, "profile_digest_mismatch")

    def test_noncanonical_payload_is_rejected(self) -> None:
        profiles = _valid_profiles()
        noncanonical = "  " + canonical_json(profiles)
        digest = canonical_json_digest(profiles)
        with self.assertRaises(ContractError) as ctx:
            project_deployment_profiles(noncanonical, digest)
        self.assertEqual(ctx.exception.code, "noncanonical_profile_json")

    def test_unsupported_profile_schema_is_rejected(self) -> None:
        profiles = _valid_profiles()
        profiles["web"]["config_schema_version"] = "2"
        payload = canonical_json(profiles)
        digest = canonical_json_digest(profiles)
        with self.assertRaises(ContractError) as ctx:
            project_deployment_profiles(payload, digest)
        self.assertEqual(ctx.exception.code, "unsupported_profile_schema")


class SelectProjectionProfilesTests(unittest.TestCase):
    def test_missing_projection_raises_unavailable(self) -> None:
        with self.assertRaises(DeploymentProfilesUnavailable):
            select_projection_profiles(None)

    def test_synced_projection_returns_validated_map(self) -> None:
        profiles = _valid_profiles()
        result = select_projection_profiles(FakeProjection(profiles))
        self.assertEqual(result, profiles)

    def test_corrupt_projection_is_revalidated_on_read(self) -> None:
        # A stored map that no longer satisfies the contract is rejected on read,
        # so the projection cannot hand callers an invalid profile map.
        with self.assertRaises(ContractError):
            select_projection_profiles(FakeProjection({"web": {"group": "web_servers"}}))


if __name__ == "__main__":
    unittest.main()
