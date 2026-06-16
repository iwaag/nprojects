from __future__ import annotations

import unittest

from nautobot_service_catalog.analysis import FetchedFile, analyze_repositories
from nautobot_service_catalog.loaders import RepositoryEntry


class FakeFetcher:
    def __init__(
        self,
        catalog_file: FetchedFile | None = None,
        basic_files: list[FetchedFile] | None = None,
        default_branch: str | None = "main",
    ) -> None:
        self.catalog_file = catalog_file
        self.basic_files = basic_files or []
        self.default_branch_value = default_branch
        self.default_branch_calls = 0
        self.fetch_first_calls = 0
        self.fetch_many_calls = 0

    def default_branch(self, repository: RepositoryEntry) -> str | None:
        self.default_branch_calls += 1
        return self.default_branch_value

    def fetch_first(self, repository: RepositoryEntry, paths: list[str], refs: list[str]) -> FetchedFile | None:
        self.fetch_first_calls += 1
        return self.catalog_file

    def fetch_many(self, repository: RepositoryEntry, paths: list[str], refs: list[str]) -> list[FetchedFile]:
        self.fetch_many_calls += 1
        return self.basic_files


class AnalysisTests(unittest.TestCase):
    def test_disabled_repository_is_skipped_without_fetch(self) -> None:
        repository = RepositoryEntry(url="https://github.com/example/service", enabled=False)
        fetcher = FakeFetcher()

        result = analyze_repositories([repository], fetch_timeout=1, fetcher=fetcher)

        self.assertEqual(result.repository_analysis[0]["status"], "skipped")
        self.assertEqual(result.repository_analysis[0]["reasons"], ["repository_disabled"])
        self.assertEqual(result.desired_services, [])
        self.assertEqual(fetcher.default_branch_calls, 0)
        self.assertEqual(fetcher.fetch_first_calls, 0)
        self.assertEqual(fetcher.fetch_many_calls, 0)

    def test_missing_catalog_is_insufficient(self) -> None:
        repository = RepositoryEntry(
            url="https://github.com/example/service",
            catalog_paths=["catalog-info.yaml"],
            basic_file_paths=["README.md"],
        )
        fetcher = FakeFetcher(
            catalog_file=None,
            basic_files=[FetchedFile(path="README.md", ref="main", text="# Service", source="fake")],
        )

        result = analyze_repositories([repository], fetch_timeout=1, fetcher=fetcher)

        analysis = result.repository_analysis[0]
        self.assertEqual(analysis["status"], "insufficient")
        self.assertEqual(analysis["reasons"], ["catalog_info_missing"])
        self.assertEqual(analysis["fetched_basic_files"], ["README.md"])
        self.assertEqual(result.desired_services, [])

    def test_service_component_generates_candidate(self) -> None:
        repository = RepositoryEntry(
            url="https://github.com/example/Example.Service",
            owner="platform",
            catalog_paths=["catalog-info.yaml"],
            basic_file_paths=[],
        )
        catalog = FetchedFile(
            path="catalog-info.yaml",
            ref="main",
            source="fake",
            text=(
                "apiVersion: backstage.io/v1alpha1\n"
                "kind: Component\n"
                "metadata:\n"
                "  name: Example.Service\n"
                "  title: Example Service\n"
                "spec:\n"
                "  type: service\n"
                "  lifecycle: production\n"
                "  owner: ignored-by-explicit-owner\n"
            ),
        )
        fetcher = FakeFetcher(catalog_file=catalog)

        result = analyze_repositories([repository], fetch_timeout=1, fetcher=fetcher)

        analysis = result.repository_analysis[0]
        self.assertEqual(analysis["status"], "catalog_parsed")
        self.assertEqual(analysis["generated_service_count"], 1)
        self.assertEqual(result.desired_services[0]["name"], "example-service")
        self.assertEqual(result.desired_services[0]["display_name"], "Example Service")
        self.assertEqual(result.desired_services[0]["role"], "service")
        self.assertEqual(result.desired_services[0]["catalog"]["owner"], "platform")

    def test_non_service_component_does_not_generate_candidate(self) -> None:
        repository = RepositoryEntry(
            url="https://github.com/example/library",
            catalog_paths=["catalog-info.yaml"],
            basic_file_paths=[],
        )
        catalog = FetchedFile(
            path="catalog-info.yaml",
            ref="main",
            source="fake",
            text=(
                "apiVersion: backstage.io/v1alpha1\n"
                "kind: Component\n"
                "metadata:\n"
                "  name: Example Library\n"
                "spec:\n"
                "  type: library\n"
                "  lifecycle: production\n"
            ),
        )
        fetcher = FakeFetcher(catalog_file=catalog)

        result = analyze_repositories([repository], fetch_timeout=1, fetcher=fetcher)

        self.assertEqual(result.repository_analysis[0]["status"], "insufficient")
        self.assertEqual(
            result.repository_analysis[0]["reasons"],
            ["catalog_info_found_but_no_service_component"],
        )
        self.assertEqual(result.desired_services, [])


if __name__ == "__main__":
    unittest.main()
