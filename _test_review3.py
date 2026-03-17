import re

# Test: HR negative context gap for HR >= 1.0 with = sign
# "HR=1.5" is NOT caught because the [=:] pattern only checks 0.\d
# "HR=1.5 (95% CI 1.2-1.9)" is NOT caught by ANY pattern.
# Let's check each pattern:
# 1. hazard\s+ratio -> no
# 2. adjusted\s+hr\b -> no
# 3. \bahr\b -> no
# 4. \bchr\b -> no
# 5. \bhr\s*[=:]\s*0\.\d -> no (1.5 not 0.X)
# 6. \bhr\s+0\.\d -> no
# 7. \bhr\s*\(\s*95\s*% -> no (it's "HR=1.5 (" not "HR (")
# 8. \bhr\s*\[\s*95\s*% -> no
# 9. \bhr\s*;?\s*95\s*%\s*ci -> no
# 10. \bhr\s+\d\.\d+\s*[,;(] -> no (it's "HR=" not "HR ")
# So "HR=1.5 (95% CI 1.2-1.9)" passes through as a heart rate match!
# This is a real false positive for hazard ratio text.

# Test: the 'EF' short token with the Ejection Fraction fallback unit
# If keyword is 'EF' and text is 'EF 45%', extract_unit sees '%' in '45%'.
# _PERCENT_CONTEXT_RE.search('ef 45%') -> checks for 'percent|% followed by change/reduction/...'
# '45%' doesn't have those contexts. So extract_unit returns ('%', '%').
# But the KEYWORD_FALLBACK_UNITS for Ejection Fraction is '%'.
# So both paths give '%'. Consistent. Good.

# Test: validate_enrichment_staleness SQL injection via enrichment_log table
# The SQL is parameterized, no injection risk. Good.

# Test: _load_prev_capsules sorts by generated_utc string
# ISO timestamps sort correctly as strings. Good.
# But what if generated_utc is missing? c.get("generated_utc", "") -> "" sorts first.
# The _CAPSULE_REQUIRED_KEYS check requires "generated_utc" to be present.
# But it only checks key existence, not that the value is non-empty.
# A capsule with {"generated_utc": ""} would pass validation but sort incorrectly.
# Practically unlikely but worth noting.

# Test: defaultdict(KeywordStats) behavior
# When you access keyword_stats["new_key"], it creates KeywordStats() with defaults.
# mention_count=0, study_ids=set(), placebo_study_ids=set().
# But wait: dataclass field(default_factory=set) creates a new set per instance.
# defaultdict(KeywordStats) calls KeywordStats() which uses the defaults. Good.
# No shared mutable default issue.

# Test: normalize_keyword fallback path
# If kw_lower matches a rule in the first loop (keyword-only),
# it returns immediately. The second loop (combined) is never reached.
# But what if kw_lower = 'map' (len 3)?
# token_in_text('vasopressor-free days', 'map') -> len('vasopressor-free days') > 3,
# word boundary \bvasopressor-free days\b in 'map' -> no match.
# ... continues through rules ...
# token_in_text('mean arterial pressure', 'map') -> len > 3, word boundary -> no match.
# token_in_text('blood pressure', 'map') -> no match.
# ...
# Eventually reaches MAP rule: tokens are ['mean arterial pressure'].
# Wait, no. Let me re-read CANONICAL_RULES.
# MAP rule: ("MAP", ["mean arterial pressure"])
# The tokens are ["mean arterial pressure"] only. Not ["map", "mean arterial pressure"].
# So token_in_text('mean arterial pressure', 'map') -> no match.
# Then Blood Pressure: ['blood pressure', 'systolic', 'diastolic'] -> no match.
# Heart Rate: ['heart rate', 'hr'] -> 'hr' len 2, exact match. 'map'.split() -> ['map']. 'hr' != 'map'. No.
# ... continues ...
# None match! Falls through to combined text loop.
# In the combined loop, "map {matched_text}" is checked.
# If matched_text is "Mean arterial pressure measured continuously",
# then combined = "map mean arterial pressure measured continuously"
# token_in_text checks MAP rule: 'mean arterial pressure' in combined -> word boundary match -> YES!
# Returns "MAP". Correct.
# BUT: if matched_text is just "MAP target 65 mmHg",
# combined = "map map target 65 mmhg"
# token_in_text for MAP rule: 'mean arterial pressure' in "map map target 65 mmhg" -> no.
# Falls through to Blood Pressure? No match. Heart Rate? 'hr' exact word? No.
# ... eventually hits nothing relevant for 'map'.
# Returns keyword.strip() or "Unmapped". keyword is 'MAP', so returns 'MAP'.
# Wait, but 'MAP' is NOT in CANONICAL_RULES tokens. It's only a canonical NAME.
# So normalize_keyword('MAP', 'MAP target 65 mmHg') returns 'MAP'.
# This happens to be the correct canonical name, but only by coincidence!
# The keyword happens to match the canonical name "MAP" exactly.

# But what about keyword 'map' (lowercase from config)?
# keyword.strip() returns 'map'. This does NOT match any canonical name exactly.
# Wait, the config has 'MAP' (uppercase). Let me check:
print("Config keyword 'MAP' -> normalize_keyword fallback returns 'MAP' (correct by coincidence)")
print("If config had lowercase 'map', it would return 'map' which != canonical 'MAP'")

