"""Personnel role parsing — supports multiple roles per person."""

from __future__ import annotations

import json

DEALERSHIP_ROLES = ("Advisor", "Technician", "Warranty Admin", "Manager")
PLATFORM_ADMIN_ROLES = ("Admin",)
ALL_PERSONNEL_ROLES = DEALERSHIP_ROLES + PLATFORM_ADMIN_ROLES

ROLE_PRIORITY = ("Admin", "Manager", "Warranty Admin", "Advisor", "Technician")


def normalize_roles_list(roles) -> list[str]:
    """Accept a single role string or list; return deduped valid roles in priority order."""
    if roles is None:
        items: list[str] = []
    elif isinstance(roles, str):
        items = [roles.strip()]
    elif isinstance(roles, (list, tuple, set)):
        items = [str(r).strip() for r in roles if str(r).strip()]
    else:
        items = [str(roles).strip()]

    allowed = set(ALL_PERSONNEL_ROLES)
    picked = [r for r in items if r in allowed]
    if not picked:
        return []

    ordered: list[str] = []
    for role in ROLE_PRIORITY:
        if role in picked:
            ordered.append(role)
    for role in picked:
        if role not in ordered:
            ordered.append(role)
    return ordered


def parse_personnel_roles(record) -> list[str]:
    """Read roles from a personnel row (dict, Series, or mapping)."""
    if record is None:
        return []

    if hasattr(record, "to_dict"):
        record = record.to_dict()

    raw_roles = record.get("roles") if isinstance(record, dict) else None
    if isinstance(raw_roles, str) and raw_roles.strip():
        try:
            raw_roles = json.loads(raw_roles)
        except json.JSONDecodeError:
            raw_roles = [raw_roles]

    roles = normalize_roles_list(raw_roles)
    if roles:
        return roles

    legacy = ""
    if isinstance(record, dict):
        legacy = str(record.get("role") or "").strip()
    return normalize_roles_list(legacy)


def primary_personnel_role(roles: list[str]) -> str:
    for role in ROLE_PRIORITY:
        if role in roles:
            return role
    return roles[0] if roles else ""


def format_roles_display(roles: list[str]) -> str:
    return " · ".join(roles)


def person_has_any_role(record, *roles: str) -> bool:
    if not roles:
        return False
    have = set(parse_personnel_roles(record))
    return bool(have.intersection(roles))
