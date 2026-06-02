"""Isolated HTML/JS embeds (iframe) for scripts that must not run in the main app DOM."""

from __future__ import annotations

import streamlit.components.v1 as components


def embed_html(html: str, *, height: int = 0, width: int = 0) -> None:
    """Embed HTML in a minimal iframe.

    Scripts target ``window.parent`` (Streamlit shell). ``st.html`` runs in the main
    document and can blank the app; ``st.iframe`` on Cloud 1.58+ was unreliable here.
    """
    components.html(html, height=height, width=width)
