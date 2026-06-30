"""
Compare — benchmark two or more locations side by side.
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
    CHART_SEQ, DARK, INK, LIME, MUTED, SENTIMENT_CONFIG,
    inject_css, ranked_list, sp, style_plotly,
)

load_dotenv()
storage.init_db()

st.set_page_config(page_title="Compare — Scraper", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")
inject_css()

st.markdown("# Compare locations")
st.markdown(
    f'<p style="color:{MUTED};font-size:0.9rem;margin-top:0.25rem;">'
    f'Benchmark suburbs against each other — volume, ratings, sentiment and what makes each tick.</p>',
    unsafe_allow_html=True,
)
sp("sm")

all_jobs  = storage.get_all_jobs()
done_jobs = [j for j in all_jobs if j["status"] == "completed"]

if len(done_jobs) < 2:
    st.info("You need at least **two completed jobs** to compare. Run more scrapes from **Home**.", icon="ℹ️")
    st.stop()

job_opts = {
    f"{j['location']}  ·  {j['created_at'][:10]}  ({j['record_count']:,})": j["id"]
    for j in done_jobs
}
default = list(job_opts.keys())[:2]
chosen = st.multiselect("Select 2–4 jobs to compare", list(job_opts.keys()),
                        default=default, max_selections=4)

if len(chosen) < 2:
    st.warning("Select at least two jobs to compare.")
    st.stop()

chosen_ids = [job_opts[c] for c in chosen]
jobs = [next(j for j in done_jobs if j["id"] == jid) for jid in chosen_ids]


# ---------------------------------------------------------------------------
# Gather per-job stats
# ---------------------------------------------------------------------------

def short_name(loc: str) -> str:
    return loc.split(",")[0].strip().title()[:22]


records = []
for j in jobs:
    name   = short_name(j["location"])
    places = storage.get_places_df(j["id"])
    revs   = storage.get_reviews_df(j["id"])
    posts  = storage.get_social_posts_df(j["id"])

    avg_rating = revs["rating"].dropna().mean() if not revs.empty and "rating" in revs.columns else None
    pos_pct = None
    sent_frames = []
    if not revs.empty and "sentiment_label" in revs.columns:
        sent_frames.append(revs[["sentiment_label"]])
    if not posts.empty and "sentiment_label" in posts.columns:
        sent_frames.append(posts[["sentiment_label"]])
    if sent_frames:
        s = pd.concat(sent_frames, ignore_index=True)
        pos_pct = (s["sentiment_label"] == "positive").mean() * 100

    records.append({
        "job": name,
        "location": j["location"],
        "id": j["id"],
        "places": len(places),
        "reviews": len(revs),
        "posts": len(posts),
        "avg_rating": avg_rating,
        "pos_pct": pos_pct,
        "places_df": places,
        "reviews_df": revs,
        "posts_df": posts,
    })

cmp_df = pd.DataFrame([{k: r[k] for k in
                        ("job", "places", "reviews", "posts", "avg_rating", "pos_pct")}
                       for r in records])

# ---------------------------------------------------------------------------
# Headline comparison table
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.markdown("### At a glance")
    disp = cmp_df.copy()
    disp["avg_rating"] = disp["avg_rating"].map(lambda v: f"{v:.2f} ⭐" if pd.notna(v) else "—")
    disp["pos_pct"]    = disp["pos_pct"].map(lambda v: f"{v:.0f}%" if pd.notna(v) else "—")
    disp.columns = ["Location", "Places", "Reviews", "Posts", "Avg rating", "Positive"]
    st.dataframe(disp, width="stretch", hide_index=True)

sp("md")

# ---------------------------------------------------------------------------
# Volume + rating + sentiment charts
# ---------------------------------------------------------------------------

c1, c2 = st.columns(2, gap="large")

with c1:
    with st.container(border=True):
        st.markdown("### Records collected")
        vol = cmp_df.melt(id_vars="job", value_vars=["places", "reviews", "posts"],
                          var_name="type", value_name="count")
        vol["type"] = vol["type"].str.title()
        fig = px.bar(vol, x="job", y="count", color="type", barmode="group",
                     color_discrete_sequence=CHART_SEQ)
        style_plotly(fig)
        fig.update_layout(height=320, xaxis_title="", yaxis_title="Records",
                          legend_title="")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with c2:
    with st.container(border=True):
        st.markdown("### Average rating")
        rdf = cmp_df.dropna(subset=["avg_rating"])
        if not rdf.empty:
            fig = px.bar(rdf, x="job", y="avg_rating", text="avg_rating",
                         color="avg_rating", range_y=[0, 5],
                         color_continuous_scale=["#EF4444", "#FBBF24", "#10B981"])
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            style_plotly(fig)
            fig.update_layout(height=320, xaxis_title="", yaxis_title="Avg rating",
                              coloraxis_showscale=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.caption("No rating data.")

sp("md")

c3, c4 = st.columns(2, gap="large")

with c3:
    with st.container(border=True):
        st.markdown("### Sentiment mix")
        sent_rows = []
        for r in records:
            frames = []
            if not r["reviews_df"].empty and "sentiment_label" in r["reviews_df"].columns:
                frames.append(r["reviews_df"][["sentiment_label"]])
            if not r["posts_df"].empty and "sentiment_label" in r["posts_df"].columns:
                frames.append(r["posts_df"][["sentiment_label"]])
            if frames:
                s = pd.concat(frames, ignore_index=True)
                vc = s["sentiment_label"].value_counts(normalize=True) * 100
                for lab in ("positive", "neutral", "negative"):
                    sent_rows.append({"job": r["job"], "sentiment": lab.title(),
                                      "pct": vc.get(lab, 0.0)})
        if sent_rows:
            sdf = pd.DataFrame(sent_rows)
            fig = px.bar(sdf, x="job", y="pct", color="sentiment", barmode="stack",
                         color_discrete_map={"Positive": SENTIMENT_CONFIG["positive"]["color"],
                                             "Neutral":  SENTIMENT_CONFIG["neutral"]["color"],
                                             "Negative": SENTIMENT_CONFIG["negative"]["color"]})
            style_plotly(fig)
            fig.update_layout(height=320, xaxis_title="", yaxis_title="% of mentions",
                              legend_title="")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.caption("No sentiment data.")

with c4:
    with st.container(border=True):
        st.markdown("### Category mix")
        cat_rows = []
        for r in records:
            pdf = r["places_df"]
            if pdf.empty or "categories" not in pdf.columns:
                continue
            cats = pdf["categories"].dropna().str.split(", ").explode()
            cats = cats[~cats.str.contains("point_of_interest|establishment|store", na=True)]
            for cat, cnt in cats.value_counts().items():
                cat_rows.append({"job": r["job"],
                                 "category": cat.replace("_", " ").title(), "count": cnt})
        if cat_rows:
            cdf = pd.DataFrame(cat_rows)
            top_cats = cdf.groupby("category")["count"].sum().nlargest(8).index
            cdf = cdf[cdf["category"].isin(top_cats)]
            fig = px.bar(cdf, x="category", y="count", color="job", barmode="group",
                         color_discrete_sequence=CHART_SEQ)
            style_plotly(fig)
            fig.update_layout(height=320, xaxis_title="", yaxis_title="Places",
                              legend_title="")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.caption("No category data.")

sp("md")

# ---------------------------------------------------------------------------
# Top-rated place per location
# ---------------------------------------------------------------------------

st.markdown("## Top-rated place in each location")
sp("xs")

cols = st.columns(len(records), gap="medium")
for col, r in zip(cols, records):
    with col:
        with st.container(border=True):
            pdf = r["places_df"]
            if not pdf.empty and "rating" in pdf.columns and not pdf["rating"].dropna().empty:
                d = pdf[pdf["rating"].notna()].sort_values(
                    ["rating", "review_count"], ascending=False).head(3)
                rows = []
                for _, p in d.iterrows():
                    cat = str(p.get("categories", "") or "").split(",")[0].replace("_", " ").title()
                    rc = p.get("review_count")
                    rcs = f"{int(rc):,} reviews" if pd.notna(rc) else ""
                    rows.append((str(p.get("name", "—")),
                                 " · ".join([x for x in [cat, rcs] if x]) or "—",
                                 f"{p['rating']:.1f} ⭐"))
                ranked_list(f"📍 {r['job']}", rows, empty="No rated places.")
            else:
                ranked_list(f"📍 {r['job']}", [], empty="No rated places.")
