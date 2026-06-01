"""Isolated HTML/JS embeds (iframe) for scripts that must not run in the main app DOM."""

from __future__ import annotations

import streamlit.components.v1 as components


def embed_html(html: str, *, height: int = 0, width: int = 0) -> None:
    """Embed HTML in a zero-size iframe.

    st.html runs in the main document; our chrome/auth/copy scripts expect an iframe
    and can blank the app if injected with unsafe_allow_javascript on st.html.
    components.v1.html remains the supported path for this until st.iframe is available.
    """
    components.html(html, height=height, width=width)
