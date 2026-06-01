"""Read-only Supabase access for JARVIS — separate from RO Guard app code."""

from __future__ import annotations

import pandas as pd

from jarvis.config import REVIEW_LIMIT, SUPABASE_KEY, SUPABASE_URL
from jarvis.review_snapshot import compute_roi_metrics, load_reviews, normalize_reviews_dataframe


def get_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_review_dataframe():
    client = get_client()
    if client is None:
        return pd.DataFrame(), "Supabase is not configured. Copy RO Guard `.env` or set SUPABASE_URL + SUPABASE_KEY."
    try:
        df = load_reviews(client, limit=REVIEW_LIMIT)
    except Exception as exc:
        return pd.DataFrame(), f"Could not load reviews: {exc}"
    if df.empty:
        return df, "No reviews found in Supabase yet."
    return normalize_reviews_dataframe(df), ""


def load_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    return compute_roi_metrics(df)
