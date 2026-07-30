"""
MedAssist AI - Project Launcher (Memory-Optimized)
==================================================
Run this file to start the backend and frontend servers simultaneously.

Usage:
    python main.py              - Start both backend and frontend
    python main.py --backend    - Start only the backend
    python main.py --frontend   - Start only the frontend
"""

import subprocess
import sys
import os
import signal
import time
import argparse

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

# Virtual environment python / uvicorn
VENV_PYTHON = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
VENV_UVICORN = os.path.join(BACKEND_DIR, ".venv", "Scripts", "uvicorn.exe")

# ── ANSI Colors ───────────────────────────────────────────────────────────────
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    BLUE    = "\033[94m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    MAGENTA = "\033[95m"


def log(prefix: str, color: str, msg: str):
    print(f"{color}{Color.BOLD}[{prefix}]{Color.RESET} {msg}", flush=True)


# ── Server starters ──────────────────────────────────────────────────────────
def start_backend() -> subprocess.Popen:
    log("BACKEND", Color.BLUE, "Starting FastAPI backend on http://0.0.0.0:8000 (accessible on network) ...")
    python_exe = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    cmd = [
        python_exe,
        "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    # Memory-optimized spawn (avoids WinError 1455 paging file exhaustion)
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=BACKEND_DIR,
        stdout=None,
        stderr=None,
        creationflags=flags,
    )
    return proc


def start_frontend() -> subprocess.Popen:
    log("FRONTEND", Color.GREEN, "Starting Next.js frontend on http://0.0.0.0:3000 (accessible on network) ...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    cmd = [npm_cmd, "run", "dev"]
    # Memory-optimized spawn
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=FRONTEND_DIR,
        stdout=None,
        stderr=None,
        creationflags=flags,
    )
    return proc


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="MedAssist AI - Project Launcher")
    parser.add_argument("--backend",  action="store_true", help="Start only the backend")
    parser.add_argument("--frontend", action="store_true", help="Start only the frontend")
    args = parser.parse_args()

    run_backend  = args.backend  or not args.frontend
    run_frontend = args.frontend or not args.backend

    print()
    print(f"{Color.MAGENTA}{Color.BOLD}{'=' * 55}")
    print(f"  MedAssist AI - Multi-Agent Healthcare Assistant")
    print(f"{'=' * 55}{Color.RESET}")
    print()

    processes: list[subprocess.Popen] = []

    try:
        if run_backend:
            processes.append(start_backend())
            time.sleep(1.0)

        if run_frontend:
            processes.append(start_frontend())

        log("LAUNCHER", Color.CYAN if hasattr(Color, 'CYAN') else Color.BLUE, "All services started successfully.")
        print()

        # Keep parent alive to listen for Ctrl+C
        while True:
            time.sleep(1.0)

    except KeyboardInterrupt:
        print()
        log("LAUNCHER", Color.YELLOW, "Shutting down services...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass
        log("LAUNCHER", Color.YELLOW, "All services stopped cleanly.")


if __name__ == "__main__":
    main()
