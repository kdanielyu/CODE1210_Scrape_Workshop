"""
Results — overview-first analysis of one scraping job.

Structure:
  1. Job selector + metadata summary bar
  2. KPI row
  3. Map (full width)
  4. Highlights: top-rated · most-reviewed · top discussions/lowest-rated
  5. Per-source deep-dive tabs (charts, keyword analysis, data tables)
Filters live in the floating sidebar and apply everywhere.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

import core.storage as storage
from utils import (
    BG, DARK, INK, LIME, MUTED, SENTIMENT_CONFIG, SOURCE_CONFIG,
    extract_keywords, inject_css, keyword_chips, ranked_list,
    source_badge, sp, style_plotly, summary_bar,
)

load_dotenv()
storage.init_db()

st.set_page_config(page_title="Results — Scraper", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown("# Results")
st.markdown(
    f'<p style="color:{MUTED};font-size:0.9rem;margin-top:0.25rem;">'
    f'Explore everything collected for a location — places, reviews, sentiment and discussion.</p>',
    unsafe_allow_html=True,
)
sp("sm")

all_jobs  = storage.get_all_jobs()
done_jobs = [j for j in all_jobs if j["status"] == "completed"]

if not done_jobs:
    st.info("No completed jobs yet. Head to **Home** and run a scraping job first.", icon="ℹ️")
    st.stop()

job_labels = {
    f"{j['location']}  ·  {j['created_at'][:16]}  ({j['record_count']:,} records)": j["id"]
    for j in done_jobs
}
sel_col, del_col = st.columns([5, 1])
with sel_col:
    sel = st.selectbox("Select scraping job", list(job_labels.keys()), label_visibility="collapsed")
job_id = job_labels[sel]
job = next(j for j in done_jobs if j["id"] == job_id)

with del_col:
    with st.popover("🗑️ Delete scrape", use_container_width=True):
        st.markdown(
            f"**Delete this scrape?**  \n"
            f"_{job['location']}_ — **{job['record_count']:,} records** will be permanently removed."
        )
        if st.button("Yes, delete", type="primary", key="del_job_confirm"):
            storage.delete_job(job_id)
            st.session_state.pop("active_job_id", None)
            st.rerun()

places_df  = storage.get_places_df(job_id)
reviews_df = storage.get_reviews_df(job_id)
posts_df   = storage.get_social_posts_df(job_id)

present_sources = set()
for df in (places_df, reviews_df, posts_df):
    if not df.empty and "source" in df.columns:
        present_sources.update(df["source"].unique())


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### ⚙️ Filters")
    st.divider()

    st.markdown("**Data source**")
    src_options = {
        "google":   "📍 Google Places",
        "mastodon": "🐘 Mastodon",
    }
    filter_sources = [
        k for k, lab in src_options.items()
        if k in present_sources and st.checkbox(lab, value=True, key=f"src_{k}")
    ]
    st.divider()

    st.markdown("**Data type**")
    show_places  = st.checkbox("Places / Businesses", value=True, key="show_places")
    show_reviews = st.checkbox("Reviews",             value=True, key="show_reviews")
    show_posts   = st.checkbox("Social posts",        value=True, key="show_posts")
    st.divider()

    filter_min_rating = st.slider("Minimum rating", 1.0, 5.0, 1.0, 0.5, format="%.1f ⭐")
    st.divider()

    st.markdown("**Sentiment**")
    sent_opts = {"positive": "😊 Positive", "neutral": "😐 Neutral", "negative": "😟 Negative"}
    filter_sentiments = [
        k for k, lab in sent_opts.items()
        if st.checkbox(lab, value=True, key=f"sent_{k}")
    ]
    st.divider()

    filter_category = st.text_input("Category contains", placeholder="restaurant, park…")
    filter_keyword  = st.text_input("Keyword search", placeholder="search text / title…")
    st.divider()

    social_present = present_sources & {"mastodon"}
    if social_present:
        score_label = "Min likes/upvotes"
        filter_min_score = st.number_input(score_label, min_value=0, value=0, step=10)
    else:
        filter_min_score = 0

    filter_date_from = st.date_input("Published from", value=None, key="date_from")
    filter_date_to   = st.date_input("Published to",   value=None, key="date_to")
    st.divider()

    if st.button("Reset filters", width="stretch"):
        for k in list(st.session_state.keys()):
            if k.startswith(("src_", "show_", "sent_", "date_")):
                del st.session_state[k]
        st.rerun()


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def apply_filters(df, *, reviews=False, posts=False, places=False):
    if df.empty:
        return df
    d = df.copy()
    if filter_sources and "source" in d.columns:
        d = d[d["source"].isin(filter_sources)]
    if (reviews or places) and "rating" in d.columns and filter_min_rating > 1.0:
        d = d[d["rating"].isna() | (d["rating"] >= filter_min_rating)]
    if filter_sentiments and "sentiment_label" in d.columns:
        d = d[d["sentiment_label"].isin(filter_sentiments)]
    if places and filter_category and "categories" in d.columns:
        d = d[d["categories"].str.contains(filter_category, case=False, na=False)]
    if filter_keyword:
        if reviews and "text" in d.columns:
            d = d[d["text"].str.contains(filter_keyword, case=False, na=False)]
        elif posts and "title" in d.columns:
            mask = d["title"].str.contains(filter_keyword, case=False, na=False)
            if "body" in d.columns:
                mask |= d["body"].str.contains(filter_keyword, case=False, na=False)
            d = d[mask]
        elif places and "name" in d.columns:
            mask = d["name"].str.contains(filter_keyword, case=False, na=False)
            if "address" in d.columns:
                mask |= d["address"].str.contains(filter_keyword, case=False, na=False)
            d = d[mask]
    if "published_at" in d.columns:
        if filter_date_from:
            d = d[d["published_at"] >= filter_date_from.isoformat()]
        if filter_date_to:
            d = d[d["published_at"] <= filter_date_to.isoformat() + "T23:59:59"]
    if posts and filter_min_score > 0 and "score" in d.columns:
        d = d[d["score"] >= filter_min_score]
    return d


pl_f  = apply_filters(places_df,  places=True)  if show_places  else pd.DataFrame()
rev_f = apply_filters(reviews_df, reviews=True) if show_reviews else pd.DataFrame()
pos_f = apply_filters(posts_df,   posts=True)   if show_posts   else pd.DataFrame()


# ---------------------------------------------------------------------------
# Metadata summary bar
# ---------------------------------------------------------------------------

radius_txt = f"{job['radius_m'] / 1000:g} km" if job["radius_m"] >= 1000 else f"{job['radius_m']} m"
summary_bar([
    ("Location", job["location"]),
    ("Radius", radius_txt),
    ("Sources", job["sources"]),
    ("Scraped", job["created_at"][:16].replace("T", " ")),
    ("Total records", f"{job['record_count']:,}"),
])
sp("sm")

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Places", f"{len(pl_f):,}")
m2.metric("Reviews", f"{len(rev_f):,}")
m3.metric("Social posts", f"{len(pos_f):,}")
avg_r = rev_f["rating"].dropna().mean() if not rev_f.empty and "rating" in rev_f.columns else None
m4.metric("Avg rating", f"{avg_r:.2f} ⭐" if avg_r else "—")

pos_pct = None
for d in (rev_f, pos_f):
    if pos_pct is None and not d.empty and "sentiment_label" in d.columns:
        vc = d["sentiment_label"].value_counts(normalize=True)
        pos_pct = vc.get("positive", 0.0) * 100
m5.metric("Positive", f"{pos_pct:.0f}%" if pos_pct is not None else "—")

legend = [source_badge(k) for k in SOURCE_CONFIG if k in present_sources and k in filter_sources]
if legend:
    st.markdown(
        f'<div style="margin:10px 0 0;">'
        f'<span style="color:{MUTED};font-size:0.66rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:0.09em;margin-right:8px;">Data from</span>'
        + "  ".join(legend) + "</div>",
        unsafe_allow_html=True,
    )

sp("md")

# ---------------------------------------------------------------------------
# Map + sentiment overview
# ---------------------------------------------------------------------------

col_map, col_sent = st.columns([3, 2], gap="large")

with col_map:
    with st.container(border=True):
        st.markdown("### Map")
        try:
            import folium
            from streamlit_folium import st_folium

            mp = (pl_f[["latitude", "longitude", "name", "rating", "source"]]
                  .dropna(subset=["latitude", "longitude"]) if not pl_f.empty else pd.DataFrame())

            if not mp.empty:
                m = folium.Map(location=[job["latitude"], job["longitude"]],
                               zoom_start=14, tiles="CartoDB positron")
                for _, row in mp.iterrows():
                    cfg = SOURCE_CONFIG.get(row.get("source", ""), {})
                    color = cfg.get("color", "#888")
                    popup = (
                        f"<b>{row['name']}</b>"
                        + (f"<br>⭐ {row['rating']:.1f}" if pd.notna(row.get("rating")) else "")
                        + f"<br><span style='color:{color};font-weight:600'>{cfg.get('label','')}</span>"
                    )
                    folium.CircleMarker(
                        [row["latitude"], row["longitude"]],
                        radius=6, color=color, fill=True, fill_color=color, fill_opacity=0.8,
                        popup=folium.Popup(popup, max_width=220), tooltip=row["name"],
                    ).add_to(m)
                folium.Marker(
                    [job["latitude"], job["longitude"]],
                    popup=f"Search centre: {job['location']}",
                    icon=folium.Icon(color="black", icon="star"),
                ).add_to(m)
                lats, lngs = mp["latitude"].tolist(), mp["longitude"].tolist()
                m.fit_bounds([[min(lats) - 0.002, min(lngs) - 0.002],
                              [max(lats) + 0.002, max(lngs) + 0.002]])
                st_folium(m, use_container_width=True, height=420, returned_objects=[])
            else:
                st.caption("No geo-tagged places match the current filters.")
        except ImportError:
            st.warning("Install `folium` and `streamlit-folium` to view the map.")

with col_sent:
    with st.container(border=True):
        st.markdown("### Sentiment overview")
        # Combine review + post sentiment
        sent_frames = []
        if not rev_f.empty and "sentiment_label" in rev_f.columns:
            sent_frames.append(rev_f[["sentiment_label"]])
        if not pos_f.empty and "sentiment_label" in pos_f.columns:
            sent_frames.append(pos_f[["sentiment_label"]])
        if sent_frames:
            allsent = pd.concat(sent_frames, ignore_index=True)
            vc = allsent["sentiment_label"].value_counts().reset_index()
            vc.columns = ["label", "count"]
            fig = px.pie(vc, names="label", values="count", color="label", hole=0.62,
                         color_discrete_map={k: v["color"] for k, v in SENTIMENT_CONFIG.items()})
            fig.update_traces(textposition="inside", textinfo="percent")
            style_plotly(fig)
            fig.update_layout(showlegend=True, height=240,
                              legend=dict(orientation="v", x=1, y=0.5, yanchor="middle"))
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="sent_overview")

            total = int(vc["count"].sum())
            breakdown = ""
            for _, r in vc.iterrows():
                cfg = SENTIMENT_CONFIG.get(r["label"], {})
                pct = r["count"] / total * 100 if total else 0
                breakdown += (
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-size:0.82rem;margin:3px 0;">'
                    f'<span style="color:{INK};">{cfg.get("icon","")} {cfg.get("label", r["label"])}</span>'
                    f'<span style="font-weight:700;color:{INK};">{pct:.0f}%</span></div>'
                )
            st.markdown(breakdown, unsafe_allow_html=True)
        else:
            st.caption("No sentiment data for the current filters.")

sp("md")

# ---------------------------------------------------------------------------
# Highlights
# ---------------------------------------------------------------------------

st.markdown("## Highlights")
sp("xs")

hl1, hl2, hl3 = st.columns(3, gap="medium")


def _place_rows(df, sort_col, ascending=False, need_rating=False):
    if df.empty:
        return []
    d = df.copy()
    if need_rating and "rating" in d.columns:
        d = d[d["rating"].notna()]
    if sort_col not in d.columns or d.empty:
        return []
    d = d.sort_values(sort_col, ascending=ascending).head(5)
    rows = []
    for _, r in d.iterrows():
        name = str(r.get("name", "—"))
        cat = str(r.get("categories", "") or "").split(",")[0].replace("_", " ").title()
        src = SOURCE_CONFIG.get(r.get("source", ""), {}).get("label", "")
        secondary = " · ".join([x for x in [cat, src] if x])
        if sort_col == "rating":
            metric = f"{r['rating']:.1f} ⭐"
        elif sort_col == "review_count":
            rc = r.get("review_count")
            metric = f"{int(rc):,}" if pd.notna(rc) else "—"
        else:
            metric = str(r.get(sort_col, ""))
        rows.append((name, secondary or "—", metric))
    return rows


with hl1:
    with st.container(border=True):
        ranked_list("⭐ Top rated places",
                    _place_rows(pl_f, "rating", ascending=False, need_rating=True),
                    empty="No rated places.")

with hl2:
    with st.container(border=True):
        ranked_list("🔥 Most reviewed",
                    _place_rows(pl_f, "review_count", ascending=False),
                    empty="No review counts.")

with hl3:
    with st.container(border=True):
        if not pos_f.empty and "score" in pos_f.columns:
            d = pos_f.sort_values("score", ascending=False).head(5)
            rows = []
            for _, r in d.iterrows():
                sub = str(r.get("subreddit") or "")
                channel = sub if sub.startswith("#") else f"#{sub}"
                rows.append((
                    str(r.get("title", "—"))[:70],
                    f"{channel} · {int(r.get('comment_count', 0))} comments",
                    f"⭐ {int(r.get('score', 0)):,}",
                ))
            ranked_list("💬 Top discussions", rows, empty="No discussions.")
        else:
            ranked_list("📉 Lowest rated places",
                        _place_rows(pl_f, "rating", ascending=True, need_rating=True),
                        empty="No rated places.")

sp("md")


# ---------------------------------------------------------------------------
# Deep-dive helpers
# ---------------------------------------------------------------------------

def rating_hist(df, color, key):
    if df.empty or "rating" not in df.columns or df["rating"].dropna().empty:
        st.caption("No rating data.")
        return
    fig = px.histogram(df["rating"].dropna(), nbins=10, color_discrete_sequence=[color])
    style_plotly(fig)
    fig.update_layout(showlegend=False, height=250, bargap=0.08,
                      xaxis_title="Rating", yaxis_title="Count")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def sentiment_pie(df, key):
    if df.empty or "sentiment_label" not in df.columns:
        st.caption("No sentiment data.")
        return
    vc = df["sentiment_label"].value_counts().reset_index()
    vc.columns = ["label", "count"]
    fig = px.pie(vc, names="label", values="count", color="label", hole=0.55,
                 color_discrete_map={k: v["color"] for k, v in SENTIMENT_CONFIG.items()})
    fig.update_traces(textposition="inside", textinfo="percent+label")
    style_plotly(fig)
    fig.update_layout(showlegend=False, height=250)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)


def data_table(df, cols, key, height=400, table_name=None):
    q = st.text_input("Search this table", key=f"q_{key}", label_visibility="collapsed",
                      placeholder="🔍  Search this table…")
    if not df.empty and q:
        str_cols = [c for c in cols if c in df.columns and df[c].dtype == object]
        if str_cols:
            mask = pd.Series(False, index=df.index)
            for c in str_cols:
                mask |= df[c].str.contains(q, case=False, na=False)
            df = df[mask]
    vis = [c for c in cols if c in df.columns]
    if df.empty:
        st.caption("No records match the current filters.")
        return
    st.dataframe(df[vis], width="stretch", hide_index=True, height=height)
    st.caption(f"{len(df):,} records shown")


def with_source(df):
    if df.empty or "source" not in df.columns:
        return df
    d = df.copy()
    d["Source"] = d["source"].map(lambda s: SOURCE_CONFIG.get(s, {}).get("label", s))
    return d


# ---------------------------------------------------------------------------
# Deep-dive tabs
# ---------------------------------------------------------------------------

st.markdown("## Deep dive")
sp("xs")

tab_defs = {}
if "google" in present_sources and "google" in filter_sources:
    tab_defs["📍 Google Places"] = "google"
if "mastodon" in present_sources and "mastodon" in filter_sources:
    tab_defs["🐘 Mastodon"] = "mastodon"

if not tab_defs:
    st.info("No data for the selected sources. Adjust the sidebar filters.")
    st.stop()

tabs = st.tabs(list(tab_defs.keys()))
keys = list(tab_defs.keys())

# ── Google ───────────────────────────────────────────────────────────
if "📍 Google Places" in tab_defs:
    with tabs[keys.index("📍 Google Places")]:
        g_pl  = pl_f[pl_f["source"] == "google"]   if not pl_f.empty  else pd.DataFrame()
        g_rev = rev_f[rev_f["source"] == "google"] if not rev_f.empty else pd.DataFrame()

        a, b = st.columns(2)
        with a:
            with st.container(border=True):
                st.markdown("#### Rating distribution")
                rating_hist(g_rev, SOURCE_CONFIG["google"]["color"], "g_hist")
        with b:
            with st.container(border=True):
                st.markdown("#### Review sentiment")
                sentiment_pie(g_rev, "g_pie")

        c, d = st.columns(2)
        with c:
            with st.container(border=True):
                st.markdown("#### Top categories by avg rating")
                if not g_pl.empty and "categories" in g_pl.columns and not g_pl["rating"].dropna().empty:
                    cdf = g_pl[["categories", "rating"]].dropna().copy()
                    cdf["category"] = cdf["categories"].str.split(", ")
                    cdf = cdf.explode("category")
                    cdf = cdf[~cdf["category"].str.contains("point_of_interest|establishment", na=True)]
                    cavg = (cdf.groupby("category")["rating"].agg(["mean", "count"])
                            .query("count >= 2").sort_values("mean", ascending=False)
                            .head(10).reset_index())
                    if not cavg.empty:
                        fig = px.bar(cavg, x="mean", y="category", orientation="h", color="mean",
                                     color_continuous_scale=["#EF4444", "#FBBF24", "#10B981"],
                                     range_x=[3, 5])
                        style_plotly(fig)
                        fig.update_layout(showlegend=False, coloraxis_showscale=False,
                                          height=300, xaxis_title="Avg rating", yaxis_title="",
                                          yaxis=dict(autorange="reversed"))
                        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="g_cat")
                    else:
                        st.caption("Not enough category data.")
                else:
                    st.caption("Not enough category data.")
        with d:
            with st.container(border=True):
                st.markdown("#### What reviewers mention")
                keyword_chips(extract_keywords(g_rev["text"].tolist() if not g_rev.empty and "text" in g_rev else []))

        with st.expander(f"📍 Places ({len(g_pl):,})", expanded=True):
            data_table(with_source(g_pl),
                       ["name", "address", "rating", "review_count", "categories",
                        "price_level", "phone", "url", "Source"], "g_pl_q",
                       table_name="places")
        with st.expander(f"⭐ Reviews ({len(g_rev):,})", expanded=False):
            data_table(with_source(g_rev),
                       ["place_name", "author", "rating", "sentiment_label",
                        "sentiment_score", "text", "published_at", "Source"], "g_rev_q", 460,
                       table_name="reviews")

# ── Mastodon ─────────────────────────────────────────────────────────
if "🐘 Mastodon" in tab_defs:
    with tabs[keys.index("🐘 Mastodon")]:
        m_pos = pos_f[pos_f["source"] == "mastodon"] if not pos_f.empty else pd.DataFrame()

        a, b = st.columns(2)
        with a:
            with st.container(border=True):
                st.markdown("#### Favourites distribution")
                if not m_pos.empty and "score" in m_pos.columns:
                    fig = px.histogram(m_pos["score"].clip(lower=0), nbins=20,
                                       color_discrete_sequence=[SOURCE_CONFIG["mastodon"]["color"]])
                    style_plotly(fig)
                    fig.update_layout(showlegend=False, height=250,
                                      xaxis_title="Favourites", yaxis_title="Posts")
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="m_hist")
                else:
                    st.caption("No engagement data.")
        with b:
            with st.container(border=True):
                st.markdown("#### Post sentiment")
                sentiment_pie(m_pos, "m_pie")

        c, d = st.columns(2)
        with c:
            with st.container(border=True):
                st.markdown("#### Posts by hashtag / instance")
                if not m_pos.empty and "subreddit" in m_pos.columns:
                    hc = m_pos["subreddit"].value_counts().head(12).reset_index()
                    hc.columns = ["channel", "posts"]
                    fig = px.bar(hc, x="posts", y="channel", orientation="h",
                                 color_discrete_sequence=[SOURCE_CONFIG["mastodon"]["color"]])
                    style_plotly(fig)
                    fig.update_layout(showlegend=False, height=300,
                                      xaxis_title="Posts", yaxis_title="",
                                      yaxis=dict(autorange="reversed"))
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="m_tag")
                else:
                    st.caption("No channel data.")
        with d:
            with st.container(border=True):
                st.markdown("#### What the community discusses")
                texts = []
                if not m_pos.empty:
                    texts = (m_pos.get("title", pd.Series(dtype=str)).fillna("") + " "
                             + m_pos.get("body", pd.Series(dtype=str)).fillna("")).tolist()
                keyword_chips(extract_keywords(texts))

        with st.expander(f"🐘 Posts ({len(m_pos):,})", expanded=True):
            data_table(with_source(m_pos),
                       ["author", "subreddit", "title", "score", "comment_count",
                        "sentiment_label", "published_at", "url", "Source"], "m_pos_q", 460,
                       table_name="social_posts")

