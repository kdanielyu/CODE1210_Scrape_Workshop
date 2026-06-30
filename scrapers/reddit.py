"""
Reddit scraper — TEMPLATE.

This file is an intentionally incomplete scaffold that shows you exactly how
to plug a new data source into the Urban Data Scraper pipeline.  Every section
marked  # TODO  is where you write your own code.

────────────────────────────────────────────────────────────────
HOW THIS FITS INTO THE ARCHITECTURE
────────────────────────────────────────────────────────────────

  Scraper.py (_build_scrapers)
      │
      └─► RedditScraper()          ← instantiated here
              │
              └─► .scrape(job)     ← called by core/runner.py in a background thread
                      │
                      ├─ calls Reddit API (via praw)
                      ├─ builds SocialPost dataclasses
                      └─ calls storage.insert_social_post(post)
                                 │
                                 └─► data/urban_data.db  (SQLite)

The dashboard pages (1_Results.py, 2_Compare.py, 3_Export.py) read from the
same database automatically — you don't need to touch the UI at all.

────────────────────────────────────────────────────────────────
TO ACTIVATE THIS SCRAPER
────────────────────────────────────────────────────────────────

1.  Install praw:
        pip install praw

    Or add  praw>=7.7  to requirements.txt and re-run  python3 run.py --install

2.  Register a Reddit "script" app at  https://www.reddit.com/prefs/apps
    and copy the credentials into your .env:

        REDDIT_CLIENT_ID=xxxxxxxxxxxx
        REDDIT_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
        REDDIT_USER_AGENT=UrbanDataScraper/1.0 by YourUsername

3.  Fill in the three  # TODO  sections below.

4.  Register the scraper in Scraper.py → _build_scrapers():

        mapping = {
            "Google Places": ("scrapers.google_places", "GooglePlacesScraper"),
            "Mastodon":      ("scrapers.mastodon",       "MastodonScraper"),
            "Reddit":        ("scrapers.reddit",         "RedditScraper"),   # ← add this
        }

    Then add a checkbox in the "Data sources" section of the same file:
        use_reddit = sc3.checkbox("🟠 Reddit", value=False)

5.  Add "reddit" to SOURCE_CONFIG in utils.py:
        "reddit": {"label": "Reddit", "icon": "🟠", "color": "#FF4500", "soft": "#FFE9DF"},

────────────────────────────────────────────────────────────────
REFERENCE: key types you will use
────────────────────────────────────────────────────────────────

  SearchJob (core/models.py)
    .id          str   — unique job UUID, use as job_id for every record
    .location    str   — free-text location, e.g. "Newtown, Sydney NSW"
    .latitude    float — geocoded lat
    .longitude   float — geocoded lng
    .radius_m    int   — search radius in metres
    .max_results int   — hard cap per source (0 = unlimited)

  SocialPost (core/models.py)
    .job_id          str
    .source          str           — use "reddit"
    .post_id         str           — unique ID from the platform
    .subreddit       str | None    — subreddit name, e.g. "r/sydney"
    .title           str           — post headline
    .body            str           — post text / selftext
    .author          str           — username
    .score           int           — upvotes (or likes)
    .comment_count   int
    .url             str
    .latitude        float | None  — set if available
    .longitude       float | None  — set if available
    .sentiment_score float | None  — VADER compound score  [-1, +1]
    .sentiment_label str | None    — "positive" | "neutral" | "negative"
    .published_at    str | None    — ISO-8601 datetime string

────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import core.storage as storage
from core.models import SearchJob, SocialPost
from scrapers.base import BaseScraper

load_dotenv()

log = logging.getLogger(__name__)
_vader = SentimentIntensityAnalyzer()

# ---------------------------------------------------------------------------
# Constants — tune these to control scrape volume and politeness
# ---------------------------------------------------------------------------

_POST_LIMIT   = 100   # max posts fetched per subreddit search
_BODY_MAX     = 3_000 # truncate long selftext to this many characters
_TITLE_MAX    = 300   # truncate long titles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sentiment(text: str) -> tuple[Optional[float], Optional[str]]:
    """Run VADER sentiment on *text*. Returns (compound_score, label)."""
    if not text or not text.strip():
        return None, None
    compound = _vader.polarity_scores(text)["compound"]
    label = "positive" if compound >= 0.05 else "negative" if compound <= -0.05 else "neutral"
    return round(compound, 4), label


def _location_to_subreddits(location: str) -> list[str]:
    """
    Derive a list of candidate subreddit names from a free-text location.

    This is a simple heuristic — feel free to improve it.

    Examples
    --------
    "Newtown, Sydney NSW"  →  ["sydney", "newsouthwales", "australia"]
    "Fitzroy, Melbourne"   →  ["melbourne", "victoria", "australia"]
    "Brisbane CBD"         →  ["brisbane", "queensland", "australia"]
    """
    import re

    candidates: list[str] = []

    # Strip coordinates — no subreddit to derive
    if re.match(r"^-?\d+\.?\d*\s*,\s*-?\d+\.?\d*$", location.strip()):
        return ["australia"]

    lower = location.lower()
    parts = [p.strip() for p in re.sub(r"[^\w,\s]", "", lower).split(",") if p.strip()]

    # State → subreddit mapping
    _state_map = {
        "nsw": "newsouthwales",   "new south wales": "newsouthwales",
        "vic": "victoria",        "victoria": "victoria",
        "qld": "queensland",      "queensland": "queensland",
        "sa":  "southaustralia",  "south australia": "southaustralia",
        "wa":  "westernaustralia","western australia": "westernaustralia",
        "tas": "tasmania",        "tasmania": "tasmania",
        "act": "canberra",        "nt": "darwin",
    }

    # City → subreddit mapping (extend as needed)
    _city_map = {
        "sydney": "sydney", "melbourne": "melbourne", "brisbane": "brisbane",
        "perth": "perth", "adelaide": "adelaide", "canberra": "canberra",
        "hobart": "hobart", "darwin": "darwin", "gold coast": "goldcoast",
        "newcastle": "newcastle", "wollongong": "wollongong",
    }

    for part in parts:
        stripped = " ".join(w for w in part.split() if len(w) > 1)
        # Check city map
        for city_key, sub in _city_map.items():
            if city_key in stripped and sub not in candidates:
                candidates.append(sub)
                break
        # Check state map
        for state_key, sub in _state_map.items():
            if state_key in stripped and sub not in candidates:
                candidates.append(sub)
                break

    candidates.append("australia")
    return candidates


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class RedditScraper(BaseScraper):
    """
    Scrape location-relevant Reddit posts using the PRAW library.

    The scraper searches candidate subreddits derived from the job's location
    string and stores results as SocialPost records.
    """

    name = "reddit"

    def __init__(self) -> None:
        # ── TODO 1 of 3 ──────────────────────────────────────────────────
        # Initialise the PRAW Reddit client using your .env credentials.
        #
        # Install praw first:  pip install praw
        #
        # Example:
        #
        #   import praw
        #
        #   client_id     = os.getenv("REDDIT_CLIENT_ID", "")
        #   client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
        #   user_agent    = os.getenv("REDDIT_USER_AGENT", "UrbanDataScraper/1.0")
        #
        #   if not client_id or not client_secret:
        #       raise EnvironmentError(
        #           "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set in .env.\n"
        #           "Register a script app at https://www.reddit.com/prefs/apps"
        #       )
        #
        #   self.reddit = praw.Reddit(
        #       client_id=client_id,
        #       client_secret=client_secret,
        #       user_agent=user_agent,
        #       read_only=True,
        #   )
        #
        # ─────────────────────────────────────────────────────────────────
        raise NotImplementedError(
            "RedditScraper is not yet configured.\n"
            "Open scrapers/reddit.py and complete the three TODO sections."
        )

    def _build_post(
        self,
        submission,          # praw.models.Submission
        subreddit_name: str,
        job_id: str,
    ) -> Optional[SocialPost]:
        """
        Convert a PRAW Submission object into a SocialPost dataclass.

        ── TODO 2 of 3 ──────────────────────────────────────────────────
        Map the PRAW Submission fields to SocialPost fields.

        Useful PRAW Submission attributes:
          submission.id              — unique Reddit post ID
          submission.title           — post headline
          submission.selftext        — body text (empty for link posts)
          submission.author.name     — username (may raise AttributeError if deleted)
          submission.score           — net upvotes
          submission.num_comments    — comment count
          submission.permalink       — path, prefix with "https://reddit.com"
          submission.created_utc     — Unix timestamp (float)
          submission.subreddit.display_name — subreddit name

        Example:
        ─────────────────────────────────────────────────────────────────

        try:
            title = submission.title[:_TITLE_MAX]
            body  = (submission.selftext or "")[:_BODY_MAX]
            text  = f"{title} {body}".strip()
            s_score, s_label = _sentiment(text)

            try:
                author = submission.author.name
            except AttributeError:
                author = "[deleted]"

            pub_at = datetime.fromtimestamp(
                submission.created_utc, tz=timezone.utc
            ).isoformat()

            return SocialPost(
                job_id=job_id,
                source="reddit",
                post_id=submission.id,
                subreddit=f"r/{subreddit_name}",
                title=title,
                body=body,
                author=author,
                score=submission.score,
                comment_count=submission.num_comments,
                url=f"https://reddit.com{submission.permalink}",
                latitude=None,
                longitude=None,
                sentiment_score=s_score,
                sentiment_label=s_label,
                published_at=pub_at,
            )
        except Exception as exc:
            log.debug("Skipping Reddit post %s: %s", getattr(submission, "id", "?"), exc)
            return None

        ─────────────────────────────────────────────────────────────────
        """
        # Remove this line once you implement the method above.
        raise NotImplementedError("Complete TODO 2 in scrapers/reddit.py")

    def scrape(self, job: SearchJob) -> int:
        """
        Search candidate subreddits for posts relevant to job.location.

        ── TODO 3 of 3 ──────────────────────────────────────────────────
        Use PRAW to search each candidate subreddit and insert results.

        Pattern to follow:

        subreddits = _location_to_subreddits(job.location)
        seen:  set[str] = set()
        count: int      = 0
        cap   = job.max_results or 0

        for sub_name in subreddits:
            if cap and count >= cap:
                break

            query = job.location.split(",")[0].strip()   # e.g. "Newtown"

            try:
                sub = self.reddit.subreddit(sub_name)
                # Search the subreddit for posts mentioning the location.
                # You can also try sub.hot(), sub.new(), sub.top() etc.
                for submission in sub.search(query, limit=_POST_LIMIT, sort="new"):
                    if cap and count >= cap:
                        break
                    if submission.id in seen:
                        continue
                    seen.add(submission.id)

                    post = self._build_post(submission, sub_name, job.id)
                    if post:
                        storage.insert_social_post(post)
                        count += 1

            except Exception as exc:
                log.warning("Reddit r/%s error: %s", sub_name, exc)

        return count

        ─────────────────────────────────────────────────────────────────
        """
        # Remove this line once you implement the method above.
        raise NotImplementedError("Complete TODO 3 in scrapers/reddit.py")
