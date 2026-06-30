"""
Shared design system: palette, CSS, and UI helpers.

Design language — "Soft Glass":
  - Airy light gradient canvas  (mint → white → lavender)
  - Frosted-glass cards: translucent white, backdrop blur, 22 px radius, soft shadow
  - Emerald accent  #10B981 / #059669
  - Slate ink text  #1F2937  ·  muted slate  #6B7280
  - Floating frosted-glass sidebar (light), emerald active pill
  - Inter type family — tight headline tracking, generous body line-height
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Palette
#   (constant names kept stable so page imports don't break)
# ---------------------------------------------------------------------------

LIME    = "#10B981"   # primary emerald accent
LIME_DK = "#059669"   # deeper emerald (hover / press)
ACCENT_SOFT = "#D1FAE5"
DARK    = "#0E2A22"   # deep emerald-slate (dark glass cards)
INK     = "#1F2937"   # slate-800 — primary text
MUTED   = "#6B7280"   # slate-500 — secondary text
BG      = "#EAF3EF"   # light mint tint (small fills)
CARD    = "rgba(255,255,255,0.72)"
BORDER  = "rgba(255,255,255,0.7)"

SOURCE_CONFIG: dict = {
    "google":   {"label": "Google Places", "icon": "📍", "color": "#0E7C5A", "soft": "#D4F3E5"},
    "mastodon": {"label": "Mastodon",      "icon": "🐘", "color": "#6364FF", "soft": "#ECEEFE"},
}

SENTIMENT_CONFIG: dict = {
    "positive": {"icon": "😊", "label": "Positive", "color": "#10B981", "soft": "#D1FAE5"},
    "neutral":  {"icon": "😐", "label": "Neutral",  "color": "#9CA3AF", "soft": "#EEF1F0"},
    "negative": {"icon": "😟", "label": "Negative", "color": "#EF4444", "soft": "#FEE2E2"},
}

CHART_SEQ = ["#10B981", "#6EE7B7", "#A78BFA", "#93C5FD", "#FBBF24", "#34D399"]


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
/* ================================================================
   URBAN DATA SCRAPER — Soft Glass design system
   ================================================================ */

@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300..900&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

html, body, [class*="css"], .stApp {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}}

/* ── App shell — soft gradient canvas ───────────────────────── */
.stApp {{
    background:
        radial-gradient(1100px 600px at 12% -8%, rgba(16,185,129,0.16), transparent 60%),
        radial-gradient(1000px 620px at 100% 0%, rgba(167,139,250,0.16), transparent 55%),
        linear-gradient(135deg, #E9F6EF 0%, #F5F7F6 42%, #F1EEF9 100%);
    background-attachment: fixed;
}}

.block-container {{
    padding: 2rem 2.5rem 5rem !important;
    max-width: 1480px;
}}

#MainMenu, footer {{ display: none !important; }}

/* Header — keep transparent so the sidebar toggle stays interactive */
header[data-testid="stHeader"] {{
    background: transparent !important;
    border-bottom: none !important;
    box-shadow: none !important;
}}
/* Streamlit 1.58: stExpandSidebarButton lives inside stToolbar.
   Keep the toolbar visible but hide everything except the expand button. */
[data-testid="stToolbar"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}

/* ── Typography reset ───────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {{
    margin: 0 !important; padding: 0 !important;
    line-height: 1.15 !important; color: {INK} !important;
}}
h1 {{ font-size: 2.2rem !important;  font-weight: 800 !important; letter-spacing: -0.035em; }}
h2 {{ font-size: 1.42rem !important; font-weight: 750 !important; letter-spacing: -0.025em; }}
h3 {{ font-size: 1.05rem !important; font-weight: 700 !important; letter-spacing: -0.01em; }}
h4, h5, h6 {{ font-size: 0.9rem !important; font-weight: 700 !important; }}

p {{ margin: 0 !important; line-height: 1.65; font-size: 0.9rem; color: {INK}; }}
strong {{ font-weight: 700; }}

.stMarkdown {{ margin-bottom: 0.5rem; }}
.stMarkdown + [data-testid] {{ margin-top: 0; }}

[data-testid="stCaptionContainer"] p {{
    font-size: 0.77rem !important; color: {MUTED} !important; line-height: 1.5;
}}

/* ── Spacing helpers ────────────────────────────────────────── */
.sp-xs {{ height: 0.35rem; display: block; }}
.sp-sm {{ height: 0.8rem;  display: block; }}
.sp-md {{ height: 1.4rem;  display: block; }}
.sp-lg {{ height: 2.2rem;  display: block; }}

/* ── Frosted-glass cards ── st.container(border=True) ───────── */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: rgba(255,255,255,0.62) !important;
    backdrop-filter: blur(18px) saturate(150%);
    -webkit-backdrop-filter: blur(18px) saturate(150%);
    border: 1px solid rgba(255,255,255,0.75) !important;
    border-radius: 22px !important;
    padding: 1.35rem 1.55rem !important;
    box-shadow:
        0 10px 30px rgba(16,52,40,0.09),
        0 2px 8px rgba(16,52,40,0.04),
        inset 0 1px 0 rgba(255,255,255,0.7);
    transition: box-shadow 0.22s ease, transform 0.22s ease;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    box-shadow:
        0 16px 44px rgba(16,52,40,0.13),
        0 4px 12px rgba(16,52,40,0.06),
        inset 0 1px 0 rgba(255,255,255,0.8);
}}

div[data-testid="stVerticalBlockBorderWrapper"] > div > div[data-testid="stVerticalBlock"] {{
    gap: 0.6rem;
}}
.main > div > div > div[data-testid="stVerticalBlock"] {{ gap: 1.2rem; }}

/* ── Metrics — glass tiles ──────────────────────────────────── */
[data-testid="stMetric"] {{
    background: rgba(255,255,255,0.62);
    backdrop-filter: blur(18px) saturate(150%);
    -webkit-backdrop-filter: blur(18px) saturate(150%);
    border: 1px solid rgba(255,255,255,0.75);
    border-radius: 20px;
    padding: 1.1rem 1.3rem 1rem;
    box-shadow: 0 8px 24px rgba(16,52,40,0.08), inset 0 1px 0 rgba(255,255,255,0.7);
    transition: transform 0.16s ease, box-shadow 0.16s ease;
}}
[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 14px 34px rgba(16,52,40,0.13), inset 0 1px 0 rgba(255,255,255,0.8);
}}
[data-testid="stMetricLabel"] p {{
    font-size: 0.67rem !important; color: {MUTED} !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: 0.1em; margin: 0 0 0.4rem !important;
}}
[data-testid="stMetricValue"] {{
    font-size: 1.95rem !important; font-weight: 800 !important; color: {INK} !important;
    line-height: 1.05; letter-spacing: -0.03em;
}}
[data-testid="stMetricDelta"] {{ font-size: 0.74rem !important; }}

/* ── Buttons ────────────────────────────────────────────────── */
div.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, {LIME} 0%, {LIME_DK} 100%) !important;
    color: #FFFFFF !important; border: none !important; border-radius: 12px !important;
    font-weight: 650 !important; font-size: 0.88rem !important;
    padding: 0.55rem 1.5rem !important; letter-spacing: 0.01em;
    box-shadow: 0 6px 18px rgba(16,185,129,0.34);
    transition: all 0.15s ease;
}}
div.stButton > button[kind="primary"]:hover {{
    filter: brightness(1.05);
    transform: translateY(-1px);
    box-shadow: 0 10px 26px rgba(16,185,129,0.42) !important;
}}
div.stButton > button[kind="secondary"] {{
    background: rgba(255,255,255,0.7) !important;
    backdrop-filter: blur(8px);
    color: {INK} !important; border: 1px solid rgba(16,52,40,0.12) !important;
    border-radius: 12px !important; font-weight: 600 !important; font-size: 0.88rem !important;
    transition: all 0.15s ease;
}}
div.stButton > button[kind="secondary"]:hover {{
    border-color: {LIME} !important; color: {LIME_DK} !important;
}}
div.stDownloadButton > button {{
    background: linear-gradient(135deg, {LIME} 0%, {LIME_DK} 100%) !important;
    color: #FFFFFF !important; border: none !important; border-radius: 12px !important;
    font-weight: 650 !important; font-size: 0.88rem !important;
    box-shadow: 0 6px 18px rgba(16,185,129,0.34); transition: all 0.15s ease;
}}
div.stDownloadButton > button:hover {{ filter: brightness(1.05); transform: translateY(-1px); }}

/* ── Tabs — glass segmented control ─────────────────────────── */
.stTabs [data-baseweb="tab-list"] {{
    background: rgba(255,255,255,0.55);
    backdrop-filter: blur(12px);
    border-radius: 14px; padding: 5px; gap: 3px;
    border: 1px solid rgba(255,255,255,0.7);
    box-shadow: 0 4px 14px rgba(16,52,40,0.06);
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 10px !important; padding: 6px 17px !important;
    font-weight: 600 !important; font-size: 0.86rem !important;
    color: {MUTED} !important; background: transparent !important;
    transition: color 0.12s ease;
}}
.stTabs [data-baseweb="tab"]:hover {{ color: {INK} !important; }}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(135deg, {LIME} 0%, {LIME_DK} 100%) !important;
    color: #FFFFFF !important;
    box-shadow: 0 4px 12px rgba(16,185,129,0.32);
}}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}
.stTabs [data-baseweb="tab-panel"] {{ padding-top: 1.1rem; }}

/* ── Expanders ──────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: rgba(255,255,255,0.6) !important;
    backdrop-filter: blur(14px) saturate(140%);
    -webkit-backdrop-filter: blur(14px) saturate(140%);
    border-radius: 16px !important;
    border: 1px solid rgba(255,255,255,0.72) !important;
    box-shadow: 0 6px 18px rgba(16,52,40,0.06) !important;
    overflow: hidden;
}}
[data-testid="stExpander"] summary {{
    font-size: 0.88rem !important; font-weight: 700 !important;
    color: {INK} !important; padding: 0.85rem 1.1rem !important;
}}
[data-testid="stExpander"] summary:hover {{ color: {LIME_DK} !important; }}
[data-testid="stExpanderDetails"] {{ padding: 0 1.1rem 1rem; }}

/* ── Inputs & controls ──────────────────────────────────────── */
[data-baseweb="input"] > div, [data-baseweb="base-input"],
[data-baseweb="select"] > div, .stTextInput > div > div {{
    border-radius: 11px !important; font-size: 0.9rem !important;
    background: rgba(255,255,255,0.8) !important;
}}
[data-baseweb="input"] > div:focus-within, [data-baseweb="select"] > div:focus-within {{
    border-color: {LIME} !important;
    box-shadow: 0 0 0 3px rgba(16,185,129,0.16) !important;
}}
[data-testid="stTextInput"] label p, [data-testid="stSelectbox"] label p,
[data-testid="stSlider"] label p, [data-testid="stMultiSelect"] label p,
[data-testid="stNumberInput"] label p, [data-testid="stRadio"] label p,
[data-testid="stDateInput"] label p {{
    font-size: 0.82rem !important; font-weight: 600 !important;
    color: {INK} !important; margin-bottom: 0.2rem !important;
}}
[data-testid="stCheckbox"] p {{ font-size: 0.88rem !important; color: {INK} !important; }}
[data-baseweb="slider"] [role="slider"] {{ background: {LIME} !important; }}
[data-baseweb="tag"] {{
    border-radius: 8px !important; font-size: 0.78rem !important;
    background: {ACCENT_SOFT} !important;
}}
[data-baseweb="tag"] span {{ color: {LIME_DK} !important; }}

[data-testid="stDataFrame"], iframe {{ border-radius: 14px; overflow: hidden; }}
[data-testid="stAlert"] {{ border-radius: 14px !important; }}
hr {{ border-color: rgba(16,52,40,0.1); margin: 0.6rem 0; }}

[data-testid="stSelectbox"] li, [data-testid="stMultiSelect"] li {{ font-size: 0.88rem !important; }}

/* ================================================================
   SIDEBAR — always-visible frosted-glass (light) panel
   ================================================================ */

/* Streamlit 1.58 slides the sidebar off-screen via translateX and shrinks
   it to max-width:0 when "collapsed". Override all three so the panel is
   permanently on-screen with no collapse/expand controls. */
section[data-testid="stSidebar"] {{
    background: rgba(255,255,255,0.96) !important;
    backdrop-filter: blur(20px) saturate(150%);
    -webkit-backdrop-filter: blur(20px) saturate(150%);
    border-right: 2px solid rgba(16,185,129,0.35) !important;
    box-shadow: 4px 0 28px rgba(16,52,40,0.12) !important;
    width: 290px !important;
    min-width: 290px !important;
    /* Streamlit 1.58 sets max-width:0 when collapsed — override so our
       min-width wins and the panel stays fully on-screen. */
    max-width: none !important;
    /* Override Streamlit's translateX collapse animation */
    transform: none !important;
    padding: 14px 10px 24px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    transition: width 0.25s ease, min-width 0.25s ease;
    z-index: 100 !important;
    position: relative !important;
}}

/* Reset any inner-div styling that may conflict */
section[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 100% !important;
    overflow: visible !important;
}}

/* Sidebar text — slate */
section[data-testid="stSidebar"] p {{
    color: {INK} !important; font-size: 0.88rem !important; margin: 0 !important;
}}
section[data-testid="stSidebar"] strong {{ color: {INK} !important; font-weight: 700 !important; }}
section[data-testid="stSidebar"] .stMarkdown p {{
    color: {INK} !important; font-size: 0.78rem !important; font-weight: 700 !important;
    text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 0.35rem !important;
}}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{
    color: {INK} !important; font-size: 1rem !important; font-weight: 750 !important;
    margin: 0.6rem 0 0.8rem !important; padding: 0 14px !important;
}}
section[data-testid="stSidebar"] hr {{ border-color: rgba(16,52,40,0.1); margin: 0 !important; }}

/* ── Equal spacing between every sidebar control ─────────────────
   Single source of truth: flex gap on the vertical block.
   Zero out per-widget extra margins so gap is the only spacing. */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: 0.9rem;
    padding-left: 4px;
    padding-right: 4px;
}}
section[data-testid="stSidebar"] [data-testid="stCheckbox"],
section[data-testid="stSidebar"] [data-testid="stSlider"],
section[data-testid="stSidebar"] [data-testid="stTextInput"],
section[data-testid="stSidebar"] [data-testid="stNumberInput"],
section[data-testid="stSidebar"] [data-testid="stSelectbox"],
section[data-testid="stSidebar"] [data-testid="stMultiSelect"],
section[data-testid="stSidebar"] [data-testid="stDateInput"],
section[data-testid="stSidebar"] .stMarkdown {{
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}}

/* ── Hide all sidebar show/hide controls — panel is permanently visible ── */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarHeader"] button[data-testid="baseButton-header"],
[data-testid="stExpandSidebarButton"] {{
    display: none !important;
}}

/* Nav links */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{ padding: 6px 0; }}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
    border-radius: 12px; margin: 2px 10px; padding: 8px 13px;
    transition: background 0.13s ease; display: flex; align-items: center; gap: 10px;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span {{
    font-size: 0.9rem !important; font-weight: 550 !important; color: {INK} !important;
    text-transform: capitalize !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
    background: rgba(16,185,129,0.1) !important;
}}
/* Active nav — soft emerald pill, emerald text/icon */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {{
    background: {ACCENT_SOFT} !important;
    box-shadow: inset 0 0 0 1px rgba(16,185,129,0.4);
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] svg,
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] * {{
    color: {LIME_DK} !important; fill: {LIME_DK} !important; font-weight: 700 !important;
}}

/* Sidebar checkboxes */
section[data-testid="stSidebar"] [data-testid="stCheckbox"] p {{
    color: {INK} !important; font-size: 0.87rem !important;
    text-transform: none !important; letter-spacing: normal !important; font-weight: 500 !important;
}}

/* Sidebar inputs (light) */
section[data-testid="stSidebar"] [data-baseweb="input"] > div,
section[data-testid="stSidebar"] [data-baseweb="select"] > div,
section[data-testid="stSidebar"] [data-baseweb="base-input"] {{
    background: rgba(255,255,255,0.85) !important;
    border-color: rgba(16,52,40,0.12) !important;
}}
section[data-testid="stSidebar"] input {{ color: {INK} !important; font-size: 0.88rem !important; }}
section[data-testid="stSidebar"] [data-testid="stMultiSelect"] label p,
section[data-testid="stSidebar"] [data-testid="stSlider"] label p,
section[data-testid="stSidebar"] [data-testid="stNumberInput"] label p,
section[data-testid="stSidebar"] [data-testid="stTextInput"] label p,
section[data-testid="stSidebar"] [data-testid="stDateInput"] label p {{
    color: {INK} !important; font-size: 0.8rem !important;
    text-transform: uppercase !important; letter-spacing: 0.05em !important; font-weight: 700 !important;
}}

/* Sidebar secondary button */
section[data-testid="stSidebar"] div.stButton > button[kind="secondary"] {{
    background: rgba(255,255,255,0.75) !important;
    border-color: rgba(16,52,40,0.12) !important; color: {INK} !important;
}}
section[data-testid="stSidebar"] div.stButton > button[kind="secondary"]:hover {{
    border-color: {LIME} !important; color: {LIME_DK} !important;
}}

/* Scrollbars */
section[data-testid="stSidebar"] > div::-webkit-scrollbar,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar {{ width: 5px; }}
section[data-testid="stSidebar"] > div::-webkit-scrollbar-thumb,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]::-webkit-scrollbar-thumb {{
    background: rgba(16,52,40,0.18); border-radius: 5px;
}}

/* ================================================================
   HTML card helpers (st.markdown)
   ================================================================ */
/* Dark emerald-teal glass card (status / last completed) */
.uds-dark {{
    background: linear-gradient(135deg, #0E3B2E 0%, #0B2A24 100%);
    border-radius: 22px; padding: 1.4rem 1.6rem; color: #FFFFFF;
    box-shadow: 0 14px 38px rgba(11,42,36,0.34), inset 0 1px 0 rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.07);
}}
/* Soft emerald glass card (get-started) */
.uds-lime {{
    background: linear-gradient(135deg, rgba(209,250,229,0.85) 0%, rgba(255,255,255,0.6) 100%);
    backdrop-filter: blur(16px);
    border-radius: 22px; padding: 1.4rem 1.6rem; color: {INK};
    box-shadow: 0 12px 32px rgba(16,185,129,0.16), inset 0 1px 0 rgba(255,255,255,0.6);
    border: 1px solid rgba(16,185,129,0.28);
}}

/* Stat-card text elements */
.sc-label {{
    display: block; font-size: 0.67rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: {MUTED}; margin-bottom: 0.35rem; line-height: 1;
}}
.sc-value {{
    display: block; font-size: 2rem; font-weight: 800; color: {INK};
    letter-spacing: -0.03em; line-height: 1; margin-bottom: 0.25rem;
}}
.sc-sub {{
    display: block; font-size: 0.76rem; color: {MUTED}; font-weight: 500; line-height: 1.4;
}}

</style>
"""


