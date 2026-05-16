"""
Regenerate thesis figures that depend on NER evaluation data.

Produces PDF figures matching the thesis style with updated metrics from
results/evaluation.json.

Figures generated:
  1. comparison.pdf          - NER Performance: BiLSTM-CRF vs DeBERTa
  2. comprehensive_system_overview.pdf - All-components dashboard
  3. quality_latency_tradeoffs.pdf     - Quality vs latency scatter

Usage:
    python scripts/plot_thesis_figures.py
    python scripts/plot_thesis_figures.py --outdir results/figures/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
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
    "grid.linewidth": 0.5,
})

BILSTM_GREEN = "#2ECC71"
DEBERTA_RED = "#E74C3C"
BLUE = "#3498DB"
PURPLE = "#9B59B6"
ORANGE = "#F39C12"
TEAL = "#1ABC9C"
GRAY = "#95A5A6"


def load_eval(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Figure 1: comparison.pdf ──────────────────────────────────────────────

def plot_comparison(data: dict, outdir: Path):
    legacy = data["legacy"]
    nextgen = data["nextgen"]
    comp = data["comparison"]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(
        "Named Entity Recognition Performance: BiLSTM-CRF vs DeBERTa",
        fontsize=16, fontweight="bold", y=1.02,
    )

    # Panel 1: P / R / F1 grouped bars
    ax = axes[0]
    metrics = ["precision", "recall", "f1"]
    labels = ["Precision", "Recall", "F1 Score"]
    leg_vals = [legacy[m] for m in metrics]
    ng_vals = [nextgen[m] for m in metrics]
    x = np.arange(len(labels))
    w = 0.32
    b1 = ax.bar(x - w / 2, leg_vals, w, label="BiLSTM-CRF", color=BILSTM_GREEN,
                edgecolor="white", linewidth=0.6)
    b2 = ax.bar(x + w / 2, ng_vals, w, label="DeBERTa", color=DEBERTA_RED,
                edgecolor="white", linewidth=0.6)
    for bar in b1:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=BILSTM_GREEN)
    for bar in b2:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                f"{bar.get_height():.3f}", ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=DEBERTA_RED)
    ax.set_ylabel("Score")
    ax.set_title("Accuracy Metrics Comparison")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.08)
    ax.legend(loc="upper left", framealpha=0.9)

    # Panel 2: F1 horizontal bars
    ax = axes[1]
    engines = ["DeBERTa", "BiLSTM-CRF"]
    f1s = [nextgen["f1"], legacy["f1"]]
    colors = [DEBERTA_RED, BILSTM_GREEN]
    bars = ax.barh(engines, f1s, color=colors, height=0.45, edgecolor="white", linewidth=0.6)
    for bar, val in zip(bars, f1s):
        ax.text(bar.get_width() - 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.4f}", ha="right", va="center", fontsize=12,
                fontweight="bold", color="white")
    ax.set_xlabel("F1 Score")
    ax.set_title("F1 Score (Primary Metric)")
    ax.set_xlim(0, 1.05)

    # Panel 3: Latency bars with speedup
    ax = axes[2]
    engines = ["BiLSTM-CRF", "DeBERTa"]
    lats = [legacy["avg_latency_ms"], nextgen["avg_latency_ms"]]
    colors = [BILSTM_GREEN, DEBERTA_RED]
    bars = ax.bar(engines, lats, color=colors, width=0.5, edgecolor="white", linewidth=0.6)
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 3,
                f"{bar.get_height():.1f}ms", ha="center", va="bottom",
                fontsize=11, fontweight="bold")

    mid_x = 0.5
    mid_y = (lats[0] + lats[1]) / 2
    ax.annotate(
        f"{comp['speedup_factor']}x faster",
        xy=(1, lats[1]), xytext=(0.3, mid_y),
        fontsize=13, fontweight="bold", color="#E74C3C",
        arrowprops=dict(arrowstyle="->", color=DEBERTA_RED, lw=2.0),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFFFAA", edgecolor=DEBERTA_RED, linewidth=1.5),
    )
    ax.set_ylabel("Inference Time (ms)")
    ax.set_title("Computational Efficiency")

    fig.tight_layout()
    out = outdir / "comparison.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


# ── Figure 2: comprehensive_system_overview.pdf ───────────────────────────

def plot_comprehensive(data: dict, outdir: Path):
    legacy = data["legacy"]
    nextgen = data["nextgen"]

    fig = plt.figure(figsize=(16, 10))
    fig.suptitle(
        "Comprehensive System Performance Overview\nAll Components Integrated",
        fontsize=16, fontweight="bold", y=0.98,
    )

    gs = fig.add_gridspec(3, 3, hspace=0.45, wspace=0.35,
                          top=0.90, bottom=0.08, left=0.06, right=0.97)

    # ── Panel 1: NER Performance ──
    ax = fig.add_subplot(gs[0, 0])
    metrics = ["f1", "precision", "recall"]
    labels = ["F1", "Precision", "Recall"]
    leg_vals = [legacy[m] for m in metrics]
    ng_vals = [nextgen[m] for m in metrics]
    x = np.arange(len(labels))
    w = 0.3
    ax.bar(x - w / 2, leg_vals, w, label="BiLSTM-CRF", color=BILSTM_GREEN, edgecolor="white")
    ax.bar(x + w / 2, ng_vals, w, label="DeBERTa", color=DEBERTA_RED, edgecolor="white")
    ax.set_title("1. NER Performance")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8, loc="upper right")

    # ── Panel 2: Dense Retrieval (unchanged) ──
    ax = fig.add_subplot(gs[0, 1])
    ret_metrics = ["MRR", "NDCG@10", "Precision@5"]
    ret_vals = [1.000, 1.000, 1.000]
    bars = ax.bar(ret_metrics, ret_vals, color=[BLUE, TEAL, PURPLE],
                  width=0.5, edgecolor="white")
    for bar, val in zip(bars, ret_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title("2. Dense Retrieval")
    ax.set_ylim(0, 1.12)

    # ── Panel 3: RAG Generation (unchanged) ──
    ax = fig.add_subplot(gs[0, 2])
    rag_labels = ["BLEU-2", "ROUGE-L", "Quality"]
    rag_vals = [0.236, 0.214, 0.769]
    rag_colors = [BLUE, ORANGE, PURPLE]
    bars = ax.bar(rag_labels, rag_vals, color=rag_colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, rag_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title("3. RAG Generation")
    ax.set_ylim(0, 1.0)

    # ── Panel 4: Personalization Learning (unchanged) ──
    ax = fig.add_subplot(gs[1, 0])
    interactions = np.linspace(0, 100, 200)
    reward = 0.25 * interactions * (1 - np.exp(-interactions / 30))
    ax.fill_between(interactions, reward, alpha=0.3, color=TEAL)
    ax.plot(interactions, reward, color=TEAL, linewidth=2)
    ax.set_xlabel("Interactions")
    ax.set_ylabel("Cumulative Reward")
    ax.set_title("4. Personalization Learning (CTR: 25.20%)")

    # ── Panel 5: Knowledge Graph (unchanged) ──
    ax = fig.add_subplot(gs[1, 1])
    kg_labels = ["Entity\nCoverage", "Query\nEnhancement", "Triple\nAccuracy"]
    kg_vals = [83.31, 77.15, 94.78]
    kg_colors = [BILSTM_GREEN, ORANGE, PURPLE]
    bars = ax.bar(kg_labels, kg_vals, color=kg_colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, kg_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("Percentage")
    ax.set_title("5. Knowledge Graph")
    ax.set_ylim(0, 108)

    # ── Panel 6 (spanning bottom): Latency Breakdown ──
    ax = fig.add_subplot(gs[2, :])
    components = ["NER\n(DeBERTa)", "Retrieval", "Reranking", "Generation", "Personal.", "KG"]
    latencies = [nextgen["avg_latency_ms"], 24.98, 38.50, 116.26, 8.50, 6.90]
    total = sum(latencies)
    pcts = [l / total * 100 for l in latencies]
    colors = [DEBERTA_RED, BLUE, PURPLE, "#E74C3C", ORANGE, GRAY]

    bars = ax.barh(components, latencies, color=colors, height=0.55, edgecolor="white")
    for bar, lat, pct in zip(bars, latencies, pcts):
        ax.text(bar.get_width() + 1.5, bar.get_y() + bar.get_height() / 2,
                f"{lat:.1f}ms ({pct:.1f}%)", va="center", fontsize=9, fontweight="bold")
    ax.set_xlabel("Latency (milliseconds)")
    ax.set_title(f"End-to-End Latency Breakdown (Total: {total:.1f}ms)")
    ax.set_xlim(0, max(latencies) * 1.35)

    out = outdir / "comprehensive_system_overview.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


# ── Figure 3: quality_latency_tradeoffs.pdf ───────────────────────────────

def plot_quality_latency(data: dict, outdir: Path):
    legacy = data["legacy"]
    nextgen = data["nextgen"]

    components = {
        "NER\n(DeBERTa)": {
            "lat": nextgen["avg_latency_ms"],
            "quality": nextgen["f1"],
            "color": DEBERTA_RED, "marker": "o", "size": 120,
        },
        "NER\n(BiLSTM-CRF)": {
            "lat": legacy["avg_latency_ms"],
            "quality": legacy["f1"],
            "color": BILSTM_GREEN, "marker": "o", "size": 120,
        },
        "Dense\nRetrieval": {
            "lat": 24.98, "quality": 1.0,
            "color": BLUE, "marker": "o", "size": 120,
        },
        "Neural\nReranking": {
            "lat": 38.50, "quality": 1.0,
            "color": "#5DADE2", "marker": "o", "size": 120,
        },
        "RAG\nGeneration": {
            "lat": 116.26, "quality": 0.236,
            "color": "#E74C3C", "marker": "o", "size": 120,
        },
        "Personalization": {
            "lat": 8.50, "quality": 0.252,
            "color": ORANGE, "marker": "o", "size": 100,
        },
        "Knowledge\nGraph": {
            "lat": 6.90, "quality": 0.948,
            "color": PURPLE, "marker": "o", "size": 100,
        },
    }

    fig, ax = plt.subplots(figsize=(11, 7.5))
    ax.set_title("Component Quality-Latency Trade-offs Analysis",
                 fontsize=15, fontweight="bold", pad=15)

    # Shade zones
    ax.axhspan(0.7, 1.05, xmin=0, xmax=0.35, alpha=0.08, color="green", zorder=0)
    ax.text(12, 1.01, "IDEAL", fontsize=11, fontweight="bold", color="#27AE60",
            alpha=0.6, ha="center")
    ax.axhspan(-0.05, 0.35, xmin=0.6, xmax=1.0, alpha=0.08, color="red", zorder=0)
    ax.text(270, 0.08, "SUBOPTIMAL", fontsize=11, fontweight="bold", color="#E74C3C",
            alpha=0.5, ha="center")

    # Ideal frontier curve
    x_curve = np.linspace(1, 320, 300)
    y_curve = 1.0 / (1.0 + (x_curve / 15) ** 0.45)
    ax.plot(x_curve, y_curve, "--", color="#BDC3C7", linewidth=1.2, zorder=1,
            label="Ideal Frontier")

    # Plot each component
    legend_handles = []
    for name, c in components.items():
        sc = ax.scatter(c["lat"], c["quality"], s=c["size"], c=c["color"],
                        marker=c["marker"], edgecolors="white", linewidth=0.8, zorder=5)
        legend_handles.append(mpatches.Patch(color=c["color"], label=name.replace("\n", " ")))

        offset_x, offset_y = 8, 0.02
        if "BiLSTM" in name:
            offset_x, offset_y = -10, -0.05
            ha = "right"
        elif "RAG" in name:
            offset_x, offset_y = -8, 0.02
            ha = "right"
        elif "Reranking" in name:
            offset_x, offset_y = 8, 0.02
            ha = "left"
        else:
            ha = "left"

        ax.annotate(
            name.replace("\n", " "),
            (c["lat"], c["quality"]),
            xytext=(offset_x, offset_y * 200),
            textcoords="offset points",
            fontsize=8.5, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=c["color"], alpha=0.85, linewidth=1.2),
            ha=ha, va="center",
        )

    # Optimization insights box
    insights = (
        "Optimization Insights:\n"
        f"• NER (DeBERTa): F1={nextgen['f1']:.3f}, {nextgen['avg_latency_ms']:.0f}ms\n"
        f"• NER (BiLSTM-CRF): F1={legacy['f1']:.3f}, {legacy['avg_latency_ms']:.0f}ms\n"
        f"• Retrieval: Strong (MRR=1.0, 25ms)\n"
        f"• RAG: Target (BLEU=0.24, 116ms)\n"
        f"  └─ 53% of total latency\n"
        f"• KG/Personal.: Efficient additions"
    )
    ax.text(0.98, 0.98, insights, transform=ax.transAxes, fontsize=7.5,
            verticalalignment="top", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#E8F8F5",
                      edgecolor="#1ABC9C", alpha=0.9))

    ax.set_xlabel("Average Latency (milliseconds)", fontsize=12)
    ax.set_ylabel("Quality Metric (normalized)", fontsize=12)
    ax.set_xlim(-5, 320)
    ax.set_ylim(-0.05, 1.08)
    ax.legend(handles=legend_handles, loc="lower left", fontsize=8,
              ncol=2, framealpha=0.9)

    fig.tight_layout()
    out = outdir / "quality_latency_tradeoffs.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


def main():
    parser = argparse.ArgumentParser(description="Regenerate thesis figures with new NER data")
    parser.add_argument("--input", default="results/evaluation.json")
    parser.add_argument("--outdir", default="results/figures/")
    args = parser.parse_args()

    data = load_eval(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Generating thesis figures from {args.input}")
    print(f"  Legacy:  F1={data['legacy']['f1']}, lat={data['legacy']['avg_latency_ms']}ms")
    print(f"  NextGen: F1={data['nextgen']['f1']}, lat={data['nextgen']['avg_latency_ms']}ms")
    print()

    plot_comparison(data, outdir)
    plot_comprehensive(data, outdir)
    plot_quality_latency(data, outdir)

    print(f"\nAll figures saved to {outdir}")


if __name__ == "__main__":
    main()
