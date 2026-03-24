#!/usr/bin/env python
"""
Generate publication-quality figures for PLOS ONE submission.

Outputs TIFF (300 DPI, LZW compression) for each figure.
PLOS ONE requires: TIFF or EPS, min 300 DPI, RGB color mode.

Usage:
    python paper/generate_figures.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SUMMARY_PATH = os.path.join(PROJECT_DIR, "output", "icu_hemodynamic_summary.json")
PLACEBO_SUMMARY_PATH = os.path.join(PROJECT_DIR, "output", "icu_hemodynamic_summary_placebo.json")
FIG_DIR = os.path.join(SCRIPT_DIR, "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── Load data ──────────────────────────────────────────────────────────
with open(SUMMARY_PATH, encoding="utf-8") as f:
    summary = json.load(f)
with open(PLACEBO_SUMMARY_PATH, encoding="utf-8") as f:
    placebo_summary = json.load(f)

# ── Style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "figure.dpi": 300,
})

DPI = 300
ACCENT = "#2a5569"
ACCENT2 = "#e2674a"
ACCENT3 = "#f4b36b"


def save_tiff(fig, name):
    """Save figure as TIFF (300 DPI, LZW) and EPS."""
    tiff_path = os.path.join(FIG_DIR, f"{name}.tiff")
    eps_path = os.path.join(FIG_DIR, f"{name}.eps")
    fig.savefig(tiff_path, dpi=DPI, format="tiff", pil_kwargs={"compression": "tiff_lzw"},
                bbox_inches="tight", facecolor="white")
    fig.savefig(eps_path, dpi=DPI, format="eps", bbox_inches="tight", facecolor="white")
    print(f"  Saved: {tiff_path}")
    print(f"  Saved: {eps_path}")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════
# Fig 1: Adapted PRISMA-ScR flow diagram
# ══════════════════════════════════════════════════════════════════════
def fig1_prisma_flow():
    pf = summary["prisma_flow"]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    box_props = dict(boxstyle="round,pad=0.4", facecolor="#dce8f0", edgecolor=ACCENT, linewidth=1.5)
    box_props_gray = dict(boxstyle="round,pad=0.4", facecolor="#f0eded", edgecolor="#999", linewidth=1)
    box_props_green = dict(boxstyle="round,pad=0.4", facecolor="#d4edda", edgecolor="#28a745", linewidth=1.5)

    # Row 1: Sources
    ax.text(2.5, 9.2, f"ClinicalTrials.gov\nn = {pf['ctgov_retrieved']:,}",
            ha="center", va="center", fontsize=10, fontweight="bold", bbox=box_props)
    ax.text(7.5, 9.2, f"PubMed\nn = {pf['pubmed_retrieved']:,}",
            ha="center", va="center", fontsize=10, fontweight="bold", bbox=box_props)

    # Arrows down to merge
    ax.annotate("", xy=(5, 7.8), xytext=(2.5, 8.6), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))
    ax.annotate("", xy=(5, 7.8), xytext=(7.5, 8.6), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))

    # Row 2: Dedup
    ax.text(5, 7.5, f"Duplicates removed: {pf['duplicates_removed']:,}\nTotal after deduplication: {pf['total_after_dedup']:,}",
            ha="center", va="center", fontsize=10, bbox=box_props)

    # Arrow down
    ax.annotate("", xy=(5, 6.0), xytext=(5, 6.9), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))

    # Row 3: Split
    ax.text(5, 5.7, f"ICU RCTs included\nn = {pf['total_after_dedup']:,}",
            ha="center", va="center", fontsize=11, fontweight="bold", bbox=box_props_green)

    # Arrow down + right (excluded)
    ax.annotate("", xy=(8.5, 5.7), xytext=(6.8, 5.7), arrowprops=dict(arrowstyle="->", color="#999", lw=1.2))
    ax.text(8.5, 5.7, f"Excluded\n(no hemodynamic match)\nn = {pf['excluded_no_hemo']:,}",
            ha="center", va="center", fontsize=9, bbox=box_props_gray)

    # Arrow down
    ax.annotate("", xy=(3.5, 4.2), xytext=(5, 5.1), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))
    ax.annotate("", xy=(6.5, 4.2), xytext=(5, 5.1), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))

    # Row 4: Two boxes
    ax.text(3.0, 3.8, f"Hemodynamic outcomes\nn = {pf['with_hemodynamic_outcomes']:,}\n({pf['with_hemodynamic_outcomes']/pf['total_after_dedup']*100:.1f}%)",
            ha="center", va="center", fontsize=10, bbox=box_props)
    ax.text(7.0, 3.8, f"Placebo/sham arms\nn = {pf['with_placebo_arms']:,}\n({pf['with_placebo_arms']/pf['total_after_dedup']*100:.1f}%)",
            ha="center", va="center", fontsize=10, bbox=box_props)

    # Arrows to intersection
    ax.annotate("", xy=(5, 2.3), xytext=(3.0, 3.1), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))
    ax.annotate("", xy=(5, 2.3), xytext=(7.0, 3.1), arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.5))

    # Row 5: Intersection
    ax.text(5, 2.0, f"Hemodynamic + Placebo\nn = {pf['with_hemo_and_placebo']:,}\n({pf['with_hemo_and_placebo']/pf['total_after_dedup']*100:.1f}%)",
            ha="center", va="center", fontsize=10, fontweight="bold", bbox=box_props_green)

    ax.set_title("Fig 1. Adapted PRISMA-ScR Flow Diagram", fontsize=13, fontweight="bold", pad=15)

    save_tiff(fig, "Fig1_PRISMA_flow")


# ══════════════════════════════════════════════════════════════════════
# Fig 2: Temporal distribution by decade
# ══════════════════════════════════════════════════════════════════════
def fig2_temporal():
    yd = summary["year_distribution"]  # dict: year_str -> count

    decades = {"Pre-1990": 0, "1990s": 0, "2000s": 0, "2010s": 0, "2020s": 0}
    for yr_str, count in yd.items():
        yr = int(yr_str)
        if yr < 1990:
            decades["Pre-1990"] += count
        elif yr < 2000:
            decades["1990s"] += count
        elif yr < 2010:
            decades["2000s"] += count
        elif yr < 2020:
            decades["2010s"] += count
        else:
            decades["2020s"] += count

    # Exclude Pre-1990 (n=14) per manuscript note
    labels = ["1990s", "2000s", "2010s", "2020s"]
    values = [decades[l] for l in labels]
    total = sum(values)

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=[ACCENT, ACCENT, ACCENT2, ACCENT2], edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, values):
        pct = val / total * 100
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 150,
                f"{val:,}\n({pct:.1f}%)", ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Number of registered ICU RCTs")
    ax.set_xlabel("Decade of start date")
    ax.set_title("Fig 2. Temporal Distribution of ICU RCT Registrations", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, max(values) * 1.2)

    fig.tight_layout()
    save_tiff(fig, "Fig2_temporal_distribution")


# ══════════════════════════════════════════════════════════════════════
# Fig 3: Geographic distribution (top 15 countries)
# ══════════════════════════════════════════════════════════════════════
def fig3_geographic():
    countries = summary["countries"]  # dict: country -> count
    sorted_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:15]

    labels = [c[0] for c in sorted_countries]
    values = [c[1] for c in sorted_countries]

    fig, ax = plt.subplots(figsize=(8, 6))
    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, values, color=ACCENT, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()

    total = summary["prisma_flow"]["total_after_dedup"]
    for bar, val in zip(bars, values):
        pct = val / total * 100
        ax.text(bar.get_width() + 50, bar.get_y() + bar.get_height() / 2,
                f"{val:,} ({pct:.1f}%)", ha="left", va="center", fontsize=8)

    ax.set_xlabel("Number of registered ICU RCTs")
    ax.set_title("Fig 3. Geographic Distribution of Registered ICU RCTs\n(Top 15 Countries)", fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(0, max(values) * 1.25)

    fig.tight_layout()
    save_tiff(fig, "Fig3_geographic_distribution")


# ══════════════════════════════════════════════════════════════════════
# Fig 4: Hemodynamic keyword signal map (total vs placebo)
# ══════════════════════════════════════════════════════════════════════
def fig4_signal_map():
    nk = summary["normalized_keywords"]

    # Build data from normalized keywords
    labels = []
    total_counts = []
    placebo_counts = []
    for item in nk:
        kw = item["keyword"]
        sc = item["study_count"]
        pc = item.get("placebo_study_count", 0)
        if sc > 0:
            labels.append(kw)
            total_counts.append(sc)
            placebo_counts.append(pc)

    total_arr = np.array(total_counts, dtype=float)
    placebo_arr = np.array(placebo_counts, dtype=float)

    fig, ax = plt.subplots(figsize=(8, 7))

    # Scatter
    sizes = np.clip(total_arr / total_arr.max() * 200, 20, 200)
    ax.scatter(total_arr, placebo_arr, s=sizes, c=ACCENT, alpha=0.7, edgecolors="white", linewidth=0.5)

    # Diagonal reference line (mean placebo ratio)
    max_val = max(total_arr.max(), placebo_arr.max()) * 1.1
    mean_ratio = placebo_arr.sum() / total_arr.sum()
    ax.plot([0, max_val], [0, max_val * mean_ratio], "--", color="#999", lw=1,
            label=f"Mean placebo ratio ({mean_ratio:.1%})")

    # Label top keywords and evidence gaps
    for i, (lbl, tc, pc) in enumerate(zip(labels, total_counts, placebo_counts)):
        # Label if top-7 by total count OR if placebo < 5
        if tc > sorted(total_counts, reverse=True)[6] or pc <= 4:
            ax.annotate(lbl, (tc, pc), fontsize=6.5, alpha=0.85,
                        xytext=(5, 3), textcoords="offset points")

    ax.set_xlabel("Total study count (normalized category)")
    ax.set_ylabel("Placebo study count")
    ax.set_title("Fig 4. Hemodynamic Keyword Signal Map\n(Total vs. Placebo Study Coverage)", fontweight="bold")
    ax.legend(fontsize=9, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    save_tiff(fig, "Fig4_keyword_signal_map")


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating PLOS ONE figures (TIFF 300 DPI + EPS)...\n")

    print("Fig 1: PRISMA-ScR flow diagram")
    fig1_prisma_flow()

    print("\nFig 2: Temporal distribution")
    fig2_temporal()

    print("\nFig 3: Geographic distribution")
    fig3_geographic()

    print("\nFig 4: Keyword signal map")
    fig4_signal_map()

    print(f"\nAll figures saved to: {FIG_DIR}")
    print("Formats: TIFF (300 DPI, LZW) + EPS")
