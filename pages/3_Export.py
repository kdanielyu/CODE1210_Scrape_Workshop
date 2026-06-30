"""
Export & History — review all jobs, see source breakdown, and download data.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

import core.storage as storage
from utils import MUTED, SOURCE_CONFIG, inject_css, source_badge, sp, style_plotly

load_dotenv()
storage.init_db()

st.set_page_config(page_title="Export — Scraper", page_icon="📥", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown("# Export & History")
st.markdown(
    f'<p style="color:{MUTED};font-size:0.9rem;margin-top:0.25rem;">'
    f'Audit every job and download clean, source-labelled data for further analysis.</p>',
    unsafe_allow_html=True,
)
sp("sm")

all_jobs = storage.get_all_jobs()
if not all_jobs:
    st.info("No jobs yet. Run a scraping job from **Home** first.", icon="ℹ️")
    st.stop()

# ---------------------------------------------------------------------------
# Job history
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.markdown("### Job history")
    df = pd.DataFrame(all_jobs).copy()
    df["id_short"]     = df["id"].str[:8]
    df["created_at"]   = df["created_at"].str[:16]
    df["completed_at"] = df["completed_at"].fillna("—").str[:16]
    status_icon = {
        "completed": "✅ Completed", "running": "⏳ Running",
        "failed": "❌ Failed", "pending": "📋 Pending",
    }
    df["Status"] = df["status"].map(status_icon).fillna(df["status"])
    show = df[["id_short", "location", "sources", "Status",
               "record_count", "created_at", "completed_at"]].copy()
    show.columns = ["Job ID", "Location", "Sources", "Status", "Records", "Started", "Completed"]
    st.dataframe(show, width="stretch", hide_index=True,
                 height=min(60 + len(show) * 35, 380))

done_jobs = [j for j in all_jobs if j["status"] == "completed"]

# ---------------------------------------------------------------------------
# Source breakdown
# ---------------------------------------------------------------------------

if done_jobs:
    sp("sm")
    with st.container(border=True):
        st.markdown("### Source breakdown by job")
        rows = []
        for j in done_jobs:
            pl = storage.get_places_df(j["id"])
            rv = storage.get_reviews_df(j["id"])
            ps = storage.get_social_posts_df(j["id"])
            for src in ("google", "mastodon"):
                total = (
                    int((pl["source"] == src).sum() if not pl.empty else 0)
                    + int((rv["source"] == src).sum() if not rv.empty else 0)
                    + int((ps["source"] == src).sum() if not ps.empty else 0)
                )
                if total:
                    rows.append({"job": j["location"][:28],
                                 "Source": SOURCE_CONFIG[src]["label"],
                                 "records": total})
        if rows:
            sdf = pd.DataFrame(rows)
            fig = px.bar(sdf, x="job", y="records", color="Source", barmode="group",
                         color_discrete_map={SOURCE_CONFIG[s]["label"]: SOURCE_CONFIG[s]["color"]
                                             for s in SOURCE_CONFIG})
            style_plotly(fig)
            fig.update_layout(height=320, xaxis_title="", yaxis_title="Records")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Export panel
# ---------------------------------------------------------------------------

sp("sm")
with st.container(border=True):
    st.markdown("### Export data")

    if not done_jobs:
        st.caption("No completed jobs to export yet.")
        st.stop()

    job_opts = {
        f"{j['location']}  ·  {j['created_at'][:16]}  ({j['record_count']:,} records)": j["id"]
        for j in done_jobs
    }
    selected_labels = st.multiselect(
        "Jobs to export",
        options=list(job_opts.keys()),
        default=[list(job_opts.keys())[0]],
        help="Select multiple jobs to merge their data into a single file.",
    )
    selected_ids = [job_opts[l] for l in selected_labels]

    c1, c2 = st.columns(2)
    with c1:
        fmt = st.radio("Format", ["CSV", "XLSX", "JSON"], horizontal=True)
    with c2:
        src_filter = st.multiselect(
            "Limit to sources",
            options=["google", "mastodon"],
            default=["google", "mastodon"],
            format_func=lambda s: SOURCE_CONFIG[s]["label"],
        )

    fmt_lower = fmt.lower()
    mime = {
        "csv":  "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
    }

    def generate(job_ids, fmt, srcs) -> bytes:
        import io, json
        places  = pd.concat([storage.get_places_df(j)       for j in job_ids], ignore_index=True)
        reviews = pd.concat([storage.get_reviews_df(j)      for j in job_ids], ignore_index=True)
        posts   = pd.concat([storage.get_social_posts_df(j) for j in job_ids], ignore_index=True)

        def flt(d):
            if d.empty or "source" not in d.columns or not srcs:
                return d
            return d[d["source"].isin(srcs)]

        def label(d):
            if d.empty or "source" not in d.columns:
                return d
            d = d.copy()
            d.insert(d.columns.get_loc("source") + 1, "source_label",
                     d["source"].map(lambda s: SOURCE_CONFIG.get(s, {}).get("label", s)))
            return d

        sheets = {"places": label(flt(places)),
                  "reviews": label(flt(reviews)),
                  "social_posts": label(flt(posts))}

        if fmt == "csv":
            frames = []
            for name, d in sheets.items():
                if not d.empty:
                    d = d.copy(); d.insert(0, "_table", name); frames.append(d)
            merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            return merged.to_csv(index=False).encode("utf-8")
        if fmt == "xlsx":
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                for name, d in sheets.items():
                    if not d.empty:
                        d.to_excel(w, sheet_name=name, index=False)
            return buf.getvalue()
        if fmt == "json":
            return json.dumps({k: v.to_dict("records") for k, v in sheets.items()},
                              indent=2, default=str).encode("utf-8")
        return b""

    if st.button("Prepare export", type="primary", disabled=not selected_ids):
        with st.spinner(f"Generating {fmt}…"):
            try:
                data = generate(selected_ids, fmt_lower, src_filter)
                locs = "+".join(
                    next(j["location"] for j in done_jobs if j["id"] == jid)
                    .replace(" ", "_").replace(",", "")
                    for jid in selected_ids[:2]
                )
                date = next(j["created_at"][:10] for j in done_jobs if j["id"] == selected_ids[0])
                fname = f"urban_data_{locs}_{date}.{fmt_lower}"

                st.download_button(
                    f"⬇️  Download {fmt}  ({len(data):,} bytes)",
                    data=data, file_name=fname, mime=mime[fmt_lower],
                )
                st.success("Export ready — click above to download.")

                p = sum(len(storage.get_places_df(j))       for j in selected_ids)
                r = sum(len(storage.get_reviews_df(j))      for j in selected_ids)
                s = sum(len(storage.get_social_posts_df(j)) for j in selected_ids)
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric("Places", f"{p:,}")
                cc2.metric("Reviews", f"{r:,}")
                cc3.metric("Social posts", f"{s:,}")
            except Exception as exc:
                st.error(f"Export failed: {exc}")
