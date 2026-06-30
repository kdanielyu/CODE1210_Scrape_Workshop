"""
Scraper — Home
"""

import os
from typing import Callable

import googlemaps
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

import core.storage as storage
from core.models import SearchJob
from core.runner import launch
from scrapers.google_places import PLACE_TYPE_LABELS
from utils import (
    DARK, INK, LIME, MUTED, SOURCE_CONFIG,
    inject_css, source_badge, sp, style_plotly,
)

load_dotenv()
storage.init_db()

st.set_page_config(
    page_title="Scraper",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@st.cache_resource
def _gmaps():
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    return googlemaps.Client(key=key) if key else None


@st.cache_data(ttl=30, show_spinner=False)
def _get_suggestions(text: str) -> list[str]:
    """Return up to 5 Google Places autocomplete suggestions for *text*."""
    client = _gmaps()
    if not client or not text or len(text) < 2:
        return []
    try:
        results = client.places_autocomplete(text, types=["geocode"])
        return [r["description"] for r in results[:5]]
    except Exception:
        return []


def geocode(loc: str) -> tuple[float, float]:
    client = _gmaps()
    if client is None:
        raise EnvironmentError("GOOGLE_MAPS_API_KEY is not configured in .env")
    res = client.geocode(loc)
    if not res:
        raise ValueError(
            f"Could not geocode '{loc}'. Try suburb + city, e.g. 'Newtown, Sydney NSW'."
        )
    g = res[0]["geometry"]["location"]
    return g["lat"], g["lng"]


def _build_scrapers(sources: list[str]) -> tuple[list[Callable], list[str]]:
    scrapers, warns = [], []
    mapping = {
        "Google Places": ("scrapers.google_places", "GooglePlacesScraper"),
        "Mastodon":      ("scrapers.mastodon",       "MastodonScraper"),
    }
    for label in sources:
        mod, cls = mapping[label]
        try:
            m = __import__(mod, fromlist=[cls])
            scrapers.append(getattr(m, cls)())
        except Exception as e:
            warns.append(f"{label} — {e}")
    return scrapers, warns


def stat_card(col, label: str, value: str, sub: str) -> None:
    with col:
        with st.container(border=True):
            st.markdown(
                f'<span class="sc-label">{label}</span>'
                f'<span class="sc-value">{value}</span>'
                f'<span class="sc-sub">{sub}</span>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Aggregate data
# ---------------------------------------------------------------------------

all_jobs     = storage.get_all_jobs()
done_jobs    = [j for j in all_jobs if j["status"] == "completed"]
running_jobs = [j for j in all_jobs if j["status"] == "running"]

places_all  = storage.get_places_df()
reviews_all = storage.get_reviews_df()
posts_all   = storage.get_social_posts_df()

n_places  = len(places_all)
n_reviews = len(reviews_all)
n_posts   = len(posts_all)
n_total   = n_places + n_reviews + n_posts


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

h_left, h_right = st.columns([4, 1])
with h_left:
    st.markdown("# Scraper")
    st.markdown(
        f'<p style="color:{MUTED};font-size:0.93rem;margin-top:0.25rem;">Collect reviews, '
        f'ratings &amp; community signals across Australian locations.</p>',
        unsafe_allow_html=True,
    )
with h_right:
    is_active = bool(running_jobs)
    dot_color = LIME if is_active else "#C0C4BA"
    label     = f"{len(running_jobs)} running" if is_active else "Idle"
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;align-items:center;'
        f'gap:7px;margin-top:1rem;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{dot_color};'
        f'display:inline-block;'
        f'{"box-shadow:0 0 0 4px rgba(16,185,129,0.22);" if is_active else ""}'
        f'"></span>'
        f'<span style="font-weight:600;font-size:0.88rem;color:{INK};">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

sp("sm")

# ---------------------------------------------------------------------------
# Stat cards
# ---------------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
stat_card(c1, "Total records", f"{n_total:,}", f"across {len(all_jobs)} job{'s' if len(all_jobs) != 1 else ''}")
stat_card(c2, "Places",        f"{n_places:,}",  "businesses & POIs")
stat_card(c3, "Reviews",       f"{n_reviews:,}", "ratings & comments")
stat_card(c4, "Social posts",  f"{n_posts:,}",   "community discussions")

sp("md")

# ---------------------------------------------------------------------------
# Launch form  +  Status card
# ---------------------------------------------------------------------------

col_form, col_status = st.columns([3, 2], gap="large")

# ── Launch form ──────────────────────────────────────────────────────────────
with col_form:
    with st.container(border=True):
        st.markdown("### New scraping job")
        sp("xs")

        location_typed = st.text_input(
            "Location",
            placeholder="e.g.  Newtown, Sydney NSW  ·  Fitzroy, Melbourne  ·  -33.90, 151.18",
            key="location_typed",
        )
        suggestions = _get_suggestions(location_typed)
        if suggestions:
            loc_pick = st.selectbox(
                "loc_ac",
                options=[""] + suggestions,
                format_func=lambda x: "— keep typed value —" if x == "" else "📍 " + x,
                label_visibility="collapsed",
                key="loc_ac_select",
            )
            location_input = loc_pick if loc_pick else location_typed
        else:
            location_input = location_typed

        radius_m = st.select_slider(
            "Search radius",
            options=[500, 1_000, 1_500, 2_000, 3_000, 5_000, 8_000, 10_000],
            value=1_500,
            format_func=lambda v: f"{v / 1000:g} km" if v >= 1000 else f"{v} m",
        )

        st.markdown("**Data sources**")
        sc1, sc2 = st.columns(2)
        use_google   = sc1.checkbox("📍 Google Places", value=True)
        use_mastodon = sc2.checkbox("🐘 Mastodon",       value=True)

        selected_sources = (
            (["Google Places"] if use_google   else [])
            + (["Mastodon"]    if use_mastodon else [])
        )

        with st.expander("⚙️  Scrape settings — types & limits"):
            st.markdown("**Place types** *(Google Places)*")
            default_types = ["restaurant", "cafe", "bar", "park", "tourist_attraction"]
            selected_type_labels = st.multiselect(
                "Place types",
                options=list(PLACE_TYPE_LABELS.values()),
                default=[PLACE_TYPE_LABELS[t] for t in default_types],
                label_visibility="collapsed",
                help="Which categories to collect. Leave empty to scrape all types.",
            )
            label_to_key = {v: k for k, v in PLACE_TYPE_LABELS.items()}
            selected_types = [label_to_key[l] for l in selected_type_labels]

            sp("xs")
            st.markdown("**Records per source** *(min – max)*")
            min_results, max_results = st.slider(
                "Records per source",
                min_value=20, max_value=1000,
                value=(50, 300), step=10,
                label_visibility="collapsed",
                help="Minimum target and hard cap per source.",
            )
            st.caption(
                f"Collect at least **{min_results}** and at most **{max_results}** "
                f"records per source."
            )

        sp("xs")
        start = st.button(
            "Start Scraping",
            type="primary",
            disabled=not location_input.strip() or not selected_sources,
            width="stretch",
        )


# ── Status card (auto-refreshes while running) ───────────────────────────────
with col_status:
    @st.fragment(run_every=2)
    def _status_panel() -> None:
        jid = st.session_state.get("active_job_id")
        job = storage.get_job(jid) if jid else None

        if job is None:
            if done_jobs:
                last = done_jobs[0]
                st.markdown(
                    f'<div class="uds-dark">'
                    f'<span style="font-size:0.67rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.1em;color:{LIME};">Last completed</span>'
                    f'<div style="font-size:1.15rem;font-weight:700;margin:6px 0 2px;'
                    f'line-height:1.25;color:#FFF;">{last["location"]}</div>'
                    f'<div style="font-size:0.8rem;color:#A4A8A2;margin-bottom:14px;">{last["sources"]}</div>'
                    f'<div style="font-size:2.4rem;font-weight:800;color:{LIME};line-height:1;">'
                    f'{last["record_count"]:,}</div>'
                    f'<div style="font-size:0.77rem;color:#8A8E86;margin-top:4px;">records collected</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="uds-lime">'
                    f'<span style="font-size:0.67rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.1em;opacity:0.65;">Get started</span>'
                    f'<div style="font-size:1.45rem;font-weight:800;margin:8px 0 6px;'
                    f'line-height:1.2;color:{DARK};">Take your urban research to the next level</div>'
                    f'<div style="font-size:0.87rem;color:{DARK};opacity:0.75;">'
                    f'Enter a location and click <strong>Start Scraping</strong>.</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            return

        status = job["status"]
        dot = {
            "running":   LIME,
            "completed": "#7CE38B",
            "failed":    "#FF7878",
            "pending":   "#9FA3A0",
        }.get(status, "#9FA3A0")
        label = {
            "running":   "Scraping in progress…",
            "completed": "Completed",
            "failed":    "Failed",
            "pending":   "Queued",
        }.get(status, status)

        st.markdown(
            f'<div class="uds-dark">'
            f'<span style="font-size:0.67rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.1em;color:{LIME};">Active job</span>'
            f'<div style="font-size:1.15rem;font-weight:700;margin:6px 0 2px;'
            f'line-height:1.25;color:#FFF;">{job["location"]}</div>'
            f'<div style="font-size:0.8rem;color:#A4A8A2;margin-bottom:14px;">{job["sources"]}</div>'
            f'<div style="font-size:2.4rem;font-weight:800;color:{LIME};line-height:1;">'
            f'{job["record_count"]:,}</div>'
            f'<div style="font-size:0.77rem;color:#8A8E86;margin-top:4px;margin-bottom:14px;">'
            f'records collected</div>'
            f'<div style="display:flex;align-items:center;gap:7px;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{dot};'
            f'display:inline-block;flex-shrink:0;"></span>'
            f'<span style="color:{dot};font-weight:600;font-size:0.83rem;">{label}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        sp("xs")
        if status == "completed":
            if st.button("View results →", type="primary", width="stretch"):
                st.switch_page("pages/1_Results.py")
        elif status == "failed":
            st.error(job.get("error") or "Unknown error")
        else:
            st.caption("Refreshing every 2 s")

    _status_panel()


# ---------------------------------------------------------------------------
# Handle launch
# ---------------------------------------------------------------------------

if start:
    with st.spinner("Geocoding location…"):
        try:
            lat, lng = geocode(location_input.strip())
        except Exception as exc:
            st.error(str(exc))
            st.stop()

    scrapers, warns = _build_scrapers(selected_sources)
    for w in warns:
        st.warning(f"Skipping — {w}")
    if not scrapers:
        st.error("No valid scrapers could be initialised. Check API keys in .env")
        st.stop()

    job = SearchJob(
        location=location_input.strip(),
        latitude=lat, longitude=lng,
        radius_m=radius_m,
        sources=", ".join(selected_sources),
        place_types=", ".join(selected_types),
        min_results=min_results,
        max_results=max_results,
    )
    launch(job, scrapers)
    st.session_state["active_job_id"] = job.id
    st.rerun()


# ---------------------------------------------------------------------------
# Records by source chart
# ---------------------------------------------------------------------------

sp("sm")
with st.container(border=True):
    st.markdown("### Records by source")
    if n_total == 0:
        st.caption("No data yet — run a job to populate this chart.")
    else:
        rows = []
        for src_key, cfg in SOURCE_CONFIG.items():
            cnt = (
                int((places_all["source"]  == src_key).sum() if not places_all.empty  else 0)
                + int((reviews_all["source"] == src_key).sum() if not reviews_all.empty else 0)
                + int((posts_all["source"]   == src_key).sum() if not posts_all.empty   else 0)
            )
            if cnt:
                rows.append({"Source": cfg["label"], "Records": cnt, "color": cfg["color"]})
        if rows:
            fig = px.bar(
                pd.DataFrame(rows), x="Source", y="Records", text="Records",
                color="Source",
                color_discrete_map={r["Source"]: r["color"] for r in rows},
            )
            fig.update_traces(textposition="outside", marker_line_width=0, width=0.45)
            style_plotly(fig)
            fig.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Recent jobs table
# ---------------------------------------------------------------------------

sp("sm")
with st.container(border=True):
    st.markdown("### Recent jobs")
    if not all_jobs:
        st.caption("No scraping jobs yet. Launch one above to get started.")
    else:
        _STATUS_ICON = {
            "completed": "✅ Completed", "running": "⏳ Running",
            "failed": "❌ Failed",       "pending": "📋 Pending",
        }
        _COL_W = [0.8, 2.5, 1.8, 1.4, 0.8, 1.8, 0.55]

        # Header row
        hcols = st.columns(_COL_W)
        for hc, label in zip(hcols, ["Job ID", "Location", "Sources", "Status", "Records", "Started", ""]):
            with hc:
                st.markdown(
                    f'<span style="font-size:0.68rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.09em;color:{MUTED};">{label}</span>',
                    unsafe_allow_html=True,
                )
        st.markdown('<hr style="margin:3px 0 4px;border-color:rgba(16,52,40,0.08)">', unsafe_allow_html=True)

        for job in all_jobs:
            rcols = st.columns(_COL_W)
            vals = [
                job["id"][:8],
                job["location"],
                job["sources"],
                _STATUS_ICON.get(job["status"], job["status"]),
                f"{job['record_count']:,}",
                (job["created_at"] or "")[:16].replace("T", " "),
            ]
            for rc, val in zip(rcols[:-1], vals):
                with rc:
                    st.caption(val)
            with rcols[-1]:
                with st.popover("🗑️", use_container_width=False):
                    st.markdown(
                        f"**Delete this job?**  \n"
                        f"_{job['location']}_ — {job['record_count']:,} records will be removed."
                    )
                    if st.button("Yes, delete", type="primary", key=f"del_{job['id']}"):
                        storage.delete_job(job["id"])
                        if st.session_state.get("active_job_id") == job["id"]:
                            st.session_state.pop("active_job_id", None)
                        st.rerun()

        sp("xs")
        st.caption("Use the sidebar: **Results** to explore a job · **Compare** to benchmark "
                   "locations · **Export** to download data.")
