"""Deterministic desired-vs-actual evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from ipaddress import ip_interface
import json
import re
from typing import Any, Iterable


NODE_TARGET_TYPE = "desired_node"
ENDPOINT_TARGET_TYPE = "desired_endpoint"
SERVICE_TARGET_TYPE = "desired_service"


@dataclass(frozen=True)
class EvaluationPayload:
    """Serializable fields for an IntentEvaluation row."""

    target_type: str
    target_id: str
    status: str
    deterministic_summary: dict[str, Any]
    actual_refs: list[dict[str, Any]]
    observed_facts: dict[str, Any]
    expected_facts: dict[str, Any]
    gap_summary: dict[str, Any]
    recommended_actions: list[dict[str, Any]]
    source_hash: str

    def as_defaults(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "deterministic_summary": self.deterministic_summary,
            "actual_refs": self.actual_refs,
            "observed_facts": self.observed_facts,
            "expected_facts": self.expected_facts,
            "gap_summary": self.gap_summary,
            "recommended_actions": self.recommended_actions,
        }


def evaluate_node_intent(
    desired_node: Any,
    *,
    device_candidates: Iterable[Any] = (),
    vm_candidates: Iterable[Any] = (),
) -> EvaluationPayload:
    """Compare a DesiredNode-like object with actual Device/VM-like candidates."""

    expected = _expected_node_facts(desired_node)
    realized = _realized_node_objects(desired_node)
    actual_refs: list[dict[str, Any]] = []
    observed: dict[str, Any] = {"candidates": []}
    gaps: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    if len(realized) > 1:
        actual_refs = [_actual_ref(object_type, obj) for object_type, obj in realized]
        observed["actual"] = [_actual_node_facts(object_type, obj) for object_type, obj in realized]
        gaps.append({"code": "multiple_realized_links", "severity": "conflict"})
        status = "conflict"
    elif len(realized) == 1:
        object_type, actual = realized[0]
        actual_refs = [_actual_ref(object_type, actual)]
        actual_facts = _actual_node_facts(object_type, actual)
        observed["actual"] = actual_facts
        gaps.extend(_node_mismatches(expected, actual_facts))
        status = "conflict" if gaps else "satisfied"
    else:
        candidates = _rank_node_candidates(
            desired_node,
            device_candidates=device_candidates,
            vm_candidates=vm_candidates,
        )
        observed["candidates"] = [candidate for candidate in candidates if candidate["score"] > 0]
        strong = [candidate for candidate in observed["candidates"] if candidate["score"] >= 40]
        if not strong:
            gaps.append({"code": "missing_actual_node", "severity": "missing"})
            actions.append(
                {
                    "action": "link_desired_node_to_actual",
                    "target": _target_ref(desired_node),
                    "reason": "No deterministic Device or VirtualMachine candidate was found.",
                    "requires_review": True,
                }
            )
            status = "missing"
        elif len(strong) == 1 or strong[0]["score"] > strong[1]["score"]:
            selected = strong[0]
            actual_refs = [selected["actual_ref"]]
            observed["actual"] = selected["facts"]
            gaps.append({"code": "actual_node_not_linked", "severity": "partial"})
            actions.append(
                {
                    "action": "link_desired_node_to_actual",
                    "target": _target_ref(desired_node),
                    "actual_ref": selected["actual_ref"],
                    "reason": "A single deterministic actual node candidate was found but is not explicitly linked.",
                    "requires_review": True,
                }
            )
            status = "partial"
        else:
            gaps.append({"code": "ambiguous_actual_node_candidates", "severity": "conflict"})
            actions.append(
                {
                    "action": "link_desired_node_to_actual",
                    "target": _target_ref(desired_node),
                    "candidates": [candidate["actual_ref"] for candidate in strong],
                    "reason": "Multiple actual node candidates matched with the same confidence.",
                    "requires_review": True,
                }
            )
            status = "conflict"

    summary = {
        "target": _target_ref(desired_node),
        "status": status,
        "gap_codes": [gap["code"] for gap in gaps],
        "actual_ref_count": len(actual_refs),
        "candidate_count": len(observed.get("candidates") or []),
        "evaluation_scope": "node_identity_and_primary_facts",
    }
    return _payload(
        target_type=NODE_TARGET_TYPE,
        target_id=_pk(desired_node),
        status=status,
        deterministic_summary=summary,
        actual_refs=actual_refs,
        observed_facts=observed,
        expected_facts=expected,
        gap_summary={"gaps": gaps},
        recommended_actions=actions,
    )


def evaluate_endpoint_intent(
    desired_endpoint: Any,
    *,
    ip_candidates: Iterable[Any] = (),
    node_evaluation: EvaluationPayload | dict[str, Any] | None = None,
) -> EvaluationPayload:
    """Compare a DesiredEndpoint-like object with actual IP and interface facts."""

    expected = _expected_endpoint_facts(desired_endpoint)
    realized_ip = getattr(desired_endpoint, "realized_ip_address", None)
    actual_refs: list[dict[str, Any]] = []
    observed: dict[str, Any] = {}
    gaps: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    if realized_ip is not None:
        actual_refs.append(_actual_ref("ipam.ipaddress", realized_ip))
        observed["actual_ip_address"] = _actual_ip_facts(realized_ip)
        expected_host = _host_address(expected.get("ip_address"))
        actual_host = _host_address(observed["actual_ip_address"].get("address"))
        if expected_host and actual_host and expected_host != actual_host:
            gaps.append(
                {
                    "code": "ip_address_mismatch",
                    "severity": "conflict",
                    "expected": expected_host,
                    "actual": actual_host,
                }
            )
    else:
        matches = _matching_ip_candidates(expected.get("ip_address"), ip_candidates)
        observed["ip_candidates"] = matches
        if expected.get("ip_address") and not matches:
            gaps.append({"code": "missing_actual_ip_address", "severity": "partial"})
            actions.append(
                {
                    "action": "create_or_link_ip_address",
                    "target": _target_ref(desired_endpoint),
                    "reason": "No actual IPAddress candidate matches the desired endpoint address.",
                    "requires_review": True,
                }
            )
        elif len(matches) == 1:
            actual_refs.append(matches[0]["actual_ref"])
            gaps.append({"code": "actual_ip_address_not_linked", "severity": "partial"})
            actions.append(
                {
                    "action": "create_or_link_ip_address",
                    "target": _target_ref(desired_endpoint),
                    "actual_ref": matches[0]["actual_ref"],
                    "reason": "A matching IPAddress exists but the desired endpoint is not explicitly linked.",
                    "requires_review": True,
                }
            )
        elif len(matches) > 1:
            gaps.append({"code": "ambiguous_ip_address_candidates", "severity": "conflict"})

    interface_candidates = _interface_candidates_for_endpoint(desired_endpoint, node_evaluation)
    observed["interface_candidates"] = interface_candidates
    mac_candidates = [candidate for candidate in interface_candidates if candidate.get("mac_address")]
    observed["dhcp_mac_candidates"] = mac_candidates
    if _wants_dhcp_material(desired_endpoint):
        if not interface_candidates:
            gaps.append({"code": "missing_interface_candidate", "severity": "partial"})
        elif not mac_candidates:
            gaps.append({"code": "missing_mac_address", "severity": "partial"})
        elif len(mac_candidates) > 1:
            gaps.append({"code": "ambiguous_interface", "severity": "partial"})
            actions.append(
                {
                    "action": "select_dhcp_interface",
                    "target": _target_ref(desired_endpoint),
                    "candidates": mac_candidates,
                    "reason": "Multiple MAC-address-bearing interfaces could satisfy this endpoint.",
                    "requires_review": True,
                }
            )

    if any(gap["severity"] == "conflict" for gap in gaps):
        status = "conflict"
    elif gaps:
        status = "partial"
    else:
        status = "satisfied"

    dhcp_blocking_gap_codes = {"ambiguous_interface", "missing_mac_address", "missing_interface_candidate"}
    dhcp_reservation_ready = (
        len(mac_candidates) == 1
        and not any(gap["code"] in dhcp_blocking_gap_codes for gap in gaps)
        and not any(gap["severity"] == "conflict" for gap in gaps)
    )
    summary = {
        "target": _target_ref(desired_endpoint),
        "status": status,
        "gap_codes": [gap["code"] for gap in gaps],
        "actual_ref_count": len(actual_refs),
        "dhcp_mac_candidate_count": len(mac_candidates),
        "dhcp_reservation_ready": dhcp_reservation_ready,
        "evaluation_scope": "endpoint_ip_and_dhcp_mac_candidates",
    }
    return _payload(
        target_type=ENDPOINT_TARGET_TYPE,
        target_id=_pk(desired_endpoint),
        status=status,
        deterministic_summary=summary,
        actual_refs=actual_refs,
        observed_facts=observed,
        expected_facts=expected,
        gap_summary={"gaps": gaps},
        recommended_actions=actions,
    )


def evaluate_service_intent(
    desired_service: Any,
    *,
    dependencies: Iterable[Any] | None = None,
    observed_facts: dict[str, Any] | None = None,
    ai_review_enabled: bool = False,
) -> EvaluationPayload:
    """Evaluate a DesiredService-like object without invoking AI review."""

    dependency_rows = _service_dependencies(desired_service, dependencies)
    expected = _expected_service_facts(desired_service, dependency_rows)
    observed = {
        "service_observation_status": "provided" if observed_facts is not None else "unknown",
        "service_facts": _mapping(observed_facts),
        "ai_review": {
            "enabled": bool(ai_review_enabled),
            "executed": False,
        },
    }
    actual_refs: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    lifecycle = expected.get("lifecycle")
    if lifecycle in {"deprecated", "retired"}:
        gaps.append(
            {
                "code": "service_lifecycle_inactive",
                "severity": "needs_review",
                "lifecycle": lifecycle,
            }
        )
        actions.append(
            {
                "action": "review_service_lifecycle",
                "target": _target_ref(desired_service),
                "reason": "The desired service lifecycle is inactive.",
                "requires_review": True,
            }
        )
    elif lifecycle in {"", "unknown"}:
        gaps.append({"code": "missing_service_lifecycle", "severity": "unknown"})

    for dependency in expected["dependencies"]:
        if dependency["resolution_status"] != "unresolved":
            continue
        gaps.append(
            {
                "code": "unresolved_dependency",
                "severity": "partial",
                "dependency": dependency,
            }
        )
        actions.append(
            {
                "action": "resolve_service_dependency",
                "target": _target_ref(desired_service),
                "dependency": dependency,
                "reason": "A desired service dependency is unresolved.",
                "requires_review": True,
            }
        )

    if observed_facts is None:
        gaps.append({"code": "service_observed_facts_unknown", "severity": "unknown"})

    status = _status_from_gaps(gaps)
    summary = {
        "target": _target_ref(desired_service),
        "status": status,
        "gap_codes": [gap["code"] for gap in gaps],
        "dependency_counts": expected["dependency_counts"],
        "requirements_present": bool(expected["requirements"]),
        "service_observation_status": observed["service_observation_status"],
        "ai_review_ready": True,
        "ai_review_executed": False,
        "evaluation_scope": "service_lifecycle_requirements_dependencies",
    }
    return _payload(
        target_type=SERVICE_TARGET_TYPE,
        target_id=_pk(desired_service),
        status=status,
        deterministic_summary=summary,
        actual_refs=actual_refs,
        observed_facts=observed,
        expected_facts=expected,
        gap_summary={"gaps": gaps},
        recommended_actions=actions,
    )


def _payload(
    *,
    target_type: str,
    target_id: str,
    status: str,
    deterministic_summary: dict[str, Any],
    actual_refs: list[dict[str, Any]],
    observed_facts: dict[str, Any],
    expected_facts: dict[str, Any],
    gap_summary: dict[str, Any],
    recommended_actions: list[dict[str, Any]],
) -> EvaluationPayload:
    source = {
        "target_type": target_type,
        "target_id": target_id,
        "actual_refs": actual_refs,
        "expected_facts": expected_facts,
        "observed_facts": observed_facts,
        "gap_summary": gap_summary,
    }
    return EvaluationPayload(
        target_type=target_type,
        target_id=target_id,
        status=status,
        deterministic_summary=deterministic_summary,
        actual_refs=actual_refs,
        observed_facts=observed_facts,
        expected_facts=expected_facts,
        gap_summary=gap_summary,
        recommended_actions=recommended_actions,
        source_hash=_stable_hash(source),
    )


def _expected_node_facts(desired_node: Any) -> dict[str, Any]:
    expected_spec = _mapping(getattr(desired_node, "expected_spec", None))
    return {
        "name": _text(getattr(desired_node, "name", None)),
        "slug": _text(getattr(desired_node, "slug", None)),
        "node_type": _text(getattr(desired_node, "node_type", None)),
        "lifecycle": _text(getattr(desired_node, "lifecycle", None)),
        "role": _text(getattr(desired_node, "role", None)),
        "expected_spec": expected_spec,
        "hostname": _first_text(expected_spec.get("hostname"), expected_spec.get("host_name")),
        "serial": _first_text(expected_spec.get("serial"), expected_spec.get("serial_number")),
        "uuid": _first_text(expected_spec.get("uuid"), expected_spec.get("node_uuid")),
        "platform": _first_text(expected_spec.get("platform"), expected_spec.get("os")),
    }


def _expected_endpoint_facts(desired_endpoint: Any) -> dict[str, Any]:
    return {
        "name": _text(getattr(desired_endpoint, "name", None)),
        "endpoint_type": _text(getattr(desired_endpoint, "endpoint_type", None)),
        "ip_address": _text(getattr(desired_endpoint, "ip_address", None)),
        "dns_name": _text(getattr(desired_endpoint, "dns_name", None)),
        "generate_dnsmasq": bool(getattr(desired_endpoint, "generate_dnsmasq", False)),
        "dnsmasq_record_type": _text(getattr(desired_endpoint, "dnsmasq_record_type", None)),
    }


def _expected_service_facts(desired_service: Any, dependencies: list[Any]) -> dict[str, Any]:
    dependency_facts = [_dependency_facts(dependency) for dependency in dependencies]
    counts = {
        "total": len(dependency_facts),
        "resolved": 0,
        "unresolved": 0,
        "external": 0,
        "ignored": 0,
        "other": 0,
    }
    for dependency in dependency_facts:
        status = dependency["resolution_status"]
        counts[status if status in counts else "other"] += 1
    return {
        "name": _text(getattr(desired_service, "name", None)),
        "slug": _text(getattr(desired_service, "slug", None)),
        "display_name": _text(getattr(desired_service, "display_name", None)),
        "service_type": _text(getattr(desired_service, "service_type", None)),
        "lifecycle": _text(getattr(desired_service, "lifecycle", None)),
        "catalog_namespace": _text(getattr(desired_service, "catalog_namespace", None)),
        "catalog_metadata_name": _text(getattr(desired_service, "catalog_metadata_name", None)),
        "catalog_owner": _text(getattr(desired_service, "catalog_owner", None)),
        "requirements": _mapping(getattr(desired_service, "requirements", None)),
        "placement_policy": _mapping(getattr(desired_service, "placement_policy", None)),
        "dependencies": dependency_facts,
        "dependency_counts": counts,
    }


def _realized_node_objects(desired_node: Any) -> list[tuple[str, Any]]:
    realized = []
    realized_device = getattr(desired_node, "realized_device", None)
    realized_vm = getattr(desired_node, "realized_vm", None)
    if realized_device is not None:
        realized.append(("dcim.device", realized_device))
    if realized_vm is not None:
        realized.append(("virtualization.virtualmachine", realized_vm))
    return realized


def _rank_node_candidates(
    desired_node: Any,
    *,
    device_candidates: Iterable[Any],
    vm_candidates: Iterable[Any],
) -> list[dict[str, Any]]:
    expected = _expected_node_facts(desired_node)
    candidates = []
    for object_type, actual in [
        *[("dcim.device", device) for device in device_candidates],
        *[("virtualization.virtualmachine", vm) for vm in vm_candidates],
    ]:
        facts = _actual_node_facts(object_type, actual)
        score, reasons = _node_candidate_score(expected, facts)
        candidates.append(
            {
                "actual_ref": _actual_ref(object_type, actual),
                "facts": facts,
                "match_reasons": reasons,
                "score": score,
            }
        )
    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["actual_ref"]["object_type"], candidate["actual_ref"]["name"]))
    return candidates


def _node_candidate_score(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons = []
    expected_names = {_norm(expected.get("name")), _norm(expected.get("slug")), _norm(expected.get("hostname"))}
    actual_names = {
        _norm(actual.get("name")),
        _norm(actual.get("hostname")),
        _norm(actual.get("custom_fields", {}).get("hostname")),
        _norm(actual.get("custom_fields", {}).get("nodeutils_hostname")),
    }
    expected_names.discard("")
    actual_names.discard("")
    if expected_names.intersection(actual_names):
        score += 50
        reasons.append("name_or_hostname")
    for key, weight in (("serial", 80), ("uuid", 80), ("platform", 10)):
        if _norm(expected.get(key)) and _norm(expected.get(key)) == _norm(actual.get(key)):
            score += weight
            reasons.append(key)
    return score, reasons


def _node_mismatches(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    gaps = []
    for key in ("serial", "uuid", "platform"):
        expected_value = _text(expected.get(key))
        actual_value = _text(actual.get(key))
        if expected_value and actual_value and _norm(expected_value) != _norm(actual_value):
            gaps.append(
                {
                    "code": f"{key}_mismatch",
                    "severity": "conflict",
                    "expected": expected_value,
                    "actual": actual_value,
                }
            )
    expected_hostname = _text(expected.get("hostname"))
    actual_hostname = _first_text(actual.get("hostname"), actual.get("name"))
    if expected_hostname and actual_hostname and _norm(expected_hostname) != _norm(actual_hostname):
        gaps.append(
            {
                "code": "hostname_mismatch",
                "severity": "conflict",
                "expected": expected_hostname,
                "actual": actual_hostname,
            }
        )
    return gaps


def _actual_node_facts(object_type: str, actual: Any) -> dict[str, Any]:
    custom_fields = _custom_fields(actual)
    platform = _display_value(getattr(actual, "platform", None))
    return {
        "object_type": object_type,
        "id": _pk(actual),
        "name": _text(getattr(actual, "name", None)),
        "hostname": _first_text(
            getattr(actual, "hostname", None),
            custom_fields.get("hostname"),
            custom_fields.get("nodeutils_hostname"),
        ),
        "serial": _first_text(getattr(actual, "serial", None), custom_fields.get("serial"), custom_fields.get("serial_number")),
        "uuid": _first_text(getattr(actual, "uuid", None), custom_fields.get("uuid"), custom_fields.get("node_uuid")),
        "platform": _first_text(platform, custom_fields.get("platform"), custom_fields.get("os")),
        "custom_fields": custom_fields,
        "interfaces": [_interface_facts(object_type, actual, interface) for interface in _interfaces(actual)],
        "interface_count": len(_interfaces(actual)),
    }


def _actual_ip_facts(actual_ip: Any) -> dict[str, Any]:
    return {
        "object_type": "ipam.ipaddress",
        "id": _pk(actual_ip),
        "address": _text(getattr(actual_ip, "address", None)),
        "dns_name": _text(getattr(actual_ip, "dns_name", None)),
    }


def _dependency_facts(dependency: Any) -> dict[str, Any]:
    resolved_service = getattr(dependency, "resolved_service", None)
    facts = {
        "dependency_kind": _text(getattr(dependency, "dependency_kind", None)),
        "namespace": _text(getattr(dependency, "namespace", None)),
        "name": _text(getattr(dependency, "name", None)),
        "raw_ref": _text(getattr(dependency, "raw_ref", None)),
        "dependency_type": _text(getattr(dependency, "dependency_type", None)),
        "resolution_status": _text(getattr(dependency, "resolution_status", None)) or "unresolved",
    }
    if resolved_service is not None:
        facts["resolved_service"] = _target_ref(resolved_service)
    return facts


def _matching_ip_candidates(ip_address: Any, ip_candidates: Iterable[Any]) -> list[dict[str, Any]]:
    expected = _host_address(ip_address)
    if not expected:
        return []
    matches = []
    for actual in ip_candidates:
        actual_host = _host_address(getattr(actual, "address", None))
        if expected == actual_host:
            matches.append({"actual_ref": _actual_ref("ipam.ipaddress", actual), "facts": _actual_ip_facts(actual)})
    matches.sort(key=lambda match: match["actual_ref"]["name"])
    return matches


def _interface_candidates_for_endpoint(
    desired_endpoint: Any,
    node_evaluation: EvaluationPayload | dict[str, Any] | None,
) -> list[dict[str, Any]]:
    desired_node = getattr(desired_endpoint, "desired_node", None)
    actual_objects = _realized_node_objects(desired_node) if desired_node is not None else []
    candidates = []
    for object_type, actual_node in actual_objects:
        for interface in _interfaces(actual_node):
            candidates.append(_interface_facts(object_type, actual_node, interface))

    if candidates:
        return sorted(candidates, key=_interface_sort_key)

    evaluation_data = node_evaluation.as_defaults() if isinstance(node_evaluation, EvaluationPayload) else node_evaluation
    if isinstance(evaluation_data, dict):
        observed = _mapping(evaluation_data.get("observed_facts"))
        actual = observed.get("actual")
        if isinstance(actual, dict):
            for interface in _list(actual.get("interfaces")):
                if isinstance(interface, dict):
                    candidates.append(interface)
    return sorted(candidates, key=_interface_sort_key)


def _interface_facts(object_type: str, actual_node: Any, interface: Any) -> dict[str, Any]:
    return {
        "actual_node_ref": _actual_ref(object_type, actual_node),
        "interface_id": _pk(interface),
        "interface_name": _text(getattr(interface, "name", None)),
        "mac_address": _normalize_mac(getattr(interface, "mac_address", None)),
        "enabled": bool(getattr(interface, "enabled", True)),
    }


def _wants_dhcp_material(desired_endpoint: Any) -> bool:
    return bool(getattr(desired_endpoint, "generate_dnsmasq", False)) and bool(_text(getattr(desired_endpoint, "ip_address", None)))


def _interfaces(actual_node: Any) -> list[Any]:
    interfaces = getattr(actual_node, "interfaces", None)
    if interfaces is None:
        interfaces = getattr(actual_node, "vm_interfaces", None)
    if interfaces is None:
        return []
    if hasattr(interfaces, "all"):
        return list(interfaces.all())
    return list(interfaces)


def _service_dependencies(desired_service: Any, dependencies: Iterable[Any] | None) -> list[Any]:
    if dependencies is not None:
        return list(dependencies)
    related = getattr(desired_service, "dependencies", None)
    if related is None:
        return []
    if hasattr(related, "all"):
        return list(related.all())
    return list(related)


def _status_from_gaps(gaps: list[dict[str, Any]]) -> str:
    severities = {gap.get("severity") for gap in gaps}
    if "conflict" in severities:
        return "conflict"
    if "missing" in severities:
        return "missing"
    if "partial" in severities:
        return "partial"
    if "needs_review" in severities:
        return "needs_review"
    if "unknown" in severities:
        return "unknown"
    return "satisfied"


def _actual_ref(object_type: str, obj: Any) -> dict[str, Any]:
    return {
        "object_type": object_type,
        "id": _pk(obj),
        "name": _text(getattr(obj, "name", None) or getattr(obj, "address", None)),
    }


def _target_ref(obj: Any) -> dict[str, Any]:
    return {
        "id": _pk(obj),
        "name": _text(getattr(obj, "name", None)),
    }


def _custom_fields(obj: Any) -> dict[str, Any]:
    for attr in ("custom_field_data", "_custom_field_data"):
        value = getattr(obj, attr, None)
        if isinstance(value, dict):
            return value
    return {}


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    for attr in ("name", "slug"):
        attr_value = getattr(value, attr, None)
        if attr_value:
            return str(attr_value)
    return str(value)


def _host_address(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        return str(ip_interface(text).ip)
    except ValueError:
        return text.split("/", maxsplit=1)[0]


def _normalize_mac(value: Any) -> str:
    text = re.sub(r"[^0-9A-Fa-f]", "", _text(value))
    if len(text) != 12:
        return ""
    return ":".join(text[index : index + 2].lower() for index in range(0, 12, 2))


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm(value: Any) -> str:
    return _text(value).lower()


def _pk(obj: Any) -> str:
    return str(getattr(obj, "pk", None) or getattr(obj, "id", None) or "")


def _interface_sort_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text(candidate.get("actual_node_ref", {}).get("name")),
        _text(candidate.get("interface_name")),
        _text(candidate.get("mac_address")),
    )
