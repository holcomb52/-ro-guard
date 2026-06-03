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


def embed_script(html: str) -> None:
    """Zero-size iframe for JS that must not affect page layout or scroll."""
    embed_html(html, height=0, width=0)


def ensure_sidebar_expanded() -> None:
    """Keep the desktop sidebar open so account/settings stay visible."""
    embed_script(
        """
        <script>
        (function () {
          function expandSidebar(doc) {
            if (!doc || !doc.body) return;
            var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            if (!sidebar) return;
            sidebar.style.setProperty("transform", "translateX(0)", "important");
            sidebar.style.setProperty("visibility", "visible", "important");
            sidebar.style.setProperty("opacity", "1", "important");
            sidebar.style.setProperty("min-width", "21rem", "important");
            sidebar.style.setProperty("width", "21rem", "important");
            sidebar.setAttribute("aria-expanded", "true");
            var toggle = doc.querySelector('[data-testid="collapsedControl"]')
              || doc.querySelector('[data-testid="stSidebarCollapsedControl"]');
            if (toggle && sidebar.getAttribute("aria-expanded") === "false") {
              toggle.click();
            }
          }
          function sweep() {
            try { expandSidebar(document); } catch (e) {}
            try { expandSidebar(window.parent.document); } catch (e) {}
          }
          sweep();
          setTimeout(sweep, 250);
          setTimeout(sweep, 1000);
        })();
        </script>
        """,
    )