def inject_css() -> None:
    """Inject design-system CSS."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Spacing helper
# ---------------------------------------------------------------------------

def sp(size: str = "md") -> None:
    """Insert a controlled vertical gap. size: xs | sm | md | lg"""
    st.markdown(f'<div class="sp-{size}"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section heading helper
# ---------------------------------------------------------------------------

def section_heading(title: str, sub: str = "") -> None:
    html = f'<div style="margin-bottom:0.6rem">'
    html += f'<div style="font-size:1.05rem;font-weight:700;color:{INK};letter-spacing:-0.01em;line-height:1.2">{title}</div>'
    if sub:
        html += f'<div style="font-size:0.78rem;color:{MUTED};margin-top:2px;line-height:1.4">{sub}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Badge helpers
# ---------------------------------------------------------------------------

def source_badge(source: str) -> str:
    cfg = SOURCE_CONFIG.get((source or "").lower(),
                            {"label": source or "—", "icon": "●", "color": "#666", "soft": "#EEE"})
    return (
        f'<span style="background:{cfg["soft"]};color:{cfg["color"]};'
        f'border-radius:8px;padding:3px 10px;font-size:0.71rem;font-weight:700;'
        f'display:inline-block;letter-spacing:0.01em;line-height:1.8">'
        f'{cfg["icon"]} {cfg["label"]}</span>'
    )


def sentiment_badge(label: str) -> str:
    cfg = SENTIMENT_CONFIG.get((label or "").lower(),
                               {"icon": "", "label": label or "—", "color": "#666", "soft": "#EEE"})
    return (
        f'<span style="background:{cfg["soft"]};color:{cfg["color"]};'
        f'border-radius:8px;padding:3px 10px;font-size:0.71rem;font-weight:700;'
        f'display:inline-block;line-height:1.8">{cfg["icon"]} {cfg["label"]}</span>'
    )


# ---------------------------------------------------------------------------
# Plotly styling
# ---------------------------------------------------------------------------

def style_plotly(fig):
    """Transparent background + consistent Inter font styling."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, sans-serif", color=INK, size=12),
        margin=dict(t=24, b=8, l=4, r=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, font_size=11),
        xaxis=dict(gridcolor="rgba(16,52,40,0.08)", zerolinecolor="rgba(16,52,40,0.12)", tickfont_size=11),
        yaxis=dict(gridcolor="rgba(16,52,40,0.08)", zerolinecolor="rgba(16,52,40,0.12)", tickfont_size=11),
    )
    return fig


