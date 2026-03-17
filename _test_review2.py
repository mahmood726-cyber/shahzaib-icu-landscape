import re

# Test: HR negative context - does it handle 'HR=1.5' (value >= 1.0)?
# The pattern has: r"|\bhr\s*[=:]\s*0\.\d" -> only catches HR=0.X
# HR=1.23 is NOT caught by this specific pattern.
# But: r"|\bhr\s+\d\.\d+\s*[,;(]" -> catches "HR 1.23," but NOT "HR=1.23"
# So "HR=1.5 (95% CI 1.2-1.9)" -> the [=:] pattern only matches 0.X.
# But the (95% pattern catches "HR (95%". Hmm, but it's "HR=1.5 (95%", not "HR (95%".
# Let's test:
neg_re = re.compile(
    r"(?:"
    r"hazard\s+ratio"
    r"|adjusted\s+hr\b"
    r"|\bahr\b"
    r"|\bchr\b"
    r"|\bhr\s*[=:]\s*0\.\d"
    r"|\bhr\s+0\.\d"
    r"|\bhr\s*\(\s*95\s*%"
    r"|\bhr\s*\[\s*95\s*%"
    r"|\bhr\s*;?\s*95\s*%\s*ci"
    r"|\bhr\s+\d\.\d+\s*[,;(]"
    r")",
    re.IGNORECASE,
)

tests_hr = [
    ("HR=0.85", True, "HR=0.85 should be hazard ratio"),
    ("HR 0.72", True, "HR 0.72 should be hazard ratio"),
    ("HR (95% CI 0.5-0.8)", True, "HR with 95% CI should be hazard ratio"),
    ("HR=1.5 (95% CI 1.2-1.9)", False, "HR=1.5 NOT caught - no 0.X, no space before digit"),
    ("HR 1.23, 95% CI", True, "HR 1.23, caught by last pattern"),
    ("HR=1.23", False, "HR=1.23 NOT caught - [=:] only catches 0.X"),
    ("HR=2.1 (95% CI: 1.5-2.8)", False, "HR=2.1 NOT caught"),
    ("heart rate HR 80 bpm", False, "HR 80 is heart rate, not caught by neg"),
    ("hazard ratio", True, "explicit hazard ratio text"),
    ("adjusted HR", True, "adjusted HR"),
    ("HR; 95% CI 0.8-1.2", True, "HR; 95% CI pattern"),
    ("HR 95% CI", True, "HR 95% CI pattern"),
]

print("=== HR negative context tests ===")
for text, expected, desc in tests_hr:
    actual = bool(neg_re.search(text))
    status = "OK" if actual == expected else "FAIL"
    print(f'{status}: "{text}" expected={expected} got={actual} -- {desc}')

# Test: keyword_in_text for 'MAP' (len 3, exact word match)
# 'MAP' in outcome "Mean arterial pressure (MAP)" -> split -> [..., '(map)'] -> no match!
# Because split includes parens. The text is lowered and split on whitespace.
# '(map)' != 'map'. So MAP won't match when it's in parentheses!
print("\n=== MAP matching in parentheses ===")
text_map = "mean arterial pressure (map) measured"
parts = text_map.lower().replace("/", " ").split()
print(f"Parts: {parts}")
print(f"'map' in parts: {any(p == 'map' for p in parts)}")
# ['mean', 'arterial', 'pressure', '(map)', 'measured'] -> '(map)' != 'map'
# This is a false negative! However, 'mean arterial pressure' (the longer token)
# would match via word boundary in the same rule, so this is actually fine.
# But what about text that only says "(MAP)" without the full phrase?
text_map2 = "primary outcome: MAP"
parts2 = text_map2.lower().replace("/", " ").split()
print(f"Parts for 'primary outcome: MAP': {parts2}")
print(f"'map' in parts: {any(p == 'map' for p in parts2)}")
# ['primary', 'outcome:', 'map'] -> 'map' matches. Good.

text_map3 = "primary outcome: (MAP)"
parts3 = text_map3.lower().replace("/", " ").split()
print(f"Parts for 'primary outcome: (MAP)': {parts3}")
print(f"'map' in parts: {any(p == 'map' for p in parts3)}")
# ['primary', 'outcome:', '(map)'] -> '(map)' != 'map'. FALSE NEGATIVE.

