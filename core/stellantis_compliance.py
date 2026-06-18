"""WAM + Stellantis audit documentation compliance checks.

Identifies missing proof on the RO before submit — supplements uploaded WAM
excerpts and the Stellantis field-audit guide to reduce denials and chargebacks.
"""

from __future__ import annotations

import re

from core.stellantis_audit import attach_stellantis_codes, stellantis_codes_for_rule

JOB_TOPICS: dict[str, list[str]] = {
    "battery_replacement": ["battery test", "battery replacement", "test slip", "failed battery", "aux battery"],
    "ac_repair": ["a/c repair", "evac", "recharge", "refrigerant", "compressor", "air conditioning"],
    "oil_leak": ["oil leak", "oil leakage", "oil dye", "leak detection", "engine oil"],
    "sublet_repair": ["sublet", "sublet invoice", "outside repair"],
    "rental_involved": ["rental", "loaner", "rental days"],
    "warranty_add_on": ["add-on", "add on", "w+", "warranty add-on", "manager approval"],
    "parts_warranty": ["parts warranty", "mopar", "mopa", "original ro"],
    "alignment_involved": ["alignment", "wheel alignment", "align vehicle", "four wheel alignment"],
}

DOCUMENTATION_CHECKS: list[dict] = [
    {
        "rule_key": "oil_leak",
        "parent_field": "oil_leak",
        "topic": "oil_leak",
        "proof_field": "oil_dye_billed",
        "wam_phrases": ["oil dye", "leak detection", "oil leak"],
        "action": "Bill oil dye when leak detection work is performed.",
        "label": "Oil dye billed",
    },
    {
        "rule_key": "battery_test_slip",
        "parent_field": "battery_replacement",
        "topic": "battery_replacement",
        "proof_field": "battery_test_slip",
        "wam_phrases": ["battery test", "test slip", "failed battery", "battery code"],
        "action": "Attach failed battery test slip/code to the RO.",
        "label": "Battery test slip",
    },
    {
        "rule_key": "alignment_report",
        "parent_field": "alignment_involved",
        "topic": "alignment_involved",
        "proof_field": "alignment_report_attached",
        "wam_phrases": ["alignment", "wheel alignment", "align vehicle"],
        "action": "Attach alignment printout to the repair order.",
        "label": "Alignment report",
    },
    {
        "rule_key": "ac_evac_slip",
        "parent_field": "ac_repair",
        "topic": "ac_repair",
        "proof_field": "ac_evac_slip",
        "wam_phrases": ["evac", "recharge", "refrigerant", "a/c repair"],
        "action": "Attach A/C EVAC/recharge slip to the RO.",
        "label": "A/C EVAC slip",
    },
    {
        "rule_key": "parts_warranty_mopa",
        "parent_field": "parts_warranty",
        "topic": "parts_warranty",
        "proof_field": "mopa_original_ro",
        "wam_phrases": ["parts warranty", "mopar", "mopa", "original ro"],
        "action": "Attach MOPAR and original RO support for parts warranty.",
        "label": "Parts warranty / MOPAR",
    },
    {
        "rule_key": "warranty_add_on",
        "parent_field": "warranty_add_on",
        "topic": "warranty_add_on",
        "proof_field": "manager_approval",
        "wam_phrases": ["add-on", "w+", "warranty add-on", "manager approval"],
        "action": "Obtain Service Manager sign-off for W+ add-on work.",
        "label": "W+ manager sign-off",
    },
    {
        "rule_key": "warranty_add_on_customer_signoff",
        "parent_field": "warranty_add_on",
        "topic": "warranty_add_on",
        "proof_field": "customer_warranty_add_on_signoff",
        "wam_phrases": ["add-on", "w+", "warranty add-on", "customer authorization"],
        "action": "Confirm customer signed off on warranty add-on work.",
        "label": "W+ customer sign-off",
    },
    {
        "rule_key": "sublet",
        "parent_field": "sublet_repair",
        "topic": "sublet_repair",
        "proof_fields": ["sublet_vin", "sublet_mileage", "sublet_notes"],
        "wam_phrases": ["sublet", "outside repair", "sublet invoice"],
        "action": "Sublet invoice must show VIN, mileage, and detailed repair notes.",
        "label": "Sublet invoice package",
    },
    {
        "rule_key": "rental",
        "parent_field": "rental_involved",
        "topic": "rental_involved",
        "proof_fields": ["rental_days", "manager_signed_rental"],
        "wam_phrases": ["rental", "loaner"],
        "action": "Bill rental days and obtain manager sign-off on the RO.",
        "label": "Rental documentation",
    },
]


def _parent_checkbox_checked(job: dict, check: dict) -> bool:
    """True only when the user checked the parent warranty checkbox on Review."""
    parent = check.get("parent_field") or check.get("topic")
    return bool(job.get(parent))


def _job_narrative_text(job: dict) -> str:
    return " ".join(
        str(job.get(key) or "") for key in ("concern", "cause", "correction")
    ).lower()


def narrative_indicates_repair(job: dict, topic: str) -> bool:
    phrases = JOB_TOPICS.get(topic, [])
    if not phrases:
        return False
    text = _job_narrative_text(job)
    return any(phrase in text for phrase in phrases)


