"""Subscription pricing and prospect ROI calculator for sales conversations."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

SALES_CONTACT_EMAIL = "holcomb52@yahoo.com"
SALES_CONTACT_LABEL = "Schedule a demo"


@dataclass(frozen=True)
class PricingPlan:
    plan_id: str
    name: str
    monthly: float | None
    annual: float | None
    tagline: str
    features: tuple[str, ...]
    badge: str
    featured: bool = False
    per_store_from: float | None = None


PRICING_PLANS: tuple[PricingPlan, ...] = (
    PricingPlan(
        plan_id="pilot",
        name="Pilot",
        monthly=149.0,
        annual=1490.0,
        tagline="Early adopter — prove ROI with your team",
        features=(
            "Single store",
            "Unlimited RO audits",
            "Claim Learning library",
            "Reporting & coaching dashboards",
            "Email support",
        ),
        badge="Limited availability",
    ),
    PricingPlan(
        plan_id="standard",
        name="Single Store",
        monthly=299.0,
        annual=2990.0,
        tagline="Full production — one rooftop",
        features=(
            "Everything in Pilot",
            "VIN recall checks",
            "Audit PDF exports",
            "Outcome tracking & ROI reporting",
            "Priority support",
        ),
        badge="Most popular",
        featured=True,
    ),
    PricingPlan(
        plan_id="group",
        name="Dealer Group",
        monthly=None,
        annual=None,
        per_store_from=199.0,
        tagline="2+ rooftops — volume pricing",
        features=(
            "Per-store pricing from $199/mo",
            "Shared Claim Learning library",
            "Group reporting roll-ups",
            "Onboarding & training",
            "Custom annual contract",
        ),
        badge="Contact for quote",
    ),
)


def plan_by_id(plan_id: str) -> PricingPlan:
    for plan in PRICING_PLANS:
        if plan.plan_id == plan_id:
            return plan
    return PRICING_PLANS[1]


def compute_sales_roi(
    *,
    monthly_claims: float,
    avg_claim_value: float,
    rejections_per_month: float,
    issue_reduction_pct: float,
    rework_cost_pct: float,
    minutes_saved_per_review: float,
    admin_hourly_rate: float,
    monthly_subscription: float,
    billing_annual: bool = False,
) -> dict:
    """Estimate monthly/annual value vs subscription for a prospect conversation."""
    monthly_claims = max(float(monthly_claims or 0), 0.0)
    avg_claim_value = max(float(avg_claim_value or 0), 0.0)
    rejections_per_month = max(float(rejections_per_month or 0), 0.0)
    issue_reduction_pct = max(min(float(issue_reduction_pct or 0), 100.0), 0.0)
    rework_cost_pct = max(min(float(rework_cost_pct or 0), 100.0), 0.0)
    minutes_saved_per_review = max(float(minutes_saved_per_review or 0), 0.0)
    admin_hourly_rate = max(float(admin_hourly_rate or 0), 0.0)
    monthly_subscription = max(float(monthly_subscription or 0), 0.0)

    rejections_avoided = rejections_per_month * (issue_reduction_pct / 100.0)
    rejection_savings = rejections_avoided * avg_claim_value * (rework_cost_pct / 100.0)
    time_savings = monthly_claims * (minutes_saved_per_review / 60.0) * admin_hourly_rate
    monthly_value = rejection_savings + time_savings
    monthly_net = monthly_value - monthly_subscription

    annual_subscription = (
        monthly_subscription * 10.0 if billing_annual else monthly_subscription * 12.0
    )
    annual_value = monthly_value * 12.0
    annual_net = annual_value - annual_subscription

    payback_months = (
        monthly_subscription / monthly_value if monthly_value > 0 else None
    )
    one_rejection_value = avg_claim_value * (rework_cost_pct / 100.0)
    months_one_rejection = (
        monthly_subscription / one_rejection_value if one_rejection_value > 0 else None
    )
    roi_pct = (
        (annual_net / annual_subscription * 100.0) if annual_subscription > 0 else 0.0
    )

    return {
        "monthly_claims": monthly_claims,
        "rejections_avoided": rejections_avoided,
        "rejection_savings": rejection_savings,
        "time_savings": time_savings,
        "monthly_value": monthly_value,
        "monthly_subscription": monthly_subscription,
        "monthly_net": monthly_net,
        "annual_value": annual_value,
        "annual_subscription": annual_subscription,
        "annual_net": annual_net,
        "payback_months": payback_months,
        "one_rejection_value": one_rejection_value,
        "months_one_rejection": months_one_rejection,
        "roi_pct": roi_pct,
        "billing_annual": billing_annual,
    }


def _store_defaults_from_reviews(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty:
        return None
    work = df.copy()
    if "created_at" in work.columns:
        work["created_at"] = pd.to_datetime(work["created_at"], errors="coerce")
        work = work.dropna(subset=["created_at"])
    if work.empty:
        return None

    span_days = max((work["created_at"].max() - work["created_at"].min()).days, 1)
    months = max(span_days / 30.0, 1.0)
    monthly_claims = len(work) / months

    claim_col = work.get("total_claim_value", pd.Series(dtype=float))
    avg_claim = float(pd.to_numeric(claim_col, errors="coerce").fillna(0).mean())

    rejected = pd.to_numeric(work.get("rejected", 0), errors="coerce").fillna(0)
    rejections_per_month = float(rejected.sum()) / months

    return {
        "monthly_claims": round(max(monthly_claims, 1.0), 1),
        "avg_claim_value": round(max(avg_claim, 100.0), 0),
        "rejections_per_month": round(max(rejections_per_month, 0.0), 1),
    }


def _format_months(value: float | None) -> str:
    if value is None or value <= 0:
        return "—"
    if value < 1.0:
        return f"{value * 30:.0f} days"
    return f"{value:.1f} months"


def _render_pricing_cards(selected_plan_id: str) -> str:
    cols = st.columns(len(PRICING_PLANS))
    for col, plan in zip(cols, PRICING_PLANS):
        with col:
            featured = " pricing-card-featured" if plan.featured else ""
            selected = " pricing-card-selected" if plan.plan_id == selected_plan_id else ""
            if plan.monthly is not None:
                price_html = (
                    f'<div class="pricing-price">${plan.monthly:,.0f}'
                    f'<span>/mo</span></div>'
                    f'<div class="pricing-annual">${plan.annual:,.0f}/yr billed annually '
                    f"(2 months free)</div>"
                )
            else:
                price_html = (
                    f'<div class="pricing-price">From ${plan.per_store_from:,.0f}'
                    f'<span>/store/mo</span></div>'
                    f'<div class="pricing-annual">Custom annual contracts</div>'
                )
            features_html = "".join(f"<li>{item}</li>" for item in plan.features)
            st.markdown(
                f"""
                <div class="pricing-card{featured}{selected}">
                    <div class="pricing-badge">{plan.badge}</div>
                    <div class="pricing-name">{plan.name}</div>
                    <div class="pricing-tagline">{plan.tagline}</div>
                    {price_html}
                    <ul class="pricing-features">{features_html}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
    return selected_plan_id


