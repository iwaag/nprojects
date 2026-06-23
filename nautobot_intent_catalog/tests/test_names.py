from __future__ import annotations

import unittest

from nautobot_intent_catalog.names import (
    canonical_node_name,
    default_dns_name,
    default_mdns_name,
)


class NameHelperTests(unittest.TestCase):
    def test_canonical_node_name_preserves_short_names(self) -> None:
        self.assertEqual(canonical_node_name("pc1"), "pc1")

    def test_canonical_node_name_trims_and_lowercases(self) -> None:
        self.assertEqual(canonical_node_name("  PC1  "), "pc1")

    def test_canonical_node_name_strips_local_suffix(self) -> None:
        self.assertEqual(canonical_node_name("PC1.local"), "pc1")

    def test_canonical_node_name_strips_home_arpa_suffix(self) -> None:
        self.assertEqual(canonical_node_name("pc1.home.arpa"), "pc1")

    def test_canonical_node_name_does_not_strip_unknown_fqdn_suffix(self) -> None:
        self.assertEqual(canonical_node_name("db01.prod.example.com"), "db01.prod.example.com")

    def test_canonical_node_name_uses_label_boundary_for_suffixes(self) -> None:
        self.assertEqual(canonical_node_name("pc1local"), "pc1local")
        self.assertEqual(canonical_node_name("pc1home.arpa"), "pc1home.arpa")

    def test_default_dns_name_uses_canonical_label(self) -> None:
        self.assertEqual(default_dns_name("PC1.local"), "pc1.home.arpa")

    def test_default_dns_name_allows_explicit_suffix(self) -> None:
        self.assertEqual(default_dns_name("pc1.home.arpa", suffix="lab.example"), "pc1.lab.example")

    def test_default_mdns_name_uses_canonical_label(self) -> None:
        self.assertEqual(default_mdns_name("pc1.home.arpa"), "pc1.local")

    def test_defaults_return_blank_for_blank_node_name(self) -> None:
        self.assertEqual(default_dns_name(""), "")
        self.assertEqual(default_mdns_name(None), "")


if __name__ == "__main__":
    unittest.main()
