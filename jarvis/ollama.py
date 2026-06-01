"""Local Ollama client — all inference stays on this machine."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from jarvis.config import OLLAMA_HOST, OLLAMA_MODEL

SYSTEM_PROMPT = """You are JARVIS, a private warranty operations assistant for the RO Guard owner.
You analyze RO Guard review data snapshots provided by the user message.
You help interpret metrics, advisor patterns, rejections, pending outcomes, and trends.

Rules:
- Be concise and practical for a service/warranty manager.
- Only use facts from the data snapshot; say when data is missing.
- Never write cause/correction narratives for warranty submission.
- Never claim to connect to ChatGPT or external AI services.
- Suggest concrete next steps when you see risk (hard stops, low scores, rejections).
"""


def list_models() -> tuple[list[str], str]:
    url = f"{OLLAMA_HOST}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return [], f"Ollama is not reachable at {OLLAMA_HOST}: {exc}"
    except Exception as exc:
        return [], str(exc)

    models = []
    for item in payload.get("models") or []:
        name = str(item.get("name") or "").strip()
        if name:
            models.append(name)
    if not models:
        return [], "Ollama is running but no models are installed. Run: ollama pull llama3.2"
    return models, ""


def ping() -> tuple[bool, str]:
    models, err = list_models()
    if err:
        return False, err
    return True, f"Ollama OK — {len(models)} model(s) installed"


def chat(messages: list[dict], *, model: str | None = None) -> tuple[str, str]:
    """Return (assistant_text, error)."""
    model = (model or OLLAMA_MODEL).strip()
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return "", f"Ollama request failed: {exc}"
    except Exception as exc:
        return "", str(exc)

    message = payload.get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        return "", "Ollama returned an empty response."
    return text, ""
