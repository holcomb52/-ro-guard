"""Stellantis OEM warranty audit reason codes and RO Guard rule mapping.

Based on Stellantis North America Dealer Audit — Warranty Audit Reason Code
Application Guide (dealer field audit checklist).
"""

from __future__ import annotations

import re
from typing import Iterable

# Stellantis chargeback reason codes (letter = primary bucket).
STELLANTIS_REASON_CODES: dict[str, dict] = {
    "A": {
        "title": "Parts Unavailable (Short Parts Only)",
        "summary": "Parts claimed were not purchased from Stellantis or an authorized source.",
        "subcodes": ["A1 — Non-Mopar parts misrepresented as Mopar"],
    },
    "B": {
        "title": "Non-Warranty Item",
        "summary": "Repair is not a warrantable defect (physical damage, shop supplies, goodwill, etc.).",
        "subcodes": [
            "B1 — Physical damage / abuse",
            "B2 — Brake cleaner / shop supplies",
            "B3 — Customer responsibility items",
            "B4 — Transportation damage claimed as warranty",
            "B6 — Shortage and error claimed as warranty",
            "B7 — Physical damage not a material/workmanship defect",
        ],
    },
    "C": {
        "title": "Labor Not Supported",
        "summary": "Time punches or documentation do not support labor claimed.",
        "subcodes": ["C1 — Time documentation not supported"],
    },
    "D": {
        "title": "Duplications / Shop Comebacks",
        "summary": "Repeat repair for the same complaint — prior repair not corrected.",
        "subcodes": [],
    },
    "E": {
        "title": "Add-On Operations",
        "summary": "Add-on labor/parts not supported or missing authorization.",
        "subcodes": [],
    },
    "F": {
        "title": "New Vehicle Prep Irregularities",
        "summary": "New vehicle prep claimed incorrectly.",
        "subcodes": [],
    },
    "G": {
        "title": "Claimed Labor Operation Unsupported",
        "summary": "Labor operation does not match documented repair.",
        "subcodes": [],
    },
    "H": {
        "title": "Labor Repair Efficiency",
        "summary": "Flagged time vs allotted time out of acceptable range.",
        "subcodes": [],
    },
    "I": {
        "title": "Claim Alteration",
        "summary": "Claim altered after submission or does not match RO documentation.",
        "subcodes": [],
    },
    "J": {
        "title": "Unsupported Sublet Repairs",
        "summary": "Sublet invoice missing VIN, mileage, or detailed notes.",
        "subcodes": [],
    },
    "K": {
        "title": "Required Specs Not Recorded",
        "summary": "Missing battery test, A/C EVAC, alignment report, oil dye, or similar proof.",
        "subcodes": [],
    },
    "L": {
        "title": "Designated Management Person Authorization Missing",
        "summary": "Rental, W+, or other repairs require manager sign-off.",
        "subcodes": [],
    },
    "M": {
        "title": "Tech Notes Do Not Support Repair",
        "summary": "Concern, cause, or correction does not support the claim (Pencil Wrench / CCC).",
        "subcodes": [],
    },
    "N": {
        "title": "Missing Claims",
        "summary": "Warranty work performed but not claimed (post-audit recovery).",
        "subcodes": [],
    },
    "O": {
        "title": "Overcharges",
        "summary": "Claim amount exceeds supported labor/parts.",
        "subcodes": [],
    },
    "P": {
        "title": "Unsupported Mopar Claims",
        "summary": "Non-Mopar parts or unsupported Mopar claim documentation.",
        "subcodes": [],
    },
    "Q": {
        "title": "Not the Owner of Record / Invalid Warranty Coverage",
        "summary": "Coverage or ownership does not support the claim.",
        "subcodes": [],
    },
    "R": {
        "title": "Parts Unavailable (Related Parts)",
        "summary": "Related parts not supported by purchase documentation.",
        "subcodes": [],
    },
    "S": {
        "title": "Customer Signature Missing",
        "summary": "Customer authorization / repair order signature not on file.",
        "subcodes": [],
    },
    "T": {
        "title": "Diagnostic Operation Discrepancies",
        "summary": "Diagnostic labor (854xxxx) or cause narrative missing DTC/tests/results.",
        "subcodes": [],
    },
    "X": {
        "title": "Zero Mile Paint/Trim — No Manager Authorization",
        "summary": "Paint/trim repair at delivery requires manager authorization.",
        "subcodes": [],
    },
}

