from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nautobot_intent_catalog.loaders import (
    DEFAULT_BASIC_FILE_PATHS,
    DEFAULT_CATALOG_PATHS,
    load_service_repositories,
)


class LoaderTests(unittest.TestCase):
    def test_loader_applies_analysis_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service_repositories.yaml"
            path.write_text(
                "service_repositories:\n"
                "  - url: https://github.com/example/service\n",
                encoding="utf-8",
            )

            result = load_service_repositories(path)

        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.repositories), 1)
        repository = result.repositories[0]
        self.assertEqual(repository.catalog_paths, list(DEFAULT_CATALOG_PATHS))
        self.assertEqual(repository.basic_file_paths, list(DEFAULT_BASIC_FILE_PATHS))
        self.assertTrue(repository.catalog_paths_defaulted)
        self.assertTrue(repository.basic_file_paths_defaulted)

    def test_loader_preserves_explicit_empty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service_repositories.yaml"
            path.write_text(
                "service_repositories:\n"
                "  - url: https://github.com/example/service\n"
                "    catalog_paths: []\n"
                "    basic_file_paths: []\n",
                encoding="utf-8",
            )

            result = load_service_repositories(path)

        repository = result.repositories[0]
        self.assertEqual(repository.catalog_paths, [])
        self.assertEqual(repository.basic_file_paths, [])
        self.assertFalse(repository.catalog_paths_defaulted)
        self.assertFalse(repository.basic_file_paths_defaulted)


if __name__ == "__main__":
    unittest.main()
