#!/usr/bin/env python3
"""
Utility script to launch the backend Flask app and the Vue frontend in DEV mode.
Usage: `python scripts/start_dev.py`
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start backend and frontend for development.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to run the backend (default: current interpreter).",
    )
    parser.add_argument(
        "--npm",
        default="npm.cmd" if os.name == "nt" else "npm",
        help="npm binary to use for the frontend (default: npm on PATH).",
    )
    return parser.parse_args()


def start_processes(commands: List[Tuple[str, List[str], Path]]) -> List[Tuple[str, subprocess.Popen]]:
    processes: List[Tuple[str, subprocess.Popen]] = []
    for name, cmd, cwd in commands:
        # For npm run serve, we want to see the output
        proc = subprocess.Popen(cmd, cwd=str(cwd))
        processes.append((name, proc))
        print(f"[dev] started {name} (pid={proc.pid}) -> {' '.join(cmd)}")
    return processes


def stop_processes(processes: List[Tuple[str, subprocess.Popen]]) -> None:
    for name, proc in processes:
        if proc.poll() is None:
            print(f"[dev] stopping {name} (pid={proc.pid})")
            # On Windows, terminate might not kill the whole tree, but for dev it's usually okay
            proc.terminate()
    for name, proc in processes:
        if proc.poll() is None:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[dev] force killing {name} (pid={proc.pid})")
                proc.kill()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    frontend_dir = repo_root / "frontend"

    commands = [
        ("backend", [args.python, "backend/app.py"], repo_root),
        ("frontend", [args.npm, "run", "serve"], frontend_dir),
    ]

    processes = start_processes(commands)
    print("[dev] backend and frontend (dev server) running.")
    print("[dev] Backend: http://localhost:5000")
    print("[dev] Frontend: http://localhost:8080 (usually)")
    print("[dev] Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    # If one crashes, we should probably stop the other
                    raise RuntimeError(f"{name} exited with code {proc.returncode}")
    except KeyboardInterrupt:
        print("\n[dev] Ctrl+C received.")
    except RuntimeError as exc:
        print(f"[dev] {exc}")
    finally:
        stop_processes(processes)
        print("[dev] shutdown complete.")


if __name__ == "__main__":
    # Improve Ctrl+C responsiveness on Windows
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
