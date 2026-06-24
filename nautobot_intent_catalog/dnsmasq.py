"""Deterministic dnsmasq export helpers for desired endpoints."""

from __future__ import annotations

from dataclasses import dataclass
import json
from ipaddress import ip_interface
import re
from typing import Any, Iterable, Mapping


ELIGIBLE_NODE_LIFECYCLES = frozenset({"planned", "approved", "active"})
ELIGIBLE_ENDPOINT_TYPES = frozenset({"primary", "management", "service", "vpn"})
SUPPORTED_RECORD_TYPES = frozenset({"host_record", "address", "cname"})
DNSMASQ_EXPORT_SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class DnsmasqExport:
    """Serializable dnsmasq export payload."""

    summary: dict[str, Any]
    dns_records: list[dict[str, Any]]
    dhcp_reservations: list[dict[str, Any]]
    skipped: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "dns_records": self.dns_records,
            "dhcp_reservations": self.dhcp_reservations,
            "skipped": self.skipped,
        }


def export_dnsmasq_records(
    endpoints: Iterable[Any],
    *,
    endpoint_evaluations: Mapping[str, Any] | None = None,
    node_evaluations: Mapping[str, Any] | None = None,
    include_skipped: bool = True,
) -> DnsmasqExport:
    """Return deterministic DNS records and DHCP reservations for desired endpoints."""

    dns_records: list[dict[str, Any]] = []
    dhcp_reservations: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    dns_skipped_count = 0
    dhcp_skipped_count = 0
    total_count = 0

    for endpoint in endpoints:
        total_count += 1
        dns_skip_reasons = _dns_skip_reasons(endpoint)
        if dns_skip_reasons:
            dns_skipped_count += 1
            if include_skipped:
                skipped.append(_skip_entry(endpoint, "dns_record", dns_skip_reasons))
        else:
            dns_records.append(_dns_record_entry(endpoint))

        endpoint_evaluation = _evaluation_for(endpoint, endpoint_evaluations)
        desired_node = getattr(endpoint, "desired_node", None)
        node_evaluation = _evaluation_for(desired_node, node_evaluations)
        reservation = resolve_dhcp_reservation(
            endpoint,
            endpoint_evaluation=endpoint_evaluation,
            node_evaluation=node_evaluation,
        )
        if reservation["skip_reasons"]:
            dhcp_skipped_count += 1
            if include_skipped:
                skipped.append(_skip_entry(endpoint, "dhcp_reservation", reservation["skip_reasons"]))
        else:
            dhcp_reservations.append(reservation)

    dns_records.sort(key=_dns_record_sort_key)
    dhcp_reservations.sort(key=_dhcp_reservation_sort_key)
    skipped.sort(key=_skip_sort_key)
    summary = {
        "dns_records": len(dns_records),
        "dhcp_reservations": len(dhcp_reservations),
        "eligible_endpoints": len(dns_records),
        "record_types": {
            "address": sum(1 for record in dns_records if record["record_type"] == "address"),
            "cname": sum(1 for record in dns_records if record["record_type"] == "cname"),
            "host_record": sum(1 for record in dns_records if record["record_type"] == "host_record"),
        },
        "skipped": {
            "details": len(skipped),
            "dhcp_reservations": dhcp_skipped_count,
            "dns_records": dns_skipped_count,
        },
        "skipped_endpoint_details": len(skipped),
        "skipped_endpoints": dns_skipped_count,
        "total_endpoints": total_count,
    }
    return DnsmasqExport(
        summary=summary,
        dns_records=dns_records,
        dhcp_reservations=dhcp_reservations,
        skipped=skipped,
    )


