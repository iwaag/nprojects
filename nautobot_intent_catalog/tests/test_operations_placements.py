from __future__ import annotations

import unittest

from nautobot_intent_catalog.operations import placements


class FakeValidationError(Exception):
    def __init__(self, message_dict):
        super().__init__(message_dict)
        self.message_dict = message_dict


class FakeIntegrityError(Exception):
    pass


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows

    def exists(self):
        return bool(self.rows)


class FakeManager:
    def __init__(self):
        self.rows = []

    def filter(self, **criteria):
        return FakeQuerySet(
            [
                row
                for row in self.rows
                if all(getattr(row, field_name, None) == expected for field_name, expected in criteria.items())
            ]
        )

    def add(self, row):
        row.pk = len(self.rows) + 1
        self.rows.append(row)


class FakeAtomic:
    def __init__(self, manager):
        self.manager = manager
        self.snapshot = None

    def __enter__(self):
        self.snapshot = list(self.manager.rows)
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is not None:
            self.manager.rows = self.snapshot
        return False


class FakeTransaction:
    def __init__(self, manager):
        self.manager = manager

    def atomic(self):
        return FakeAtomic(self.manager)


class FakeDesiredServicePlacement:
    objects = FakeManager()

    def __init__(self, **attrs):
        self.pk = None
        for key, value in attrs.items():
            setattr(self, key, value)

    def full_clean(self):
        return None

    def save(self):
        self.__class__.objects.add(self)


class FakeService:
    def __init__(self, slug="web-service", pk="service-1"):
        self.slug = slug
        self.pk = pk


class FakeNode:
    def __init__(self, pk="node-1"):
        self.pk = pk


class FakeEndpoint:
    def __init__(self, desired_node_id="node-1"):
        self.desired_node_id = desired_node_id


def _profiles() -> dict:
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


class PlacementOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.originals = {
            "ValidationError": placements.ValidationError,
            "DesiredServicePlacement": placements.DesiredServicePlacement,
            "transaction": placements.transaction,
            "IntegrityError": placements.IntegrityError,
        }
        self.addCleanup(self.restore_module)
        FakeDesiredServicePlacement.objects = FakeManager()
        placements.ValidationError = FakeValidationError
        placements.DesiredServicePlacement = FakeDesiredServicePlacement
        placements.transaction = FakeTransaction(FakeDesiredServicePlacement.objects)
        placements.IntegrityError = FakeIntegrityError

    def restore_module(self) -> None:
        for name, value in self.originals.items():
            setattr(placements, name, value)

    def _create(self, **overrides):
        kwargs = {
            "desired_service": FakeService(),
            "desired_node": FakeNode(),
            "deployment_profile": "web",
            "profiles": _profiles(),
            "instance_name": "web-1",
            "config": {"service_port": 8080},
        }
        kwargs.update(overrides)
        return placements.create_desired_service_placement(**kwargs)

    def test_creates_placement_with_derived_and_fixed_fields(self) -> None:
        result = self._create()

        placement = result.placement
        self.assertIs(placement, FakeDesiredServicePlacement.objects.rows[0])
        self.assertEqual(placement.instance_name, "web-1")
        self.assertEqual(placement.deployment_profile, "web")
        self.assertEqual(placement.config_schema_version, "1")
        self.assertEqual(placement.assignment_source, "manual")
        self.assertEqual(placement.desired_state, "active")
        self.assertEqual(placement.config, {"service_port": 8080})

    def test_instance_name_defaults_to_service_slug(self) -> None:
        result = self._create(instance_name=None, desired_service=FakeService(slug="cache-svc"))
        self.assertEqual(result.placement.instance_name, "cache-svc")

    def test_optional_config_defaults_to_empty_object_when_not_required(self) -> None:
        profiles = _profiles()
        profiles["web"]["variables"]["service_port"]["required"] = False
        result = self._create(config=None, profiles=profiles)
        self.assertEqual(result.placement.config, {})

    def test_unknown_profile_is_rejected_without_creating(self) -> None:
        with self.assertRaises(FakeValidationError) as ctx:
            self._create(deployment_profile="missing")
        self.assertIn("deployment_profile", ctx.exception.message_dict)
        self.assertEqual(FakeDesiredServicePlacement.objects.rows, [])

    def test_unknown_config_key_is_rejected_without_creating(self) -> None:
        with self.assertRaises(FakeValidationError) as ctx:
            self._create(config={"bad_key": 1})
        self.assertIn("config", ctx.exception.message_dict)
        self.assertEqual(FakeDesiredServicePlacement.objects.rows, [])

    def test_missing_required_config_is_rejected_without_creating(self) -> None:
        with self.assertRaises(FakeValidationError) as ctx:
            self._create(config={})
        self.assertIn("config", ctx.exception.message_dict)
        self.assertEqual(FakeDesiredServicePlacement.objects.rows, [])

    def test_wrong_config_type_is_rejected_without_creating(self) -> None:
        with self.assertRaises(FakeValidationError) as ctx:
            self._create(config={"service_port": "not-an-int"})
        self.assertIn("config", ctx.exception.message_dict)
        self.assertEqual(FakeDesiredServicePlacement.objects.rows, [])

    def test_endpoint_outside_node_is_rejected_without_creating(self) -> None:
        with self.assertRaises(FakeValidationError) as ctx:
            self._create(desired_endpoint=FakeEndpoint(desired_node_id="other-node"))
        self.assertIn("desired_endpoint", ctx.exception.message_dict)
        self.assertEqual(FakeDesiredServicePlacement.objects.rows, [])

    def test_endpoint_on_node_is_accepted(self) -> None:
        node = FakeNode(pk="node-1")
        result = self._create(desired_node=node, desired_endpoint=FakeEndpoint(desired_node_id="node-1"))
        self.assertEqual(len(FakeDesiredServicePlacement.objects.rows), 1)
        self.assertIs(result.placement.desired_endpoint.desired_node_id, "node-1")

    def test_duplicate_instance_name_is_rejected_without_creating_second(self) -> None:
        service = FakeService()
        self._create(desired_service=service, instance_name="web-1")
        with self.assertRaises(FakeValidationError) as ctx:
            self._create(desired_service=service, instance_name="web-1")
        self.assertIn("instance_name", ctx.exception.message_dict)
        self.assertEqual(len(FakeDesiredServicePlacement.objects.rows), 1)

    def test_optional_fields_pass_through(self) -> None:
        result = self._create(
            desired_state="disabled",
            instance_role="primary",
            reason="initial rollout",
        )
        placement = result.placement
        self.assertEqual(placement.desired_state, "disabled")
        self.assertEqual(placement.instance_role, "primary")
        self.assertEqual(placement.reason, "initial rollout")

    def test_derived_fields_are_not_operator_inputs(self) -> None:
        # The operation does not accept the derived/fixed values as inputs, so an
        # operator cannot hand-type config_schema_version or assignment_source.
        with self.assertRaises(TypeError):
            self._create(config_schema_version="1")
        with self.assertRaises(TypeError):
            self._create(assignment_source="policy")


if __name__ == "__main__":
    unittest.main()
