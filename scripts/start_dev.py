#!/usr/bin/env python3
"""
Launch the backend Flask app and optionally the Vue frontend dev server.

Usage:
    python scripts/start_dev.py           # backend + frontend dev server
    python scripts/start_dev.py --backend-only  # backend only (demo mode)
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
    parser = argparse.ArgumentParser(description="Start backend and frontend.")
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Only start the backend (no frontend dev server).",
    )
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
        proc = subprocess.Popen(cmd, cwd=str(cwd))
        processes.append((name, proc))
        print(f"[dev] started {name} (pid={proc.pid}) -> {' '.join(cmd)}")
    return processes


def stop_processes(processes: List[Tuple[str, subprocess.Popen]]) -> None:
    for name, proc in processes:
        if proc.poll() is None:
            print(f"[dev] stopping {name} (pid={proc.pid})")
            proc.terminate()
    for name, proc in processes:
        if proc.poll() is None:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"[dev] force killing {name} (pid={proc.pid})")
                proc.kill()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    commands = [
        ("backend", [args.python, "backend/app.py"], repo_root),
    ]

    if not args.backend_only:
        frontend_dir = repo_root / "frontend"
        commands.append(("frontend", [args.npm, "run", "serve"], frontend_dir))

    processes = start_processes(commands)
    mode = "backend only" if args.backend_only else "backend + frontend"
    print(f"[dev] running ({mode}). Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} exited with code {proc.returncode}")
    except KeyboardInterrupt:
        print("\n[dev] Ctrl+C received.")
    except RuntimeError as exc:
        print(f"[dev] {exc}")
    finally:
        stop_processes(processes)
        print("[dev] shutdown complete.")


if __name__ == "__main__":
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