def _rental_work_applies(job: dict) -> bool:
    if narrative_indicates_repair(job, "rental_involved"):
        return True
    try:
        return int(job.get("rental_days") or 0) > 0
    except (TypeError, ValueError):
        return False


def work_applies(job: dict, topic: str) -> bool:
    if topic == "rental_involved":
        return _rental_work_applies(job)
    return bool(job.get(topic)) or narrative_indicates_repair(job, topic)


def _has_proof(job: dict, check: dict) -> bool:
    fields = check.get("proof_fields")
    if fields:
        if check["rule_key"] == "sublet":
            return all(bool(job.get(field)) for field in fields)
        if check["rule_key"] == "rental":
            days = int(job.get("rental_days") or 0)
            return days > 0 and bool(job.get("manager_signed_rental"))
        return all(bool(job.get(field)) for field in fields)
    field = check.get("proof_field")
    return bool(job.get(field)) if field else True


def _message_for_gap(check: dict) -> str:
    codes = ", ".join(stellantis_codes_for_rule(check["rule_key"])) or "audit"
    return (
        f"Missing {check['label']} — {check['action']} "
        f"(WAM + Stellantis {codes})."
    )


def evaluate_documentation_compliance(
    job: dict,
    manual_sections: list | None = None,
) -> list[dict]:
    """Return findings when a parent warranty checkbox is checked but proof is not."""
    del manual_sections  # Score uses checkbox pairs only — not WAM excerpts or narrative.
    findings: list[dict] = []
    seen_rules: set[str] = set()

    for check in DOCUMENTATION_CHECKS:
        rule_key = check["rule_key"]
        if not _parent_checkbox_checked(job, check):
            continue

        if rule_key == "sublet":
            sublet_gaps = []
            if not job.get("sublet_vin"):
                sublet_gaps.append("VIN")
            if not job.get("sublet_mileage"):
                sublet_gaps.append("mileage")
            if not job.get("sublet_notes"):
                sublet_gaps.append("detailed repair notes")
            if sublet_gaps and rule_key not in seen_rules:
                seen_rules.add(rule_key)
                codes = ", ".join(stellantis_codes_for_rule(rule_key)) or "audit"
                findings.append(
                    attach_stellantis_codes(
                        {
                            "rule": rule_key,
                            "message": (
                                f"Sublet invoice missing {', '.join(sublet_gaps)} — "
                                f"required by WAM + Stellantis {codes}."
                            ),
                        }
                    )
                )
            continue

        if rule_key == "rental":
            if rule_key in seen_rules:
                continue
            if int(job.get("rental_days") or 0) <= 0:
                seen_rules.add(rule_key)
                codes = ", ".join(stellantis_codes_for_rule(rule_key)) or "audit"
                findings.append(
                    attach_stellantis_codes(
                        {
                            "rule": rule_key,
                            "message": (
                                f"Rental involved but rental days are not billed (WAM + Stellantis {codes})."
                            ),
                        }
                    )
                )
                continue
            if not job.get("manager_signed_rental"):
                seen_rules.add(rule_key)
                codes = ", ".join(stellantis_codes_for_rule(rule_key)) or "audit"
                findings.append(
                    attach_stellantis_codes(
                        {
                            "rule": rule_key,
                            "message": (
                                f"Rental involved but manager sign-off is missing (WAM + Stellantis {codes})."
                            ),
                        }
                    )
                )
            continue

        if _has_proof(job, check) or rule_key in seen_rules:
            continue
        seen_rules.add(rule_key)
        findings.append(
            attach_stellantis_codes(
                {
                    "rule": rule_key,
                    "message": _message_for_gap(check),
                }
            )
        )

    return findings


def _catalog_check_for_rule(rule_key: str) -> dict | None:
    for check in DOCUMENTATION_CHECKS:
        if check["rule_key"] == rule_key:
            return check
    return None


