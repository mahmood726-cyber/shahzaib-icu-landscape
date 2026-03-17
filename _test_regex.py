import re

pat = re.compile(
    r"(?:cerebral\s+perfusion(?!\s+pressure)"
    r"|myocardial\s+perfusion\s+(?:scan|imaging|study|scintigraphy|spect|pet)"
    r"|perfusion\s+(?:scan|imaging|study|scintigraphy))",
    re.IGNORECASE,
)

# Should match (true positives)
positives = [
    "cerebral perfusion monitoring",
    "myocardial perfusion scan",
    "myocardial perfusion imaging",
    "myocardial perfusion study",
    "myocardial perfusion scintigraphy",
    "myocardial perfusion spect",
    "myocardial perfusion pet",
    "perfusion scan results",
    "perfusion imaging technique",
    "MYOCARDIAL PERFUSION SCAN",  # case insensitive
]

# Should NOT match (true negatives)
negatives = [
    "cerebral perfusion pressure",
    "myocardial perfusion",           # bare - no qualifying noun
    "myocardial perfusion deficit",   # not a scan/imaging term
    "myocardial perfusion injury",    # hemodynamic concept, not imaging
    "myocardial perfusion reserve",   # hemodynamic concept
]

ok = True
print("=== Should match ===")
for t in positives:
    m = pat.search(t)
    status = "PASS" if m else "FAIL"
    if not m:
        ok = False
    print(f"  {status}: {t!r}")

print()
print("=== Should NOT match ===")
for t in negatives:
    m = pat.search(t)
    status = "PASS" if not m else "FAIL"
    if m:
        ok = False
    print(f"  {status}: {t!r}")

print()
print("ALL PASSED" if ok else "SOME FAILURES")
