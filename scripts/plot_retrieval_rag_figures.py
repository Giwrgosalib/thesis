"""
Regenerate the two performance figures whose values were previously
hardcoded: retrieval_performance.pdf and rag_performance.pdf.

Both now read from the current JSON output of evaluate_retrieval_full.py
and benchmark_rag_pipeline.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.grid": True,
    "grid.alpha": 0.25,
})

BLUE = "#3498DB"
TEAL = "#1ABC9C"
PURPLE = "#9B59B6"
ORANGE = "#F39C12"
RED = "#E74C3C"
GREEN = "#27AE60"


def plot_retrieval(metrics: dict, outdir: Path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(
        f"Dense Retrieval System Performance "
        f"(E5-base-v2, {metrics['avg_retrieval_latency_ms']:.2f} ms avg latency, "
        f"{metrics['num_queries']} queries)",
        fontsize=14, fontweight="bold", y=1.02,
    )

    # ── Panel 1: NDCG at cutoffs ──
    ax = axes[0]
    ks = ["5", "10"]
    ndcg_vals = [metrics["NDCG@5"], metrics["NDCG@10"]]
    bars = ax.bar(ks, ndcg_vals, color=[TEAL, BLUE], width=0.45, edgecolor="white")
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                f"{bar.get_height():.4f}", ha="center", va="bottom",
                fontsize=11, fontweight="bold")
    ax.set_ylabel("NDCG Score")
    ax.set_title("NDCG Scores at Different Cutoffs")
    ax.set_xlabel("Cutoff (k)")
    ax.set_ylim(0, 1.0)

    # ── Panel 2: Precision vs Recall at k ──
    ax = axes[1]
    cutoffs = ["@1", "@5", "@10"]
    p_vals = [metrics["Precision@1"], metrics["Precision@5"], None]
    r_vals = [metrics["Recall@1"], metrics["Recall@5"], metrics["Recall@10"]]
    x = np.arange(len(cutoffs))
    w = 0.32
    # Plot precision only where available
    p_x = [x[i] - w / 2 for i in range(len(cutoffs)) if p_vals[i] is not None]
    p_y = [v for v in p_vals if v is not None]
    ax.bar(p_x, p_y, w, label="Precision@k", color=ORANGE, edgecolor="white")
    for xi, yi in zip(p_x, p_y):
        ax.text(xi, yi + 0.015, f"{yi:.3f}", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=ORANGE)
    ax.bar(x + w / 2, r_vals, w, label="Recall@k", color=GREEN, edgecolor="white")
    for xi, yi in zip(x + w / 2, r_vals):
        ax.text(xi, yi + 0.015, f"{yi:.3f}", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=GREEN)
    ax.set_xticks(x)
    ax.set_xticklabels(cutoffs)
    ax.set_title("Precision vs Recall at k")
    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper left")

    # ── Panel 3: Overall metrics ──
    ax = axes[2]
    names = ["MRR", "MAP", "NDCG@10", "Recall@10"]
    vals = [metrics["MRR"], metrics["MAP"], metrics["NDCG@10"], metrics["Recall@10"]]
    colors = [RED, PURPLE, BLUE, GREEN]
    bars = ax.barh(names, vals, color=colors, height=0.55, edgecolor="white")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_width() - 0.02, bar.get_y() + bar.get_height() / 2,
                f"{v:.4f}", ha="right", va="center", fontsize=11,
                fontweight="bold", color="white")
    ax.set_xlabel("Score")
    ax.set_title("Overall Retrieval Quality Metrics")
    ax.set_xlim(0, 1.05)
    ax.invert_yaxis()

    fig.tight_layout()
    out = outdir / "retrieval_performance.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


def plot_rag(metrics: dict, outdir: Path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(
        f"RAG Pipeline Performance (FLAN-T5-small, "
        f"{metrics['config']['samples']} samples)",
        fontsize=14, fontweight="bold", y=1.02,
    )

    # ── Panel 1: Latency percentiles for total ──
    ax = axes[0]
    tot = metrics["total_ms"]
    pcts = ["P50", "P95", "P99"]
    vals = [tot["p50"], tot["p95"], tot["p99"]]
    bars = ax.bar(pcts, vals, color=[BLUE, ORANGE, RED], width=0.5,
                  edgecolor="white")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{v:.0f} ms", ha="center", va="bottom",
                fontsize=11, fontweight="bold")
    ax.set_ylabel("End-to-End Latency (ms)")
    ax.set_title("Latency Distribution")
    ax.set_ylim(0, max(vals) * 1.18)

    # ── Panel 2: Component breakdown (donut) ──
    ax = axes[1]
    rt = metrics["retrieval_ms"]["mean"]
    gn = metrics["generation_ms"]["mean"]
    sizes = [rt, gn]
    labels = [f"Retrieval\n({rt:.1f} ms)", f"Generation\n({gn:.1f} ms)"]
    colors = [TEAL, RED]
    wedges, _, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, autopct="%1.1f%%",
        startangle=90, pctdistance=0.78,
        wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")
        at.set_color("white")
    ax.set_title("RAG Component Breakdown")

    # ── Panel 3: Throughput summary ──
    ax = axes[2]
    ax.axis("off")
    th = metrics["throughput"]
    cfg = metrics["config"]
    lines = [
        ("Mean total latency", f"{tot['mean']:.1f} ms"),
        ("Generation mean", f"{gn:.1f} ms"),
        ("Tokens / response", f"{th['mean_tokens_per_response']:.1f}"),
        ("Throughput", f"{th['tokens_per_second']:.1f} tok/s"),
        ("Generator", str(cfg.get("generator", "—")).split("/")[-1][:40]),
        ("Device", str(cfg.get("device", "—"))),
        ("Samples", str(cfg.get("samples", "—"))),
    ]
    y0 = 0.95
    dy = 0.11
    for i, (k, v) in enumerate(lines):
        y = y0 - i * dy
        ax.text(0.05, y, k, fontsize=11, fontweight="bold", va="top")
        ax.text(0.55, y, v, fontsize=11, color="#333", va="top")
    ax.set_title("Throughput and Configuration")

    fig.tight_layout()
    out = outdir / "rag_performance.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval_json", default="results/retrieval_metrics.json")
    parser.add_argument("--rag_json",       default="results/rag_benchmark.json")
    parser.add_argument("--outdir",         default="thesis_project_refixed (1)/figures/")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with open(args.retrieval_json) as f:
        ret = json.load(f)
    with open(args.rag_json) as f:
        rag = json.load(f)

    print("Regenerating retrieval + RAG performance figures…")
    plot_retrieval(ret, outdir)
    plot_rag(rag, outdir)
    print("Done.")


if __name__ == "__main__":
    main()
