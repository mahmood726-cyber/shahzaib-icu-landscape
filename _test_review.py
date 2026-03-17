import re

# Test: 'sec' pattern with lookbehind/lookahead
pattern = r"(?<!\w)(?:\d+(?:\.\d+)?\s*)sec(?:onds)?(?!\w)"
tests = [
    ("30 seconds", True),
    ("5sec", True),
    ("5.5 seconds", True),
    ("seconds", False),
    ("sec", False),
    ("0.5sec", True),
]
for text, expected in tests:
    match = re.search(pattern, text.lower())
    actual = bool(match)
    status = "OK" if actual == expected else "FAIL"
    print(f'{status}: "{text}" expected={expected} got={actual}')

# Test: PERCENT_CONTEXT_RE
_PERCENT_CONTEXT_RE = re.compile(
    r"(?:percent(?:age)?|%)\s*(?:change|reduction|increase|decrease|improvement|of\s)",
    re.IGNORECASE,
)
tests2 = [
    ("50% reduction in SOFA", True),
    ("Percent change in CO", True),
    ("ejection fraction %", False),
    ("EF 50%", False),
    ("50% of patients", True),
]
print()
for text, expected in tests2:
    match = _PERCENT_CONTEXT_RE.search(text.lower())
    actual = bool(match)
    status = "OK" if actual == expected else "FAIL"
    print(f'{status}: "{text}" expected_exclude={expected} got_exclude={actual}')

# Test: 'Lactate clearance' token ordering in Lactate rule
# Both 'lactate' and 'lactate clearance' are in the same rule
# But the issue is: if keyword is 'lactate clearance' and text has 'lactate clearance',
# normalize_keyword checks kw_lower='lactate clearance' against each rule.
# For the Lactate rule, it checks token_in_text('lactate', 'lactate clearance').
# 'lactate' is > 3 chars, word boundary: \blactate\b in 'lactate clearance' -> matches.
# So it returns 'Lactate' for the first token 'lactate' before reaching 'lactate clearance'.
# This is OK since both map to the same canonical name 'Lactate'.

# Test: 'apache ii' vs 'apache' in ICU Severity Score rule
# Both are in the same rule. token_in_text('sofa', ...) checked first.
# If keyword is 'apache ii', token_in_text('sofa', 'apache ii') -> no match.
# Then 'apache' -> word boundary \bapache\b in 'apache ii' -> matches! Maps to ICU Severity Score.
# This is correct.

# Test: 'ef' short token matching
# 'ef' has len 2, so exact word match via split.
# text.replace('/', ' ').split() must contain exactly 'ef'.
# 'LVEF' -> ['lvef'] -> no match. This is a false negative.
# 'EF of 35%' -> ['ef', 'of', '35%'] -> match.
# 'EF-value' -> ['ef-value'] -> no match. False negative.
print()
tests3 = [
    ("EF of 35%", True),
    ("LVEF measured at 35%", False),  # false negative
    ("EF-value of 40%", False),  # false negative
    ("measured EF 50%", True),
]
for text, expected in tests3:
    lowered = text.lower()
    parts = lowered.replace("/", " ").split()
    actual = any(p == "ef" for p in parts)
    status = "OK" if actual == expected else "FAIL"
    print(f'{status}: "{text}" ef_match expected={expected} got={actual}')

# Test: 'pap' short token - 'PAP smear' false positive?
# 'pap' has len 3, exact word match.
# 'PAP smear' -> replace / -> 'pap smear' -> split -> ['pap', 'smear'] -> matches 'pap'!
# But PAP smear has nothing to do with Pulmonary Artery Pressure.
print()
text_pap = "PAP smear performed"
parts_pap = text_pap.lower().replace("/", " ").split()
print(f'PAP smear false positive: {any(p == "pap" for p in parts_pap)}')

# Test: 'do2' token matching
# 'do2' has len 3, exact word match.
# 'DO2 measurement' -> ['do2', 'measurement'] -> matches.
# 'DO2I' -> ['do2i'] -> no match (indexed version).
print()
tests_do2 = [
    ("DO2 measurement", True),
    ("DO2I indexed", False),
    ("measured DO2", True),
]
for text, expected in tests_do2:
    parts = text.lower().replace("/", " ").split()
    actual = any(p == "do2" for p in parts)
    status = "OK" if actual == expected else "FAIL"
    print(f'{status}: "{text}" do2_match expected={expected} got={actual}')

# Test: _csv_safe edge cases
def _csv_safe(value):
    if not value:
        return value
    if value[0] in ("=", "+", "@", "\t", "\r"):
        return "'" + value
    for prefix in ("\n=", "\n+", "\n@", "\r=", "\r+", "\r@"):
        if prefix in value:
            return "'" + value
    return value

print()
# Does _csv_safe handle double quotes in values? CSV injection via " is possible.
# The csv.DictWriter handles quoting, but _csv_safe doesn't escape internal quotes.
# This is actually fine since csv.DictWriter will properly quote fields.
# But what about tab injection? \t at position 0 is caught.
tests_csv = [
    ("=CMD()", "'=CMD()"),
    ("+1+1", "'+1+1"),
    ("@SUM(A1)", "'@SUM(A1)"),
    ("normal text", "normal text"),
    ("", ""),
    (None, None),
    ("line1\n=CMD()", "'line1\n=CMD()"),
    ("-0.5 mmHg", "-0.5 mmHg"),  # - is not guarded (by design)
]
for inp, expected in tests_csv:
    actual = _csv_safe(inp)
    status = "OK" if actual == expected else "FAIL"
    print(f'{status}: csv_safe({inp!r}) expected={expected!r} got={actual!r}')

# Test: _pct_change edge cases
def _pct_change(old, new):
    if old == 0:
        return None if new > 0 else 0.0
    return abs(new - old) / old * 100.0

print()
# 0 -> 0 should return 0.0
print(f"_pct_change(0, 0) = {_pct_change(0, 0)}")
# 0 -> -5 -> new > 0 is False, returns 0.0. But this is wrong - 0 to -5 is not 0% change!
# However, the totals should never be negative (they're counts), so this is probably OK.
# But what about negative new? The summary totals validator checks non-negative.
print(f"_pct_change(0, -5) = {_pct_change(0, -5)}")
# 100 -> 0: abs(0-100)/100 * 100 = 100%
print(f"_pct_change(100, 0) = {_pct_change(100, 0)}")
