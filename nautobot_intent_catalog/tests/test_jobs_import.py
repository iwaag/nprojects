from __future__ import annotations

import unittest
from types import SimpleNamespace

from nautobot_intent_catalog import jobs


class _FakeObject:
    def __init__(self, **values):
        self.pk = values.pop("pk", None)
        self.cleaned = False
        self.saved = False
        for key, value in values.items():
            setattr(self, key, value)

    def full_clean(self):
        self.cleaned = True

    def save(self):
        self.saved = True
        self.pk = self.pk or "created-id"


class _FakeQuerySet:
    def __init__(self, rows):
        self.rows = list(rows)

    def count(self):
        return len(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def get(self):
        if len(self.rows) != 1:
            raise LookupError("not exactly one row")
        return self.rows[0]


class _FakeManager:
    def __init__(self, rows):
        self.rows = rows
        self.last_filter = None

    def filter(self, **values):
        self.last_filter = values
        return _FakeQuerySet(self.rows)


def _fake_model(rows):
    class FakeModel(_FakeObject):
        objects = _FakeManager(rows)

    return FakeModel


class StrictImportHelperTests(unittest.TestCase):
    def test_validated_upsert_is_idempotent_for_matching_defaults(self) -> None:
        row = _FakeObject(pk="existing-id", value="same")
        model = _fake_model([row])

        status, result = jobs._validated_upsert(model, {"key": "identity"}, {"value": "same"})

        self.assertEqual(status, "unchanged")
        self.assertIs(result, row)
        self.assertFalse(row.cleaned)
        self.assertFalse(row.saved)

    def test_validated_upsert_validates_before_create_or_update(self) -> None:
        existing = _FakeObject(pk="existing-id", value="old")
        update_model = _fake_model([existing])

        status, _result = jobs._validated_upsert(
            update_model,
            {"key": "identity"},
            {"value": "new"},
        )

        self.assertEqual(status, "updated")
        self.assertTrue(existing.cleaned)
        self.assertTrue(existing.saved)

        create_model = _fake_model([])
        status, created = jobs._validated_upsert(
            create_model,
            {"key": "identity"},
            {"value": "new"},
        )
        self.assertEqual(status, "created")
        self.assertTrue(created.cleaned)
        self.assertTrue(created.saved)

    def test_endpoint_resolution_is_always_scoped_to_selected_node(self) -> None:
        endpoint = SimpleNamespace(pk="endpoint-id")
        model = _fake_model([endpoint])
        original = getattr(jobs, "DesiredEndpoint", None)
        jobs.DesiredEndpoint = model
        node = SimpleNamespace(pk="node-id")
        try:
            result = jobs._resolve_desired_endpoint(
                node,
                {"name": "primary", "endpoint_type": "primary"},
                required=True,
            )
        finally:
            if original is None:
                del jobs.DesiredEndpoint
            else:
                jobs.DesiredEndpoint = original

        self.assertIs(result, endpoint)
        self.assertEqual(
            model.objects.last_filter,
            {"desired_node": node, "name": "primary", "endpoint_type": "primary"},
        )

    def test_service_resolution_uses_the_complete_qualified_identity(self) -> None:
        service = SimpleNamespace(pk="service-id")
        model = _fake_model([service])
        original = getattr(jobs, "DesiredService", None)
        jobs.DesiredService = model
        reference = {
            "intent_source": "infrastructure",
            "catalog_namespace": "default",
            "catalog_metadata_name": "dnsmasq",
            "service_type": "service",
        }
        try:
            result = jobs._resolve_desired_service(reference)
        finally:
            if original is None:
                del jobs.DesiredService
            else:
                jobs.DesiredService = original

        self.assertIs(result, service)
        self.assertEqual(
            model.objects.last_filter,
            {
                "intent_source__slug": "infrastructure",
                "catalog_namespace": "default",
                "catalog_metadata_name": "dnsmasq",
                "service_type": "service",
            },
        )


if __name__ == "__main__":
    unittest.main()
