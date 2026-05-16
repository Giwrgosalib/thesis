"""
Regenerate additional thesis figures with updated NER data.

Figures generated:
  1. bilstm_per_entity.pdf     - BiLSTM-CRF per-entity-type F1
  2. ner_output_comparison.pdf  - Side-by-side NER output for example query
  3. latency_donut.pdf          - End-to-end latency donut chart

Usage:
    python scripts/plot_thesis_figures_extra.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def load_eval(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Figure 1: BiLSTM-CRF per-entity-type F1 ──────────────────────────────

def plot_bilstm_per_entity(data: dict, outdir: Path):
    legacy_pt = data["legacy"]["per_type"]

    items = [(t, d["f1"], d["support"]) for t, d in legacy_pt.items() if d["support"] >= 5]
    items.sort(key=lambda x: x[1], reverse=True)

    types = [t for t, _, _ in items]
    f1s = [f for _, f, _ in items]
    supports = [s for _, _, s in items]

    def bar_color(f1):
        if f1 >= 0.6:
            return "#2ECC71"
        elif f1 >= 0.3:
            return "#F1C40F"
        else:
            return "#E67E73"

    colors = [bar_color(f) for f in f1s]

    fig, ax = plt.subplots(figsize=(12, max(4, len(types) * 0.42)))
    y = np.arange(len(types))
    bars = ax.barh(y, f1s, color=colors, height=0.65, edgecolor="white", linewidth=0.5)

    for i, (bar, f1, sup) in enumerate(zip(bars, f1s, supports)):
        if f1 > 0.03:
            ax.text(bar.get_width() + 0.01, i, f"{f1:.2f}  (n={sup})",
                    va="center", fontsize=8.5, color="#333")
        else:
            ax.text(0.01, i, f"{f1:.2f}  (n={sup})", va="center", fontsize=8.5, color="#666")

    ax.set_yticks(y)
    ax.set_yticklabels(types)
    ax.set_xlabel("F1 Score")
    ax.set_title("BiLSTM-CRF Performance by Entity Type")
    ax.set_xlim(0, 1.0)
    ax.invert_yaxis()
    ax.grid(True, axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    legend_patches = [
        mpatches.Patch(color="#2ECC71", label="F1 >= 0.60"),
        mpatches.Patch(color="#F1C40F", label="0.30 <= F1 < 0.60"),
        mpatches.Patch(color="#E67E73", label="F1 < 0.30"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=9)

    fig.tight_layout()
    out = outdir / "bilstm_per_entity.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


# ── Figure 2: NER Output Comparison ──────────────────────────────────────

def _draw_entity_row(ax, y_center, entities, title, is_correct, query_tokens):
    ax.text(0.02, y_center + 0.12, title, fontsize=12, fontweight="bold",
            transform=ax.transAxes, va="center")

    status_text = "Correct" if is_correct else "Incorrect"
    status_color = "#27AE60" if is_correct else "#E74C3C"
    status_mark = "✔" if is_correct else "✘"
    ax.text(0.95, y_center + 0.12, f"{status_mark} {status_text}",
            fontsize=12, fontweight="bold", color=status_color,
            transform=ax.transAxes, va="center", ha="right")

    label_colors = {
        "BRAND": ("#FFCDD2", "#C62828"),
        "MODEL": ("#C8E6C9", "#2E7D32"),
        "PRODUCT_TYPE": ("#C8E6C9", "#2E7D32"),
        "SIZE": ("#D1C4E9", "#4A148C"),
        "COLOR": ("#FFF9C4", "#F57F17"),
    }

    total_chars = sum(len(e["text"]) for e in entities)
    spacing = 0.02
    total_spacing = spacing * (len(entities) - 1)
    usable_width = 0.85
    x_start = 0.07

    x = x_start
    box_height = 0.08
    for ent in entities:
        width = (len(ent["text"]) / total_chars) * (usable_width - total_spacing)
        bg, text_color = label_colors.get(ent["label"], ("#E0E0E0", "#333333"))

        rect = mpatches.FancyBboxPatch(
            (x, y_center - box_height / 2), width, box_height,
            boxstyle="round,pad=0.008", facecolor=bg, edgecolor="#BDBDBD",
            linewidth=0.8, transform=ax.transAxes,
        )
        ax.add_patch(rect)

        ax.text(x + width / 2, y_center, ent["text"],
                fontsize=11, fontweight="bold", ha="center", va="center",
                transform=ax.transAxes, color="#333")

        ax.text(x + width / 2, y_center - box_height / 2 - 0.03, ent["label"],
                fontsize=8.5, ha="center", va="top", transform=ax.transAxes,
                color="#666")

        x += width + spacing


def plot_ner_comparison(outdir: Path):
    query = 'Apple MacBook Pro 14 inch silver'

    legacy_entities = [
        {"text": "Apple", "label": "PRODUCT_TYPE"},
        {"text": "MacBook Pro", "label": "PRODUCT_TYPE"},
        {"text": "14 inch", "label": "SIZE"},
        {"text": "silver", "label": "PRODUCT_TYPE"},
    ]

    nextgen_entities = [
        {"text": "Apple", "label": "BRAND"},
        {"text": "MacBook Pro", "label": "MODEL"},
        {"text": "14 inch", "label": "SIZE"},
        {"text": "silver", "label": "COLOR"},
    ]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(0.5, 0.95, f'NER Output Comparison: "{query}"',
            fontsize=14, fontweight="bold", ha="center", va="top",
            transform=ax.transAxes)

    _draw_entity_row(ax, 0.72, legacy_entities,
                     "BiLSTM-CRF (Legacy)", False, query.split())

    ax.plot([0.05, 0.95], [0.50, 0.50], color="#BDBDBD",
            linestyle="--", linewidth=1, transform=ax.transAxes, clip_on=False)

    _draw_entity_row(ax, 0.30, nextgen_entities,
                     "DeBERTa (Transformer)", True, query.split())

    legend_items = [
        ("BRAND", "#FFCDD2"), ("MODEL", "#C8E6C9"),
        ("SIZE", "#D1C4E9"), ("COLOR", "#FFF9C4"),
        ("PRODUCT_TYPE", "#C8E6C9"),
    ]
    for i, (label, color) in enumerate(legend_items):
        x_pos = 0.10 + i * 0.18
        rect = mpatches.FancyBboxPatch(
            (x_pos, 0.02), 0.04, 0.04,
            boxstyle="round,pad=0.005", facecolor=color,
            edgecolor="#BDBDBD", linewidth=0.5, transform=ax.transAxes,
        )
        ax.add_patch(rect)
        ax.text(x_pos + 0.05, 0.04, label, fontsize=8, va="center",
                transform=ax.transAxes, color="#555")

    fig.tight_layout()
    out = outdir / "ner_output_comparison.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


# ── Figure 3: Latency donut chart ────────────────────────────────────────

def plot_latency_donut(data: dict, outdir: Path):
    nextgen_lat = data["nextgen"]["avg_latency_ms"]

    components = [
        ("Response Generation (RAG)", 116.26),
        ("NER (DeBERTa)", nextgen_lat),
        ("Neural Reranking", 38.50),
        ("Dense Retrieval", 24.98),
        ("Personalization", 8.50),
        ("Knowledge Graph", 6.90),
    ]
    labels = [c[0] for c in components]
    sizes = [c[1] for c in components]
    total = sum(sizes)
    pcts = [s / total * 100 for s in sizes]

    colors = [
        "#F28B82",  # RAG - coral/red
        "#7BAAF7",  # NER - blue
        "#81C995",  # Reranking - green
        "#FDD663",  # Retrieval - yellow
        "#C2A0D6",  # Personalization - purple
        "#F7B9D0",  # KG - pink
    ]

    explode = [0.05 if s == max(sizes) else 0 for s in sizes]

    fig, ax = plt.subplots(figsize=(9, 7))

    wedges, texts, autotexts = ax.pie(
        sizes, labels=None, colors=colors, autopct="",
        startangle=90, pctdistance=0.82, explode=explode,
        wedgeprops=dict(width=0.35, edgecolor="white", linewidth=2),
    )

    for i, (wedge, pct, size) in enumerate(zip(wedges, pcts, sizes)):
        angle = (wedge.theta2 - wedge.theta1) / 2.0 + wedge.theta1
        x = np.cos(np.deg2rad(angle))
        y = np.sin(np.deg2rad(angle))

        if pct >= 5:
            ax.annotate(
                f"{pct:.1f}%",
                xy=(x * 0.82, y * 0.82),
                ha="center", va="center",
                fontsize=11, fontweight="bold", color="#333",
            )

    ax.legend(
        wedges, [f"{l} ({s:.1f}ms)" for l, s in zip(labels, sizes)],
        title="System Components",
        loc="center right",
        bbox_to_anchor=(1.32, 0.5),
        fontsize=9,
        title_fontsize=10,
    )

    ax.set_title(f"End-to-End Latency Breakdown\nTotal: {total:.1f}ms",
                 fontsize=15, fontweight="bold", pad=20)

    fig.tight_layout()
    out = outdir / "latency_donut.pdf"
    fig.savefig(out, bbox_inches="tight", format="pdf")
    plt.close(fig)
    print(f"  Saved {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="results/evaluation.json")
    parser.add_argument("--outdir", default="results/figures/")
    args = parser.parse_args()

    data = load_eval(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("Generating additional thesis figures")
    plot_bilstm_per_entity(data, outdir)
    plot_ner_comparison(outdir)
    plot_latency_donut(data, outdir)
    print(f"\nAll figures saved to {outdir}")


if __name__ == "__main__":
    main()
