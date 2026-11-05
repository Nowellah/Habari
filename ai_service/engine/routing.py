"""Which referral routes may be offered for a given assessment.

These are route keys, not contacts. The case system maps each key to a real
partner. The family_or_school route is removed whenever the person involved
is a parent, teacher or guardian.
"""
from .schemas import Routing, Severity, TriageResult

_ROUTES_BY_SEVERITY = {
    Severity.S1: ("information", "helpline"),
    Severity.S2: ("information", "helpline", "platform_report", "family_or_school"),
    Severity.S3: (
        "information",
        "helpline",
        "platform_report",
        "family_or_school",
        "child_protection_partner",
        "police",
    ),
    Severity.S4: ("helpline", "child_protection_partner", "police", "emergency_services"),
}


def build_routing(result: TriageResult) -> Routing:
    routes = list(_ROUTES_BY_SEVERITY[result.severity])
    if result.external_only:
        routes = [route for route in routes if route != "family_or_school"]
    return Routing(
        external_only=result.external_only,
        allowed_routes=routes,
        human_decision_required=result.severity == Severity.S4,
    )
