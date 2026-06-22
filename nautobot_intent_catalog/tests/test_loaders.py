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


if __name__ == "__main__":
    unittest.main()
