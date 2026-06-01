"""Chart helpers for RO Shield dashboards and PDF exports."""

from __future__ import annotations

import io
import os
from typing import Optional

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# RO Shield palette
COLORS = {
    "stop": "#e74c3c",
    "review": "#f1c40f",
    "ready": "#2ecc71",
    "primary": "#3b96ff",
    "secondary": "#8cc4ff",
    "muted": "#95a5a6",
    "bg": "#0b1118",
    "text": "#f8fbff",
    "grid": "#2a3f5f",
}


def _prep_figure(figsize=None, *, compact: bool = False):
    if figsize is None:
        figsize = (4.2, 2.6) if compact else (5.5, 4.2)
    try:
        plt.style.use("dark_background")
    except (KeyError, OSError, ValueError):
        pass
    fig, ax = plt.subplots(figsize=figsize, facecolor=COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.patch.set_facecolor(COLORS["bg"])
    return fig, ax


def fig_to_png_bytes(fig, *, compact: bool = False) -> bytes:
    buf = io.BytesIO()
    dpi = 130 if compact else 160
    pad = 0.12 if compact else 0.3
    fig.savefig(
        buf,
        format="png",
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=pad,
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _pie_or_placeholder(ax, labels, values, title, colors, *, compact: bool = False):
    title_fs = 10 if compact else 12
    legend_fs = 7 if compact else 8
    pct_fs = 7 if compact else 8
    clean = [(label, val) for label, val in zip(labels, values) if val > 0]
    if not clean:
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center", color=COLORS["text"], fontsize=9)
        ax.set_title(title, color=COLORS["text"], fontsize=title_fs, pad=6)
        ax.axis("off")
        return
    labels, values = zip(*clean)
    wedges, _, autotexts = ax.pie(
        values,
        autopct=lambda pct: f"{pct:.0f}%" if pct >= 4 else "",
        startangle=90,
        colors=colors[: len(values)],
        textprops={"color": COLORS["text"], "fontsize": pct_fs},
        pctdistance=0.72,
    )
    if compact:
        ax.legend(
            wedges,
            labels,
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            frameon=False,
            fontsize=legend_fs,
            labelcolor=COLORS["text"],
        )
    else:
        ax.legend(
            wedges,
            labels,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.02),
            ncol=min(len(labels), 3),
            frameon=False,
            fontsize=legend_fs,
            labelcolor=COLORS["text"],
        )
    for autotext in autotexts:
        autotext.set_color("#081018")
        autotext.set_fontsize(pct_fs)
        autotext.set_weight("bold")
    ax.set_title(title, color=COLORS["text"], fontsize=title_fs, pad=6)


def audit_outcomes_pie(metrics: dict, *, compact: bool = False) -> bytes:
    fig, ax = _prep_figure(compact=compact)
    _pie_or_placeholder(
        ax,
        ["Do Not Submit", "Needs Review", "Ready"],
        [
            metrics.get("do_not_submit_count", 0),
            metrics.get("needs_review_count", 0),
            metrics.get("ready_count", 0),
        ],
        "Audit Outcomes",
        [COLORS["stop"], COLORS["review"], COLORS["ready"]],
        compact=compact,
    )
    return fig_to_png_bytes(fig, compact=compact)


def first_pass_pie(metrics: dict, *, compact: bool = False) -> bytes:
    fig, ax = _prep_figure(compact=compact)
    tracked = (
        metrics.get("first_pass_count", 0)
        + metrics.get("rejected_count", 0)
        + metrics.get("paid_after_rejection_count", 0)
    )
    other = max(0, metrics.get("review_count", 0) - tracked)
    _pie_or_placeholder(
        ax,
        ["First-Pass Paid", "Rejected", "Paid After Rejection", "Not Tracked"],
        [
            metrics.get("first_pass_count", 0),
            metrics.get("rejected_count", 0),
            metrics.get("paid_after_rejection_count", 0),
            other,
        ],
        "Submission Results",
        [COLORS["ready"], COLORS["stop"], COLORS["review"], COLORS["muted"]],
        compact=compact,
    )
    return fig_to_png_bytes(fig, compact=compact)


def issue_breakdown_pie(metrics: dict, *, compact: bool = False) -> bytes:
    fig, ax = _prep_figure(compact=compact)
    reviews = max(metrics.get("review_count", 0), 0)
    hard = metrics.get("hard_stop_count", 0)
    warn = metrics.get("warning_count", 0)
    clean = max(0, reviews - min(reviews, hard + warn))
    _pie_or_placeholder(
        ax,
        ["Hard Stops", "Warnings", "Clean Jobs"],
        [hard, warn, clean],
        "Issues Found",
        [COLORS["stop"], COLORS["review"], COLORS["ready"]],
        compact=compact,
    )
    return fig_to_png_bytes(fig, compact=compact)


def weekly_activity_chart(weekly: pd.DataFrame, *, compact: bool = False) -> Optional[bytes]:
    if weekly is None or weekly.empty:
        return None
    figsize = (4.2, 2.2) if compact else (7.5, 4.2)
    fig, ax = _prep_figure(figsize=figsize, compact=compact)
    x = range(len(weekly))
    width = 0.38
    ax.bar([i - width / 2 for i in x], weekly["reviews"], width=width, label="Reviews", color=COLORS["primary"])
    ax.bar([i + width / 2 for i in x], weekly["hard_stops"], width=width, label="Hard Stops", color=COLORS["stop"])
    ax.set_xticks(list(x))
    tick_fs = 6 if compact else 8
    title_fs = 9 if compact else 12
    ax.set_xticklabels(weekly["week"], rotation=35, ha="right", fontsize=tick_fs)
    ax.set_title("Reviews & Hard Stops by Week", color=COLORS["text"], fontsize=title_fs, pad=6)
    ax.grid(axis="y", color=COLORS["grid"], alpha=0.35)
    ax.legend(facecolor=COLORS["bg"], edgecolor=COLORS["grid"], labelcolor=COLORS["text"], fontsize=tick_fs)
    ax.tick_params(colors=COLORS["text"], labelsize=tick_fs)
    return fig_to_png_bytes(fig, compact=compact)


def advisor_hard_stops_chart(advisor_df: pd.DataFrame, limit: int = 8, *, compact: bool = False) -> Optional[bytes]:
    if advisor_df is None or advisor_df.empty:
        return None
    top = advisor_df.sort_values("hard_stops", ascending=False).head(limit)
    if top["hard_stops"].sum() <= 0:
        return None
    figsize = (4.2, 2.4) if compact else (7.5, 4.5)
    fig, ax = _prep_figure(figsize=figsize, compact=compact)
    y_labels = [str(name)[:18] for name in top["advisor"]]
    y_pos = range(len(y_labels))
    ax.barh(list(y_pos), top["hard_stops"], color=COLORS["primary"])
    ax.set_yticks(list(y_pos))
    tick_fs = 6 if compact else 8
    title_fs = 9 if compact else 12
    ax.set_yticklabels(y_labels, fontsize=tick_fs)
    ax.invert_yaxis()
    ax.set_title("Hard Stops by Advisor", color=COLORS["text"], fontsize=title_fs, pad=6)
    ax.grid(axis="x", color=COLORS["grid"], alpha=0.35)
    ax.tick_params(colors=COLORS["text"], labelsize=tick_fs)
    return fig_to_png_bytes(fig, compact=compact)


def hard_stop_rules_chart(rule_totals: pd.DataFrame, limit: int = 10, *, compact: bool = False) -> Optional[bytes]:
    """Horizontal bar chart of top audit rule findings."""
    if rule_totals is None or rule_totals.empty:
        return None
    count_col = "total_count" if "total_count" in rule_totals.columns else "count"
    top = rule_totals.sort_values(count_col, ascending=False).head(limit)
    if top[count_col].sum() <= 0:
        return None

    label_col = "rule_label" if "rule_label" in top.columns else "rule_key"
    figsize = (4.6, max(2.4, 0.35 * len(top))) if compact else (7.8, max(4.0, 0.42 * len(top)))
    fig, ax = _prep_figure(figsize=figsize, compact=compact)
    y_labels = [str(name)[:34] for name in top[label_col]]
    y_pos = range(len(y_labels))
    ax.barh(list(y_pos), top[count_col], color=COLORS["stop"])
    ax.set_yticks(list(y_pos))
    tick_fs = 6 if compact else 8
    title_fs = 9 if compact else 12
    ax.set_yticklabels(y_labels, fontsize=tick_fs)
    ax.invert_yaxis()
    ax.set_title("Hard Stop & Warning Breakdown", color=COLORS["text"], fontsize=title_fs, pad=6)
    ax.grid(axis="x", color=COLORS["grid"], alpha=0.35)
    ax.tick_params(colors=COLORS["text"], labelsize=tick_fs)
    return fig_to_png_bytes(fig, compact=compact)


def review_status_pie(df: pd.DataFrame, *, compact: bool = False) -> Optional[bytes]:
    if df is None or df.empty or "status" not in df.columns:
        return None
    status = df["status"].astype(str)
    stop = status.str.contains("DO NOT", case=False, na=False).sum()
    review = status.str.contains("NEEDS", case=False, na=False).sum()
    ready = status.str.contains("READY", case=False, na=False).sum()
    fig, ax = _prep_figure(compact=compact)
    _pie_or_placeholder(
        ax,
        ["Do Not Submit", "Needs Review", "Ready"],
        [stop, review, ready],
        "Review Status Mix",
        [COLORS["stop"], COLORS["review"], COLORS["ready"]],
        compact=compact,
    )
    return fig_to_png_bytes(fig, compact=compact)


def score_distribution_chart(df: pd.DataFrame, *, compact: bool = False) -> Optional[bytes]:
    if df is None or df.empty or "score" not in df.columns:
        return None
    scores = pd.to_numeric(df["score"], errors="coerce").dropna()
    if scores.empty:
        return None
    figsize = (4.2, 2.6) if compact else (7.0, 4.2)
    fig, ax = _prep_figure(figsize=figsize, compact=compact)
    bins = [0, 50, 70, 85, 100]
    labels = ["0-49", "50-69", "70-84", "85-100"]
    counts = pd.cut(scores, bins=bins, labels=labels, include_lowest=True).value_counts().sort_index()
    ax.bar(counts.index.astype(str), counts.values, color=[COLORS["stop"], COLORS["review"], COLORS["secondary"], COLORS["ready"]])
    title_fs = 9 if compact else 12
    tick_fs = 6 if compact else 8
    ax.set_title("Audit Score Distribution", color=COLORS["text"], fontsize=title_fs, pad=6)
    ax.grid(axis="y", color=COLORS["grid"], alpha=0.35)
    ax.tick_params(colors=COLORS["text"], labelsize=tick_fs)
    return fig_to_png_bytes(fig, compact=compact)