def resolve_dhcp_reservation(
    endpoint: Any,
    *,
    endpoint_evaluation: Any | None = None,
    node_evaluation: Any | None = None,
) -> dict[str, Any]:
    """Return one DHCP reservation entry or a skipped entry for a desired endpoint."""

    skip_reasons = _dhcp_skip_reasons(endpoint)
    endpoint_data = _evaluation_data(endpoint_evaluation)
    node_data = _evaluation_data(node_evaluation)
    endpoint_summary = _mapping(endpoint_data.get("deterministic_summary"))
    endpoint_observed = _mapping(endpoint_data.get("observed_facts"))
    node_actual_refs = _list(node_data.get("actual_refs"))
    mac_candidates = [
        candidate
        for candidate in _list(endpoint_observed.get("dhcp_mac_candidates"))
        if isinstance(candidate, dict)
    ]
    actual_refs = _unique_actual_refs(mac_candidates, node_actual_refs)
    normalized_mac_candidates = []

    if not endpoint_data:
        skip_reasons.append("missing_endpoint_evaluation")
    if endpoint_summary and endpoint_summary.get("dhcp_reservation_ready") is False:
        skip_reasons.append("endpoint_evaluation_not_dhcp_ready")
    if len(actual_refs) != 1:
        skip_reasons.append("missing_actual_node" if not actual_refs else "ambiguous_actual_node")

    for candidate in mac_candidates:
        mac_address = _normalize_mac(candidate.get("mac_address"))
        if mac_address:
            normalized = {**candidate, "mac_address": mac_address}
            normalized_mac_candidates.append(normalized)

    if not mac_candidates:
        skip_reasons.append("missing_mac_address")
    elif not normalized_mac_candidates:
        skip_reasons.append("invalid_mac_address")
    elif len({candidate["mac_address"] for candidate in normalized_mac_candidates}) != 1:
        skip_reasons.append("ambiguous_interface")

    desired_node = getattr(endpoint, "desired_node", None)
    dns_name = _text(getattr(endpoint, "dns_name", None))
    ip_address = _host_address(_text(getattr(endpoint, "ip_address", None)))
    mac_address = normalized_mac_candidates[0]["mac_address"] if normalized_mac_candidates else ""
    actual_ref = actual_refs[0] if len(actual_refs) == 1 else {}
    line = f"dhcp-host={mac_address},{dns_name},{ip_address}" if not skip_reasons else ""
    return {
        "actual_ref": actual_ref,
        "confidence": "deterministic" if not skip_reasons else "none",
        "desired_endpoint": _text(getattr(endpoint, "name", None)),
        "desired_endpoint_id": _pk(endpoint),
        "desired_node": _text(getattr(desired_node, "name", None)),
        "desired_node_id": _pk(desired_node),
        "desired_node_slug": _text(getattr(desired_node, "slug", None)),
        "dns_name": dns_name,
        "endpoint_type": _text(getattr(endpoint, "endpoint_type", None)),
        "ip_address": ip_address,
        "ip_policy": _text(getattr(endpoint, "ip_policy", None)),
        "line": line,
        "mac_address": mac_address,
        "skip_reasons": sorted(set(skip_reasons)),
    }


def render_dnsmasq_records_conf(
    export: DnsmasqExport,
    *,
    generated_at: str,
    job_result_id: str | None = None,
) -> str:
    """Return dnsmasq configuration text for a generated export."""

    lines = [
        "# Generated by Nautobot Intent Catalog",
        f"# schema_version: {DNSMASQ_EXPORT_SCHEMA_VERSION}",
        f"# generated_at: {generated_at}",
    ]
    if job_result_id:
        lines.append(f"# job_result_id: {job_result_id}")
    lines.extend(record["line"] for record in export.dns_records)
    lines.extend(reservation["line"] for reservation in export.dhcp_reservations)
    return "\n".join(lines) + "\n"


def dnsmasq_export_payload(
    export: DnsmasqExport,
    *,
    generated_at: str,
    job_result_id: str | None = None,
) -> dict[str, Any]:
    """Return a stable, machine-readable dnsmasq export payload."""

    return {
        "schema_version": DNSMASQ_EXPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "job_result_id": job_result_id,
        "summary": export.summary,
        "dns_records": export.dns_records,
        "dhcp_reservations": export.dhcp_reservations,
        "skipped": export.skipped,
    }


def render_dnsmasq_export_json(
    export: DnsmasqExport,
    *,
    generated_at: str,
    job_result_id: str | None = None,
) -> str:
    """Return a deterministic JSON representation of a generated export."""

    return json.dumps(
        dnsmasq_export_payload(export, generated_at=generated_at, job_result_id=job_result_id),
        sort_keys=True,
        ensure_ascii=True,
        indent=2,
    ) + "\n"


def _dns_skip_reasons(endpoint: Any) -> list[str]:
    reasons = _base_skip_reasons(endpoint)
    record_type = _text(getattr(endpoint, "dnsmasq_record_type", None))
    if record_type not in SUPPORTED_RECORD_TYPES:
        reasons.append("dnsmasq_record_type_not_supported")
    if record_type == "cname" and not _text(getattr(endpoint, "vpn_dns_name", None)):
        reasons.append("missing_cname_alias")
    return reasons


def _dhcp_skip_reasons(endpoint: Any) -> list[str]:
    reasons = _base_skip_reasons(endpoint)
    if _text(getattr(endpoint, "ip_policy", None)) != "dhcp_reserved":
        reasons.append("ip_policy_not_dhcp_reserved")
    return reasons


def _base_skip_reasons(endpoint: Any) -> list[str]:
    reasons = []
    desired_node = getattr(endpoint, "desired_node", None)
    lifecycle = _text(getattr(desired_node, "lifecycle", None))
    endpoint_type = _text(getattr(endpoint, "endpoint_type", None))

    if not bool(getattr(endpoint, "generate_dnsmasq", False)):
        reasons.append("generate_dnsmasq_false")
    if not _text(getattr(endpoint, "ip_address", None)):
        reasons.append("missing_ip_address")
    if not _text(getattr(endpoint, "dns_name", None)):
        reasons.append("missing_dns_name")
    if lifecycle not in ELIGIBLE_NODE_LIFECYCLES:
        reasons.append("node_lifecycle_not_exportable")
    if endpoint_type not in ELIGIBLE_ENDPOINT_TYPES:
        reasons.append("endpoint_type_not_exportable")
    return reasons


