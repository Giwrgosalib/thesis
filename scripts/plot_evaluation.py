"""
Generate thesis-ready charts from results/evaluation.json.

Usage:
    python scripts/plot_evaluation.py
    python scripts/plot_evaluation.py --input results/evaluation.json --outdir results/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.3,
})

LEGACY_COLOR = "#4A90D9"
NEXTGEN_COLOR = "#E85D3A"
ACCENT = "#2ECC71"


def load_data(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def plot_overall_prf(data: dict, outdir: Path):
    metrics = ["precision", "recall", "f1"]
    labels = ["Precision", "Recall", "F1"]
    legacy_vals = [data["legacy"][m] for m in metrics]
    nextgen_vals = [data["nextgen"][m] for m in metrics]

    x = np.arange(len(labels))
    width = 0.32

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars1 = ax.bar(x - width / 2, legacy_vals, width, label="Legacy (BiLSTM-CRF)",
                   color=LEGACY_COLOR, edgecolor="white", linewidth=0.5)
    bars2 = ax.bar(x + width / 2, nextgen_vals, width, label="NextGen (DeBERTa)",
                   color=NEXTGEN_COLOR, edgecolor="white", linewidth=0.5)

    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=10, color=LEGACY_COLOR)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{bar.get_height():.2f}", ha="center", va="bottom", fontsize=10, color=NEXTGEN_COLOR)

    ax.set_ylabel("Score")
    ax.set_title("Overall Entity-Level Metrics (1000 test queries)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(outdir / "overall_prf.png")
    plt.close(fig)
    print(f"  Saved overall_prf.png")


def plot_per_type_f1(data: dict, outdir: Path, min_support: int = 10):
    legacy_pt = data["legacy"]["per_type"]
    nextgen_pt = data["nextgen"]["per_type"]

    all_types = sorted(set(legacy_pt) | set(nextgen_pt))
    types = [t for t in all_types
             if legacy_pt.get(t, {}).get("support", 0) >= min_support
             or nextgen_pt.get(t, {}).get("support", 0) >= min_support]
    types.sort(key=lambda t: nextgen_pt.get(t, {}).get("f1", 0), reverse=True)

    legacy_f1 = [legacy_pt.get(t, {}).get("f1", 0) for t in types]
    nextgen_f1 = [nextgen_pt.get(t, {}).get("f1", 0) for t in types]
    supports = [max(legacy_pt.get(t, {}).get("support", 0),
                    nextgen_pt.get(t, {}).get("support", 0)) for t in types]

    y = np.arange(len(types))
    height = 0.35

    fig, ax = plt.subplots(figsize=(9, max(4, len(types) * 0.55)))
    ax.barh(y + height / 2, legacy_f1, height, label="Legacy (BiLSTM-CRF)",
            color=LEGACY_COLOR, edgecolor="white", linewidth=0.5)
    ax.barh(y - height / 2, nextgen_f1, height, label="NextGen (DeBERTa)",
            color=NEXTGEN_COLOR, edgecolor="white", linewidth=0.5)

    for i, (lf, nf, sup) in enumerate(zip(legacy_f1, nextgen_f1, supports)):
        ax.text(max(lf, nf) + 0.02, i, f"n={sup}", va="center", fontsize=8, color="#666")

    ax.set_yticks(y)
    ax.set_yticklabels(types)
    ax.set_xlabel("F1 Score")
    ax.set_title(f"Per-Entity-Type F1 (types with support >= {min_support})")
    ax.set_xlim(0, 1.15)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.legend(loc="lower right")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(outdir / "per_type_f1.png")
    plt.close(fig)
    print(f"  Saved per_type_f1.png")


def plot_latency(data: dict, outdir: Path):
    engines = ["Legacy\n(BiLSTM-CRF)", "NextGen\n(DeBERTa)"]
    avg = [data["legacy"]["avg_latency_ms"], data["nextgen"]["avg_latency_ms"]]
    p50 = [data["legacy"]["p50_latency_ms"], data["nextgen"]["p50_latency_ms"]]

    x = np.arange(len(engines))
    width = 0.3

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    bars1 = ax.bar(x - width / 2, avg, width, label="Mean", color=LEGACY_COLOR,
                   edgecolor="white", linewidth=0.5)
    bars2 = ax.bar(x + width / 2, p50, width, label="P50", color=NEXTGEN_COLOR,
                   edgecolor="white", linewidth=0.5)

    for bar in list(bars1) + list(bars2):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"{bar.get_height():.0f}ms", ha="center", va="bottom", fontsize=10)

    speedup = data["comparison"]["speedup_factor"]
    ax.annotate(f"{speedup}x faster", xy=(1, max(avg[1], p50[1]) + 15),
                fontsize=12, fontweight="bold", color=ACCENT, ha="center")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("Inference Latency per Query")
    ax.set_xticks(x)
    ax.set_xticklabels(engines)
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "latency_comparison.png")
    plt.close(fig)
    print(f"  Saved latency_comparison.png")


def plot_precision_recall_scatter(data: dict, outdir: Path, min_support: int = 10):
    legacy_pt = data["legacy"]["per_type"]
    nextgen_pt = data["nextgen"]["per_type"]

    all_types = sorted(set(legacy_pt) | set(nextgen_pt))
    types = [t for t in all_types
             if legacy_pt.get(t, {}).get("support", 0) >= min_support
             or nextgen_pt.get(t, {}).get("support", 0) >= min_support]

    fig, ax = plt.subplots(figsize=(7, 6))

    for t in types:
        lp = legacy_pt.get(t, {}).get("precision", 0)
        lr = legacy_pt.get(t, {}).get("recall", 0)
        np_ = nextgen_pt.get(t, {}).get("precision", 0)
        nr = nextgen_pt.get(t, {}).get("recall", 0)

        if lp > 0 or lr > 0:
            ax.scatter(lr, lp, color=LEGACY_COLOR, s=60, alpha=0.7, zorder=3)
        if np_ > 0 or nr > 0:
            ax.scatter(nr, np_, color=NEXTGEN_COLOR, s=60, alpha=0.7, zorder=3)

        if (lp > 0 or lr > 0) and (np_ > 0 or nr > 0):
            ax.annotate("", xy=(nr, np_), xytext=(lr, lp),
                        arrowprops=dict(arrowstyle="->", color="#999", lw=0.8))

        label_x = nr if (np_ > 0 or nr > 0) else lr
        label_y = np_ if (np_ > 0 or nr > 0) else lp
        if label_x > 0 or label_y > 0:
            ax.annotate(t, (label_x, label_y), fontsize=7, alpha=0.8,
                        xytext=(4, 4), textcoords="offset points")

    for f1_val in [0.2, 0.4, 0.6, 0.8]:
        r_range = np.linspace(0.01, 1.0, 200)
        p_range = (f1_val * r_range) / (2 * r_range - f1_val)
        mask = (p_range > 0) & (p_range <= 1.0)
        ax.plot(r_range[mask], p_range[mask], "--", color="#ccc", linewidth=0.8, zorder=1)
        valid_idx = np.where(mask)[0]
        if len(valid_idx) > 0:
            mid = valid_idx[len(valid_idx) // 3]
            ax.text(r_range[mid], p_range[mid], f"F1={f1_val}", fontsize=7,
                    color="#aaa", rotation=30)

    ax.scatter([], [], color=LEGACY_COLOR, s=60, label="Legacy (BiLSTM-CRF)")
    ax.scatter([], [], color=NEXTGEN_COLOR, s=60, label="NextGen (DeBERTa)")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title(f"Precision vs Recall by Entity Type (support >= {min_support})")
    ax.set_xlim(-0.05, 1.08)
    ax.set_ylim(-0.05, 1.08)
    ax.set_aspect("equal")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(outdir / "precision_recall_scatter.png")
    plt.close(fig)
    print(f"  Saved precision_recall_scatter.png")


def plot_summary_dashboard(data: dict, outdir: Path):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    # F1 comparison
    ax = axes[0]
    engines = ["Legacy", "NextGen"]
    f1s = [data["legacy"]["f1"], data["nextgen"]["f1"]]
    colors = [LEGACY_COLOR, NEXTGEN_COLOR]
    bars = ax.bar(engines, f1s, color=colors, width=0.5, edgecolor="white")
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{bar.get_height():.2%}", ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.set_ylabel("F1 Score")
    ax.set_title("F1 Score")
    ax.set_ylim(0, 1.1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))

    # Latency comparison
    ax = axes[1]
    lats = [data["legacy"]["avg_latency_ms"], data["nextgen"]["avg_latency_ms"]]
    bars = ax.bar(engines, lats, color=colors, width=0.5, edgecolor="white")
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"{bar.get_height():.0f}ms", ha="center", va="bottom", fontsize=12, fontweight="bold")
    ax.set_ylabel("Avg Latency (ms)")
    ax.set_title("Inference Speed")

    # Improvement stats
    ax = axes[2]
    ax.axis("off")
    comp = data["comparison"]
    lines = [
        (f"+{comp['f1_delta']:.2%}", "F1 improvement"),
        (f"{comp['speedup_factor']}x", "faster inference"),
        (f"{data['num_queries']}", "test queries"),
    ]
    for i, (big, small) in enumerate(lines):
        y = 0.78 - i * 0.32
        ax.text(0.5, y, big, ha="center", va="center", fontsize=22,
                fontweight="bold", color=NEXTGEN_COLOR, transform=ax.transAxes)
        ax.text(0.5, y - 0.1, small, ha="center", va="center", fontsize=11,
                color="#666", transform=ax.transAxes)
    ax.set_title("NextGen vs Legacy")

    fig.suptitle("NER Engine Evaluation Summary", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(outdir / "summary_dashboard.png", bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved summary_dashboard.png")


def main():
    parser = argparse.ArgumentParser(description="Plot evaluation results")
    parser.add_argument("--input", default="results/evaluation.json")
    parser.add_argument("--outdir", default="results/")
    parser.add_argument("--min_support", type=int, default=10,
                        help="Minimum support to include entity type in per-type charts")
    args = parser.parse_args()

    data = load_data(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Generating charts from {args.input}")
    plot_overall_prf(data, outdir)
    plot_per_type_f1(data, outdir, args.min_support)
    plot_latency(data, outdir)
    plot_precision_recall_scatter(data, outdir, args.min_support)
    plot_summary_dashboard(data, outdir)
    print(f"\nAll charts saved to {outdir}/")


if __name__ == "__main__":
    main()