# Actually wait. The hemodynamic_keywords config has "MAP" as a keyword.
# In fetch_ctgov, find_hemodynamic_keywords returns matching keywords preserving case.
# So the CSV has "MAP" in the keyword column.
# normalize_keyword("MAP", text) -> kw_lower = "map"
# First loop: no token matches 'map' as shown above.
# Second loop with combined text: depends on matched_text.
# If matched_text contains "mean arterial pressure", it maps to "MAP". Good.
# If matched_text only contains "MAP" (abbreviation), no token matches.
# Returns "MAP".strip() = "MAP". This IS the canonical name, so it works.

# But this is fragile. If the canonical name were different (e.g., "MAP (Mean Arterial Pressure)"),
# the fallback would return the raw keyword instead.
# The real issue: MAP rule only has "mean arterial pressure" as a token, not "map".
# So the abbreviation "MAP" is never explicitly matched. It only works because:
# 1. The raw keyword is "MAP" from config
# 2. When normalization fails, it returns the raw keyword
# 3. The raw keyword coincidentally equals the canonical name

# Let me check if there are other abbreviation-only keywords in config:
config_keywords = [
    "MAP", "HR", "SV", "SVV", "PPV", "CVP", "PAP", "PCWP",
    "SVR", "SVRI", "PVR", "SvO2", "ScvO2", "CPO", "DO2", "VO2", "EF",
    "SOFA", "APACHE", "APACHE II", "SAPS", "SAPS II", "MODS", "qSOFA",
    "TAPSE", "GLS", "E/e' ratio", "LVOT", "VTI",
]

# Check which config keywords have their lowercase version as a token in CANONICAL_RULES
CANONICAL_RULES = [
    ("Vasopressor-free days", ["vasopressor-free days"]),
    ("Vasopressor dose", ["vasopressor dose"]),
    ("Ventilation duration", ["ventilator-free days", "mechanical ventilation duration"]),
    ("Shock index", ["shock index"]),
    ("Capillary Refill", ["capillary refill", "capillary refill time"]),
    ("MAP", ["mean arterial pressure"]),
    ("Blood Pressure", ["blood pressure", "systolic", "diastolic"]),
    ("Heart Rate", ["heart rate", "hr"]),
    ("Cardiac Output/Index", ["cardiac output", "cardiac index"]),
    ("Cardiac Power Output", ["cardiac power output", "cpo"]),
    ("Stroke Volume", ["stroke volume", "sv"]),
    ("SVV", ["stroke volume variation", "svv"]),
    ("PPV", ["pulse pressure variation", "ppv"]),
    ("CVP", ["central venous pressure", "cvp"]),
    ("PAP", ["pulmonary artery pressure", "pap"]),
    ("PCWP", ["pulmonary capillary wedge pressure", "pcwp"]),
    ("SVR", ["systemic vascular resistance", "systemic vascular resistance index", "svr", "svri"]),
    ("PVR", ["pulmonary vascular resistance", "pvr"]),
    ("Venous O2 Saturation", ["mixed venous oxygen saturation", "central venous oxygen saturation", "svo2", "scvo2"]),
    ("Lactate", ["lactate", "lactate clearance"]),
    ("Oxygen Delivery", ["oxygen delivery", "do2"]),
    ("Oxygen Consumption", ["oxygen consumption", "vo2"]),
    ("Ejection Fraction", ["ejection fraction", "ef"]),
    ("Hemodynamics (general)", ["hemodynamic", "haemodynamic"]),
    ("Vasopressor/Inotrope", ["vasopressor", "vasoactive", "norepinephrine", "noradrenaline", "epinephrine", "adrenaline", "dopamine", "dobutamine", "phenylephrine", "vasopressin", "milrinone", "levosimendan", "inotrope", "inotropic"]),
    ("Tissue Perfusion", ["tissue perfusion", "peripheral perfusion", "perfusion index"]),
    ("Perfusion", ["perfusion"]),
    ("Fluid Responsiveness", ["passive leg raising", "fluid responsiveness", "fluid challenge", "pulse contour"]),
    ("Echocardiographic", ["tapse", "global longitudinal strain", "gls", "e/e' ratio", "lvot", "velocity time integral", "vti"]),
    ("Resuscitation Endpoints", ["base deficit", "base excess", "anion gap"]),
    ("ICU Severity Score", ["sofa", "apache", "apache ii", "saps", "saps ii", "mods", "qsofa"]),
]

all_tokens = set()
for _, tokens in CANONICAL_RULES:
    for t in tokens:
        all_tokens.add(t.lower())

print("\n=== Config abbreviation keywords NOT in CANONICAL_RULES tokens ===")
for kw in config_keywords:
    if kw.lower() not in all_tokens:
        print(f"  '{kw}' (lowercase '{kw.lower()}') NOT found in tokens")

# Check: which of these have their canonical name == the keyword?
canonical_names = {name for name, _ in CANONICAL_RULES}
print("\n=== ...of which the keyword matches a canonical name ===")
for kw in config_keywords:
    if kw.lower() not in all_tokens:
        if kw in canonical_names:
            print(f"  '{kw}' matches canonical name (works by coincidence)")
        else:
            print(f"  '{kw}' does NOT match any canonical name -> will be returned raw")
