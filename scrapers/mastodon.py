"""
Mastodon scraper — public posts from Australian Mastodon instances.

Strategy:
  1. Convert the location string to Instagram-style hashtags (same helper used
     by the former Instagram scraper):
       "Newtown, Sydney NSW" → ["newtown", "newtownsydney", "sydney", "newtownaustralia"]
  2. For each hashtag query both Australian Mastodon instances:
       • aus.social    — largest Australian general-purpose instance
       • mastodon.au   — dedicated Australian instance
  3. Paginate each hashtag/instance timeline using `max_id` until cap is hit.
  4. Apply VADER sentiment to post text (HTML stripped first).
  5. Deduplicate by (instance, post_id).
  6. No authentication required — all endpoints are public.
"""

import html
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import core.storage as storage
from core.models import SearchJob, SocialPost
from scrapers.base import BaseScraper

log = logging.getLogger(__name__)
_vader = SentimentIntensityAnalyzer()

_INSTANCES   = ["aus.social", "mastodon.au"]
_PER_PAGE    = 40          # Mastodon API max per request
_PAGES_MAX   = 5           # pages per hashtag/instance combo
_SLEEP       = 1.0         # seconds between requests (stay polite)
_BODY_MAX    = 3_000
_TITLE_MAX   = 120


# ---------------------------------------------------------------------------
# Hashtag conversion  (shared logic with former instagram.py)
# ---------------------------------------------------------------------------

def _to_hashtags(location: str) -> list[str]:
    """
    Derive a ranked list of hashtags from a free-text location string.
    Same algorithm as the Instagram scraper; reused here for Mastodon.
    """
    tags: list[str] = []

    coord_re = re.compile(r"^-?\d+\.?\d*\s*,\s*-?\d+\.?\d*$")
    cleaned = location.strip()
    if coord_re.match(cleaned):
        return []

    cleaned = re.sub(r"[^\w,\s]", "", cleaned.lower())
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]

    _stop = {
        "nsw", "vic", "qld", "sa", "wa", "tas", "nt", "act",
        "australia", "au", "new south wales", "victoria", "queensland",
        "south australia", "western australia", "tasmania",
    }

    def slugify(s: str) -> str:
        return re.sub(r"\s+", "", s)

    def words(s: str) -> list[str]:
        return [w for w in s.split() if w not in _stop and len(w) > 1]

    if not parts:
        return []

    suburb_words = words(parts[0])
    suburb_clean = slugify(" ".join(suburb_words))

    city_words: list[str] = []
    city_clean = ""
    state_abbr = ""
    if len(parts) > 1:
        all_city_words = words(" ".join(parts[1:]))
        city_main  = [w for w in words(parts[1]) if len(w) > 3]
        city_clean = slugify(" ".join(city_main if city_main else all_city_words))
        city_words = all_city_words
        state_abbr = slugify(" ".join(
            w for w in words(" ".join(parts[1:])) if 2 <= len(w) <= 3
        ))

    if suburb_clean and suburb_clean not in _stop:
        tags.append(suburb_clean)

    if suburb_clean and city_clean and suburb_clean != city_clean:
        tags.append(suburb_clean + city_clean)

    if suburb_clean and state_abbr and suburb_clean + state_abbr not in tags:
        tags.append(suburb_clean + state_abbr)

    if city_clean and city_clean not in tags and city_clean not in _stop:
        tags.append(city_clean)

    if len(suburb_words) > 1:
        first_word = suburb_words[0]
        if first_word not in tags and first_word not in _stop:
            tags.append(first_word)

    aus_tag = suburb_clean + "australia"
    if aus_tag not in tags:
        tags.append(aus_tag)

    return [t for t in tags if t]


# ---------------------------------------------------------------------------
# HTML helper
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------

def _sentiment(text: str):
    if not text or not text.strip():
        return None, None
    c = _vader.polarity_scores(text)["compound"]
    label = "positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral"
    return round(c, 4), label


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class MastodonScraper(BaseScraper):
    name = "mastodon"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "UrbanDataScraper/1.0 (research)"})

    def _fetch_tag(
        self,
        instance: str,
        tag: str,
        seen: set[str],
        job_id: str,
        cap: int,
    ) -> int:
        """Paginate one hashtag timeline on one instance."""
        count  = 0
        url    = f"https://{instance}/api/v1/timelines/tag/{tag}"
        params = {"limit": _PER_PAGE}

        for _page in range(_PAGES_MAX):
            if cap and (len(seen) >= cap):
                break
            try:
                resp = self._session.get(url, params=params, timeout=10)
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                statuses = resp.json()
            except Exception as exc:
                log.warning("Mastodon %s/#%s error: %s", instance, tag, exc)
                break

            if not statuses:
                break

            for st in statuses:
                if cap and len(seen) >= cap:
                    break

                uid = f"{instance}:{st.get('id', '')}"
                if uid in seen:
                    continue
                seen.add(uid)

                sp = self._build_post(st, instance, tag, job_id)
                if sp:
                    storage.insert_social_post(sp)
                    count += 1

            # Pagination: use the `id` of the last post as max_id
            params["max_id"] = statuses[-1]["id"]
            time.sleep(_SLEEP)

        return count

    def _build_post(
        self,
        st: dict,
        instance: str,
        tag: str,
        job_id: str,
    ) -> Optional[SocialPost]:
        try:
            raw_content = st.get("content", "")
            text = _strip_html(raw_content)
            if not text:
                return None

            title = text[:_TITLE_MAX].replace("\n", " ").strip()
            body  = text[:_BODY_MAX]

            s_score, s_label = _sentiment(text)

            acct = st.get("account", {})
            author = acct.get("acct") or acct.get("username") or "unknown"

            pub_at: Optional[str] = None
            created = st.get("created_at")
            if created:
                try:
                    pub_at = datetime.fromisoformat(
                        created.replace("Z", "+00:00")
                    ).isoformat()
                except Exception:
                    pub_at = created

            return SocialPost(
                job_id=job_id,
                source="mastodon",
                post_id=f"{instance}_{st['id']}",
                subreddit=f"#{tag}@{instance}",      # hashtag + instance for context
                title=title,
                body=body,
                author=author,
                score=st.get("favourites_count", 0),
                comment_count=st.get("replies_count", 0),
                url=st.get("url") or f"https://{instance}/@{author}/{st.get('id','')}",
                latitude=None,
                longitude=None,
                sentiment_score=s_score,
                sentiment_label=s_label,
                published_at=pub_at,
            )
        except Exception as exc:
            log.debug("Skipping Mastodon post: %s", exc)
            return None

    def scrape(self, job: SearchJob) -> int:
        hashtags = _to_hashtags(job.location)
        if not hashtags:
            log.warning("MastodonScraper: could not derive hashtags from %r", job.location)
            return 0

        seen:  set[str] = set()
        count: int      = 0
        cap = job.max_results or 0

        for tag in hashtags:
            if cap and count >= cap:
                break
            for instance in _INSTANCES:
                if cap and count >= cap:
                    break
                n = self._fetch_tag(instance, tag, seen, job.id, cap)
                count += n

        return count
