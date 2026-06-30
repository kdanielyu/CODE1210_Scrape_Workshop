"""
scrapers — pluggable data-source connectors.

Each scraper subclasses BaseScraper and implements scrape(job) -> int.
Register new scrapers in Scraper.py _build_scrapers() to expose them in the UI.

Active scrapers
---------------
google_places.py  — Google Maps Places API (requires API key)
mastodon.py       — Mastodon public hashtag timelines (no key required)

Template
--------
reddit.py         — Reddit via PRAW (fill in the three TODO sections)
"""
