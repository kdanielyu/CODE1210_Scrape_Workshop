"""
run.py — one-command launcher for Urban Data Scraper.

Works on a clean machine even when the system Python is
"externally managed" (PEP 668 — common on macOS/Homebrew and
Debian/Ubuntu). It does this by creating an isolated virtual
environment (.venv) and installing everything there, so pip never
touches the protected system Python.

Usage:
    python3 run.py              # set up .venv (if needed) + install deps + launch
    python3 run.py --install    # set up .venv + install deps only, then exit
    python3 run.py --no-install # skip the dependency step, launch immediately
    python3 run.py --no-venv    # use the current Python instead of creating .venv
"""

from __future__ import annotations

import argparse
import os
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
VENV = ROOT / ".venv"

MIN_PYTHON = (3, 10)

# Set in the environment when we re-launch inside .venv, so the child
# process knows not to try bootstrapping a venv again.
BOOTSTRAP_FLAG = "UDS_IN_VENV"


# ---------------------------------------------------------------------------
# Pretty output
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
# Virtual-environment helpers
# ---------------------------------------------------------------------------

def venv_python(venv: Path) -> Path:
    """Path to the python interpreter inside a venv (cross-platform)."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def in_managed_env() -> bool:
    """True if we're already inside a virtualenv/venv or a conda env."""
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return True
    if os.environ.get("CONDA_PREFIX"):
        return True
    return False


def bootstrap_venv_and_reexec(passthrough_args: list[str]) -> None:
    """Create .venv (if needed) and re-run this script with its interpreter.

    This is the key fix for the 'externally-managed-environment' error:
    pip runs inside the venv, which is never externally managed.
    """
    py = venv_python(VENV)

    if not py.exists():
        heading("Creating an isolated virtual environment (.venv) ...")
        info("This avoids the 'externally-managed-environment' pip error.")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
        except subprocess.CalledProcessError:
            error("Could not create a virtual environment with 'python -m venv'.")
            warn(
                "On Debian/Ubuntu, install the venv package first:\n"
                "        sudo apt install python3-venv\n"
                "     Then re-run:  python3 run.py"
            )
            sys.exit(1)
        ok(f"Virtual environment created: {VENV.name}/")
    else:
        ok(f"Reusing virtual environment: {VENV.name}/")

    # Re-run this exact script using the venv's interpreter.
    env = os.environ.copy()
    env[BOOTSTRAP_FLAG] = "1"
    cmd = [str(py), str(Path(__file__).resolve()), *passthrough_args]
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)


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
    heading("Installing / verifying dependencies ...")
    # Upgrade pip first — old pip in fresh venvs sometimes can't resolve wheels.
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        check=False,
    )
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQ)],
        check=False,
    )
    if result.returncode != 0:
        error("pip install failed (see the messages above).")
        warn(
            "If the error mentions 'externally-managed-environment', run the\n"
            "     launcher WITHOUT --no-venv so it installs inside .venv:\n"
            "        python3 run.py"
        )
        sys.exit(result.returncode)
    ok("All dependencies satisfied.")


def prepare_data_dir() -> None:
    (DATA / "exports").mkdir(parents=True, exist_ok=True)
    ok(f"Data directory ready: {DATA}")


def check_env() -> None:
    if ENV.exists():
        ok(".env found.")
        return

    example = ROOT / ".env.example"
    if example.exists():
        ENV.write_text(example.read_text())
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
    try:
        result = subprocess.run(
            [sys.executable, "-m", "streamlit", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        ok(f"Streamlit {result.stdout.strip()}")
    except Exception:
        error(
            "Streamlit is not installed in this environment. "
            "Run  python3 run.py --install  first."
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def launch() -> None:
    heading("Starting Urban Data Scraper ...")
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
        help="Set up the environment and install dependencies only, then exit.",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Skip the pip install step and launch immediately.",
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Use the current Python instead of creating/using .venv.",
    )
    args = parser.parse_args()

    bootstrapped = os.environ.get(BOOTSTRAP_FLAG) == "1"

    if not bootstrapped:
        heading("Urban Data Scraper — startup")
        print()
        check_python()

        # Use a virtual environment unless the user opted out or is already
        # inside a managed environment (venv / virtualenv / conda).
        if not args.no_venv and not in_managed_env():
            bootstrap_venv_and_reexec(sys.argv[1:])
            return  # not reached — bootstrap re-execs and exits

        if in_managed_env():
            ok(f"Using active environment: {Path(sys.prefix).name}")
        else:
            warn("Installing into the system Python (--no-venv).")
    else:
        ok(f"Active environment: {VENV.name}/  (Python {sys.version.split()[0]})")

    prepare_data_dir()
    check_env()

    if not args.no_install:
        install_requirements()

    if args.install:
        ok("Setup complete. Run  python3 run.py  to start the dashboard.")
        return

    check_streamlit()
    launch()


if __name__ == "__main__":
    main()