# ---------------------------------------------------------------------------
# Insight helpers
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset("""
a about above after again against all am an and any are aren't as at be because been
before being below between both but by can't cannot could couldn't did didn't do does
doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he he'd he'll he's her here here's hers herself him himself his how how's
i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my
myself no nor not of off on once only or other ought our ours ourselves out over own same
shan't she she'd she'll she's should shouldn't so some such than that that's the their
theirs them themselves then there there's these they they'd they'll they're they've this
those through to too under until up very was wasn't we we'd we'll we're we've were weren't
what what's when when's where where's which while who who's whom why why's with won't would
wouldn't you you'd you'll you're you've your yours yourself yourselves get got also really
just very much many lot place places one two get really would like good great im dont didnt
ive theyre weve youre thats food service time day way back going went come came see
""".split())


def extract_keywords(texts, top_n: int = 18, min_len: int = 3):
    """Return [(word, count), ...] most-common content words across *texts*."""
    import re
    from collections import Counter

    counter: Counter = Counter()
    for t in texts:
        if not t:
            continue
        for w in re.findall(r"[a-zA-Z][a-zA-Z']+", str(t).lower()):
            w = w.strip("'")
            if len(w) >= min_len and w not in _STOPWORDS:
                counter[w] += 1
    return counter.most_common(top_n)


