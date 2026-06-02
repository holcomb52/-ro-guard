"""Isolated HTML/JS embeds (iframe) for scripts that must not run in the main app DOM."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


def embed_html(html: str, *, height: int = 0, width: int = 0) -> None:
    """Embed HTML in a minimal iframe.

    Scripts target ``window.parent`` (Streamlit shell). ``st.html`` runs in the main
    document and can blank the app; never use it for these embeds.
    """
    iframe = getattr(st, "iframe", None)
    if iframe is not None:
        iframe(
            html,
            height=height if height > 0 else 1,
            width=width if width > 0 else 1,
        )
        return
    components.html(html, height=height, width=width)
