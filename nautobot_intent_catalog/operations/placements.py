"""Service-placement use-case operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nautobot_intent_catalog.production_inventory_contract import (
    ContractError,
    map_placement_config,
    validate_deployment_profiles,
)

try:
    from django.core.exceptions import ValidationError
    from django.db import IntegrityError, transaction

    from nautobot_intent_catalog.models import DesiredServicePlacement
except ImportError:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    ValidationError = None  # type: ignore[assignment]
    IntegrityError = Exception  # type: ignore[assignment]
    transaction = None  # type: ignore[assignment]
    DesiredServicePlacement = None  # type: ignore[assignment]


# Map config-contract violation codes onto the form field that owns them so the
# UI and a future API surface the same field-keyed validation result.
_CONTRACT_ERROR_FIELDS = {
    "unknown_profile": "deployment_profile",
    "unsupported_config_schema": "config_schema_version",
}


@dataclass(frozen=True)
class DesiredServicePlacementCreationResult:
    """Object created by a quick service placement operation."""

    placement: Any


def create_desired_service_placement(
    *,
    desired_service: Any,
    desired_node: Any,
    deployment_profile: str,
    profiles: Any,
    instance_name: str | None = None,
    desired_endpoint: Any | None = None,
    desired_state: str = "active",
    instance_role: str | None = None,
    config: Any | None = None,
    reason: str | None = None,
) -> DesiredServicePlacementCreationResult:
    """Create one ``DesiredServicePlacement`` from operator-chosen inputs.

    ``config_schema_version`` is derived from the selected profile and
    ``assignment_source`` is fixed to ``manual``; neither is an operator input.
    The operation raises Django ``ValidationError`` with a field-keyed error
    dictionary so forms and future API views can present the same result.
    """

    _require_django()
    if desired_service is None:
        _raise_validation_error({"desired_service": ["This field is required."]})
    if desired_node is None:
        _raise_validation_error({"desired_node": ["This field is required."]})

    deployment_profile = _required_str(deployment_profile, "deployment_profile")
    desired_state = _required_str(desired_state, "desired_state")
    instance_role = _optional_str(instance_role)
    reason = _optional_str(reason)

    resolved_instance_name = _optional_str(instance_name) or _optional_str(
        getattr(desired_service, "slug", None)
    )
    if resolved_instance_name is None:
        _raise_validation_error(
            {"instance_name": ["Instance name is required and could not be derived from the service slug."]}
        )

    config_object = _config_object(config)
    config_schema_version = _profile_config_schema_version(deployment_profile, profiles)
    _validate_config(deployment_profile, config_schema_version, config_object, profiles)
    _validate_endpoint_ownership(desired_endpoint=desired_endpoint, desired_node=desired_node)
    _validate_instance_uniqueness(desired_service=desired_service, instance_name=resolved_instance_name)

    try:
        with transaction.atomic():
            placement = DesiredServicePlacement(
                desired_service=desired_service,
                desired_node=desired_node,
                desired_endpoint=desired_endpoint,
                instance_name=resolved_instance_name,
                desired_state=desired_state,
                instance_role=instance_role,
                deployment_profile=deployment_profile,
                config_schema_version=config_schema_version,
                config=config_object,
                assignment_source="manual",
                reason=reason,
            )
            placement.full_clean()
            placement.save()
    except IntegrityError as exc:
        _raise_validation_error(
            {"__all__": [f"Desired service placement could not be created because of a uniqueness conflict: {exc}"]}
        )

    return DesiredServicePlacementCreationResult(placement=placement)


def _profile_config_schema_version(deployment_profile: str, profiles: Any) -> str:
    try:
        validated_profiles = validate_deployment_profiles(dict(profiles))
    except (ContractError, TypeError, ValueError) as exc:
        _raise_validation_error({"deployment_profile": [f"Deployment profiles are unavailable: {exc}"]})
    if deployment_profile not in validated_profiles:
        _raise_validation_error(
            {"deployment_profile": [f"Unknown deployment profile {deployment_profile!r}."]}
        )
    return validated_profiles[deployment_profile]["config_schema_version"]


def _validate_config(
    deployment_profile: str,
    config_schema_version: str,
    config: dict[str, Any],
    profiles: Any,
) -> None:
    try:
        map_placement_config(deployment_profile, config_schema_version, config, profiles)
    except ContractError as exc:
        field = _CONTRACT_ERROR_FIELDS.get(exc.code, "config")
        _raise_validation_error({field: [str(exc)]})


def _validate_endpoint_ownership(*, desired_endpoint: Any, desired_node: Any) -> None:
    if desired_endpoint is None:
        return
    if getattr(desired_endpoint, "desired_node_id", None) != getattr(desired_node, "pk", None):
        _raise_validation_error(
            {"desired_endpoint": ["Selected endpoint must belong to the placement node."]}
        )


def _validate_instance_uniqueness(*, desired_service: Any, instance_name: str) -> None:
    if DesiredServicePlacement.objects.filter(
        desired_service=desired_service,
        instance_name=instance_name,
    ).exists():
        _raise_validation_error(
            {"instance_name": ["A placement with this instance name already exists for the service."]}
        )


def _config_object(config: Any | None) -> dict[str, Any]:
    if config is None:
        return {}
    if not isinstance(config, dict):
        _raise_validation_error({"config": ["Placement config must be a JSON object."]})
    return config


def _required_str(value: Any, field_name: str) -> str:
    normalized = str(value).strip() if value is not None else ""
    if not normalized:
        _raise_validation_error({field_name: ["This field is required."]})
    return normalized


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _require_django() -> None:
    if ValidationError is None or transaction is None or DesiredServicePlacement is None:
        raise RuntimeError("Django and Nautobot are required to run placement operations.")


def _raise_validation_error(errors: dict[str, list[str]]) -> None:
    if ValidationError is None:
        raise RuntimeError(errors)
    raise ValidationError(errors)
