"""
Google Places scraper — comprehensive multi-type search.

Strategy:
  1. Run places_nearby for each of PLACE_TYPES (15 categories).
  2. Paginate the full 3 pages per type (60 results) with retry logic,
     because Google's next_page_token needs a moment to become valid.
  3. Deduplicate across types by place_id.
  4. Fetch Place Details (incl. up to 5 reviews) for every unique place.
  5. Apply VADER sentiment to each review text.

Note on review limits: Google's official Places API returns a maximum of
5 reviews per place (most-relevant). There is no public endpoint to page
through every review, so 5/place is the comprehensive ceiling via the API.
"""

import os
import time
from datetime import datetime

import googlemaps
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import core.storage as storage
from core.models import Place, Review, SearchJob
from scrapers.base import BaseScraper

load_dotenv()

_vader = SentimentIntensityAnalyzer()

MAX_PAGES = 3          # Google hard-caps nearby search at 3 pages (60 results)
PAGE_RETRIES = 4       # retries while waiting for next_page_token to activate

# Broad coverage across urban POI types
PLACE_TYPES = [
    "restaurant",
    "cafe",
    "bar",
    "meal_takeaway",
    "lodging",
    "shopping_mall",
    "store",
    "supermarket",
    "park",
    "tourist_attraction",
    "museum",
    "gym",
    "hospital",
    "school",
    "transit_station",
]

# Friendly labels for the dashboard's data-type selector
PLACE_TYPE_LABELS: dict[str, str] = {
    "restaurant":         "Restaurants",
    "cafe":               "Cafes",
    "bar":                "Bars & pubs",
    "meal_takeaway":      "Takeaway",
    "lodging":            "Hotels & lodging",
    "shopping_mall":      "Shopping malls",
    "store":              "Shops & retail",
    "supermarket":        "Supermarkets",
    "park":               "Parks",
    "tourist_attraction": "Attractions",
    "museum":             "Museums & galleries",
    "gym":                "Gyms & fitness",
    "hospital":           "Hospitals & clinics",
    "school":             "Schools",
    "transit_station":    "Transit stations",
}


def _sentiment(text: str):
    if not text or not text.strip():
        return None, None
    c = _vader.polarity_scores(text)["compound"]
    label = "positive" if c >= 0.05 else "negative" if c <= -0.05 else "neutral"
    return round(c, 4), label


class GooglePlacesScraper(BaseScraper):
    name = "google"

    def __init__(self) -> None:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GOOGLE_MAPS_API_KEY is not set in .env")
        self.client = googlemaps.Client(key=api_key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_page(self, lat, lng, radius, ptype, token):
        """Fetch the next page, retrying until the token activates."""
        for attempt in range(PAGE_RETRIES):
            time.sleep(2.0 + attempt)  # progressive backoff: 2s, 3s, 4s, 5s
            try:
                res = self.client.places_nearby(
                    location=(lat, lng), radius=radius, type=ptype, page_token=token
                )
                status = res.get("status")
                if status == "OK":
                    return res
                if status == "INVALID_REQUEST":
                    continue   # token not ready yet — wait and retry
                return None     # ZERO_RESULTS or other terminal status
            except Exception:
                continue
        return None

    def _paginate_nearby(self, lat, lng, radius, ptype) -> list:
        """Fetch all available pages of a nearby search for one place type."""
        collected = []
        try:
            result = self.client.places_nearby(
                location=(lat, lng), radius=radius, type=ptype
            )
        except Exception:
            return collected

        for _ in range(MAX_PAGES):
            collected.extend(result.get("results", []))
            token = result.get("next_page_token")
            if not token:
                break
            result = self._next_page(lat, lng, radius, ptype, token)
            if result is None:
                break

        return collected

    def _fetch_reviews(self, place_id: str) -> tuple[list, str | None, str | None]:
        """Fetch up to 5 reviews + phone + website from Place Details."""
        try:
            resp = self.client.place(
                place_id,
                fields=["reviews", "formatted_phone_number", "website"],
            )
            result = resp.get("result", {})
            return (
                result.get("reviews", []),
                result.get("formatted_phone_number"),
                result.get("website"),
            )
        except Exception:
            return [], None, None

    # ------------------------------------------------------------------
    # Main scrape
    # ------------------------------------------------------------------

    def scrape(self, job: SearchJob) -> int:
        seen_place_ids: set[str] = set()
        count = 0
        n_places = 0

        # Which categories to search: user-selected first, then the remaining
        # defaults as a fallback used only to reach the min_results target.
        selected = [t.strip() for t in (job.place_types or "").split(",") if t.strip()]
        primary = selected if selected else list(PLACE_TYPES)
        fallback = [t for t in PLACE_TYPES if t not in primary]
        search_order = primary + fallback
        n_primary = len(primary)

        max_results = job.max_results or 0   # 0 = unlimited
        min_results = job.min_results or 0

        for idx, ptype in enumerate(search_order):
            # Stop once the hard cap is reached.
            if max_results and n_places >= max_results:
                break
            # Only dip into fallback categories if we still need to hit min.
            if idx >= n_primary:
                if not min_results or n_places >= min_results:
                    break

            raw_results = self._paginate_nearby(
                job.latitude, job.longitude, job.radius_m, ptype
            )

            for p in raw_results:
                if max_results and n_places >= max_results:
                    break
                place_id = p.get("place_id", "")
                if not place_id or place_id in seen_place_ids:
                    continue
                seen_place_ids.add(place_id)

                name = p.get("name", "")
                loc = p.get("geometry", {}).get("location", {})

                # Fetch reviews + contact details for rated places
                reviews, phone, website = [], None, None
                if p.get("user_ratings_total", 0) > 0:
                    reviews, phone, website = self._fetch_reviews(place_id)
                    time.sleep(0.06)

                place = Place(
                    job_id=job.id,
                    source="google",
                    place_id=place_id,
                    name=name,
                    address=p.get("vicinity", ""),
                    latitude=loc.get("lat", 0.0),
                    longitude=loc.get("lng", 0.0),
                    rating=p.get("rating"),
                    review_count=p.get("user_ratings_total"),
                    categories=", ".join(p.get("types", [])),
                    price_level=p.get("price_level"),
                    phone=phone,
                    url=website,
                )
                storage.insert_place(place)
                count += 1
                n_places += 1

                for r in reviews:
                    text = r.get("text", "")
                    s_score, s_label = _sentiment(text)
                    pub_ts = r.get("time")
                    pub_at = (
                        datetime.fromtimestamp(pub_ts).isoformat()
                        if pub_ts else None
                    )
                    review = Review(
                        job_id=job.id,
                        source="google",
                        place_id=place_id,
                        place_name=name,
                        author=r.get("author_name", ""),
                        rating=r.get("rating"),
                        text=text,
                        sentiment_score=s_score,
                        sentiment_label=s_label,
                        published_at=pub_at,
                    )
                    storage.insert_review(review)
                    count += 1

        return count
