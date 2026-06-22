from __future__ import annotations

import unittest

from nautobot_intent_catalog.importers import (
    dependency_key,
    desired_endpoint_defaults,
    desired_endpoint_identity,
    desired_node_defaults,
    desired_node_identity,
    desired_service_defaults,
    desired_service_dependencies,
    desired_service_identity,
    intent_source_defaults,
)
from nautobot_intent_catalog.loaders import DesiredEndpointEntry, DesiredNodeEntry, IntentSourceEntry


class ImporterTests(unittest.TestCase):
    def test_intent_source_defaults_normalize_loader_fields(self) -> None:
        source = IntentSourceEntry(
            url="https://github.com/example/service",
            enabled=False,
            ref="main",
            owner="platform",
            service_hint="service",
            catalog_paths=["catalog-info.yaml"],
            basic_file_paths=["README.md"],
            raw_url_template="https://example.test/{ref}/{path}",
        )

        self.assertEqual(
            intent_source_defaults(source),
            {
                "name": "service",
                "slug": "service",
                "source_type": "git_repository",
                "enabled": False,
                "ref": "main",
                "owner": "platform",
                "description": None,
                "source_config": {
                    "service_hint": "service",
                    "catalog_paths": ["catalog-info.yaml"],
                    "basic_file_paths": ["README.md"],
                    "catalog_paths_defaulted": False,
                    "basic_file_paths_defaulted": False,
                    "raw_url_template": "https://example.test/{ref}/{path}",
                },
            },
        )

    def test_desired_service_identity_and_defaults_use_catalog_shape(self) -> None:
        service = {
            "name": "storage-service",
            "display_name": "Storage Service",
            "role": "service",
            "prefers_gpu": False,
            "intent_source": {
                "url": "https://github.com/example/storage",
                "ref": "main",
                "catalog_path": "catalog-info.yaml",
            },
            "catalog": {
                "kind": "Component",
                "namespace": "default",
                "metadata_name": "storage",
                "spec_type": "service",
                "owner": "platform",
                "lifecycle": "production",
            },
            "analysis": {
                "status": "catalog_derived",
                "confidence": "medium",
                "reasons": ["backstage_component_catalog_found"],
            },
        }

        self.assertEqual(
            desired_service_identity(service),
            {
                "catalog_namespace": "default",
                "catalog_metadata_name": "storage",
                "service_type": "service",
            },
        )
        defaults = desired_service_defaults(service)
        self.assertEqual(defaults["name"], "storage-service")
        self.assertEqual(defaults["slug"], "storage-service")
        self.assertEqual(defaults["source_ref"], "main")
        self.assertEqual(defaults["catalog_owner"], "platform")
        self.assertEqual(defaults["requirements"]["analysis_reasons"], ["backstage_component_catalog_found"])

    def test_desired_service_dependencies_drop_malformed_rows(self) -> None:
        service = {
            "dependencies": [
                {
                    "raw_ref": "resource:default/postgresql",
                    "kind": "resource",
                    "namespace": "default",
                    "name": "postgresql",
                    "dependency_type": "resource",
                    "resolution_status": "unresolved",
                },
                {"raw_ref": "", "kind": "", "namespace": "default", "name": ""},
            ]
        }

        dependencies = desired_service_dependencies(service)

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependency_key(dependencies[0]), ("resource", "default", "postgresql"))

    def test_desired_node_identity_and_defaults(self) -> None:
        node = DesiredNodeEntry(
            name="Edge Router 1",
            slug="edge-router-1",
            node_type="virtual_machine",
            lifecycle="approved",
            role="edge",
            expected_spec={"cpu": 2},
            notes="planned replacement",
        )

        self.assertEqual(desired_node_identity(node), {"slug": "edge-router-1"})
        self.assertEqual(
            desired_node_defaults(node, intent_source_id="source-id"),
            {
                "name": "Edge Router 1",
                "node_type": "virtual_machine",
                "lifecycle": "approved",
                "role": "edge",
                "description": None,
                "expected_spec": {"cpu": 2},
                "notes": "planned replacement",
                "intent_source_id": "source-id",
            },
        )

    def test_desired_endpoint_identity_and_defaults(self) -> None:
        endpoint = DesiredEndpointEntry(
            name="mgmt",
            desired_node="edge-router-1",
            endpoint_type="management",
            ip_address="192.0.2.10/32",
            dns_name="edge-router-1.example.test",
            protocol="https",
            port=443,
            generate_dnsmasq=True,
        )

        self.assertEqual(
            desired_endpoint_identity(endpoint, desired_node_id="node-id"),
            {
                "desired_node_id": "node-id",
                "name": "mgmt",
                "endpoint_type": "management",
            },
        )
        self.assertEqual(
            desired_endpoint_defaults(endpoint),
            {
                "ip_address": "192.0.2.10/32",
                "dns_name": "edge-router-1.example.test",
                "mdns_name": None,
                "vpn_dns_name": None,
                "protocol": "https",
                "port": 443,
                "generate_dnsmasq": True,
                "dnsmasq_record_type": "host_record",
                "description": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
