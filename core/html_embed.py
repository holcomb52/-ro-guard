"""Isolated HTML/JS embeds (iframe) for scripts that must not run in the main app DOM."""

from __future__ import annotations

import streamlit.components.v1 as components


def embed_html(
    html: str,
    *,
    height: int | None = 0,
    width: int | None = None,
) -> None:
    """Embed HTML in an iframe.

    Scripts target ``window.parent`` (Streamlit shell). ``st.html`` runs in the main
    document and can blank the app.

    Pass ``height=0, width=0`` for invisible script embeds. Omit ``width`` (or pass
    ``None``) for visible widgets like Copy buttons so the iframe fills the column.
    """
    kwargs: dict[str, int] = {}
    if height is not None:
        kwargs["height"] = height
    if width is not None:
        kwargs["width"] = width
    components.html(html, **kwargs)
