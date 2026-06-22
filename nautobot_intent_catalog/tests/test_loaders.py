from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nautobot_intent_catalog.loaders import (
    DEFAULT_BASIC_FILE_PATHS,
    DEFAULT_CATALOG_PATHS,
    load_intent_sources,
)


class LoaderTests(unittest.TestCase):
    def test_loader_applies_analysis_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent_sources.yaml"
            path.write_text(
                "intent_sources:\n"
                "  - url: https://github.com/example/service\n",
                encoding="utf-8",
            )

            result = load_intent_sources(path)

        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.intent_sources), 1)
        intent_source = result.intent_sources[0]
        self.assertEqual(intent_source.catalog_paths, list(DEFAULT_CATALOG_PATHS))
        self.assertEqual(intent_source.basic_file_paths, list(DEFAULT_BASIC_FILE_PATHS))
        self.assertTrue(intent_source.catalog_paths_defaulted)
        self.assertTrue(intent_source.basic_file_paths_defaulted)

    def test_loader_preserves_explicit_empty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent_sources.yaml"
            path.write_text(
                "intent_sources:\n"
                "  - url: https://github.com/example/service\n"
                "    catalog_paths: []\n"
                "    basic_file_paths: []\n",
                encoding="utf-8",
            )

            result = load_intent_sources(path)

        intent_source = result.intent_sources[0]
        self.assertEqual(intent_source.catalog_paths, [])
        self.assertEqual(intent_source.basic_file_paths, [])
        self.assertFalse(intent_source.catalog_paths_defaulted)
        self.assertFalse(intent_source.basic_file_paths_defaulted)

    def test_loader_does_not_accept_old_service_repositories_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent_sources.yaml"
            path.write_text(
                "service_repositories:\n"
                "  - url: https://github.com/example/service\n",
                encoding="utf-8",
            )

            result = load_intent_sources(path)

        self.assertEqual(
            result.errors,
            ["service_repositories is not supported; rename the top-level key to intent_sources."],
        )
        self.assertEqual(result.intent_sources, [])

    def test_loader_normalizes_desired_nodes_and_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent_sources.yaml"
            path.write_text(
                "desired_nodes:\n"
                "  - name: Edge Router 1\n"
                "    node_type: virtual-machine\n"
                "    lifecycle: approved\n"
                "    role: edge\n"
                "    expected_spec:\n"
                "      cpu: 2\n"
                "desired_endpoints:\n"
                "  - name: mgmt\n"
                "    desired_node: edge-router-1\n"
                "    endpoint_type: management\n"
                "    ip_address: 192.0.2.10/32\n"
                "    dns_name: edge-router-1.example.test\n"
                "    protocol: https\n"
                "    port: 443\n"
                "    generate_dnsmasq: true\n",
                encoding="utf-8",
            )

            result = load_intent_sources(path)

        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.desired_nodes), 1)
        self.assertEqual(result.desired_nodes[0].slug, "edge-router-1")
        self.assertEqual(result.desired_nodes[0].node_type, "virtual_machine")
        self.assertEqual(result.desired_nodes[0].expected_spec, {"cpu": 2})
        self.assertEqual(len(result.desired_endpoints), 1)
        self.assertEqual(result.desired_endpoints[0].desired_node, "edge-router-1")
        self.assertEqual(result.desired_endpoints[0].port, 443)
        self.assertTrue(result.desired_endpoints[0].generate_dnsmasq)

    def test_loader_reports_endpoint_with_missing_node(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intent_sources.yaml"
            path.write_text(
                "desired_endpoints:\n"
                "  - name: mgmt\n"
                "    desired_node: missing-node\n",
                encoding="utf-8",
            )

            result = load_intent_sources(path)

        self.assertEqual(
            result.errors,
            ["desired_endpoints entry mgmt references missing desired_node: missing-node."],
        )


if __name__ == "__main__":
    unittest.main()
