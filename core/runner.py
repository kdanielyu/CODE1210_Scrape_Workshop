import threading
from datetime import datetime
from typing import Callable, List

from .models import SearchJob
from .storage import count_records, update_job_status, upsert_job

# Process-level registry so threads survive Streamlit reruns.
_threads: dict[str, threading.Thread] = {}
_lock = threading.Lock()


def is_running(job_id: str) -> bool:
    with _lock:
        t = _threads.get(job_id)
        return t is not None and t.is_alive()


def launch(job: SearchJob, scrapers: List[Callable[[SearchJob], int]]) -> None:
    """Persist the job and spawn a daemon thread to run all scrapers."""

    def _worker() -> None:
        try:
            update_job_status(job.id, "running")
            for scraper_fn in scrapers:
                scraper_fn(job)
            total = count_records(job.id)
            update_job_status(
                job.id,
                status="completed",
                record_count=total,
                completed_at=datetime.now().isoformat(),
            )
        except Exception as exc:
            update_job_status(job.id, status="failed", error=str(exc))
        finally:
            with _lock:
                _threads.pop(job.id, None)

    upsert_job(job)
    t = threading.Thread(target=_worker, daemon=True, name=f"scraper-{job.id[:8]}")
    with _lock:
        _threads[job.id] = t
    t.start()