def _requirement_trigger_hits(job: dict, check: dict) -> bool:
    topic = check.get("topic")
    if topic:
        return bool(job.get(topic))

    check_type = check.get("check_type")
    if check_type == "tech_time_documented":
        try:
            if float(job.get("tech_flagged_time") or 0) > 0 or float(job.get("time_allotted") or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
        text = _job_narrative_text(job)
        return any(
            phrase in text
            for phrase in ("time punch", "time punches", "clock time", "flagged time", "punched")
        )

    if check_type == "diagnostic_narrative":
        text = _job_narrative_text(job)
        return any(
            phrase in text
            for phrase in ("diagnostic", "854", "dtc", "scan", "test result", "diagnosed")
        )

    return False


def _requirement_satisfied(job: dict, check: dict) -> bool:
    check_type = check.get("check_type")
    if check_type in {"ro_customer_signature", "guide_acknowledgement"}:
        return True
    if check_type == "ccc_complete":
        return all(str(job.get(key) or "").strip() for key in ("concern", "cause", "correction"))
    if check_type == "tech_time_documented":
        tech_flagged = float(job.get("tech_flagged_time") or 0)
        time_allotted = float(job.get("time_allotted") or 0)
        if tech_flagged > 0 and time_allotted > 0:
            return True
        evidence = [str(p).lower() for p in check.get("evidence_phrases") or []]
        cause = str(job.get("cause") or "").lower()
        return any(phrase in cause for phrase in evidence)
    if check_type == "diagnostic_narrative":
        evidence = [str(p).lower() for p in check.get("evidence_phrases") or []]
        cause = str(job.get("cause") or "").lower()
        return any(phrase in cause for phrase in evidence)

    catalog = _catalog_check_for_rule(check.get("rule_key", ""))
    merged = {**(catalog or {}), **check}
    if merged.get("proof_field") or merged.get("proof_fields"):
        return _has_proof(job, merged)
    return True


def _message_for_guide_requirement(check: dict) -> str:
    letter = str(check.get("letter") or "").strip()
    requirement = str(check.get("requirement") or "").strip()
    snippet = requirement[:200] + ("…" if len(requirement) > 200 else "")
    catalog = _catalog_check_for_rule(check.get("rule_key", ""))
    codes = ", ".join(stellantis_codes_for_rule(check.get("rule_key", ""))) or letter or "audit"
    if catalog:
        return (
            f"Stellantis guide ({letter}): missing {check.get('label') or catalog['label']} — "
            f"{catalog['action']} ({snippet})"
        )
    return f"Stellantis guide ({letter}): confirm audit requirement — {snippet} (Stellantis {codes})."


def evaluate_guide_requirement_checks(
    job: dict,
    requirement_checks: list[dict] | None,
    seen_rules: set[str] | None = None,
) -> list[dict]:
    """Evaluate dynamic checks parsed from the active Stellantis audit guide."""
    seen = set(seen_rules or [])
    findings: list[dict] = []
    for check in requirement_checks or []:
        rule_key = str(check.get("rule_key") or "").strip()
        if not rule_key or rule_key in seen:
            continue
        check_type = check.get("check_type")
        if check_type in {"ro_customer_signature", "guide_acknowledgement"}:
            continue
        if not _requirement_trigger_hits(job, check):
            continue
        if _requirement_satisfied(job, check):
            continue
        seen.add(rule_key)
        findings.append(
            attach_stellantis_codes(
                {
                    "rule": rule_key,
                    "message": _message_for_guide_requirement(check),
                    "stellantis_letter": check.get("letter"),
                }
            )
        )
    return findings


def list_compliance_check_catalog() -> list[dict]:
    rows = []
    for check in DOCUMENTATION_CHECKS:
        rows.append(
            {
                "label": check["label"],
                "rule_key": check["rule_key"],
                "stellantis": ", ".join(stellantis_codes_for_rule(check["rule_key"])) or "—",
                "action": check["action"],
            }
        )
    rows.append(
        {
            "label": "W+ manager approval",
            "rule_key": "warranty_add_on",
            "stellantis": "E, L",
            "action": "Obtain Service Manager sign-off for W+ add-on work.",
        }
    )
    rows.append(
        {
            "label": "W+ customer sign-off",
            "rule_key": "warranty_add_on_customer_signoff",
            "stellantis": "E, L, S",
            "action": "Confirm customer signed off on warranty add-on work.",
        }
    )
    rows.append(
        {
            "label": "RO signed by customer",
            "rule_key": "stellantis_customer_signature",
            "stellantis": "S",
            "action": "Confirm customer authorization signature is on file before submit.",
        }
    )
    rows.append(
        {
            "label": "Diagnostic operation support",
            "rule_key": "stellantis_diagnostic_op",
            "stellantis": "T",
            "action": "Document DTC, scan results, or test evidence for diagnostic ops.",
        }
    )
    return rows


def render_compliance_checks_reference(
    *,
    requirement_checks: list[dict] | None = None,
    dealer_requirements: dict[str, list[str]] | None = None,
) -> None:
    import streamlit as st

    st.subheader("WAM & audit documentation checks")
    st.caption(
        "RO Guard compares warranty documentation checkboxes on Review. Score is reduced only when a "
        "parent box is checked (e.g. Oil Leak, Battery Replacement) but its matching proof box is not."
    )
    for row in list_compliance_check_catalog():
        st.markdown(f"**{row['label']}** (Stellantis {row['stellantis']})")
        st.markdown(f"- {row['action']}")

    checks = requirement_checks or []
    grouped = dealer_requirements or {}
    if checks or grouped:
        st.subheader("Active guide — dealer requirements")
        st.caption(
            f"{len(checks)} compliance checks parsed from Dealer Recommendations/Requirements "
            f"across {len(grouped)} reason codes."
        )
        with st.expander("Parsed dealer requirements", expanded=False):
            for letter in sorted(grouped):
                st.markdown(f"**{letter}**")
                for item in grouped[letter][:6]:
                    st.markdown(f"- {item}")
                if len(grouped[letter]) > 6:
                    st.caption(f"+ {len(grouped[letter]) - 6} more for {letter}")

    st.caption(
        "Upload WAM PDFs under **WAM**. Upload an updated Stellantis audit guide here when "
        "Stellantis publishes changes."
    )