def _sales_pitch_text(metrics: dict, plan: PricingPlan) -> str:
    plan_label = plan.name
    sub = metrics["monthly_subscription"]
    return (
        f"RO Shield — {plan_label} Plan ROI Estimate\n"
        f"Monthly subscription: ${sub:,.0f}\n"
        f"Estimated monthly value: ${metrics['monthly_value']:,.0f}\n"
        f"Estimated annual net: ${metrics['annual_net']:,.0f}\n"
        f"Payback: {_format_months(metrics['payback_months'])}\n"
        f"One avoided rejection (~${metrics['one_rejection_value']:,.0f}) "
        f"pays for {_format_months(metrics['months_one_rejection'])}.\n"
        f"Contact: {SALES_CONTACT_EMAIL}"
    )


def render_pricing_roi_page(*, reviews_df: pd.DataFrame | None = None) -> None:
    st.header("Pricing & ROI")
    st.caption(
        "Use this page in dealer conversations — show subscription options and estimate "
        "payback from fewer rejections and faster warranty audits."
    )

    calc_tab, plans_tab = st.tabs(["ROI Calculator", "Subscription Plans"])

    with plans_tab:
        st.markdown("### Subscription Plans")
        st.caption("All plans include unlimited RO audits for the subscribed store.")
        _render_pricing_cards("standard")
        st.markdown(
            f"""
            <div class="section-card pricing-contact-card">
                <strong>{SALES_CONTACT_LABEL}</strong> — email
                <a href="mailto:{SALES_CONTACT_EMAIL}">{SALES_CONTACT_EMAIL}</a>
                for pilot onboarding, multi-store quotes, or a live walkthrough.
            </div>
            """,
            unsafe_allow_html=True,
        )

    with calc_tab:
        store_defaults = _store_defaults_from_reviews(reviews_df) if reviews_df is not None else None

        top_left, top_right = st.columns([2, 1])
        with top_left:
            st.markdown("### ROI Calculator")
            st.caption(
                "Adjust assumptions for the store you are talking to. "
                "Defaults are conservative industry estimates."
            )
        with top_right:
            if store_defaults and st.button(
                "Use my store's data",
                key="pricing_seed_store",
                use_container_width=True,
            ):
                st.session_state["pricing_monthly_claims"] = float(store_defaults["monthly_claims"])
                st.session_state["pricing_avg_claim"] = float(store_defaults["avg_claim_value"])
                st.session_state["pricing_rejections"] = float(store_defaults["rejections_per_month"])
                st.rerun()

        plan_choice = st.selectbox(
            "Subscription plan",
            options=[p.plan_id for p in PRICING_PLANS if p.monthly is not None],
            format_func=lambda pid: plan_by_id(pid).name,
            index=1,
            key="pricing_plan_choice",
        )
        selected_plan = plan_by_id(plan_choice)
        billing_annual = st.toggle(
            "Bill annually (2 months free)",
            value=True,
            key="pricing_bill_annual",
        )
        monthly_sub = (
            selected_plan.annual / 10.0
            if billing_annual and selected_plan.annual
            else selected_plan.monthly or 299.0
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            monthly_claims = st.number_input(
                "Warranty claims audited per month",
                min_value=1.0,
                max_value=500.0,
                value=float(st.session_state.get("pricing_monthly_claims", 45.0)),
                step=1.0,
                key="pricing_monthly_claims",
            )
            avg_claim_value = st.number_input(
                "Average claim value ($)",
                min_value=50.0,
                max_value=25000.0,
                value=float(st.session_state.get("pricing_avg_claim", 1200.0)),
                step=50.0,
                key="pricing_avg_claim",
            )
        with c2:
            rejections_per_month = st.number_input(
                "Rejections / returns per month (today)",
                min_value=0.0,
                max_value=50.0,
                value=float(st.session_state.get("pricing_rejections", 3.0)),
                step=0.5,
                key="pricing_rejections",
            )
            issue_reduction_pct = st.slider(
                "Est. reduction in bad submissions with RO Shield (%)",
                min_value=10,
                max_value=80,
                value=40,
                step=5,
                key="pricing_issue_reduction",
            )
        with c3:
            rework_cost_pct = st.slider(
                "Est. cost of a rejection (% of claim value)",
                min_value=20,
                max_value=100,
                value=50,
                step=5,
                key="pricing_rework_pct",
                help="Includes rework labor, parts, admin time, and delayed payment.",
            )
            minutes_saved = st.slider(
                "Minutes saved per audit vs manual review",
                min_value=5,
                max_value=45,
                value=15,
                step=1,
                key="pricing_minutes_saved",
            )
            hourly_rate = st.number_input(
                "Warranty admin loaded hourly cost ($)",
                min_value=20.0,
                max_value=100.0,
                value=38.0,
                step=1.0,
                key="pricing_hourly_rate",
            )

        metrics = compute_sales_roi(
            monthly_claims=monthly_claims,
            avg_claim_value=avg_claim_value,
            rejections_per_month=rejections_per_month,
            issue_reduction_pct=float(issue_reduction_pct),
            rework_cost_pct=float(rework_cost_pct),
            minutes_saved_per_review=float(minutes_saved),
            admin_hourly_rate=float(hourly_rate),
            monthly_subscription=float(monthly_sub),
            billing_annual=billing_annual,
        )

        st.markdown(
            f"""
            <div class="hero">
                <h1>${metrics["monthly_value"]:,.0f}<span style="font-size:22px;color:#93c5fd;"> / month</span></h1>
                <p>Estimated value from {metrics["rejections_avoided"]:.1f} fewer rejections and audit time saved —
                vs ${metrics["monthly_subscription"]:,.0f}/mo subscription</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Est. Annual Net", f"${metrics['annual_net']:,.0f}")
        m2.metric("Payback Period", _format_months(metrics["payback_months"]))
        m3.metric(
            "One Rejection Pays For",
            _format_months(metrics["months_one_rejection"]),
            help=f"Based on ~${metrics['one_rejection_value']:,.0f} estimated cost per rejection.",
        )
        m4.metric("Annual ROI", f"{metrics['roi_pct']:,.0f}%")

        b1, b2, b3 = st.columns(3)
        b1.metric("Rejection Savings / mo", f"${metrics['rejection_savings']:,.0f}")
        b2.metric("Labor Savings / mo", f"${metrics['time_savings']:,.0f}")
        b3.metric("Subscription / mo", f"${metrics['monthly_subscription']:,.0f}")

        st.markdown("### Sales talking points")
        st.info(
            f"**Headline:** At ${avg_claim_value:,.0f} average claim value, preventing "
            f"**one rejection** covers about **{_format_months(metrics['months_one_rejection'])}** "
            f"of the **{selected_plan.name}** plan (${metrics['monthly_subscription']:,.0f}/mo).\n\n"
            f"**Conservative case:** If RO Shield helps avoid even "
            f"**{metrics['rejections_avoided']:.1f} rejections per month** and saves "
            f"**{minutes_saved:.0f} minutes** per audit, estimated net value is "
            f"**${metrics['monthly_net']:,.0f}/month** after subscription.\n\n"
            f"**Annual:** ${metrics['annual_value']:,.0f} estimated value vs "
            f"${metrics['annual_subscription']:,.0f} subscription "
            f"({'annual billing' if billing_annual else 'monthly billing'})."
        )

        with st.expander("Copy ROI summary for email or proposal"):
            pitch = _sales_pitch_text(metrics, selected_plan)
            st.code(pitch, language=None)
            st.caption("Paste into an email, proposal, or dealer group spreadsheet.")

        if store_defaults:
            st.caption(
                f"Your store averages ~{store_defaults['monthly_claims']:.0f} audits/mo, "
                f"${store_defaults['avg_claim_value']:,.0f} avg claim, "
                f"~{store_defaults['rejections_per_month']:.1f} rejections/mo — "
                "click **Use my store's data** to pre-fill."
            )
