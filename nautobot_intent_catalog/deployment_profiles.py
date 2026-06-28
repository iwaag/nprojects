"""Read-only access to the synced deployment_profiles projection.

The authoritative owner of ``deployment_profiles`` is the Ansible side; this
module only reads the advisory projection that the sync Job writes through the
same export-input contract.  The validation-bearing helpers here are pure so
they can be unit tested without a Nautobot runtime, while
:func:`load_deployment_profiles` binds them to the projection model.
"""

from __future__ import annotations

from typing import Any

from .production_inventory_contract import parse_profile_job_input, validate_deployment_profiles

try:  # pragma: no cover - Nautobot/Django are unavailable in local unit tests.
    from .models import DeploymentProfileProjection
except ImportError:
    DeploymentProfileProjection = None  # type: ignore[assignment]


class DeploymentProfilesUnavailable(RuntimeError):
    """Raised when no deployment_profiles projection has been synced yet.

    Callers (forms, operations) treat this as the explicit "not synced" state:
    profile choices and config schemas cannot be offered, and the operator
    should run the deployment_profiles sync Job with the same input as export.
    """


def project_deployment_profiles(payload: str, digest: str) -> dict[str, Any]:
    """Validate export-contract input and return the validated profile map.

    This is the exact ingestion contract used by export; the sync Job and its
    tests share it so the projection can never diverge from export validation.
    """

    return parse_profile_job_input(payload, digest)


def select_projection_profiles(projection: Any) -> dict[str, Any]:
    """Return the validated map from a projection row, revalidating on read.

    ``projection`` is the stored row (or ``None`` when nothing has been synced).
    Re-running :func:`validate_deployment_profiles` keeps the read path honest
    even though the data was validated at sync time.
    """

    if projection is None:
        raise DeploymentProfilesUnavailable(
            "No deployment_profiles have been synced; run the deployment_profiles "
            "sync Job with the same input passed to production inventory export."
        )
    return validate_deployment_profiles(projection.profiles)


def load_deployment_profiles() -> dict[str, Any]:
    """Return the validated deployment_profiles map from the projection store.

    Raises :class:`DeploymentProfilesUnavailable` when nothing is synced yet.
    """

    if DeploymentProfileProjection is None:
        raise RuntimeError("Nautobot is required to load the deployment_profiles projection.")
    projection = DeploymentProfileProjection.objects.order_by("-synced_at").first()
    return select_projection_profiles(projection)
