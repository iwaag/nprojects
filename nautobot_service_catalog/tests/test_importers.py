from __future__ import annotations

import unittest

from nautobot_service_catalog.importers import (
    candidate_defaults,
    candidate_dependencies,
    candidate_identity,
    dependency_key,
    repository_defaults,
)
from nautobot_service_catalog.loaders import RepositoryEntry


class ImporterTests(unittest.TestCase):
    def test_repository_defaults_preserve_loader_fields(self) -> None:
        repository = RepositoryEntry(
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
            repository_defaults(repository),
            {
                "enabled": False,
                "ref": "main",
                "owner": "platform",
                "service_hint": "service",
                "catalog_paths": ["catalog-info.yaml"],
                "basic_file_paths": ["README.md"],
                "raw_url_template": "https://example.test/{ref}/{path}",
            },
        )

    def test_candidate_identity_and_defaults_use_catalog_shape(self) -> None:
        candidate = {
            "name": "storage-service",
            "display_name": "Storage Service",
            "role": "service",
            "prefers_gpu": False,
            "source_repository": {
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
            candidate_identity(candidate),
            {
                "catalog_namespace": "default",
                "catalog_metadata_name": "storage",
                "catalog_spec_type": "service",
            },
        )
        defaults = candidate_defaults(candidate)
        self.assertEqual(defaults["name"], "storage-service")
        self.assertEqual(defaults["source_ref"], "main")
        self.assertEqual(defaults["catalog_owner"], "platform")
        self.assertEqual(defaults["analysis_reasons"], ["backstage_component_catalog_found"])

    def test_candidate_dependencies_drop_malformed_rows(self) -> None:
        candidate = {
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

        dependencies = candidate_dependencies(candidate)

        self.assertEqual(len(dependencies), 1)
        self.assertEqual(dependency_key(dependencies[0]), ("resource", "default", "postgresql"))


if __name__ == "__main__":
    unittest.main()
