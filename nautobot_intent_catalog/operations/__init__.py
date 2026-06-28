"""Use-case operations for Intent Catalog workflows."""

from .hosts import DesiredHostCreationResult, create_desired_node_with_primary_endpoint
from .ipam import IPAMReconcilePlan, ip_address_create_fields, plan_endpoint_ipam_reconcile
from .placements import DesiredServicePlacementCreationResult, create_desired_service_placement

__all__ = (
    "DesiredHostCreationResult",
    "DesiredServicePlacementCreationResult",
    "IPAMReconcilePlan",
    "create_desired_node_with_primary_endpoint",
    "create_desired_service_placement",
    "ip_address_create_fields",
    "plan_endpoint_ipam_reconcile",
)
