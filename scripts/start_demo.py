#!/usr/bin/env python3
"""
Utility script to launch the backend Flask app and the Vue frontend together.
Ideal for demos: `python scripts/start_demo.py`.
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
    parser = argparse.ArgumentParser(description="Start backend and frontend for demo sessions.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to run the backend (default: current interpreter).",
    )
    parser.add_argument(
        "--npm",
        default="npm",
        help="npm binary to use for the frontend (default: npm on PATH).",
    )
    return parser.parse_args()


def start_processes(commands: List[Tuple[str, List[str], Path]]) -> List[Tuple[str, subprocess.Popen]]:
    processes: List[Tuple[str, subprocess.Popen]] = []
    for name, cmd, cwd in commands:
        proc = subprocess.Popen(cmd, cwd=str(cwd))
        processes.append((name, proc))
        print(f"[demo] started {name} (pid={proc.pid}) -> {' '.join(cmd)}")
    return processes


def stop_processes(processes: List[Tuple[str, subprocess.Popen]]) -> None:
    for name, proc in processes:
        if proc.poll() is None:
            print(f"[demo] stopping {name} (pid={proc.pid})")
            proc.terminate()
    for name, proc in processes:
        if proc.poll() is None:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"[demo] force killing {name} (pid={proc.pid})")
                proc.kill()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    commands = [
        ("backend", [args.python, "backend/app.py"], repo_root),
        ("frontend", [args.npm, "run", "serve"], repo_root / "frontend"),
    ]

    processes = start_processes(commands)
    print("[demo] both processes running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
            for name, proc in processes:
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} exited with code {proc.returncode}")
    except KeyboardInterrupt:
        print("\n[demo] Ctrl+C received.")
    except RuntimeError as exc:
        print(f"[demo] {exc}")
    finally:
        stop_processes(processes)
        print("[demo] shutdown complete.")


if __name__ == "__main__":
    # Improve Ctrl+C responsiveness on Windows
    if os.name == "nt":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()