# Map internal RO Guard audit rule keys → Stellantis reason code letters.
AUDIT_RULE_TO_STELLANTIS: dict[str, list[str]] = {
    "narrative_required": ["M"],
    "pencil_wrench_cause": ["M", "T"],
    "pencil_wrench_correction": ["M"],
    "oil_leak": ["K"],
    "sublet": ["J"],
    "rental": ["L"],
    "rental_high_days": ["L"],
    "warranty_add_on": ["E", "L"],
    "tech_time": ["C", "H"],
    "battery_test_slip": ["K"],
    "ac_evac_slip": ["K"],
    "alignment_report": ["K"],
    "parts_warranty_mopa": ["A", "P", "R"],
    "manual_guidance": [],
    "stellantis_customer_signature": ["S"],
    "stellantis_non_warranty_item": ["B"],
    "stellantis_diagnostic_op": ["T"],
    "stellantis_zero_mile_paint": ["X", "L"],
}

STELLANTIS_AUDIT_RULES: dict[str, dict] = {
    "stellantis_customer_signature": {"enabled": True, "severity": "hard"},
    "stellantis_non_warranty_item": {"enabled": True, "severity": "hard"},
    "stellantis_diagnostic_op": {"enabled": True, "severity": "hard"},
    "stellantis_zero_mile_paint": {"enabled": True, "severity": "hard"},
}

STELLANTIS_AUDIT_LABELS: dict[str, str] = {
    "stellantis_customer_signature": "Stellantis S — customer RO signature on file",
    "stellantis_non_warranty_item": "Stellantis B — non-warranty item in story",
    "stellantis_diagnostic_op": "Stellantis T — diagnostic operation / DTC support",
    "stellantis_zero_mile_paint": "Stellantis X — zero-mile paint/trim manager authorization",
}

STELLANTIS_COACHING_PHRASES: dict[str, str] = {
    "stellantis_customer_signature": "missing customer repair order signature (Stellantis S)",
    "stellantis_non_warranty_item": "non-warranty language in the story (Stellantis B)",
    "stellantis_diagnostic_op": "diagnostic operation not supported (Stellantis T)",
    "stellantis_zero_mile_paint": "zero-mile paint/trim without manager authorization (Stellantis X)",
}

_NON_WARRANTY_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"\b(brake cleaner|shop supplies?|cleaner shop supply)\b",
        "B2",
        "Stellantis B2: shop supplies (e.g. brake cleaner) are not reimbursable as warranty.",
    ),
    (
        r"\b(curbs?|hit a curb|physical damage|collision|accident|abuse|vandal)\b",
        "B1",
        "Stellantis B1: physical damage / abuse is not a warrantable defect.",
    ),
    (
        r"\b(transport(ation)? damage|loose ship|missing loose ship)\b",
        "B4",
        "Stellantis B4: transportation damage must not be claimed as warranty.",
    ),
    (
        r"\b(goodwill|customer pay|cust pay|as a courtesy)\b",
        "B3",
        "Stellantis B3: customer responsibility / goodwill items are not warranty.",
    ),
    (
        r"\b(shortage|short ship|error claim)\b",
        "B6",
        "Stellantis B6: shortage/error items must not be claimed as warranty.",
    ),
]

_PAINT_TRIM_PATTERN = re.compile(
    r"\b(paint|refinish|touch.?up|trim|dent|chip|scratch|body panel|bumper cover)\b",
    re.I,
)

_DIAGNOSTIC_OP_PATTERN = re.compile(r"^854", re.I)


def stellantis_codes_for_rule(rule_key: str) -> list[str]:
    return list(AUDIT_RULE_TO_STELLANTIS.get(str(rule_key or "").strip(), []))


def stellantis_code_label(code: str) -> str:
    letter = str(code or "").strip().upper()[:1]
    meta = STELLANTIS_REASON_CODES.get(letter) or {}
    title = str(meta.get("title") or "").strip()
    return f"Stellantis {letter}" + (f" — {title}" if title else "")


def format_stellantis_codes(codes: Iterable[str]) -> str:
    letters = []
    seen: set[str] = set()
    for code in codes:
        letter = str(code or "").strip().upper()[:1]
        if letter and letter not in seen:
            seen.add(letter)
            letters.append(letter)
    if not letters:
        return ""
    return ", ".join(letters)


