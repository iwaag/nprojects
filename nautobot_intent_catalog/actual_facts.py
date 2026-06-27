"""Allowlisted actual-fact extraction for the production inventory exporter.

Pure helpers (no Django or Nautobot dependency) that read only the documented
allowlist of observed facts from a realized Device's custom fields.  The
production composer consumes these instead of parsing the unrestricted
``inventory_raw_json`` blob, and nothing here is derived or inferred from another
fact: package managers, power policy, and service placement are never produced
from actual data.

Normalization of the observed system into the ``host_os`` enum intentionally
does not happen here.  The raw nodeutils ``facts.system`` value is returned
unchanged and normalized in exactly one place,
``production_inventory_contract.evaluate_platform_policy``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

# The only realized object type schema 1.0 supports for actual-backed
# composition.  Realized Virtual Machines are skipped with
# ``unsupported_actual_type`` and deferred to a later schema.
SUPPORTED_REALIZED_TYPE = "device"

# Closed allowlist mapping each exportable actual fact to the dedicated custom
# field that the nauto nodeutils ingest job persists.  The exporter reads only
# these stable fields; adding a fact requires a concrete current consumer, a
# documented source path, and tests.
ACTUAL_FACT_FIELDS = {
    "observed_system": "host_system",
    "local_ip": "primary_ip_address",
    "mac_address": "primary_mac_address",
    "network_interface": "network_interface",
    "collected_at": "last_seen",
    "inventory_source": "inventory_source",
}

# Per-consumer required actual facts.  A fact is required only when a concrete
# current consumer needs it; not every allowlisted field is required on every
# host.
REQUIRED_FACT_BY_CONSUMER = {
    "host_os": "observed_system",  # observed OS selector groups and drift
    "wol": "mac_address",  # wake-on-LAN power control
    "network_interface": "network_interface",  # playbooks/profiles that bind to it
}


@dataclass(frozen=True)
class ActualFacts:
    """The closed set of observed facts exportable under schema 1.0.

    This structure has a field for each allowlisted fact and nothing else, so no
    derived operational value (package manager, power policy, service placement)
    can travel through it.
    """

    observed_system: str | None
    local_ip: str | None
    mac_address: str | None
    network_interface: str | None
    collected_at: str | None
    inventory_source: str | None


def read_actual_facts(custom_fields: Mapping[str, Any] | None) -> ActualFacts:
    """Read only the allowlisted actual facts from a realized Device.

    Any key outside :data:`ACTUAL_FACT_FIELDS` is ignored, so raw inventory
    blobs and other observed payloads can never leak into the exported facts.
    """

    data = custom_fields or {}

    def field(name: str) -> str | None:
        value = data.get(ACTUAL_FACT_FIELDS[name])
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    return ActualFacts(
        observed_system=field("observed_system"),
        local_ip=field("local_ip"),
        mac_address=field("mac_address"),
        network_interface=field("network_interface"),
        collected_at=field("collected_at"),
        inventory_source=field("inventory_source"),
    )


def actual_type_problem(realized_type: str | None) -> str | None:
    """Return a host-skip reason for an unusable realized actual type.

    ``None`` means the realized object is a Device and is eligible for
    actual-backed composition.
    """

    if not realized_type:
        return "no_realized_device"
    if realized_type == SUPPORTED_REALIZED_TYPE:
        return None
    return "unsupported_actual_type"


def missing_required_facts(facts: ActualFacts, consumers: Iterable[str]) -> list[str]:
    """Return skip reasons for consumer-specific facts that are absent.

    ``consumers`` lists which current consumers apply to this host (for example
    ``{"host_os", "wol"}``).  Only the facts those consumers need are required.
    """

    problems: list[str] = []
    for consumer in sorted(set(consumers)):
        try:
            attr = REQUIRED_FACT_BY_CONSUMER[consumer]
        except KeyError as exc:
            raise KeyError(f"unknown actual-fact consumer: {consumer!r}") from exc
        if getattr(facts, attr) is None:
            problems.append(f"missing_{attr}")
    return sorted(problems)
