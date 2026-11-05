"""Case allocation: an explainable ranking, not a black box.

score = 3*language match + 2*skill match + 1*same district - 0.5*open cases
Officers with a conflict flag are never chosen. A supervisor can override.
"""
from django.db.models import Count, Q

from core.models import Case, Officer

LANGUAGE_NAMES = {"lg": "Luganda", "rn": "Runyankore", "sw": "Swahili", "en": "English"}
SKILL_FOR_CATEGORY = {
    "self_harm": "child_protection", "threats": "child_protection", "grooming": "child_protection",
    "exposure_by_authority": "child_protection",
    "sextortion": "cyber", "impersonation": "cyber", "scam": "cyber", "cyberbullying": "cyber",
    "gambling_or_betting": "counselling", "inappropriate_content": "counselling",
}
SKILL_NAMES = {"child_protection": "child-protection", "cyber": "cyber", "counselling": "counselling"}
CLOSED = [Case.Status.CLOSED, Case.Status.CLOSED_UNFOUNDED, Case.Status.CLOSED_CHILD_STOP]


def _ranked(case, exclude=()):
    skill = SKILL_FOR_CATEGORY.get(case.category)
    officers = (Officer.objects.filter(conflict_flag=False).exclude(pk__in=[o.pk for o in exclude if o])
                .select_related("user")
                .annotate(open_cases=Count("case", filter=~Q(case__status__in=CLOSED) & ~Q(case__pk=case.pk))))
    ranked = []
    for o in officers:
        lang = bool(case.language) and case.language in o.languages
        has_skill = bool(skill) and skill in o.skills
        same_district = bool(case.district) and case.district == o.district
        score = 3 * lang + 2 * has_skill + 1 * same_district - 0.5 * o.open_cases
        reasons = []
        if lang:
            reasons.append(f"speaks {LANGUAGE_NAMES.get(case.language, case.language)}")
        if has_skill:
            reasons.append(f"{SKILL_NAMES[skill]} skill")
        if same_district:
            reasons.append("same district")
        reasons.append(f"{o.open_cases} open case{'s' if o.open_cases != 1 else ''}")
        ranked.append((score, -o.open_cases, -o.pk, o, reasons))
    ranked.sort(key=lambda r: r[:3], reverse=True)
    return ranked


def allocate(case, exclude=(), prefix="Assigned to"):
    ranked = _ranked(case, exclude)
    if not ranked:
        return None
    _, _, _, officer, reasons = ranked[0]
    case.assigned_officer = officer
    case.assignment_reason = f"{prefix} {officer.user.get_username()}: " + ", ".join(reasons)
    fields = ["assigned_officer", "assignment_reason"]
    if case.status in (Case.Status.RECEIVED, Case.Status.TRIAGED):
        case.status = Case.Status.ASSIGNED
        fields.append("status")
    case.save(update_fields=fields)
    return officer


def reassign_next(case, why):
    return allocate(case, exclude=[case.assigned_officer], prefix=f"Reassigned ({why}) to")


def assign_by_supervisor(case, officer, supervisor_name):
    case.assigned_officer = officer
    case.assignment_reason = f"Reassigned by {supervisor_name} to {officer.user.get_username()}"
    case.save(update_fields=["assigned_officer", "assignment_reason"])