def format_finding_display(finding) -> str:
    if not isinstance(finding, dict):
        return str(finding or "").strip()
    message = str(finding.get("message") or "").strip()
    codes = finding.get("stellantis") or stellantis_codes_for_rule(str(finding.get("rule") or ""))
    code_str = format_stellantis_codes(codes)
    if code_str:
        return f"Stellantis {code_str}: {message}"
    return message


def attach_stellantis_codes(finding: dict, *, extra_codes: list[str] | None = None) -> dict:
    rule = str(finding.get("rule") or "").strip()
    codes = stellantis_codes_for_rule(rule)
    if extra_codes:
        for code in extra_codes:
            letter = str(code or "").strip().upper()[:1]
            if letter and letter not in codes:
                codes.append(letter)
    if codes:
        finding["stellantis"] = codes
    return finding


def detect_non_warranty_issues(*texts: str) -> list[tuple[str, str]]:
    """Return (subcode, message) pairs when narrative suggests a B-code issue."""
    blob = " ".join(str(t or "") for t in texts).lower()
    if not blob.strip():
        return []
    hits: list[tuple[str, str]] = []
    seen_sub: set[str] = set()
    for pattern, subcode, message in _effective_non_warranty_patterns():
        if re.search(pattern, blob, re.I) and subcode not in seen_sub:
            seen_sub.add(subcode)
            hits.append((subcode, message))
    return hits


def get_effective_reason_codes() -> dict[str, dict]:
    """Merge uploaded guide reason codes with built-in defaults."""
    try:
        from core.stellantis_audit_store import get_bound_stellantis_config

        uploaded = get_bound_stellantis_config().get("reason_codes") or {}
    except ImportError:
        uploaded = {}

    if not uploaded:
        return STELLANTIS_REASON_CODES

    merged = {**STELLANTIS_REASON_CODES}
    for letter, meta in uploaded.items():
        if not isinstance(meta, dict):
            continue
        base = merged.get(letter, {})
        merged[letter] = {
            "title": meta.get("title") or base.get("title") or "",
            "summary": meta.get("summary") or base.get("summary") or "",
            "subcodes": meta.get("subcodes") or base.get("subcodes") or [],
        }
    return merged


def _effective_non_warranty_patterns() -> list[tuple[str, str, str]]:
    patterns: list[tuple[str, str, str]] = list(_NON_WARRANTY_PATTERNS)
    try:
        from core.stellantis_audit_store import get_bound_stellantis_config

        uploaded = get_bound_stellantis_config().get("non_warranty_patterns") or []
    except ImportError:
        uploaded = []

    if not uploaded:
        return patterns

    seen_sub = {subcode for _pattern, subcode, _message in patterns}
    extra: list[tuple[str, str, str]] = []
    for item in uploaded:
        if not isinstance(item, dict):
            continue
        subcode = str(item.get("subcode") or "").strip().upper()
        pattern = str(item.get("pattern") or "").strip()
        message = str(item.get("message") or "").strip()
        if not subcode or not pattern or not message:
            continue
        if subcode in seen_sub:
            continue
        seen_sub.add(subcode)
        extra.append((pattern, subcode, message))
    return extra + patterns


def _is_diagnostic_operation(job: dict) -> bool:
    op = str(job.get("operation_code") or "").strip().upper()
    if _DIAGNOSTIC_OP_PATTERN.match(op):
        return True
    text = f"{job.get('concern', '')} {job.get('cause', '')} {job.get('correction', '')}".lower()
    return "diagnostic" in text and any(
        token in text for token in ("854", "scan", "test", "diagnos")
    )


def detect_diagnostic_op_issues(job: dict) -> list[str]:
    """Messages for Stellantis T when diagnostic ops lack supporting evidence."""
    if not _is_diagnostic_operation(job):
        return []
    cause = str(job.get("cause") or "").lower()
    messages: list[str] = []
    if not any(
        token in cause
        for token in ("dtc", "code", "scan", "test", "measured", "inspection", "verified", "diagnosed")
    ):
        messages.append(
            "Stellantis T: diagnostic operation requires DTC, scan results, or test evidence in the cause."
        )
    return messages


