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

    return {
        "reason_codes": reason_codes,
        "non_warranty_patterns": non_warranty_patterns,
        "parse_warnings": warnings,
        "parsed_at": _utc_now_iso(),
        "reason_code_count": len(reason_codes),
    }
