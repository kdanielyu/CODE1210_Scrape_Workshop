from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


def _now() -> str:
    return datetime.now().isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class SearchJob:
    location: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    radius_m: int = 1000
    sources: str = ""          # comma-separated, e.g. "google, reddit"
    place_types: str = ""      # comma-separated Google place types to scrape
    min_results: int = 0       # soft target: keep searching until reached (0 = off)
    max_results: int = 0       # hard cap per source (0 = unlimited)
    status: str = "pending"    # pending | running | completed | failed
    id: str = field(default_factory=_uuid)
    created_at: str = field(default_factory=_now)
    completed_at: Optional[str] = None
    record_count: int = 0
    error: Optional[str] = None


@dataclass
class Place:
    job_id: str
    source: str                 # google | yelp
    place_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    rating: Optional[float] = None
    review_count: Optional[int] = None
    categories: str = ""
    price_level: Optional[int] = None
    phone: Optional[str] = None
    url: Optional[str] = None
    fetched_at: str = field(default_factory=_now)


@dataclass
class Review:
    job_id: str
    source: str                 # google | yelp
    place_id: str
    place_name: str
    author: str
    rating: Optional[float]
    text: str
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None  # positive | neutral | negative
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=_now)


@dataclass
class SocialPost:
    job_id: str
    source: str                 # mastodon
    post_id: str
    subreddit: Optional[str]
    title: str
    body: str
    author: str
    score: int
    comment_count: int
    url: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None  # positive | neutral | negative
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=_now)