def summary_bar(items: list[tuple[str, str]]) -> None:
    """Render a horizontal label:value summary strip inside a glass card."""
    cells = "".join(
        f'<div style="display:flex;flex-direction:column;gap:1px;padding-right:30px;">'
        f'<span style="font-size:0.64rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.09em;color:{MUTED};">{label}</span>'
        f'<span style="font-size:0.92rem;font-weight:650;color:{INK};">{value}</span>'
        f'</div>'
        for label, value in items
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:12px 0;align-items:center;'
        f'background:rgba(255,255,255,0.6);backdrop-filter:blur(14px);'
        f'border:1px solid rgba(255,255,255,0.72);border-radius:16px;'
        f'padding:0.85rem 1.3rem;box-shadow:0 6px 18px rgba(16,52,40,0.06);">{cells}</div>',
        unsafe_allow_html=True,
    )


def ranked_list(title: str, rows: list[tuple[str, str, str]], empty: str = "No data.") -> None:
    """
    Compact ranked insight list.
    rows = [(primary_text, secondary_text, metric_text), ...]
    """
    st.markdown(f'<div style="font-weight:750;font-size:0.95rem;color:{INK};'
                f'margin-bottom:0.7rem;">{title}</div>', unsafe_allow_html=True)
    if not rows:
        st.markdown(f'<div style="color:{MUTED};font-size:0.82rem;">{empty}</div>',
                    unsafe_allow_html=True)
        return
    html = '<div style="display:flex;flex-direction:column;gap:9px;">'
    for i, (primary, secondary, metric) in enumerate(rows, start=1):
        html += (
            f'<div style="display:flex;align-items:center;gap:11px;">'
            f'<span style="flex-shrink:0;width:23px;height:23px;border-radius:8px;'
            f'background:{ACCENT_SOFT};color:{LIME_DK};font-size:0.72rem;font-weight:800;'
            f'display:flex;align-items:center;justify-content:center;">{i}</span>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:0.84rem;font-weight:650;color:{INK};white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;">{primary}</div>'
            f'<div style="font-size:0.72rem;color:{MUTED};white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;">{secondary}</div>'
            f'</div>'
            f'<span style="flex-shrink:0;font-size:0.82rem;font-weight:800;color:{LIME_DK};">{metric}</span>'
            f'</div>'
        )
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def keyword_chips(pairs: list[tuple[str, int]]) -> None:
    """Render keyword frequency as sized emerald chips (bigger = more frequent)."""
    if not pairs:
        st.markdown(f'<div style="color:{MUTED};font-size:0.82rem;">Not enough text to analyse.</div>',
                    unsafe_allow_html=True)
        return
    max_c = max(c for _, c in pairs) or 1
    chips = ""
    for word, c in pairs:
        scale = c / max_c
        size = 0.72 + scale * 0.5
        weight = 500 + int(scale * 300)
        if scale > 0.66:
            bg, fg = "#6EE7B7", "#064E3B"
        elif scale > 0.34:
            bg, fg = "#BBF0D8", "#065F46"
        else:
            bg, fg = "#EAF3EF", "#1F2937"
        chips += (
            f'<span style="display:inline-block;background:{bg};color:{fg};'
            f'border-radius:10px;padding:4px 11px;margin:3px;font-size:{size:.2f}rem;'
            f'font-weight:{weight};">{word} <span style="opacity:0.55;font-size:0.7em;">{c}</span></span>'
        )
    st.markdown(f'<div style="line-height:2.1;">{chips}</div>', unsafe_allow_html=True)
