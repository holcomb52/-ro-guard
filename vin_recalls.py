"""NHTSA VIN decode + recall/campaign lookup (public APIs)."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VPIC_DECODE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
RECALLS_BY_VEHICLE_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
USER_AGENT = "RO-Shield/1.0 (Dealership warranty audit tool)"

RECALL_MATCH_TERMS = [
    "abs", "esc", "stability", "brake", "airbag", "seat belt", "steering",
    "transmission", "engine", "fuel", "electrical", "software", "module",
    "pcm", "tcm", "bcm", "camera", "mirror", "tailgate", "bed", "exhaust",
    "coolant", "oil", "powertrain", "driveshaft", "axle", "differential",
    "suspension", "control arm", "tie rod", "battery", "alternator", "starter",
    "hvac", "a/c", "refrigerant", "evap", "recall", "campaign", "fire",
    "stall", "shift", "reprogram", "flash", "wiring", "short", "leak",
]


def normalize_vin(vin: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (vin or "")).upper()


def _http_get_json(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def decode_vin(vin: str) -> tuple[dict | None, str | None]:
    """Decode VIN via NHTSA vPIC. Returns (vehicle_dict, error_message)."""
    vin_clean = normalize_vin(vin)
    if len(vin_clean) < 11:
        return None, "Enter at least 11 characters of the VIN to check recalls."

    url = VPIC_DECODE_URL.format(vin=urllib.parse.quote(vin_clean))
    try:
        data = _http_get_json(url)
    except Exception as exc:
        return None, f"VIN decode failed: {exc}"

    row = (data.get("Results") or [{}])[0]
    make = str(row.get("Make") or "").strip()
    model = str(row.get("Model") or "").strip()
    model_year = str(row.get("ModelYear") or "").strip()

    if not make or not model or not model_year or model_year in ("0", "0000"):
        err = str(row.get("ErrorText") or "").strip()
        return None, err or "Could not decode this VIN."

    return {
        "vin": vin_clean,
        "make": make,
        "model": model,
        "model_year": model_year,
        "trim": str(row.get("Trim") or "").strip(),
        "body_class": str(row.get("BodyClass") or "").strip(),
        "engine": str(row.get("EngineModel") or row.get("DisplacementL") or "").strip(),
        "drive_type": str(row.get("DriveType") or "").strip(),
    }, None


def _normalize_model_for_recalls(model: str) -> list[str]:
    """Try recall API with full model name and simplified variants."""
    model = (model or "").strip()
    candidates = [model]
    if " " in model:
        candidates.append(model.split()[0])
    seen = set()
    out = []
    for item in candidates:
        key = item.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def fetch_recalls_for_vehicle(make: str, model: str, model_year: str) -> list[dict]:
    """Return NHTSA recall campaigns for make/model/year."""
    last_error = None
    for model_variant in _normalize_model_for_recalls(model):
        params = urllib.parse.urlencode({
            "make": make,
            "model": model_variant,
            "modelYear": model_year,
        })
        url = f"{RECALLS_BY_VEHICLE_URL}?{params}"
        try:
            data = _http_get_json(url)
            results = data.get("results") or []
            if results:
                return results
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise RuntimeError(f"Recall lookup failed: {last_error}")
    return []


def _normalize_recall(row: dict) -> dict:
    campaign = str(row.get("NHTSACampaignNumber") or row.get("NHTSACampaign") or "").strip()
    return {
        "campaign": campaign,
        "component": str(row.get("Component") or "").strip(),
        "summary": str(row.get("Summary") or "").strip(),
        "consequence": str(row.get("Consequence") or "").strip(),
        "remedy": str(row.get("Remedy") or "").strip(),
        "report_date": str(row.get("ReportReceivedDate") or "").strip(),
        "manufacturer": str(row.get("Manufacturer") or "").strip(),
        "park_it": bool(row.get("parkIt")),
        "park_outside": bool(row.get("parkOutSide")),
        "ota": bool(row.get("overTheAirUpdate")),
    }


def score_recall_relevance(recall: dict, job_text: str) -> tuple[int, list[str]]:
    """Score how closely a recall might relate to the current repair narrative."""
    text = (job_text or "").lower()
    if not text.strip():
        return 0, []

    blob = " ".join([
        recall.get("component", ""),
        recall.get("summary", ""),
        recall.get("campaign", ""),
    ]).lower()

    hits = []
    score = 0
    for term in RECALL_MATCH_TERMS:
        if term in text and term in blob:
            hits.append(term)
            score += 8

    for word in re.findall(r"[a-z0-9]{4,}", text):
        if word in blob and word not in hits:
            hits.append(word)
            score += 4

    return min(score, 100), hits[:6]


def apply_job_relevance(recalls: list[dict], job_text: str) -> list[dict]:
    """Re-score cached recalls against the current job narrative."""
    updated = []
    for recall in recalls:
        item = dict(recall)
        score, hits = score_recall_relevance(item, job_text)
        item["relevance_score"] = score
        item["relevance_hits"] = hits
        updated.append(item)
    updated.sort(
        key=lambda r: (r.get("relevance_score", 0), r.get("report_date", "")),
        reverse=True,
    )
    return updated


def lookup_vin_recalls(vin: str, job_text: str = "") -> dict:
    """
    Decode VIN and return NHTSA recall campaigns for that vehicle configuration.

    Note: NHTSA returns campaigns by make/model/year — not VIN-specific completion status.
    Dealers must still verify in OASIS / wiTECH / DealerCONNECT.
    """
    vehicle, error = decode_vin(vin)
    if error:
        return {
            "ok": False,
            "error": error,
            "vin": normalize_vin(vin),
            "vehicle": None,
            "recalls": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        raw_recalls = fetch_recalls_for_vehicle(
            vehicle["make"],
            vehicle["model"],
            vehicle["model_year"],
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "vin": vehicle["vin"],
            "vehicle": vehicle,
            "recalls": [],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    recalls = []
    for row in raw_recalls:
        item = _normalize_recall(row)
        rel_score, rel_hits = score_recall_relevance(item, job_text)
        item["relevance_score"] = rel_score
        item["relevance_hits"] = rel_hits
        recalls.append(item)

    recalls.sort(key=lambda r: (r.get("relevance_score", 0), r.get("report_date", "")), reverse=True)
    critical = [r for r in recalls if r.get("park_it") or r.get("park_outside")]

    return {
        "ok": True,
        "error": "",
        "vin": vehicle["vin"],
        "vehicle": vehicle,
        "recalls": recalls,
        "recall_count": len(recalls),
        "critical_count": len(critical),
        "related_count": sum(1 for r in recalls if r.get("relevance_score", 0) >= 12),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": (
            "NHTSA lists safety recall campaigns for this vehicle's make, model, and year. "
            "This does not confirm whether this VIN is open or complete — verify in OASIS / wiTECH / DealerCONNECT."
        ),
    }
