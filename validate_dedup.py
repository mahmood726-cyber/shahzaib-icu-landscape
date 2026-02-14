#!/usr/bin/env python3
"""
Deduplication validation — samples merged and non-merged study pairs
for manual review of fuzzy title matching accuracy.

Usage:
  python validate_dedup.py --n 50

Outputs two CSVs in validation/:
  dedup_merged_sample.csv   — pairs that WERE merged (check for false merges)
  dedup_unmerged_sample.csv — PubMed-only records with closest CT.gov match
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
VALIDATION_DIR = ROOT / "validation"


def _levenshtein_sim(a: str, b: str) -> float:
    a, b = a.strip().lower(), b.strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for j in range(1, len(b) + 1):
        curr = [j] + [0] * len(a)
        for i in range(1, len(a) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[i] = min(curr[i - 1] + 1, prev[i] + 1, prev[i - 1] + cost)
        prev = curr
    return 1.0 - prev[len(a)] / max(len(a), len(b))


def _words(s: str) -> Set[str]:
    return {w for w in re.split(r'\W+', s.lower()) if len(w) >= 4}


def main():
    parser = argparse.ArgumentParser(description="Deduplication validation sampler")
    parser.add_argument("--n", type=int, default=50, help="Pairs per category (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    VALIDATION_DIR.mkdir(exist_ok=True)
    rng = random.Random(args.seed)

    # Load studies
    ctgov = list(csv.DictReader(open(OUTPUT_DIR / "icu_rct_broad_studies.csv", encoding="utf-8")))
    pubmed = list(csv.DictReader(open(OUTPUT_DIR / "pubmed_icu_studies.csv", encoding="utf-8")))
    print(f"CT.gov: {len(ctgov):,} | PubMed: {len(pubmed):,}")

    # Index CT.gov by NCT ID
    ct_by_id: Dict[str, Dict] = {s["nct_id"]: s for s in ctgov if s.get("nct_id")}

    # Split PubMed: those with NCT IDs (potential merges) vs those without
    pm_with_nct = [r for r in pubmed if r.get("nct_id", "").startswith("NCT")]
    pm_without_nct = [r for r in pubmed if not r.get("nct_id", "").startswith("NCT")]
    print(f"PubMed with NCT: {len(pm_with_nct)} | without: {len(pm_without_nct)}")

    # --- Part 1: Merged pairs (PubMed records with NCT IDs that match CT.gov) ---
    merged_pairs = []
    for pm in pm_with_nct:
        nct = pm["nct_id"]
        ct = ct_by_id.get(nct)
        if ct:
            pm_title = pm.get("brief_title", "")
            ct_title = ct.get("brief_title", "")
            sim = _levenshtein_sim(pm_title, ct_title)
            merged_pairs.append((pm, ct, "nct_id", sim))

    rng.shuffle(merged_pairs)
    merged_sample = merged_pairs[:args.n]

    merged_path = VALIDATION_DIR / "dedup_merged_sample.csv"
    with open(merged_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pair_id", "pubmed_id", "pubmed_title", "ctgov_nct_id", "ctgov_title",
                     "match_type", "title_similarity", "is_correct_merge", "notes"])
        for i, (pm, ct, mt, sim) in enumerate(merged_sample, 1):
            w.writerow([i, pm.get("trial_id", ""), pm.get("brief_title", ""),
                        ct["nct_id"], ct.get("brief_title", ""),
                        mt, f"{sim:.3f}", "", ""])

    print(f"Merged sample ({len(merged_sample)}): {merged_path}")

    # --- Part 2: Unmerged PubMed records — find closest CT.gov by title ---
    # Build word inverted index for fast candidate retrieval
    word_idx: Dict[str, List[str]] = defaultdict(list)
    for s in ctgov:
        nid = s.get("nct_id", "")
        for w in _words(s.get("brief_title", "")):
            word_idx[w].append(nid)

    # Sample a manageable subset of unmerged PubMed records
    rng.shuffle(pm_without_nct)
    pm_candidates = pm_without_nct[:min(500, len(pm_without_nct))]

    # Pre-compute CT.gov title words
    ct_words_cache: Dict[str, Set[str]] = {}
    for s in ctgov:
        nid = s.get("nct_id", "")
        ct_words_cache[nid] = _words(s.get("brief_title", ""))

    near_misses = []
    for idx, pm in enumerate(pm_candidates):
        pm_title = pm.get("brief_title", "")
        pm_ws = _words(pm_title)
        if not pm_ws:
            continue

        # Collect candidates via inverted index, count word hits
        cand_hits: Dict[str, int] = defaultdict(int)
        for w in pm_ws:
            for nid in word_idx.get(w, []):
                cand_hits[nid] += 1

        # Only check candidates with >= 30% Jaccard overlap
        best_sim, best_ct = 0.0, None
        for nid, hits in cand_hits.items():
            ct_ws = ct_words_cache.get(nid, set())
            union = len(pm_ws | ct_ws)
            if union == 0:
                continue
            jaccard = hits / union  # approximate (hits <= intersection)
            if jaccard < 0.2:
                continue
            ct = ct_by_id.get(nid)
            if not ct:
                continue
            sim = _levenshtein_sim(pm_title, ct.get("brief_title", ""))
            if sim > best_sim:
                best_sim = sim
                best_ct = ct

        if best_ct:
            near_misses.append((pm, best_ct, best_sim))

        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(pm_candidates)} unmerged...", flush=True)

    # Sort by similarity descending — most interesting are near-threshold
    near_misses.sort(key=lambda x: -x[2])
    unmerged_sample = near_misses[:args.n]

    unmerged_path = VALIDATION_DIR / "dedup_unmerged_sample.csv"
    with open(unmerged_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pair_id", "pubmed_id", "pubmed_title", "closest_ctgov_nct", "closest_ctgov_title",
                     "title_similarity", "should_be_merged", "notes"])
        for i, (pm, ct, sim) in enumerate(unmerged_sample, 1):
            w.writerow([i, pm.get("trial_id", ""), pm.get("brief_title", ""),
                        ct["nct_id"], ct.get("brief_title", ""),
                        f"{sim:.3f}", "", ""])

    print(f"Unmerged sample ({len(unmerged_sample)}): {unmerged_path}")
    print(f"\nSimilarity range in unmerged: {unmerged_sample[-1][2]:.3f} - {unmerged_sample[0][2]:.3f}")
    print(f"\nReview instructions:")
    print(f"  Merged: mark 'is_correct_merge' TRUE/FALSE")
    print(f"  Unmerged: mark 'should_be_merged' TRUE/FALSE")


if __name__ == "__main__":
    main()
