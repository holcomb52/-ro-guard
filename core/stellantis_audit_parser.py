"""Parse Stellantis warranty audit guide PDF text into structured reason codes."""

from __future__ import annotations

import re
from datetime import datetime, timezone

_REASON_LINE = re.compile(
    r"^[ \t]*([A-Z])\s*[-~–—]\s*(.+?)(?:\.{2,}|\.?\s*)$",
    re.MULTILINE,
)
_SUBCODE_LINE = re.compile(
    r"^[ \t°•o●·\-]*([A-Z]\d+)\s*[-–—]\s*(.+?)(?:\.{2,}|\.?\s*)$",
    re.MULTILINE,
)
_SECTION_HEADER = re.compile(
    r"^[ \t°•o●·eE]*([A-Z])\s*[-~–—]\s*(.+?)(?:\.{2,}|\.?\s*)$",
    re.MULTILINE,
)
_DESCRIPTION_BLOCK = re.compile(
    r"(?:©\s*)?Description:\s*\n(.{40,1200}?)(?:\n\s*(?:Dealer Recommendations|Example Use|Chargeback Application|Pre-Defined Comments|NOTE:|\©))",
    re.IGNORECASE | re.DOTALL,
)

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "as", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "on", "for", "with", "not", "no", "any", "must", "should",
    "using", "used", "claim", "warranty", "dealer", "item", "items", "repair",
    "repairs", "claimed", "missing", "missing",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_title(text: str) -> str:
    cleaned = re.sub(r"\.{2,}", "", str(text or "")).strip(" .")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _extract_toc_reason_codes(text: str) -> dict[str, str]:
    """Pull reason code titles from the guide table of contents."""
    titles: dict[str, str] = {}
    marker = re.search(r"Contents", text, re.I)
    window = text[marker.start() : marker.start() + 2500] if marker else text[:2500]
    for match in _REASON_LINE.finditer(window):
        letter = match.group(1).upper()
        title = _clean_title(match.group(2))
        if letter.isalpha() and len(title) >= 4 and letter not in titles:
            titles[letter] = title
    return titles


