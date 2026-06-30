"""
run.py — one-command launcher for Urban Data Scraper.

Usage:
    python3 run.py            # install deps (if needed) + start Streamlit
    python3 run.py --install  # install / refresh deps only, then exit
    python3 run.py --no-install  # skip dependency check, launch immediately
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root (same directory as this file)
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.resolve()
REQ  = ROOT / "requirements.txt"
ENV  = ROOT / ".env"
DATA = ROOT / "data"
MAIN = ROOT / "Scraper.py"

MIN_PYTHON = (3, 10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _colour(code: int, text: str) -> str:
    """Wrap text in an ANSI colour escape if the terminal supports it."""
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text


def info(msg: str)    -> None: print(_colour(36, f"  ▸  {msg}"))
def ok(msg: str)      -> None: print(_colour(32, f"  ✔  {msg}"))
def warn(msg: str)    -> None: print(_colour(33, f"  ⚠  {msg}"))
def error(msg: str)   -> None: print(_colour(31, f"  ✖  {msg}"), file=sys.stderr)
def heading(msg: str) -> None: print(_colour(1,  f"\n{msg}"))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        error(
            f"Python {'.'.join(map(str, MIN_PYTHON))}+ is required "
            f"(you have {sys.version.split()[0]})."
        )
        sys.exit(1)
    ok(f"Python {sys.version.split()[0]}")


def install_requirements() -> None:
    heading("Installing / verifying dependencies …")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQ)],
        check=False,
    )
    if result.returncode != 0:
        error("pip install failed. Fix the errors above and re-run.")
        sys.exit(result.returncode)
    ok("All dependencies satisfied.")


def prepare_data_dir() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    ok(f"Data directory ready: {DATA}")


def check_env() -> None:
    if ENV.exists():
        ok(".env found.")
        return

    example = ROOT / ".env.example"
    if example.exists():
        shutil.copy(example, ENV)
        warn(
            ".env was missing — copied from .env.example.\n"
            "     Open .env and add your GOOGLE_MAPS_API_KEY before scraping."
        )
    else:
        warn(
            ".env not found. Create one with at minimum:\n"
            "     GOOGLE_MAPS_API_KEY=your_key_here\n"
            "     (See README.md for all options.)"
        )


def check_streamlit() -> None:
    if shutil.which("streamlit") is None:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "streamlit", "--version"],
                capture_output=True,
                check=True,
            )
            ok(f"Streamlit {result.stdout.decode().strip()}")
        except Exception:
            error(
                "streamlit is not accessible. "
                "Run  python3 run.py --install  first."
            )
            sys.exit(1)
    else:
        ok("Streamlit found.")


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def launch() -> None:
    heading("Starting Urban Data Scraper …")
    print()
    info("Dashboard →  http://localhost:8501")
    info("Press Ctrl+C to stop.")
    print()

    cmd = [
        sys.executable, "-m", "streamlit", "run", str(MAIN),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    os.chdir(ROOT)
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print()
        ok("Server stopped.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Urban Data Scraper — local launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install / refresh dependencies only, then exit.",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip the pip install step and launch immediately.",
    )
    args = parser.parse_args()

    heading("Urban Data Scraper — startup")
    print()

    check_python()
    prepare_data_dir()
    check_env()

    if not args.no_install:
        install_requirements()

    if args.install:
        ok("Dependencies installed. Run  python3 run.py  to start the dashboard.")
        return

    check_streamlit()
    launch()


if __name__ == "__main__":
    main()
