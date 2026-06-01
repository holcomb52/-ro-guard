"""Shared JARVIS Q&A pipeline."""

from __future__ import annotations

from jarvis.ollama import SYSTEM_PROMPT, chat


def ask_jarvis(
    prompt: str,
    context: str,
    *,
    model: str,
    history: list[dict] | None = None,
) -> tuple[str, str]:
    """Return (answer, error)."""
    prompt = str(prompt or "").strip()
    if not prompt:
        return "", "Ask a question first."

    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history or []:
        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            llm_messages.append({"role": role, "content": content})

    llm_messages.append(
        {
            "role": "user",
            "content": f"DATA SNAPSHOT:\n\n{context}\n\n---\n\nQUESTION:\n{prompt}",
        }
    )
    return chat(llm_messages, model=model)
