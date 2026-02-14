#!/usr/bin/env python3
"""
Classification validation framework for the ICU Trial Landscape.

Generates a stratified random sample of outcome mentions for manual review,
and computes sensitivity/specificity/PPV once human labels are provided.

Usage:
  # Step 1: Generate sample for manual review
  python validate_classification.py --sample --n 200

  # Step 2: After manual review, compute metrics
  python validate_classification.py --evaluate validation_sample_labeled.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
VALIDATION_DIR = ROOT / "validation"

# Columns in the hemodynamic mentions CSV
MENTION_COLS = ["nct_id", "outcome_type", "measure", "keyword", "matched_text", "query_name"]


def load_mentions(path: Path) -> List[Dict[str, str]]:
    """Load hemodynamic mentions CSV."""
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def stratified_sample(mentions: List[Dict[str, str]], n: int, seed: int = 42) -> List[Dict[str, str]]:
    """
    Stratified random sample ensuring representation from each keyword category.

    Strategy:
    - Group mentions by normalized_keyword (or keyword)
    - Allocate proportionally with minimum 2 per category (if available)
    - Fill remaining slots randomly
    """
    rng = random.Random(seed)

    # Group by keyword
    by_keyword: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for m in mentions:
        kw = m.get("keyword", "unknown")
        by_keyword[kw].append(m)

    categories = sorted(by_keyword.keys())
    n_cats = len(categories)

    # Minimum 2 per category (or all if < 2 available)
    min_per_cat = 2
    sample = []
    remaining_pool = []

    for cat in categories:
        pool = by_keyword[cat]
        rng.shuffle(pool)
        take = min(min_per_cat, len(pool))
        sample.extend(pool[:take])
        remaining_pool.extend(pool[take:])

    # Fill remaining slots proportionally
    slots_left = n - len(sample)
    if slots_left > 0 and remaining_pool:
        rng.shuffle(remaining_pool)
        sample.extend(remaining_pool[:slots_left])

    # Shuffle final sample
    rng.shuffle(sample)
    return sample[:n]


def write_sample(sample: List[Dict[str, str]], output_path: Path) -> None:
    """Write sample CSV with columns for manual annotation."""
    fieldnames = [
        "sample_id",
        "nct_id",
        "outcome_type",
        "measure",
        "keyword_automated",
        "matched_text",
        # Human annotation columns
        "is_correct",         # TRUE/FALSE: is the automated keyword classification correct?
        "correct_keyword",    # If incorrect, what should it be? (or "NOT_HEMODYNAMIC")
        "notes",              # Free text notes
    ]

    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for i, m in enumerate(sample, 1):
            writer.writerow({
                "sample_id": i,
                "nct_id": m.get("nct_id", ""),
                "outcome_type": m.get("outcome_type", ""),
                "measure": m.get("measure", ""),
                "keyword_automated": m.get("keyword", ""),
                "matched_text": m.get("matched_text", ""),
                "is_correct": "",
                "correct_keyword": "",
                "notes": "",
            })


def evaluate(labeled_path: Path) -> Dict[str, any]:
    """
    Compute classification metrics from a labeled validation sample.

    Expected columns:
    - keyword_automated: the system's classification
    - is_correct: TRUE or FALSE
    - correct_keyword: if FALSE, the correct label (or NOT_HEMODYNAMIC for false positives)
    """
    rows = []
    with labeled_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"error": "No rows in labeled file"}

    total = len(rows)
    correct = sum(1 for r in rows if r.get("is_correct", "").strip().upper() == "TRUE")
    incorrect = total - correct

    # Per-category metrics
    by_cat: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})

    for r in rows:
        auto = r.get("keyword_automated", "").strip()
        is_ok = r.get("is_correct", "").strip().upper() == "TRUE"
        correct_kw = r.get("correct_keyword", "").strip()

        if is_ok:
            by_cat[auto]["tp"] += 1
        else:
            if correct_kw.upper() == "NOT_HEMODYNAMIC":
                # False positive: system said hemodynamic, but it's not
                by_cat[auto]["fp"] += 1
            else:
                # Misclassification: system said A, should be B
                by_cat[auto]["fp"] += 1
                if correct_kw:
                    by_cat[correct_kw]["fn"] += 1

    # Compute per-category PPV and overall metrics
    cat_metrics = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for cat in sorted(by_cat.keys()):
        tp = by_cat[cat]["tp"]
        fp = by_cat[cat]["fp"]
        fn = by_cat[cat]["fn"]
        total_tp += tp
        total_fp += fp
        total_fn += fn

        ppv = tp / (tp + fp) if (tp + fp) > 0 else None
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else None

        cat_metrics[cat] = {
            "tp": tp, "fp": fp, "fn": fn,
            "ppv": round(ppv, 3) if ppv is not None else None,
            "sensitivity": round(sensitivity, 3) if sensitivity is not None else None,
        }

    overall_ppv = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else None
    overall_sensitivity = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else None
    overall_accuracy = correct / total if total > 0 else None

    false_positive_rate = sum(1 for r in rows
                             if r.get("is_correct", "").strip().upper() == "FALSE"
                             and r.get("correct_keyword", "").strip().upper() == "NOT_HEMODYNAMIC") / total

    return {
        "total_samples": total,
        "correct": correct,
        "incorrect": incorrect,
        "overall_accuracy": round(overall_accuracy, 3) if overall_accuracy is not None else None,
        "overall_ppv": round(overall_ppv, 3) if overall_ppv is not None else None,
        "overall_sensitivity": round(overall_sensitivity, 3) if overall_sensitivity is not None else None,
        "false_positive_rate": round(false_positive_rate, 3),
        "per_category": cat_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Classification validation framework")
    parser.add_argument("--sample", action="store_true", help="Generate stratified sample for manual review")
    parser.add_argument("--n", type=int, default=200, help="Sample size (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--evaluate", type=str, help="Path to labeled CSV for evaluation")
    parser.add_argument("--source", type=str, default="broad",
                        choices=["broad", "placebo"], help="Which dataset to sample from")
    args = parser.parse_args()

    VALIDATION_DIR.mkdir(exist_ok=True)

    if args.sample:
        # Determine source file
        if args.source == "broad":
            mentions_path = OUTPUT_DIR / "icu_rct_broad_hemodynamic_mentions.csv"
        else:
            mentions_path = OUTPUT_DIR / "icu_rct_placebo_hemodynamic_mentions.csv"

        if not mentions_path.exists():
            print(f"ERROR: Mentions file not found: {mentions_path}", file=sys.stderr)
            sys.exit(1)

        print(f"Loading mentions from {mentions_path.name}...")
        mentions = load_mentions(mentions_path)
        print(f"  Total mentions: {len(mentions):,}")

        # Show distribution
        kw_counts = Counter(m.get("keyword", "unknown") for m in mentions)
        print(f"  Unique keywords: {len(kw_counts)}")
        print(f"  Top 10:")
        for kw, cnt in kw_counts.most_common(10):
            print(f"    {kw}: {cnt:,}")

        sample = stratified_sample(mentions, args.n, seed=args.seed)
        output_path = VALIDATION_DIR / f"validation_sample_{args.source}_{args.n}.csv"
        write_sample(sample, output_path)
        print(f"\nSample written to: {output_path}")
        print(f"  {len(sample)} mentions across {len(set(m['keyword'] for m in sample if 'keyword' in m))} categories")
        print(f"\nInstructions:")
        print(f"  1. Open the CSV in a spreadsheet editor")
        print(f"  2. For each row, review 'measure' and 'matched_text'")
        print(f"  3. Set 'is_correct' to TRUE if the automated keyword is appropriate")
        print(f"  4. If FALSE, enter the correct keyword in 'correct_keyword'")
        print(f"     - Use 'NOT_HEMODYNAMIC' if the mention is not hemodynamic at all")
        print(f"  5. Save and run: python validate_classification.py --evaluate {output_path}")

    elif args.evaluate:
        labeled_path = Path(args.evaluate)
        if not labeled_path.exists():
            print(f"ERROR: Labeled file not found: {labeled_path}", file=sys.stderr)
            sys.exit(1)

        print(f"Evaluating {labeled_path.name}...")
        results = evaluate(labeled_path)

        # Print summary
        print(f"\n{'='*60}")
        print(f"CLASSIFICATION VALIDATION RESULTS")
        print(f"{'='*60}")
        print(f"Total samples:       {results['total_samples']}")
        print(f"Correct:             {results['correct']}")
        print(f"Incorrect:           {results['incorrect']}")
        print(f"Overall accuracy:    {results['overall_accuracy']}")
        print(f"Overall PPV:         {results['overall_ppv']}")
        print(f"Overall sensitivity: {results['overall_sensitivity']}")
        print(f"False positive rate: {results['false_positive_rate']}")

        print(f"\nPer-category metrics:")
        print(f"{'Category':<30} {'TP':>4} {'FP':>4} {'FN':>4} {'PPV':>7} {'Sens':>7}")
        print(f"{'-'*30} {'-'*4} {'-'*4} {'-'*4} {'-'*7} {'-'*7}")
        for cat, m in sorted(results["per_category"].items()):
            ppv_str = f"{m['ppv']:.3f}" if m['ppv'] is not None else "N/A"
            sens_str = f"{m['sensitivity']:.3f}" if m['sensitivity'] is not None else "N/A"
            print(f"{cat:<30} {m['tp']:>4} {m['fp']:>4} {m['fn']:>4} {ppv_str:>7} {sens_str:>7}")

        # Save results
        results_path = VALIDATION_DIR / "validation_results.json"
        with results_path.open("w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nResults saved to: {results_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