def _dns_record_entry(endpoint: Any) -> dict[str, Any]:
    record_type = _text(getattr(endpoint, "dnsmasq_record_type", None))
    dns_name = _text(getattr(endpoint, "dns_name", None))
    ip_address = _host_address(_text(getattr(endpoint, "ip_address", None)))
    desired_node = getattr(endpoint, "desired_node", None)
    vpn_dns_name = _text(getattr(endpoint, "vpn_dns_name", None))

    if record_type == "address":
        line = f"address=/{dns_name}/{ip_address}"
        record_name = dns_name
        record_value = ip_address
    elif record_type == "cname":
        line = f"cname={vpn_dns_name},{dns_name}"
        record_name = vpn_dns_name
        record_value = dns_name
    else:
        record_type = "host_record"
        line = f"host-record={dns_name},{ip_address}"
        record_name = dns_name
        record_value = ip_address

    return {
        "desired_endpoint_id": _pk(endpoint),
        "desired_node": _text(getattr(desired_node, "name", None)),
        "desired_node_id": _pk(desired_node),
        "desired_node_slug": _text(getattr(desired_node, "slug", None)),
        "dns_name": dns_name,
        "endpoint_name": _text(getattr(endpoint, "name", None)),
        "endpoint_type": _text(getattr(endpoint, "endpoint_type", None)),
        "ip_address": ip_address,
        "ip_policy": _text(getattr(endpoint, "ip_policy", None)),
        "line": line,
        "mdns_name": _text(getattr(endpoint, "mdns_name", None)),
        "record_name": record_name,
        "record_type": record_type,
        "record_value": record_value,
        "vpn_dns_name": vpn_dns_name,
    }


def _skip_entry(endpoint: Any, item_type: str, reasons: list[str]) -> dict[str, Any]:
    desired_node = getattr(endpoint, "desired_node", None)
    return {
        "desired_endpoint_id": _pk(endpoint),
        "desired_node": _text(getattr(desired_node, "name", None)),
        "desired_node_id": _pk(desired_node),
        "desired_node_slug": _text(getattr(desired_node, "slug", None)),
        "dns_name": _text(getattr(endpoint, "dns_name", None)),
        "endpoint_name": _text(getattr(endpoint, "name", None)),
        "endpoint_type": _text(getattr(endpoint, "endpoint_type", None)),
        "ip_policy": _text(getattr(endpoint, "ip_policy", None)),
        "item_type": item_type,
        "reasons": sorted(set(reasons)),
    }


def _evaluation_for(obj: Any, evaluations: Mapping[str, Any] | None) -> Any | None:
    if obj is None or not evaluations:
        return None
    return evaluations.get(_pk(obj))


def _evaluation_data(evaluation: Any | None) -> dict[str, Any]:
    if evaluation is None:
        return {}
    if hasattr(evaluation, "as_defaults"):
        data = evaluation.as_defaults()
        return {
            **data,
            "actual_refs": data.get("actual_refs") or [],
            "deterministic_summary": data.get("deterministic_summary") or {},
            "observed_facts": data.get("observed_facts") or {},
        }
    if isinstance(evaluation, dict):
        return evaluation
    return {
        "actual_refs": getattr(evaluation, "actual_refs", None) or [],
        "deterministic_summary": getattr(evaluation, "deterministic_summary", None) or {},
        "observed_facts": getattr(evaluation, "observed_facts", None) or {},
    }


def _unique_actual_refs(mac_candidates: list[dict[str, Any]], node_actual_refs: list[Any]) -> list[dict[str, Any]]:
    refs = []
    for candidate in mac_candidates:
        ref = candidate.get("actual_node_ref")
        if isinstance(ref, dict):
            refs.append(ref)
    for ref in node_actual_refs:
        if isinstance(ref, dict):
            refs.append(ref)

    unique = {}
    for ref in refs:
        key = (_text(ref.get("object_type")), _text(ref.get("id")), _text(ref.get("name")))
        unique[key] = {
            "object_type": key[0],
            "id": key[1],
            "name": key[2],
        }
    return [unique[key] for key in sorted(unique)]


def _host_address(value: str) -> str:
    try:
        return str(ip_interface(value).ip)
    except ValueError:
        return value.split("/", maxsplit=1)[0]


def _normalize_mac(value: Any) -> str:
    text = re.sub(r"[^0-9A-Fa-f]", "", _text(value))
    if len(text) != 12:
        return ""
    return ":".join(text[index : index + 2].lower() for index in range(0, 12, 2))


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _pk(obj: Any) -> str:
    if obj is None:
        return ""
    return str(getattr(obj, "pk", None) or getattr(obj, "id", None) or "")


def _dns_record_sort_key(record: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        record["record_name"],
        record["desired_node_slug"],
        record["endpoint_type"],
        record["endpoint_name"],
    )


def _dhcp_reservation_sort_key(reservation: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        reservation["dns_name"],
        reservation["desired_node_slug"],
        reservation["endpoint_type"],
        reservation["desired_endpoint"],
    )


def _skip_sort_key(entry: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        entry["item_type"],
        entry["dns_name"],
        entry["desired_node_slug"],
        entry["endpoint_type"],
        entry["endpoint_name"],
    )