def _extract_subcodes(text: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    seen: set[str] = set()
    for match in _SUBCODE_LINE.finditer(text):
        code = match.group(1).upper()
        label = _clean_title(match.group(2))
        if not label or len(label) < 4:
            continue
        entry = f"{code} — {label}"
        if entry in seen:
            continue
        seen.add(entry)
        letter = code[0]
        grouped.setdefault(letter, []).append(entry)
    return grouped


def _extract_description(text: str, letter: str) -> str:
    pattern = re.compile(
        rf"(?:^|\n)[ \t°•o●·eE]*{re.escape(letter)}\s*[-~–—].{{0,80}}\n(?:©\s*)?Description:\s*\n(.{{40,1800}}?)"
        rf"(?:\n\s*(?:Dealer Recommendations|Example Use|Chargeback Application|Pre-Defined Comments|NOTE:|\©))",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    body = re.sub(r"\s+", " ", match.group(1)).strip()
    return body[:500]


def _keywords_from_subcode_label(label: str) -> list[str]:
    text = re.sub(r"^[A-Z]\d+\s*[-–—]\s*", "", label, flags=re.I).strip()
    text = text.replace("/", " ").replace("—", " ")
    chunks = re.split(r"[,;()]+|\band\b", text, flags=re.I)
    keywords: list[str] = []
    for chunk in chunks:
        phrase = re.sub(r"\s+", " ", chunk).strip().lower()
        if len(phrase) < 4:
            continue
        words = [w for w in phrase.split() if w not in _STOP_WORDS]
        if len(words) >= 2:
            keywords.append(" ".join(words))
        elif len(words) == 1 and len(words[0]) >= 5:
            keywords.append(words[0])
    return keywords[:4]


_REQUIREMENT_BLOCK = re.compile(
    r"(?:©\s*)?[oO°•]?\s*Dealer Recommendations/Requirements:\s*(.*?)"
    r"(?=Example Use|Chargeback Application|Pre-Defined Comments|NOTE:|©\s*Description|\n\s*[A-Z]\s*[-~–—]\s+[A-Za-z]|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_OBLIGATION = re.compile(
    r"\b(must|required|shall|mandatory|need to|cannot|should ensure|failure to|comply with|will result)\b",
    re.I,
)
_SECTION_FOR_LETTER = re.compile(
    r"(?:^|\n)[°•o●·eE©]?\s*([A-Z])\s*[-~–—]+\s*"
    r"(?:Parts Unavailable|Non-Warranty|Labor Not|Duplications|Add-On|New Vehicle|Claimed Labor|"
    r"Labor Repair|Claim Alteration|Unsupported Sublet|Required Specs|Designated Management|Tech Notes|"
    r"Missing Claims|Overcharges|Unsupported Mopar|Not the Owner|Customer Signature|Diagnostic Operation|Zero Mile)",
    re.I,
)

_REQUIREMENT_MAPPINGS: list[dict] = [
    {
        "patterns": [r"battery test", r"test slip", r"failed battery", r"battery code"],
        "rule_key": "battery_test_slip",
        "topic": "battery_replacement",
        "proof_field": "battery_test_slip",
        "label": "Battery test slip",
    },
    {
        "patterns": [r"a/c", r"evac", r"recharge", r"refrigerant"],
        "rule_key": "ac_evac_slip",
        "topic": "ac_repair",
        "proof_field": "ac_evac_slip",
        "label": "A/C EVAC slip",
    },
    {
        "patterns": [r"oil dye", r"leak detection", r"oil leak"],
        "rule_key": "oil_leak",
        "topic": "oil_leak",
        "proof_field": "oil_dye_billed",
        "label": "Oil dye billed",
    },
    {
        "patterns": [r"sublet", r"outside the dealership", r"outside repair"],
        "rule_key": "sublet",
        "topic": "sublet_repair",
        "proof_fields": ["sublet_vin", "sublet_mileage", "sublet_notes"],
        "label": "Sublet invoice package",
    },
    {
        "patterns": [r"rental", r"loaner"],
        "rule_key": "rental",
        "topic": "rental_involved",
        "proof_fields": ["rental_days", "manager_signed_rental"],
        "label": "Rental documentation",
    },
    {
        "patterns": [r"alignment", r"wheel alignment", r"align vehicle"],
        "rule_key": "alignment_report",
        "topic": "alignment_involved",
        "proof_field": "alignment_report_attached",
        "label": "Alignment report",
    },
    {
        "patterns": [r"mopar", r"parts warranty", r"original ro", r"non-mopar"],
        "rule_key": "parts_warranty_mopa",
        "topic": "parts_warranty",
        "proof_field": "mopa_original_ro",
        "label": "Parts warranty / MOPAR",
    },
    {
        "patterns": [r"time punch", r"time documentation", r"time clock", r"time punches"],
        "rule_key": "tech_time",
        "topic": None,
        "check_type": "tech_time_documented",
        "evidence_phrases": ["punch", "time punch", "clock", "flagged", "documented time"],
        "label": "Time punch documentation",
    },
    {
        "patterns": [r"manager", r"service manager", r"management person", r"signed by management"],
        "rule_key": "warranty_add_on",
        "topic": "warranty_add_on",
        "proof_field": "manager_approval",
        "label": "Manager authorization",
    },
    {
        "patterns": [r"dtc", r"diagnostic", r"854", r"scan result", r"test result"],
        "rule_key": "stellantis_diagnostic_op",
        "topic": None,
        "check_type": "diagnostic_narrative",
        "evidence_phrases": ["dtc", "code", "scan", "test", "diagnosed", "verified"],
        "label": "Diagnostic support in cause",
    },
]


def _split_requirement_bullets(block: str) -> list[str]:
    cleaned = re.sub(r"(?:^|\n)\s*[=o°•*]\s*", " ", str(block or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return []
    bullets: list[str] = []
    seen: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        sentence = sentence.strip()
        if len(sentence) < 28 or not _OBLIGATION.search(sentence):
            continue
        snippet = sentence[:320]
        if snippet not in seen:
            seen.add(snippet)
            bullets.append(snippet)
    if not bullets and len(cleaned) >= 40 and _OBLIGATION.search(cleaned):
        bullets.append(cleaned[:320])
    return bullets


def extract_dealer_requirements(text: str) -> dict[str, list[str]]:
    """Extract Dealer Recommendations/Requirements bullets grouped by reason code."""
    grouped: dict[str, list[str]] = {}
    raw = str(text or "")
    for match in _REQUIREMENT_BLOCK.finditer(raw):
        start = match.start()
        headers = _SECTION_FOR_LETTER.findall(raw[:start])
        letter = headers[-1].upper() if headers else ""
        if not letter:
            continue
        for bullet in _split_requirement_bullets(match.group(1)):
            bucket = grouped.setdefault(letter, [])
            if bullet not in bucket:
                bucket.append(bullet)
    return grouped


def _trigger_phrases_from_requirement(requirement: str) -> list[str]:
    text = requirement.lower()
    phrases: list[str] = []
    for token in re.findall(r"[a-z]{5,}", text):
        if token not in _STOP_WORDS:
            phrases.append(token)
    for mapping in _REQUIREMENT_MAPPINGS:
        for pattern in mapping["patterns"]:
            if re.search(pattern, text, re.I):
                phrases.append(re.sub(r"\\b", "", pattern))
    deduped: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        phrase = phrase.strip().lower()
        if phrase and phrase not in seen:
            seen.add(phrase)
            deduped.append(phrase)
    return deduped[:8]


def _map_requirement_to_check(letter: str, requirement: str, index: int) -> dict:
    text = requirement.lower()
    for mapping in _REQUIREMENT_MAPPINGS:
        if not any(re.search(pattern, text, re.I) for pattern in mapping["patterns"]):
            continue
        check = {
            "id": f"{letter}_{index}",
            "letter": letter,
            "requirement": requirement,
            "rule_key": mapping["rule_key"],
            "topic": mapping.get("topic"),
            "label": mapping.get("label") or "Audit requirement",
            "trigger_phrases": _trigger_phrases_from_requirement(requirement),
        }
        if mapping.get("proof_field"):
            check["proof_field"] = mapping["proof_field"]
        if mapping.get("proof_fields"):
            check["proof_fields"] = mapping["proof_fields"]
        if mapping.get("check_type"):
            check["check_type"] = mapping["check_type"]
        if mapping.get("evidence_phrases"):
            check["evidence_phrases"] = mapping["evidence_phrases"]
        return check

    return {
        "id": f"{letter}_{index}",
        "letter": letter,
        "requirement": requirement,
        "rule_key": "stellantis_guide_requirement",
        "topic": None,
        "label": "Stellantis audit guide requirement",
        "trigger_phrases": _trigger_phrases_from_requirement(requirement),
        "check_type": "guide_acknowledgement",
    }


def build_requirement_checks(dealer_requirements: dict[str, list[str]]) -> list[dict]:
    checks: list[dict] = []
    for letter in sorted(dealer_requirements):
        for index, requirement in enumerate(dealer_requirements[letter]):
            checks.append(_map_requirement_to_check(letter, requirement, index))
    return checks


def enrich_parsed_config(content: str, parsed: dict | None) -> dict:
    """Ensure parsed guide config includes dealer requirement checks."""
    payload = dict(parsed or {})
    if payload.get("requirement_checks") and payload.get("dealer_requirements"):
        return payload
    dealer_requirements = extract_dealer_requirements(content)
    payload["dealer_requirements"] = dealer_requirements
    payload["requirement_checks"] = build_requirement_checks(dealer_requirements)
    payload["requirement_check_count"] = len(payload["requirement_checks"])
    return payload


def build_non_warranty_patterns_from_subcodes(subcodes: list[str]) -> list[dict]:
    """Turn B-code subcode labels into narrative keyword checks."""
    patterns: list[dict] = []
    seen: set[str] = set()
    for entry in subcodes:
        code_match = re.match(r"^([A-Z]\d+)", entry.strip(), re.I)
        if not code_match:
            continue
        subcode = code_match.group(1).upper()
        if not subcode.startswith("B"):
            continue
        keywords = _keywords_from_subcode_label(entry)
        for keyword in keywords:
            if keyword in seen:
                continue
            seen.add(keyword)
            escaped = re.escape(keyword).replace(r"\ ", r"\s+")
            patterns.append(
                {
                    "pattern": rf"\b{escaped}\b",
                    "subcode": subcode,
                    "message": f"Stellantis {subcode}: {entry.split('—', 1)[-1].strip()} is not reimbursable as warranty.",
                }
            )
    return patterns


def parse_stellantis_audit_guide(text: str) -> dict:
    """Parse OCR/text from the Stellantis audit guide into runtime config."""
    raw = str(text or "")
    warnings: list[str] = []
    if len(raw.strip()) < 200:
        return {
            "reason_codes": {},
            "non_warranty_patterns": [],
            "parse_warnings": ["Extracted text is too short to parse."],
            "parsed_at": _utc_now_iso(),
            "reason_code_count": 0,
        }

    toc_titles = _extract_toc_reason_codes(raw)
    if len(toc_titles) < 8:
        warnings.append("Fewer than 8 reason codes found in the table of contents — check OCR quality.")

    subcodes = _extract_subcodes(raw)
    reason_codes: dict[str, dict] = {}
    for letter, title in sorted(toc_titles.items()):
        reason_codes[letter] = {
            "title": title,
            "summary": _extract_description(raw, letter),
            "subcodes": subcodes.get(letter, []),
        }

    non_warranty_patterns = build_non_warranty_patterns_from_subcodes(subcodes.get("B", []))

    return enrich_parsed_config(
        raw,
        {
            "reason_codes": reason_codes,
            "non_warranty_patterns": non_warranty_patterns,
            "parse_warnings": warnings,
            "parsed_at": _utc_now_iso(),
            "reason_code_count": len(reason_codes),
        },
    )
