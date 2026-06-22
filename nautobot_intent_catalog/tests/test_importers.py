from __future__ import annotations

import unittest

from nautobot_intent_catalog.importers import (
    dependency_key,
    desired_service_defaults,
    desired_service_dependencies,
    desired_service_identity,
    intent_source_defaults,
)
from nautobot_intent_catalog.loaders import RepositoryEntry


class ImporterTests(unittest.TestCase):
    def test_intent_source_defaults_normalize_loader_fields(self) -> None:
        source = RepositoryEntry(
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


if __name__ == "__main__":
    unittest.main()