def detect_zero_mile_paint_issue(job: dict, *, vehicle_mileage: float = 0) -> str | None:
    text = f"{job.get('concern', '')} {job.get('cause', '')} {job.get('correction', '')}"
    if not _PAINT_TRIM_PATTERN.search(text):
        return None
    mileage = float(vehicle_mileage or 0)
    if mileage > 50:
        return None
    if job.get("manager_approval") or job.get("manager_signed_rental"):
        return None
    return (
        "Stellantis X: paint/trim work at low/zero mileage requires designated manager authorization."
    )


def audit_ro_level_findings(
    *,
    customer_signature: bool,
    vehicle_mileage: float = 0,
) -> list[dict]:
    """RO-level Stellantis checks (not tied to a single job line)."""
    findings: list[dict] = []
    if not customer_signature:
        findings.append(
            attach_stellantis_codes(
                {
                    "rule": "stellantis_customer_signature",
                    "message": "Customer repair order signature is not confirmed on file.",
                },
                extra_codes=["S"],
            )
        )
    return findings


def apply_stellantis_job_checks(
    job: dict,
    hard: list,
    warn: list,
    audit_rules: dict,
    add_finding,
    *,
    vehicle_mileage: float = 0,
) -> None:
    """Append Stellantis OEM job-level findings via the shared add_finding callback."""
    text_parts = (job.get("concern"), job.get("cause"), job.get("correction"))
    for _subcode, message in detect_non_warranty_issues(*text_parts):
        add_finding(hard, warn, audit_rules, "stellantis_non_warranty_item", message)

    for message in detect_diagnostic_op_issues(job):
        add_finding(hard, warn, audit_rules, "stellantis_diagnostic_op", message)

    paint_message = detect_zero_mile_paint_issue(job, vehicle_mileage=vehicle_mileage)
    if paint_message:
        add_finding(hard, warn, audit_rules, "stellantis_zero_mile_paint", paint_message)


def split_ro_level_findings(
    findings: list[dict],
    audit_rules: dict,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (hard, warn, disabled) lists from raw RO-level finding dicts."""
    hard: list[dict] = []
    warn: list[dict] = []
    disabled: list[dict] = []
    rules = audit_rules.get("rules") or {}
    for finding in findings:
        rule_key = str(finding.get("rule") or "").strip()
        entry = rules.get(rule_key, {})
        if not entry.get("enabled", True):
            disabled.append(finding)
            continue
        severity = str(entry.get("severity", "hard") or "hard").lower()
        if severity == "warn":
            warn.append(finding)
        else:
            hard.append(finding)
    return hard, warn, disabled


def render_stellantis_audit_reference() -> None:
    """Admin reference for Stellantis OEM audit reason codes."""
    import streamlit as st

    st.subheader("Stellantis OEM audit reason codes")
    active_note = ""
    try:
        from core.stellantis_audit_store import get_bound_stellantis_config

        active = get_bound_stellantis_config()
        if active.get("document_id"):
            active_note = (
                f" Active uploaded guide: **{active.get('source_file') or 'Guide'}** "
                f"({int(active.get('reason_code_count') or 0)} codes parsed)."
            )
    except ImportError:
        pass
    st.caption(
        "Reference from the Stellantis North America Dealer Audit — Warranty Audit "
        "Reason Code Application Guide. RO Guard maps internal audit rules to these codes "
        "and applies enabled rules as hard stops or warnings."
        + active_note
    )
    reason_codes = get_effective_reason_codes()
    for letter in sorted(reason_codes):
        meta = reason_codes[letter]
        title = meta.get("title") or ""
        summary = meta.get("summary") or ""
        subcodes = meta.get("subcodes") or []
        with st.expander(f"**{letter}** — {title}", expanded=False):
            if summary:
                st.write(summary)
            mapped = []
            from core.review_store import audit_rule_label

            for rule_key, codes in AUDIT_RULE_TO_STELLANTIS.items():
                if letter in codes:
                    mapped.append(audit_rule_label(rule_key))
            if mapped:
                st.markdown("**RO Guard rules mapped here:**")
                for label in mapped:
                    st.markdown(f"- {label}")
            if subcodes:
                st.markdown("**Subcodes:**")
                for sub in subcodes:
                    st.markdown(f"- {sub}")