# Test: 'svr' and 'svri' in the same rule
# SVR rule has tokens: ['systemic vascular resistance', 'systemic vascular resistance index', 'svr', 'svri']
# If keyword is 'SVRI', token_in_text('systemic vascular resistance', 'svri') -> no match (len > 3, word boundary).
# Then 'systemic vascular resistance index' in 'svri' -> no match.
# Then 'svr' in 'svri': len 3, exact word match. 'svri'.split() -> ['svri']. 'svr' != 'svri'. No match.
# Then 'svri' in 'svri': len 4, word boundary. \bsvri\b in 'svri' -> matches!
# So 'SVRI' maps to SVR. Correct.

# Test: normalize_keyword with empty keyword
# kw_lower = '' -> kw_lower is falsy -> skip keyword-only loop
# combined = ' text...' -> works. But what if text is also empty?
# combined = ' '.strip() -> '' -> loop doesn't match -> returns '' or 'Unmapped'
# keyword.strip() is '', so returns 'Unmapped'. Fine.

# Test: extract_unit returns tuple - does build_living_map handle empty string return correctly?
# extract_unit("") returns ("", ""). unit_raw="" and unit_normalized="".
# Then fallback is checked. If no fallback, unit_normalized stays "".
# In unit_stats, it becomes "Unspecified". Good.

# Test: validate_keyword_coverage compares canonical names vs normalized keywords
# config_keywords are canonical names like "MAP", "Blood Pressure", etc.
# But normalized_keywords in summary have {"keyword": "MAP", ...}
# The validator checks: kw in found where found = {item["keyword"] for item in ...}
# So if canonical name is "MAP" and normalized keyword is "MAP", it matches. Good.
# But what about case? Canonical names are title case ("Blood Pressure"),
# and normalized keywords should also be title case (since they come from CANONICAL_RULES).
# So this is fine as long as normalization outputs the canonical name exactly.

# Test: timestamp format in capsule filenames
# truthcert.py line 404: timestamp = now.strftime("%Y%m%dT%H%M%S%fZ")
# %f is microseconds (6 digits). So the format is YYYYMMDDTHHMMSS######Z
# The capsule filename regex is: r"^capsule_[a-zA-Z0-9_-]+_\d{8}T\d{6}\d*Z\.json$"
# \d{8}T\d{6}\d*Z -> 8 date digits, T, 6 time digits, 0+ more digits, Z
# With %f, it's 8 date + 6 time + 6 microsecond = 20 digits after T.
# The regex says \d{6}\d* which allows 6+ digits. So 12 digits total works. Good.
# But what if run_timestamp is an ISO format string like "2026-02-07T21:43:37.598858+00:00"?
# now = datetime.fromisoformat(run_timestamp) -> gives datetime with microseconds
# now.strftime("%Y%m%dT%H%M%S%fZ") -> "20260207T214337598858Z" (no colons/hyphens). Good.
# But what if run_timestamp has NO microseconds? E.g. "2026-02-07T21:43:37+00:00"
# Then %f = "000000". Timestamp = "20260207T214337000000Z".
# Regex \d{8}T\d{6}\d*Z -> matches "20260207T214337000000Z". Good.

print("\n=== Capsule filename regex vs generated timestamps ===")
from datetime import datetime, timezone
test_ts = "2026-02-07T21:43:37.598858+00:00"
now = datetime.fromisoformat(test_ts)
timestamp = now.strftime("%Y%m%dT%H%M%S%fZ")
print(f"Timestamp: {timestamp}")
fn = f"capsule_broad_{timestamp}.json"
regex = re.compile(r"^capsule_[a-zA-Z0-9_-]+_\d{8}T\d{6}\d*Z\.json$")
print(f"Filename: {fn}, matches: {bool(regex.match(fn))}")

# Edge case: label with special chars
# build_living_map validates: re.match(r"^[a-zA-Z0-9_-]+$", label)
# But truthcert.py doesn't validate the label before using it in capsule_id and filename.
# If label somehow bypasses build_living_map validation (e.g., direct call to build_capsule),
# it could create files with bad names. However, the capsule filename regex would reject them
# on load, so they can't poison the drift detection.
print("\n=== Label validation in truthcert ===")
print("truthcert.py does NOT validate label - relies on build_living_map caller to validate")
print("Direct calls to build_capsule with bad labels would create unloadable capsules")
