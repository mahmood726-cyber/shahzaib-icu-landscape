/* ─────────────────────────────────────────────────────────────────────────────
 * app.js — ICU Living Evidence Map dashboard controller
 *
 * Features: dataset loading, aggregation, rendering, FilterState cross-filter
 * engine, dark mode, global search, filter chips, study detail sidebar,
 * animated counters, guided tour, virtual scroll table, multi-format export.
 * ────────────────────────────────────────────────────────────────────────── */

// ══════════════════════════════════════════════════════════════════════════════
// 0. FilterState — Central Pub/Sub cross-filter engine
// ══════════════════════════════════════════════════════════════════════════════
const FilterState = {
  _state: {},
  _listeners: [],
  set(key, value) {
    this._state[key] = value;
    this._notify();
  },
  clear(key) {
    delete this._state[key];
    this._notify();
  },
  clearAll() {
    this._state = {};
    this._notify();
  },
  get() {
    return { ...this._state };
  },
  onChange(fn) {
    this._listeners.push(fn);
  },
  offChange(fn) {
    this._listeners = this._listeners.filter((f) => f !== fn);
  },
  _notify() {
    const state = { ...this._state };
    this._listeners.forEach((fn) => fn(state));
  },
};

// ══════════════════════════════════════════════════════════════════════════════
// 1. Config + helpers
// ══════════════════════════════════════════════════════════════════════════════
const datasetConfig = {
  broad: {
    label: "All ICU RCTs",
    summary: "data/icu_hemodynamic_summary.json",
    map: "data/icu_hemodynamic_living_map.csv",
    arms: "data/icu_rct_broad_arms.csv",
    capsule: "data/capsule.json",
    enrichment: "data/enrichment_summary.json",
  },
  placebo: {
    label: "Placebo-arm subset",
    summary: "data/icu_hemodynamic_summary_placebo.json",
    map: "data/icu_hemodynamic_living_map_placebo.csv",
    arms: "data/icu_rct_placebo_arms.csv",
    capsule: "data/capsule_placebo.json",
    enrichment: "data/enrichment_summary_placebo.json",
  },
};

const formatNumber = (value) => {
  const num = Number(value || 0);
  return Number.isFinite(num) ? num.toLocaleString("en-US") : "0";
};

const sanitizeCssClass = (name) =>
  String(name || "").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40);

const sortByMentions = (items, key) =>
  [...items].sort((a, b) => (b[key] || 0) - (a[key] || 0));

// ══════════════════════════════════════════════════════════════════════════════
// 2. CSV parser (RFC 4180 compliant)
// ══════════════════════════════════════════════════════════════════════════════
const parseCsv = (text) => {
  const cleaned = text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
  const rows = [];
  let row = [];
  let current = "";
  let inQuotes = false;
  const len = cleaned.length;

  for (let i = 0; i < len; i += 1) {
    const char = cleaned[i];
    if (inQuotes) {
      if (char === '"') {
        if (i + 1 < len && cleaned[i + 1] === '"') {
          current += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else if (char === "\r") {
        // Normalize \r\n inside quoted fields
      } else {
        current += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(current);
      current = "";
    } else if (char === "\r") {
      // skip
    } else if (char === "\n") {
      row.push(current);
      current = "";
      rows.push(row);
      row = [];
    } else {
      current += char;
    }
  }
  if (current || row.length > 0) {
    row.push(current);
    rows.push(row);
  }
  if (rows.length === 0) return [];
  const headers = rows[0];
  return rows.slice(1).map((values) => {
    const obj = {};
    headers.forEach((header, idx) => {
      obj[header] = values[idx] || "";
    });
    return obj;
  });
};

// ══════════════════════════════════════════════════════════════════════════════
// 3. Data structures
// ══════════════════════════════════════════════════════════════════════════════
const buildArmsMap = (rows) => {
  const map = {};
  rows.forEach((row) => {
    const nctId = (row.nct_id || "").trim();
    if (!nctId) return;
    if (!map[nctId]) map[nctId] = [];
    map[nctId].push({
      label: row.arm_label || "",
      isPlacebo: row.is_placebo_arm === "True",
      intervention: row.intervention_names || "",
      comparatorType: row.comparator_type || "",
      armRole: row.arm_role || "",
    });
  });
  return map;
};

const buildDetailIndex = (rows) => {
  const index = {};
  rows.forEach((row) => {
    const nctId = (row.nct_id || "").trim();
    if (!nctId) return;
    if (!index[nctId]) {
      index[nctId] = {
        nct_id: nctId,
        brief_title: row.brief_title || "",
        conditions: row.conditions || "",
        overall_status: row.overall_status || "",
        phase: row.phase || "",
        has_placebo_arm: row.has_placebo_arm || "False",
        start_date: row.start_date || "",
        enrollment: row.enrollment || "",
        countries: row.countries || "",
        outcomes: [],
        _outcomeKeys: new Set(),
      };
    }
    const normalizedKeyword = row.normalized_keyword || row.keyword || "";
    const normalizedUnit = row.normalized_unit || row.unit_raw || "";
    const outcomeKey = [row.measure, normalizedKeyword, normalizedUnit, row.outcome_type].join("\0");
    if (!index[nctId]._outcomeKeys.has(outcomeKey)) {
      index[nctId].outcomes.push({
        measure: row.measure || "",
        normalized_keyword: normalizedKeyword,
        normalized_unit: normalizedUnit,
        outcome_type: row.outcome_type || "",
      });
      index[nctId]._outcomeKeys.add(outcomeKey);
    }
  });
  Object.values(index).forEach((entry) => delete entry._outcomeKeys);
  return index;
};

const increment = (map, key) => {
  if (!map[key]) {
    map[key] = { mention_count: 0, study_ids: new Set(), placebo_ids: new Set() };
  }
  return map[key];
};

const aggregateRows = (rows) => {
  const keywordMap = {};
  const conditionMap = {};
  const outcomeMap = {};
  const unitMap = {};
  const studyIds = new Set();
  const placeboStudyIds = new Set();
  let placeboMentions = 0;

  rows.forEach((row) => {
    const nctId = row.nct_id;
    if (nctId) {
      studyIds.add(nctId);
      if (row.has_placebo_arm === "True") {
        placeboStudyIds.add(nctId);
        placeboMentions += 1;
      }
    }

    const keyword = row.normalized_keyword || row.keyword || "Unmapped";
    const keywordStats = increment(keywordMap, keyword);
    keywordStats.mention_count += 1;
    if (nctId) {
      keywordStats.study_ids.add(nctId);
      if (row.has_placebo_arm === "True") keywordStats.placebo_ids.add(nctId);
    }

    const outcomeType = row.outcome_type || "unspecified";
    const outcomeStats = increment(outcomeMap, outcomeType);
    outcomeStats.mention_count += 1;
    if (nctId) {
      outcomeStats.study_ids.add(nctId);
      if (row.has_placebo_arm === "True") outcomeStats.placebo_ids.add(nctId);
    }

    const unit = row.normalized_unit || row.unit_raw || "Unspecified";
    const unitStats = increment(unitMap, unit);
    unitStats.mention_count += 1;
    if (nctId) {
      unitStats.study_ids.add(nctId);
      if (row.has_placebo_arm === "True") unitStats.placebo_ids.add(nctId);
    }

    (row.conditions || "").split(";").map((s) => s.trim()).filter(Boolean).forEach((condition) => {
      const conditionStats = increment(conditionMap, condition);
      conditionStats.mention_count += 1;
      if (nctId) {
        conditionStats.study_ids.add(nctId);
        if (row.has_placebo_arm === "True") conditionStats.placebo_ids.add(nctId);
      }
    });
  });

  const toArray = (map, keyName) =>
    Object.entries(map).map(([key, stats]) => ({
      [keyName]: key,
      mention_count: stats.mention_count,
      study_count: stats.study_ids.size,
      placebo_study_count: stats.placebo_ids.size,
    }));

  return {
    keywords: toArray(keywordMap, "keyword"),
    conditions: toArray(conditionMap, "condition"),
    outcome_types: toArray(outcomeMap, "outcome_type"),
    units: toArray(unitMap, "unit"),
    totals: {
      total_hemo_mentions: rows.length,
      placebo_hemo_mentions: placeboMentions,
      non_placebo_hemo_mentions: rows.length - placeboMentions,
      studies_with_hemo_mentions: studyIds.size,
      studies_with_placebo: placeboStudyIds.size,
    },
  };
};

// ══════════════════════════════════════════════════════════════════════════════
// 4. Rendering helpers
// ══════════════════════════════════════════════════════════════════════════════
const renderBars = (container, items, labelKey, valueKey, maxItems) => {
  container.innerHTML = "";
  const slice = items.slice(0, maxItems);
  const maxValue = slice.reduce((max, item) => Math.max(max, item[valueKey] || 0), 0) || 1;

  slice.forEach((item) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.style.cursor = "pointer";
    row.setAttribute("role", "button");
    row.setAttribute("tabindex", "0");
    row.setAttribute("aria-label", `${item[labelKey]}: ${formatNumber(item[valueKey])}`);

    const label = document.createElement("div");
    label.textContent = item[labelKey];
    label.title = item[labelKey];

    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${(item[valueKey] / maxValue) * 100}%`;
    track.appendChild(fill);

    const value = document.createElement("div");
    value.className = "bar-value";
    value.textContent = formatNumber(item[valueKey]);

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(value);

    // Cross-filter on click or keyboard activation (P0-A11Y-2)
    const activateFilter = () => {
      if (labelKey === "keyword") FilterState.set("keyword", item[labelKey]);
      else if (labelKey === "condition") FilterState.set("condition", item[labelKey]);
      else if (labelKey === "outcome_type") FilterState.set("outcome", item[labelKey]);
    };
    row.addEventListener("click", activateFilter);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activateFilter(); }
    });

    container.appendChild(row);
  });
};

const fetchJson = async (path) => {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
};

const fetchCsv = async (path) => {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.text();
};

const loadCapsule = async (path) => {
  if (!path) return null;
  try { return await fetchJson(path); } catch { return null; }
};

// ══════════════════════════════════════════════════════════════════════════════
// 5. TruthCert badge
// ══════════════════════════════════════════════════════════════════════════════
const renderBadge = (capsule) => {
  const pill = document.getElementById("badgePill");
  const capsuleId = document.getElementById("badgeCapsuleId");
  const pipelineVer = document.getElementById("badgePipelineVersion");
  const reasonsEl = document.getElementById("badgeReasons");
  const validatorsEl = document.getElementById("badgeValidators");
  const driftEl = document.getElementById("badgeDrift");
  const abstentionsEl = document.getElementById("badgeAbstentions");
  const extraEl = document.getElementById("badgeExtra");

  if (!capsule) {
    pill.textContent = "--";
    pill.className = "badge-pill badge-none";
    capsuleId.textContent = "";
    pipelineVer.textContent = "No capsule available";
    reasonsEl.innerHTML = "";
    validatorsEl.innerHTML = "";
    driftEl.innerHTML = "";
    abstentionsEl.innerHTML = "";
    extraEl.style.display = "none";
    return;
  }

  const badge = capsule.badge || "none";
  pill.textContent = badge;
  pill.className = `badge-pill badge-${sanitizeCssClass(badge)}`;
  capsuleId.textContent = capsule.capsule_id || "";
  pipelineVer.textContent = capsule.pipeline_version
    ? `git:${capsule.pipeline_version} | ${capsule.machine_id || ""}`
    : "";

  const reasons = capsule.badge_reasons || [];
  reasonsEl.innerHTML = "";
  reasons.forEach((r) => {
    const div = document.createElement("div");
    div.textContent = r;
    reasonsEl.appendChild(div);
  });

  extraEl.style.display = "";
  const validations = capsule.validations || [];
  validatorsEl.innerHTML = "";
  validations.forEach((v) => {
    const div = document.createElement("div");
    div.className = v.passed ? "validator-pass" : "validator-fail";
    const icon = v.passed ? "PASS" : "FAIL";
    div.textContent = `[${v.severity}] ${v.rule_id}: ${icon} — ${v.message}`;
    validatorsEl.appendChild(div);
  });

  const drifts = capsule.drift_events || [];
  driftEl.innerHTML = "";
  if (drifts.length === 0) {
    const div = document.createElement("div");
    div.textContent = "No drift events.";
    driftEl.appendChild(div);
  } else {
    drifts.forEach((d) => {
      const div = document.createElement("div");
      div.className = `drift-${sanitizeCssClass(d.severity || "minor")}`;
      const detail = d.pct_change != null
        ? `${d.old} \u2192 ${d.new} (${d.pct_change}%)`
        : d.ppt_shift != null
          ? `${d.old}% \u2192 ${d.new}% (${d.ppt_shift} ppt)`
          : `${d.old} \u2192 ${d.new}`;
      div.textContent = `[${d.severity}] ${d.metric}: ${detail}`;
      driftEl.appendChild(div);
    });
  }

  const abstentions = capsule.abstentions || [];
  abstentionsEl.innerHTML = "";
  if (abstentions.length > 0) {
    const header = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = "Abstentions:";
    header.appendChild(strong);
    abstentionsEl.appendChild(header);
    abstentions.forEach((a) => {
      const div = document.createElement("div");
      div.textContent = `"${a.keyword}" (${a.mention_count} mentions) \u2014 ${a.reason}`;
      abstentionsEl.appendChild(div);
    });
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// 6. State variables
// ══════════════════════════════════════════════════════════════════════════════
const datasetCache = {};
let currentDataset = "broad";
let datasetRows = [];
let datasetArms = {};
let datasetDetail = {};
let selectedNctId = null;
let currentFilteredRows = [];
let focusCondition = "";
let enrichmentData = null;
let currentBarMetric = "study_count";
let currentSummary = null;
let focusedRowIdx = -1;

// ══════════════════════════════════════════════════════════════════════════════
// 7. Dark mode
// ══════════════════════════════════════════════════════════════════════════════
const initDarkMode = () => {
  const toggle = document.getElementById("themeToggle");
  if (!toggle) return;

  // Restore from localStorage, then OS preference
  const stored = localStorage.getItem("shahzaib_theme");
  if (stored === "dark" || stored === "light") {
    document.documentElement.setAttribute("data-theme", stored);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    document.documentElement.setAttribute("data-theme", "dark");
  }

  toggle.addEventListener("click", () => {
    const isDark = document.documentElement.getAttribute("data-theme") === "dark";
    const newTheme = isDark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("shahzaib_theme", newTheme);

    // Re-render Plotly charts with new theme colors
    if (currentSummary && datasetRows.length > 0) {
      renderPlotlyCharts(currentSummary, datasetRows);
    }
  });
};

// ══════════════════════════════════════════════════════════════════════════════
// 8. Animated number counters
// ══════════════════════════════════════════════════════════════════════════════
const animateCounter = (el, target, duration = 800) => {
  if (!el || target == null) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    el.textContent = target.toLocaleString("en-US");
    return;
  }
  const start = performance.now();
  const startVal = parseInt(el.textContent.replace(/[^0-9]/g, ""), 10) || 0;
  if (startVal === target) return;

  const step = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    // Ease-out quad
    const eased = 1 - (1 - progress) * (1 - progress);
    const current = Math.floor(startVal + (target - startVal) * eased);
    el.textContent = current.toLocaleString("en-US");
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = target.toLocaleString("en-US");
  };
  requestAnimationFrame(step);
};

// ══════════════════════════════════════════════════════════════════════════════
// 9. Filter chips
// ══════════════════════════════════════════════════════════════════════════════
const renderFilterChips = (state) => {
  const container = document.getElementById("filterChips");
  if (!container) return;
  container.innerHTML = "";

  const keys = Object.keys(state);
  if (keys.length === 0) {
    container.style.display = "none";
    return;
  }
  container.style.display = "";

  keys.forEach((key) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = `${key}: ${state[key]} `;
    const btn = document.createElement("button");
    btn.setAttribute("aria-label", `Remove ${key} filter`);
    btn.textContent = "\u00d7";
    btn.addEventListener("click", () => FilterState.clear(key));
    chip.appendChild(btn);
    container.appendChild(chip);
  });

  const clearAll = document.createElement("button");
  clearAll.className = "chip chip--clear";
  clearAll.textContent = "Clear all";
  clearAll.addEventListener("click", () => FilterState.clearAll());
  container.appendChild(clearAll);
};

// ══════════════════════════════════════════════════════════════════════════════
// 10. Global search
// ══════════════════════════════════════════════════════════════════════════════
let searchTimeout = null;

const initGlobalSearch = () => {
  const input = document.getElementById("globalSearch");
  if (!input) return;

  input.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      const query = input.value.trim();
      if (!query) {
        FilterState.clear("search");
        return;
      }
      FilterState.set("search", query);
    }, 250);
  });
};

// Parse field-specific search: "keyword:MAP" or "country:USA" or "phase:3" or "year:>2020"
const matchesSearch = (row, query) => {
  if (!query) return true;

  // Field-specific syntax
  const fieldMatch = query.match(/^(\w+):(.+)$/);
  if (fieldMatch) {
    const field = fieldMatch[1].toLowerCase();
    const val = fieldMatch[2].toLowerCase();

    if (field === "keyword") {
      return (row.normalized_keyword || row.keyword || "").toLowerCase().includes(val);
    }
    if (field === "country") {
      return (row.countries || "").toLowerCase().includes(val);
    }
    if (field === "phase") {
      return (row.phase || "").toLowerCase().includes(val);
    }
    if (field === "condition") {
      return (row.conditions || "").toLowerCase().includes(val);
    }
    if (field === "year") {
      const year = parseInt((row.start_date || "").slice(0, 4), 10);
      if (val.startsWith(">")) return year > parseInt(val.slice(1), 10);
      if (val.startsWith("<")) return year < parseInt(val.slice(1), 10);
      return String(year) === val;
    }
    if (field === "placebo") {
      return (val === "yes" || val === "true") ? row.has_placebo_arm === "True" : row.has_placebo_arm !== "True";
    }
  }

  // Full-text search across key fields
  const searchable = [
    row.nct_id, row.brief_title, row.measure,
    row.normalized_keyword, row.keyword,
    row.conditions, row.outcome_type, row.countries,
  ].join(" ").toLowerCase();
  return searchable.includes(query.toLowerCase());
};

// ══════════════════════════════════════════════════════════════════════════════
// 11. Study detail sidebar
// ══════════════════════════════════════════════════════════════════════════════
const openSidebar = (nctId) => {
  const sidebar = document.getElementById("studySidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const content = document.getElementById("sidebarContent");
  if (!sidebar || !content) return;

  const detail = datasetDetail[nctId];
  const arms = datasetArms[nctId] || [];

  content.innerHTML = "";

  if (!detail) {
    content.innerHTML = '<p class="note">No details available for this study.</p>';
    sidebar.classList.add("is-open");
    sidebar.setAttribute("aria-hidden", "false");
    if (backdrop) { backdrop.classList.add("is-visible"); backdrop.setAttribute("aria-hidden", "false"); }
    return;
  }

  // Header
  const header = document.createElement("div");
  header.className = "sidebar-header";
  const title = document.createElement("h3");
  title.textContent = detail.brief_title || "Untitled trial";
  header.appendChild(title);
  content.appendChild(header);

  // Status + phase badges
  const badges = document.createElement("div");
  badges.className = "sidebar-badges";
  if (detail.overall_status) {
    const statusBadge = document.createElement("span");
    statusBadge.className = `status-badge status-badge--${sanitizeCssClass(detail.overall_status).toLowerCase()}`;
    statusBadge.textContent = detail.overall_status;
    badges.appendChild(statusBadge);
  }
  if (detail.phase) {
    const phaseBadge = document.createElement("span");
    phaseBadge.className = "status-badge";
    phaseBadge.textContent = detail.phase;
    badges.appendChild(phaseBadge);
  }
  if (detail.has_placebo_arm === "True") {
    const placeboBadge = document.createElement("span");
    placeboBadge.className = "status-badge status-placebo";
    placeboBadge.textContent = "Placebo";
    badges.appendChild(placeboBadge);
  }
  content.appendChild(badges);

  // Metadata grid
  const grid = document.createElement("div");
  grid.className = "sidebar-grid";
  const fields = [
    ["NCT ID", detail.nct_id],
    ["Start date", detail.start_date || "Not reported"],
    ["Enrollment", detail.enrollment || "Not reported"],
    ["Countries", detail.countries || "Not reported"],
    ["Conditions", detail.conditions || "Not reported"],
  ];
  fields.forEach(([label, value]) => {
    const item = document.createElement("div");
    const lbl = document.createElement("p");
    lbl.className = "detail-label";
    lbl.textContent = label;
    const val = document.createElement("p");
    val.className = "detail-value";
    val.textContent = value;
    item.appendChild(lbl);
    item.appendChild(val);
    grid.appendChild(item);
  });
  content.appendChild(grid);

  // Enrichment badges
  if (enrichmentData && enrichmentData.trials && enrichmentData.trials[nctId]) {
    const trial = enrichmentData.trials[nctId];
    const sources = trial.enrichment_sources || [];
    if (sources.length > 0) {
      const enrichSection = document.createElement("div");
      enrichSection.className = "sidebar-section";
      const enrichTitle = document.createElement("p");
      enrichTitle.className = "detail-label";
      enrichTitle.textContent = "Enrichment sources";
      enrichSection.appendChild(enrichTitle);

      const enrichBadges = document.createElement("div");
      enrichBadges.className = "sidebar-badges";
      const allSources = ["PubMed", "OpenAlex", "FAERS", "Unpaywall", "Crossref", "OpenCitations"];
      allSources.forEach((src) => {
        const badge = document.createElement("span");
        const isActive = sources.includes(src);
        badge.className = `sidebar-badge ${isActive ? "sidebar-badge--active" : "sidebar-badge--inactive"}`;
        badge.title = `${src}: ${isActive ? "Data found" : "No data"}`;
        badge.textContent = src;
        enrichBadges.appendChild(badge);
      });
      enrichSection.appendChild(enrichBadges);

      // PubMed links
      const pmids = trial.pmid_list || [];
      if (pmids.length > 0) {
        const pmidLine = document.createElement("p");
        pmidLine.className = "sidebar-pmids";
        pmidLine.appendChild(document.createTextNode("PubMed: "));
        pmids.slice(0, 3).forEach((pmid, idx) => {
          if (idx > 0) pmidLine.appendChild(document.createTextNode(", "));
          if (/^\d+$/.test(pmid)) {
            const a = document.createElement("a");
            a.href = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
            a.target = "_blank";
            a.rel = "noreferrer";
            a.textContent = pmid;
            pmidLine.appendChild(a);
          } else {
            pmidLine.appendChild(document.createTextNode(pmid));
          }
        });
        if (pmids.length > 3) pmidLine.appendChild(document.createTextNode(` (+${pmids.length - 3} more)`));
        enrichSection.appendChild(pmidLine);
      }

      // Citations
      if (trial.cited_by_total > 0) {
        const citLine = document.createElement("p");
        citLine.textContent = `Cited by: ${formatNumber(trial.cited_by_total)}`;
        enrichSection.appendChild(citLine);
      }

      // OA
      if (trial.is_oa) {
        const oaLine = document.createElement("p");
        oaLine.textContent = `Open Access (${trial.oa_status || "unknown"})`;
        enrichSection.appendChild(oaLine);
      }

      content.appendChild(enrichSection);
    }
  }

  // Arms
  if (arms.length > 0) {
    const armsSection = document.createElement("div");
    armsSection.className = "sidebar-section";
    const armsTitle = document.createElement("p");
    armsTitle.className = "detail-label";
    armsTitle.textContent = `Arms (${arms.length})`;
    armsSection.appendChild(armsTitle);
    const armsList = document.createElement("ul");
    armsList.className = "detail-list";
    arms.forEach((arm) => {
      const li = document.createElement("li");
      const tag = arm.isPlacebo ? " (placebo)" : "";
      const intervention = arm.intervention ? ` \u2014 ${arm.intervention}` : "";
      li.textContent = `${arm.label}${tag}${intervention}`;
      armsList.appendChild(li);
    });
    armsSection.appendChild(armsList);
    content.appendChild(armsSection);
  }

  // Hemodynamic outcomes
  if (detail.outcomes.length > 0) {
    const outcomeSection = document.createElement("div");
    outcomeSection.className = "sidebar-section";
    const outcomeTitle = document.createElement("p");
    outcomeTitle.className = "detail-label";
    outcomeTitle.textContent = `Hemodynamic outcomes (${detail.outcomes.length})`;
    outcomeSection.appendChild(outcomeTitle);
    const outcomeList = document.createElement("ul");
    outcomeList.className = "detail-list";
    detail.outcomes.forEach((o) => {
      const li = document.createElement("li");
      const unit = o.normalized_unit ? ` (${o.normalized_unit})` : "";
      li.textContent = `${o.measure}${unit} \u2014 ${o.normalized_keyword} [${o.outcome_type}]`;
      outcomeList.appendChild(li);
    });
    outcomeSection.appendChild(outcomeList);
    content.appendChild(outcomeSection);
  }

  // Footer buttons
  const footer = document.createElement("div");
  footer.className = "sidebar-footer";
  const nctValid = /^NCT\d{8}$/.test(detail.nct_id);
  if (nctValid) {
    const link = document.createElement("a");
    link.href = `https://clinicaltrials.gov/study/${detail.nct_id}`;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.className = "sidebar-btn";
    link.textContent = "View on ClinicalTrials.gov";
    footer.appendChild(link);
  }
  const copyBtn = document.createElement("button");
  copyBtn.className = "sidebar-btn";
  copyBtn.textContent = "Copy citation";
  copyBtn.addEventListener("click", () => {
    const citation = `${detail.brief_title} (${detail.nct_id}). ClinicalTrials.gov.`;
    navigator.clipboard.writeText(citation).then(() => {
      copyBtn.textContent = "Copied!";
      setTimeout(() => { copyBtn.textContent = "Copy citation"; }, 2000);
    }).catch(() => {});
  });
  footer.appendChild(copyBtn);
  content.appendChild(footer);

  // Open
  sidebar.classList.add("is-open");
  sidebar.setAttribute("aria-hidden", "false");
  if (backdrop) { backdrop.classList.add("is-visible"); backdrop.setAttribute("aria-hidden", "false"); }

  // Focus management: move focus into sidebar and trap Tab (P0-A11Y-1)
  _sidebarTrigger = document.activeElement;
  const closeBtn = document.getElementById("sidebarClose");
  if (closeBtn) requestAnimationFrame(() => closeBtn.focus());

  // Announce to screen reader
  announce(`Study details opened for ${detail.nct_id}`);
};

let _sidebarTrigger = null;

const _trapFocusInSidebar = (e) => {
  if (e.key !== "Tab") return;
  const sidebar = document.getElementById("studySidebar");
  if (!sidebar || !sidebar.classList.contains("is-open")) return;
  const focusable = sidebar.querySelectorAll('a[href], button, [tabindex]:not([tabindex="-1"])');
  if (focusable.length === 0) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
};
document.addEventListener("keydown", _trapFocusInSidebar);

const closeSidebar = () => {
  const sidebar = document.getElementById("studySidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (sidebar) { sidebar.classList.remove("is-open"); sidebar.setAttribute("aria-hidden", "true"); }
  if (backdrop) { backdrop.classList.remove("is-visible"); backdrop.setAttribute("aria-hidden", "true"); }
  // Restore focus to triggering element (P0-A11Y-1)
  if (_sidebarTrigger && _sidebarTrigger.focus) {
    _sidebarTrigger.focus();
    _sidebarTrigger = null;
  }
  selectedNctId = null;
};

// ══════════════════════════════════════════════════════════════════════════════
// 12. Live region announcements
// ══════════════════════════════════════════════════════════════════════════════
const announce = (message) => {
  const el = document.getElementById("liveRegion");
  if (el) {
    el.textContent = "";
    requestAnimationFrame(() => { el.textContent = message; });
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// 13. Download links + summary rendering
// ══════════════════════════════════════════════════════════════════════════════
const updateDownloadLinks = (datasetKey) => {
  const config = datasetConfig[datasetKey];
  if (!config) return;
  document.getElementById("downloadCsv").setAttribute("href", config.map);
  document.getElementById("downloadSummary").setAttribute("href", config.summary);
};

const renderSummary = (summary) => {
  const searchDate = summary.search_date_utc;
  const generatedAt = summary.generated_at || "Unknown";
  document.getElementById("generatedAt").textContent = searchDate
    ? `Searched ${searchDate.slice(0, 10)}, built ${generatedAt.slice(0, 10)}`
    : generatedAt;

  const totals = summary.totals || {};
  const isSubset = summary.label && summary.label !== "broad";
  document.getElementById("totalStudiesLabel").textContent = isSubset
    ? `ICU RCTs (${summary.label} subset)`
    : "Total ICU RCTs";

  // Animate hero stats
  animateCounter(document.getElementById("totalStudies"), totals.total_studies || 0);
  animateCounter(document.getElementById("hemoStudies"), totals.studies_with_hemo_mentions || 0);
  animateCounter(document.getElementById("placeboStudies"), totals.studies_with_placebo || 0);
  animateCounter(document.getElementById("hemoPlaceboStudies"), totals.studies_with_hemo_and_placebo || 0);
  animateCounter(document.getElementById("totalMentions"), totals.total_hemo_mentions || 0);

  const coreEl = document.getElementById("coreHemoMentions");
  const adjEl = document.getElementById("adjunctMentions");
  if (coreEl) coreEl.textContent = formatNumber(totals.core_hemo_mentions || totals.total_hemo_mentions);
  if (adjEl) adjEl.textContent = formatNumber(totals.adjunct_mentions || 0);

  document.getElementById("placeboMentions").textContent = `${formatNumber(totals.placebo_hemo_mentions)} placebo-arm mentions`;
  document.getElementById("nonPlaceboMentions").textContent = `${formatNumber(totals.non_placebo_hemo_mentions)} non-placebo mentions`;

  const placeboRatio = totals.total_hemo_mentions
    ? (totals.placebo_hemo_mentions / totals.total_hemo_mentions) * 100
    : 0;
  document.getElementById("placeboRatioBar").style.width = `${placeboRatio}%`;

  renderCharts({
    keywords: summary.normalized_keywords || summary.keywords || [],
    conditions: summary.conditions || [],
    outcome_types: summary.outcome_types || [],
    units: summary.units || [],
  });
};

const renderCharts = (stats) => {
  const keywordBars = document.getElementById("keywordBars");
  const conditionBars = document.getElementById("conditionBars");
  const outcomeBars = document.getElementById("outcomeBars");

  const barMetric = currentBarMetric || "study_count";
  const keywords = sortByMentions(stats.keywords || [], barMetric);
  const conditions = sortByMentions(stats.conditions || [], barMetric);
  const outcomes = sortByMentions(stats.outcome_types || [], barMetric);

  renderBars(keywordBars, keywords, "keyword", barMetric, 12);
  renderBars(conditionBars, conditions, "condition", barMetric, 12);
  renderBars(outcomeBars, outcomes, "outcome_type", barMetric, 6);

  const outcomeFilter = document.getElementById("outcomeFilter");
  const previousOutcome = outcomeFilter.value;
  outcomeFilter.innerHTML = '<option value="">All outcome types</option>';
  outcomes.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.outcome_type;
    option.textContent = `${item.outcome_type} (${formatNumber(item.mention_count)})`;
    outcomeFilter.appendChild(option);
  });
  outcomeFilter.value = previousOutcome;

  const unitFilter = document.getElementById("unitFilter");
  const previousUnit = unitFilter.value;
  unitFilter.innerHTML = '<option value="">All units</option>';
  const units = sortByMentions(stats.units || [], "mention_count");
  units.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.unit;
    option.textContent = `${item.unit} (${formatNumber(item.mention_count)})`;
    unitFilter.appendChild(option);
  });
  unitFilter.value = previousUnit;
};

// ══════════════════════════════════════════════════════════════════════════════
// 14. Data table with virtual scrolling
// ══════════════════════════════════════════════════════════════════════════════
const ROW_HEIGHT = 44;
const BUFFER_ROWS = 10;
let virtualRows = [];
let tableContainer = null;
let tableBody = null;

const initVirtualTable = () => {
  const tableWrap = document.querySelector(".table-wrap");
  if (!tableWrap) return;

  // Set up virtual scroll container
  tableWrap.style.maxHeight = "600px";
  tableWrap.style.overflowY = "auto";
  // Throttled scroll handler for virtual table
  let scrollRaf = null;
  tableWrap.addEventListener("scroll", () => {
    if (scrollRaf) return;
    scrollRaf = requestAnimationFrame(() => {
      renderVisibleRows();
      scrollRaf = null;
    });
  });
  tableContainer = tableWrap;
  tableBody = document.querySelector("#resultsTable tbody");

  // Arrow key navigation in table
  const table = document.getElementById("resultsTable");
  if (table) {
    table.setAttribute("tabindex", "0");
    table.addEventListener("keydown", (e) => {
      if (!virtualRows.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        focusedRowIdx = Math.min(focusedRowIdx + 1, virtualRows.length - 1);
        highlightFocusedRow(focusedRowIdx);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        focusedRowIdx = Math.max(focusedRowIdx - 1, 0);
        highlightFocusedRow(focusedRowIdx);
      } else if (e.key === "Enter" && focusedRowIdx >= 0 && focusedRowIdx < virtualRows.length) {
        e.preventDefault();
        const row = virtualRows[focusedRowIdx];
        selectedNctId = row.nct_id;
        openSidebar(row.nct_id);
        renderDetail(row.nct_id);
      } else if (e.key === "Home") {
        e.preventDefault();
        focusedRowIdx = 0;
        highlightFocusedRow(focusedRowIdx);
      } else if (e.key === "End") {
        e.preventDefault();
        focusedRowIdx = virtualRows.length - 1;
        highlightFocusedRow(focusedRowIdx);
      }
    });
  }

  function highlightFocusedRow(idx) {
    if (!tableContainer) return;
    // Scroll to make row visible
    const targetTop = idx * ROW_HEIGHT;
    const viewTop = tableContainer.scrollTop;
    const viewBottom = viewTop + tableContainer.clientHeight;
    if (targetTop < viewTop) tableContainer.scrollTop = targetTop;
    else if (targetTop + ROW_HEIGHT > viewBottom) tableContainer.scrollTop = targetTop + ROW_HEIGHT - tableContainer.clientHeight;
    // Highlight via class
    requestAnimationFrame(() => {
      const rows = tableBody.querySelectorAll("tr:not(:first-child)");
      rows.forEach((r) => r.classList.remove("is-focused"));
      // Find the row at this index in virtual rows
      const visibleRows = tableBody.querySelectorAll("tr[data-nct-id]");
      visibleRows.forEach((r) => {
        if (virtualRows[idx] && r.dataset.nctId === virtualRows[idx].nct_id) {
          r.classList.add("is-focused");
        }
      });
    });
    announce(`Row ${idx + 1} of ${virtualRows.length}: ${virtualRows[idx].nct_id}`);
  }
};

const renderVisibleRows = () => {
  if (!tableContainer || !tableBody || virtualRows.length === 0) return;

  const scrollTop = tableContainer.scrollTop;
  const viewHeight = tableContainer.clientHeight;
  const totalHeight = virtualRows.length * ROW_HEIGHT;

  const startIdx = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - BUFFER_ROWS);
  const endIdx = Math.min(virtualRows.length, Math.ceil((scrollTop + viewHeight) / ROW_HEIGHT) + BUFFER_ROWS);

  tableBody.innerHTML = "";

  // Top spacer
  if (startIdx > 0) {
    const topSpacer = document.createElement("tr");
    const topCell = document.createElement("td");
    topCell.colSpan = 7;
    topCell.style.height = `${startIdx * ROW_HEIGHT}px`;
    topCell.style.padding = "0";
    topCell.style.border = "none";
    topSpacer.appendChild(topCell);
    tableBody.appendChild(topSpacer);
  }

  // Visible rows
  for (let i = startIdx; i < endIdx; i++) {
    tableBody.appendChild(createTableRow(virtualRows[i]));
  }

  // Bottom spacer
  const bottomSpace = (virtualRows.length - endIdx) * ROW_HEIGHT;
  if (bottomSpace > 0) {
    const bottomSpacer = document.createElement("tr");
    const bottomCell = document.createElement("td");
    bottomCell.colSpan = 7;
    bottomCell.style.height = `${bottomSpace}px`;
    bottomCell.style.padding = "0";
    bottomCell.style.border = "none";
    bottomSpacer.appendChild(bottomCell);
    tableBody.appendChild(bottomSpacer);
  }
};

const createTableRow = (row) => {
  const tr = document.createElement("tr");
  tr.dataset.nctId = row.nct_id;
  tr.style.height = `${ROW_HEIGHT}px`;
  tr.setAttribute("tabindex", "-1");
  if (row.nct_id === selectedNctId) tr.classList.add("is-selected");

  const cells = [
    row.nct_id,
    row.measure,
    row.normalized_keyword || row.keyword,
    row.keyword,
    row.normalized_unit || row.unit_raw || "",
    row.outcome_type,
    row.has_placebo_arm === "True" ? "Yes" : "No",
  ];

  cells.forEach((value) => {
    const td = document.createElement("td");
    td.textContent = value || "";
    tr.appendChild(td);
  });

  const activateRow = () => {
    selectedNctId = row.nct_id;
    openSidebar(row.nct_id);
    renderDetail(row.nct_id);
    const prev = document.querySelector("#resultsTable tbody tr.is-selected");
    if (prev) prev.classList.remove("is-selected");
    tr.classList.add("is-selected");
  };

  tr.addEventListener("click", activateRow);
  tr.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activateRow(); }
  });

  return tr;
};

const renderTable = (rows) => {
  virtualRows = rows;
  focusedRowIdx = -1;
  const tbody = document.querySelector("#resultsTable tbody");

  if (rows.length === 0) {
    tbody.innerHTML = "";
    const emptyRow = document.createElement("tr");
    const emptyCell = document.createElement("td");
    emptyCell.colSpan = 7;
    emptyCell.textContent = "No results match the filters.";
    emptyRow.appendChild(emptyCell);
    tbody.appendChild(emptyRow);
    return;
  }

  // Use virtual scrolling
  if (tableContainer) {
    renderVisibleRows();
  } else {
    // Fallback: render all (pre-init)
    tbody.innerHTML = "";
    rows.slice(0, 200).forEach((row) => {
      tbody.appendChild(createTableRow(row));
    });
  }

  // Update search count (rows = displayed, currentFilteredRows = filtered, datasetRows = total)
  const countEl = document.getElementById("searchCount");
  if (countEl) {
    const total = datasetRows.length;
    const filtered = currentFilteredRows.length;
    const displayed = rows.length;
    if (displayed < filtered) {
      countEl.textContent = `Showing ${formatNumber(displayed)} of ${formatNumber(filtered)} matching mentions (${formatNumber(total)} total)`;
    } else if (filtered < total) {
      countEl.textContent = `${formatNumber(filtered)} of ${formatNumber(total)} mentions match filters`;
    } else {
      countEl.textContent = `${formatNumber(total)} outcome mentions`;
    }
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// 15. Detail panel (existing — kept for backward compat)
// ══════════════════════════════════════════════════════════════════════════════
const renderDetail = (nctId) => {
  if (!nctId) {
    document.getElementById("detailTitle").textContent = "Select a trial row to see details";
    document.getElementById("detailNct").textContent = "-";
    document.getElementById("detailStatus").textContent = "-";
    document.getElementById("detailPhase").textContent = "-";
    document.getElementById("detailConditions").textContent = "-";
    document.getElementById("detailLink").setAttribute("href", "#");
    document.getElementById("detailArms").innerHTML = "";
    document.getElementById("detailOutcomes").innerHTML = "";
    return;
  }

  const detail = datasetDetail[nctId];
  const arms = datasetArms[nctId] || [];
  const titleEl = document.getElementById("detailTitle");
  const linkEl = document.getElementById("detailLink");
  const nctEl = document.getElementById("detailNct");
  const statusEl = document.getElementById("detailStatus");
  const phaseEl = document.getElementById("detailPhase");
  const conditionsEl = document.getElementById("detailConditions");
  const armsEl = document.getElementById("detailArms");
  const outcomesEl = document.getElementById("detailOutcomes");

  if (!detail) {
    titleEl.textContent = "No details available";
    nctEl.textContent = "-";
    statusEl.textContent = "-";
    phaseEl.textContent = "-";
    conditionsEl.textContent = "-";
    linkEl.setAttribute("href", "#");
    armsEl.innerHTML = "";
    outcomesEl.innerHTML = "";
    return;
  }

  titleEl.textContent = detail.brief_title || "Untitled trial";
  nctEl.textContent = detail.nct_id;
  statusEl.textContent = detail.overall_status || "Unknown";
  phaseEl.textContent = detail.phase || "Not reported";
  conditionsEl.textContent = detail.conditions || "Not reported";
  const nctValid = /^NCT\d{8}$/.test(detail.nct_id);
  linkEl.setAttribute("href", nctValid ? `https://clinicaltrials.gov/study/${detail.nct_id}` : "#");

  armsEl.innerHTML = "";
  if (arms.length === 0) {
    const li = document.createElement("li");
    li.textContent = "Arms not loaded.";
    armsEl.appendChild(li);
  } else {
    arms.forEach((arm) => {
      const li = document.createElement("li");
      const tag = arm.isPlacebo ? " (placebo)" : "";
      const intervention = arm.intervention ? ` \u2014 ${arm.intervention}` : "";
      const role = arm.armRole ? ` [${arm.armRole}]` : "";
      const comparator = arm.comparatorType ? ` {${arm.comparatorType}}` : "";
      li.textContent = `${arm.label}${tag}${role}${comparator}${intervention}`;
      armsEl.appendChild(li);
    });
  }

  outcomesEl.innerHTML = "";
  if (!detail.outcomes.length) {
    const li = document.createElement("li");
    li.textContent = "No hemodynamic outcomes in map.";
    outcomesEl.appendChild(li);
  } else {
    detail.outcomes.forEach((outcome) => {
      const li = document.createElement("li");
      const unit = outcome.normalized_unit ? ` (${outcome.normalized_unit})` : "";
      const keyword = outcome.normalized_keyword ? ` \u2014 ${outcome.normalized_keyword}` : "";
      li.textContent = `${outcome.measure}${unit}${keyword} [${outcome.outcome_type}]`;
      outcomesEl.appendChild(li);
    });
  }

  renderDetailSources(nctId);
};

// ══════════════════════════════════════════════════════════════════════════════
// 16. CSV export
// ══════════════════════════════════════════════════════════════════════════════
const csvEscape = (value) => {
  let text = String(value ?? "");
  let needsPrefix = /^[=+@\t\r]/.test(text);
  if (!needsPrefix) needsPrefix = /[\n\r][=+@]/.test(text);
  if (needsPrefix) text = "'" + text;
  if (text.includes(",") || text.includes('"') || text.includes("\n") || text.includes("\r")) {
    return '"' + text.replace(/"/g, '""') + '"';
  }
  return text;
};

const downloadFilteredCsv = () => {
  const rows = currentFilteredRows || [];
  if (!rows.length) { announce("No data to export."); return; }
  const headers = ["nct_id", "measure", "normalized_keyword", "keyword", "normalized_unit", "outcome_type", "conditions", "has_placebo_arm"];
  const lines = [headers.join(",")];
  rows.forEach((row) => {
    const record = headers.map((key) => csvEscape(row[key] || ""));
    lines.push(record.join(","));
  });
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const blobUrl = URL.createObjectURL(blob);
  link.href = blobUrl;
  link.download = `filtered_hemodynamics_${currentDataset}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
};

// Multi-format export
const downloadFilteredJson = () => {
  const rows = currentFilteredRows || [];
  if (!rows.length) { announce("No data to export."); return; }
  const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  const blobUrl = URL.createObjectURL(blob);
  link.href = blobUrl;
  link.download = `filtered_hemodynamics_${currentDataset}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
};

const copyTableToClipboard = () => {
  const rows = currentFilteredRows || [];
  if (!rows.length) { announce("No data to copy."); return; }
  const headers = ["nct_id", "measure", "normalized_keyword", "keyword", "normalized_unit", "outcome_type", "conditions", "has_placebo_arm"];
  const lines = [headers.join("\t")];
  rows.forEach((row) => {
    lines.push(headers.map((k) => (row[k] || "").replace(/\t/g, " ")).join("\t"));
  });
  navigator.clipboard.writeText(lines.join("\n"))
    .then(() => announce("Data copied to clipboard."))
    .catch(() => announce("Failed to copy to clipboard."));
};

// ══════════════════════════════════════════════════════════════════════════════
// 17. Enrichment rendering
// ══════════════════════════════════════════════════════════════════════════════
const loadEnrichment = async (path) => {
  if (!path) return null;
  try { return await fetchJson(path); } catch { return null; }
};

const renderSourceCoverage = (enrichment) => {
  const section = document.getElementById("provenanceSection");
  const container = document.getElementById("sourceCoverage");
  if (!enrichment || enrichment.trial_count === 0) { section.style.display = "none"; return; }

  const coverage = enrichment.source_coverage;
  if (!coverage || typeof coverage !== "object") { section.style.display = "none"; return; }
  section.style.display = "";
  container.innerHTML = "";
  const totalTrials = enrichment.trial_count || 1;
  const sources = Object.entries(coverage).sort((a, b) => b[1] - a[1]);

  sources.forEach(([source, count]) => {
    const row = document.createElement("div");
    row.className = "source-coverage-row";
    const label = document.createElement("div");
    const badge = document.createElement("span");
    badge.className = `source-badge source-badge-${sanitizeCssClass(source).toLowerCase()}`;
    badge.textContent = source;
    label.appendChild(badge);
    const track = document.createElement("div");
    track.className = "bar-track";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${(count / totalTrials) * 100}%`;
    track.appendChild(fill);
    const value = document.createElement("div");
    value.className = "bar-value";
    value.textContent = `${count}`;
    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(value);
    container.appendChild(row);
  });
};

const renderDetailSources = (nctId) => {
  const sourcesDiv = document.getElementById("detailSources");
  const badgesDiv = document.getElementById("detailSourceBadges");
  const linksDiv = document.getElementById("detailSourceLinks");

  if (!enrichmentData || !enrichmentData.trials || !enrichmentData.trials[nctId]) {
    sourcesDiv.style.display = "none";
    return;
  }

  const trial = enrichmentData.trials[nctId];
  const sources = trial.enrichment_sources || [];
  if (sources.length === 0) { sourcesDiv.style.display = "none"; return; }

  sourcesDiv.style.display = "";
  badgesDiv.innerHTML = "";
  linksDiv.innerHTML = "";

  sources.forEach((source) => {
    const badge = document.createElement("span");
    badge.className = `source-badge source-badge-${sanitizeCssClass(source).toLowerCase()}`;
    badge.textContent = source;
    badgesDiv.appendChild(badge);
  });

  const pmids = trial.pmid_list || [];
  if (pmids.length > 0) {
    const pubmedLine = document.createElement("div");
    pubmedLine.appendChild(document.createTextNode("PubMed: "));
    pmids.slice(0, 5).forEach((pmid, idx) => {
      if (idx > 0) pubmedLine.appendChild(document.createTextNode(", "));
      if (/^\d+$/.test(pmid)) {
        const a = document.createElement("a");
        a.href = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
        a.target = "_blank";
        a.rel = "noreferrer";
        a.textContent = pmid;
        pubmedLine.appendChild(a);
      } else {
        pubmedLine.appendChild(document.createTextNode(pmid));
      }
    });
    if (pmids.length > 5) pubmedLine.appendChild(document.createTextNode(` (+${pmids.length - 5} more)`));
    linksDiv.appendChild(pubmedLine);
  }

  if (trial.is_oa) {
    const oaLine = document.createElement("div");
    const oaBadge = document.createElement("span");
    oaBadge.className = "oa-badge oa-badge-open";
    oaBadge.textContent = "OA";
    oaLine.textContent = "Open Access ";
    oaLine.appendChild(oaBadge);
    if (trial.oa_status) oaLine.appendChild(document.createTextNode(` (${trial.oa_status})`));
    linksDiv.appendChild(oaLine);
  }

  if (trial.cited_by_total > 0) {
    const citLine = document.createElement("div");
    citLine.textContent = `Cited by: ${formatNumber(trial.cited_by_total)}`;
    linksDiv.appendChild(citLine);
  }

  const mesh = trial.mesh_terms || [];
  if (mesh.length > 0) {
    const meshLine = document.createElement("div");
    meshLine.textContent = `MeSH: ${mesh.slice(0, 5).join(", ")}${mesh.length > 5 ? " ..." : ""}`;
    linksDiv.appendChild(meshLine);
  }

  const faers = trial.faers_top_reactions || [];
  if (faers.length > 0) {
    const faersLine = document.createElement("div");
    faersLine.textContent = `FAERS signals: ${faers.slice(0, 3).map((f) => `${f.reaction} (${formatNumber(f.count)})`).join(", ")}`;
    linksDiv.appendChild(faersLine);
  }


};

// ══════════════════════════════════════════════════════════════════════════════
// 18. Filtering (combines explorer filters + FilterState + search)
// ══════════════════════════════════════════════════════════════════════════════
const updateFocusOptions = (conditions) => {
  const select = document.getElementById("focusCondition");
  const previous = select.value;
  select.innerHTML = '<option value="">All conditions</option>';
  conditions.forEach((condition) => {
    const option = document.createElement("option");
    option.value = condition;
    option.textContent = condition;
    select.appendChild(option);
  });
  select.value = previous;
};

const applyFocus = () => {
  const rows = focusCondition
    ? datasetRows.filter((row) =>
        (row.conditions || "").toLowerCase().includes(focusCondition.toLowerCase()))
    : datasetRows;
  const stats = aggregateRows(rows);
  renderCharts(stats);

  const statsEl = document.getElementById("focusStats");
  if (!focusCondition) {
    statsEl.textContent = "Showing all conditions.";
  } else {
    statsEl.textContent = `${focusCondition} \u2014 ${formatNumber(stats.totals.total_hemo_mentions)} mentions, ${formatNumber(stats.totals.studies_with_hemo_mentions)} trials`;
  }
};

const applyFilters = () => {
  const keywordValue = document.getElementById("keywordFilter").value.trim().toLowerCase();
  const conditionValue = document.getElementById("conditionFilter").value.trim().toLowerCase();
  const outcomeValue = document.getElementById("outcomeFilter").value.trim();
  const unitValue = document.getElementById("unitFilter").value.trim();
  const sortKey = document.getElementById("sortBy").value;
  const sortDir = document.getElementById("sortDir").value;
  const placeboOnly = document.getElementById("placeboOnly").checked;
  const rowLimit = Number(document.getElementById("rowLimit").value || 100);

  // Get cross-filter state
  const crossFilter = FilterState.get();
  const searchQuery = crossFilter.search || "";

  const filtered = datasetRows.filter((row) => {
    // Focus condition
    if (focusCondition) {
      if (!(row.conditions || "").toLowerCase().includes(focusCondition.toLowerCase())) return false;
    }
    // Explorer keyword filter
    if (keywordValue) {
      const kw = (row.normalized_keyword || row.keyword || "").toLowerCase();
      const raw = (row.keyword || "").toLowerCase();
      if (!kw.includes(keywordValue) && !raw.includes(keywordValue)) return false;
    }
    // Explorer condition filter
    if (conditionValue) {
      if (!(row.conditions || "").toLowerCase().includes(conditionValue)) return false;
    }
    // Explorer outcome
    if (outcomeValue && row.outcome_type !== outcomeValue) return false;
    // Explorer unit
    if (unitValue && (row.normalized_unit || row.unit_raw || "Unspecified") !== unitValue) return false;
    // Explorer placebo
    if (placeboOnly && row.has_placebo_arm !== "True") return false;

    // FilterState cross-filters
    if (crossFilter.keyword) {
      const kw = (row.normalized_keyword || row.keyword || "").toLowerCase();
      if (!kw.includes(crossFilter.keyword.toLowerCase())) return false;
    }
    if (crossFilter.condition) {
      if (!(row.conditions || "").toLowerCase().includes(crossFilter.condition.toLowerCase())) return false;
    }
    if (crossFilter.outcome) {
      if (row.outcome_type !== crossFilter.outcome) return false;
    }
    if (crossFilter.country) {
      if (!(row.countries || "").toLowerCase().includes(crossFilter.country.toLowerCase())) return false;
    }
    if (crossFilter.phase) {
      if (!(row.phase || "").toLowerCase().includes(crossFilter.phase.toLowerCase())) return false;
    }
    // Global search
    if (searchQuery && !matchesSearch(row, searchQuery)) return false;

    return true;
  });

  const normalizeSortValue = (value) => {
    if (typeof value === "string") return value.toLowerCase();
    if (value === undefined || value === null) return "";
    return String(value).toLowerCase();
  };

  filtered.sort((a, b) => {
    let aValue = "";
    let bValue = "";
    if (sortKey === "has_placebo_arm") {
      aValue = a.has_placebo_arm === "True" ? "1" : "0";
      bValue = b.has_placebo_arm === "True" ? "1" : "0";
    } else if (sortKey === "normalized_unit") {
      aValue = a.normalized_unit || a.unit_raw || "Unspecified";
      bValue = b.normalized_unit || b.unit_raw || "Unspecified";
    } else if (sortKey === "normalized_keyword") {
      aValue = a.normalized_keyword || a.keyword || "";
      bValue = b.normalized_keyword || b.keyword || "";
    } else {
      aValue = a[sortKey] || "";
      bValue = b[sortKey] || "";
    }

    const left = normalizeSortValue(aValue);
    const right = normalizeSortValue(bValue);
    if (left < right) return sortDir === "asc" ? -1 : 1;
    if (left > right) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  // Update aria-sort on table headers
  const sortColMap = {
    nct_id: 0, measure: 1, normalized_keyword: 2,
    keyword: 3, normalized_unit: 4, outcome_type: 5, has_placebo_arm: 6,
  };
  document.querySelectorAll("#resultsTable thead th").forEach((th, idx) => {
    th.setAttribute("aria-sort",
      idx === sortColMap[sortKey]
        ? (sortDir === "asc" ? "ascending" : "descending")
        : "none"
    );
  });

  currentFilteredRows = filtered;
  renderTable(filtered.slice(0, rowLimit));

  // Announce filter result
  announce(`${filtered.length} results match current filters`);
};

// ══════════════════════════════════════════════════════════════════════════════
// 19a. Skeleton loading helpers
// ══════════════════════════════════════════════════════════════════════════════
const addSkeletons = () => {
  document.querySelectorAll(".plotly-chart").forEach((el) => {
    if (el.children.length > 0) return; // already has content
    const skel = document.createElement("div");
    skel.className = "skeleton skeleton-chart";
    skel.setAttribute("aria-hidden", "true");
    el.appendChild(skel);
  });
};

const removeSkeleton = (containerId) => {
  const el = document.getElementById(containerId);
  if (!el) return;
  const skel = el.querySelector(".skeleton");
  if (skel) skel.remove();
};

// ══════════════════════════════════════════════════════════════════════════════
// 19b. Plotly chart rendering (calls all 12 charts) — lazy loading
// ══════════════════════════════════════════════════════════════════════════════
let lazyChartObserver = null;
const renderedCharts = new Set();

const getFilteredChartRows = (rows) => {
  const crossFilter = FilterState.get();
  const needsFilter = Object.keys(crossFilter).length > 0 || focusCondition;
  if (!needsFilter) return rows;
  return rows.filter((row) => {
    // Apply focusCondition filter so charts match the table
    if (focusCondition) {
      if (!(row.conditions || "").toLowerCase().includes(focusCondition.toLowerCase())) return false;
    }
    if (crossFilter.keyword) {
      const kw = (row.normalized_keyword || row.keyword || "").toLowerCase();
      if (!kw.includes(crossFilter.keyword.toLowerCase())) return false;
    }
    if (crossFilter.condition) {
      if (!(row.conditions || "").toLowerCase().includes(crossFilter.condition.toLowerCase())) return false;
    }
    if (crossFilter.outcome) {
      if (row.outcome_type !== crossFilter.outcome) return false;
    }
    if (crossFilter.country) {
      if (!(row.countries || "").toLowerCase().includes(crossFilter.country.toLowerCase())) return false;
    }
    if (crossFilter.phase) {
      if (!(row.phase || "").toLowerCase().includes(crossFilter.phase.toLowerCase())) return false;
    }
    if (crossFilter.search && !matchesSearch(row, crossFilter.search)) return false;
    return true;
  });
};

// Chart render registry: id → render function
const buildChartRegistry = (summary, chartRows) => ({
  prismaFlowChart: () => PlotlyCharts.renderPrismaFlow("prismaFlowChart", summary),
  bubbleMatrixChart: () => PlotlyCharts.renderBubbleMatrix("bubbleMatrixChart", chartRows, summary),
  forestPlotChart: () => PlotlyCharts.renderForestPlot("forestPlotChart", chartRows),
  treemapChart: () => PlotlyCharts.renderTreemap("treemapChart", summary),
  sunburstChart: () => PlotlyCharts.renderSunburst("sunburstChart", summary),
  heatmapChart: () => PlotlyCharts.renderHeatmap("heatmapChart", chartRows),
  timeSeriesChart: () => PlotlyCharts.renderTimeSeries("timeSeriesChart", chartRows),
  sankeyChart: () => PlotlyCharts.renderSankey("sankeyChart", chartRows),
  radarChart: () => PlotlyCharts.renderRadar("radarChart", summary, chartRows),
  networkChart: () => PlotlyCharts.renderNetwork("networkChart", summary),
  choroplethChart: () => PlotlyCharts.renderChoropleth("choroplethChart", chartRows),
});

// Above-fold charts render immediately; below-fold charts defer to IntersectionObserver
const ABOVE_FOLD_CHARTS = new Set(["prismaFlowChart", "bubbleMatrixChart", "forestPlotChart"]);

const renderPlotlyCharts = (summary, rows) => {
  if (typeof PlotlyCharts === "undefined") return;

  const chartRows = getFilteredChartRows(rows);
  const registry = buildChartRegistry(summary, chartRows);

  // Choropleth visibility
  const hasCountries = chartRows.some((r) => r.countries && r.countries.trim());
  const choroplethSection = document.getElementById("choroplethSection");
  if (!hasCountries) {
    if (choroplethSection) choroplethSection.style.display = "none";
  } else {
    if (choroplethSection) choroplethSection.style.display = "";
  }

  // On cross-filter updates: re-render all visible charts immediately
  const isFilterUpdate = renderedCharts.size > 0;

  if (isFilterUpdate) {
    // Re-render all previously rendered charts
    for (const id of renderedCharts) {
      if (registry[id]) {
        if (id === "choroplethChart" && !hasCountries) continue;
        removeSkeleton(id);
        registry[id]();
      }
    }
    return;
  }

  // First render: above-fold immediately, below-fold lazy
  for (const id of ABOVE_FOLD_CHARTS) {
    if (registry[id]) {
      removeSkeleton(id);
      registry[id]();
      renderedCharts.add(id);
    }
  }

  // Set up lazy observer for below-fold charts
  if ("IntersectionObserver" in window) {
    if (lazyChartObserver) lazyChartObserver.disconnect();
    lazyChartObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.id;
          if (registry[id] && !renderedCharts.has(id)) {
            if (id === "choroplethChart" && !hasCountries) return;
            removeSkeleton(id);
            registry[id]();
            renderedCharts.add(id);
          }
          lazyChartObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: "200px 0px" });

    Object.keys(registry).forEach((id) => {
      if (ABOVE_FOLD_CHARTS.has(id)) return;
      const el = document.getElementById(id);
      if (el) lazyChartObserver.observe(el);
    });
  } else {
    // Fallback: render all
    Object.entries(registry).forEach(([id, fn]) => {
      if (ABOVE_FOLD_CHARTS.has(id)) return;
      if (id === "choroplethChart" && !hasCountries) return;
      removeSkeleton(id);
      fn();
      renderedCharts.add(id);
    });
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// 20. Guided tour
// ══════════════════════════════════════════════════════════════════════════════
const TOUR_STEPS = [
  { selector: ".cards", title: "Summary statistics", text: "Key metrics for the evidence map. Animated counters show totals at a glance.", position: "bottom" },
  { selector: ".focus-bar", title: "Filters", text: "Focus on specific conditions or switch between study count and mention count.", position: "bottom" },
  { selector: "#bubbleMatrixChart", title: "Evidence bubble matrix", text: "Flagship visualization: interventions vs outcomes. Bubble size = studies, color = placebo proportion. Click to filter.", position: "top" },
  { selector: "#forestPlotChart", title: "Forest plot", text: "Evidence strength per keyword. Bar color indicates heterogeneity (green = low, red = high).", position: "top" },
  { selector: "#choroplethChart", title: "World map", text: "Geographic distribution of ICU trials. Click a country to filter all charts.", position: "top" },
  { selector: "#timeSeriesChart", title: "Timeline", text: "Trial registrations over time. Toggle cumulative view in the legend.", position: "top" },
  { selector: "#resultsTable", title: "Data table", text: "Browse individual study outcomes. Click a row to see full details in the sidebar.", position: "top" },
  { selector: ".export-btn", title: "Export", text: "Download filtered data as CSV, JSON, or copy to clipboard.", position: "top" },
];

let tourStep = 0;
let tourActive = false;

const cleanupTour = () => {
  document.querySelectorAll(".tour-overlay, .tour-tooltip, .tour-highlight").forEach((el) => el.remove());
};

const endTour = () => {
  cleanupTour();
  tourActive = false;
  tourStep = 0;
  localStorage.setItem("shahzaib_tour_done", "true");
};

const startTour = () => {
  if (localStorage.getItem("shahzaib_tour_done") === "true") return;
  tourStep = 0;
  tourActive = true;
  showTourStep();
};

const showTourStep = () => {
  cleanupTour();

  if (tourStep >= TOUR_STEPS.length) {
    endTour();
    return;
  }

  tourActive = true;
  const step = TOUR_STEPS[tourStep];
  const target = document.querySelector(step.selector);
  if (!target) {
    tourStep++;
    showTourStep();
    return;
  }

  target.scrollIntoView({ behavior: "smooth", block: "center" });

  setTimeout(() => {
    const rect = target.getBoundingClientRect();

    // Overlay (position:fixed — click advances)
    const overlay = document.createElement("div");
    overlay.className = "tour-overlay";
    overlay.addEventListener("click", () => { tourStep++; showTourStep(); });
    document.body.appendChild(overlay);

    // Highlight (position:fixed — no scrollY needed)
    const highlight = document.createElement("div");
    highlight.className = "tour-highlight";
    highlight.style.top = `${rect.top - 8}px`;
    highlight.style.left = `${rect.left - 8}px`;
    highlight.style.width = `${rect.width + 16}px`;
    highlight.style.height = `${rect.height + 16}px`;
    document.body.appendChild(highlight);

    // Tooltip (built with createElement, not innerHTML)
    const tooltip = document.createElement("div");
    tooltip.className = "tour-tooltip";

    const titleEl = document.createElement("div");
    titleEl.className = "tour-title";
    titleEl.textContent = step.title;
    tooltip.appendChild(titleEl);

    const textEl = document.createElement("div");
    textEl.className = "tour-text";
    textEl.textContent = step.text;
    tooltip.appendChild(textEl);

    const nav = document.createElement("div");
    nav.className = "tour-nav";

    const progress = document.createElement("span");
    progress.className = "tour-progress";
    progress.textContent = `${tourStep + 1}/${TOUR_STEPS.length}`;
    nav.appendChild(progress);

    const skipBtn = document.createElement("button");
    skipBtn.className = "btn btn--ghost btn--sm";
    skipBtn.textContent = "Skip";
    skipBtn.addEventListener("click", (e) => { e.stopPropagation(); endTour(); });
    nav.appendChild(skipBtn);

    const nextBtn = document.createElement("button");
    nextBtn.className = "btn btn--sm";
    nextBtn.textContent = tourStep < TOUR_STEPS.length - 1 ? "Next" : "Finish";
    nextBtn.addEventListener("click", (e) => { e.stopPropagation(); tourStep++; showTourStep(); });
    nav.appendChild(nextBtn);

    tooltip.appendChild(nav);

    // Position tooltip (position:fixed — no scrollY needed)
    const isBottom = step.position === "bottom";
    tooltip.style.top = isBottom
      ? `${rect.bottom + 16}px`
      : `${Math.max(8, rect.top - 140)}px`;
    tooltip.style.left = `${Math.max(16, Math.min(rect.left, window.innerWidth - 380))}px`;

    document.body.appendChild(tooltip);

    // Focus management: move focus to tooltip and trap within (P0-A11Y-4)
    requestAnimationFrame(() => nextBtn.focus());
  }, 400);
};

// ══════════════════════════════════════════════════════════════════════════════
// 21. Offline badge + Service Worker
// ══════════════════════════════════════════════════════════════════════════════
const initOffline = () => {
  const badge = document.getElementById("offlineBadge");
  if (!badge) return;

  const updateBadge = () => {
    if (navigator.onLine) {
      badge.classList.remove("is-visible");
    } else {
      badge.classList.add("is-visible");
    }
  };

  window.addEventListener("online", updateBadge);
  window.addEventListener("offline", updateBadge);
  updateBadge();

  // Register service worker
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// 22. Data loading (with Web Worker offload)
// ══════════════════════════════════════════════════════════════════════════════
const parseWithWorker = (csvText) => {
  return new Promise((resolve) => {
    if (typeof Worker === "undefined") {
      resolve(parseCsv(csvText));
      return;
    }
    try {
      const worker = new Worker("data-worker.js");
      worker.onmessage = (e) => {
        if (e.data.type === "parsed") {
          worker.terminate();
          resolve(e.data.rows);
        }
      };
      worker.onerror = () => {
        worker.terminate();
        resolve(parseCsv(csvText));
      };
      worker.postMessage({ type: "parse", csv: csvText });
    } catch {
      resolve(parseCsv(csvText));
    }
  });
};

const loadDataset = async (datasetKey) => {
  if (datasetCache[datasetKey]) return datasetCache[datasetKey];
  const config = datasetConfig[datasetKey];
  if (!config) throw new Error("Unknown dataset");
  const summary = await fetchJson(config.summary);
  const csvText = await fetchCsv(config.map);
  const rows = await parseWithWorker(csvText);
  let armsRows = [];
  if (config.arms) {
    try {
      const armsText = await fetchCsv(config.arms);
      armsRows = parseCsv(armsText);
    } catch {
      armsRows = [];
    }
  }
  const armsMap = buildArmsMap(armsRows);
  const detailIndex = buildDetailIndex(rows);
  datasetCache[datasetKey] = { summary, rows, armsMap, detailIndex };
  return datasetCache[datasetKey];
};

// ══════════════════════════════════════════════════════════════════════════════
// 23. Explorer init
// ══════════════════════════════════════════════════════════════════════════════
const initExplorer = () => {
  // Text inputs: use "input" for live filtering
  ["keywordFilter", "conditionFilter"].forEach((id) => {
    document.getElementById(id).addEventListener("input", applyFilters);
  });
  // Selects + checkbox: use "change" only (avoids double-fire)
  ["outcomeFilter", "unitFilter", "sortBy", "sortDir", "rowLimit"].forEach((id) => {
    document.getElementById(id).addEventListener("change", applyFilters);
  });
  document.getElementById("placeboOnly").addEventListener("change", applyFilters);

  // Export buttons
  document.getElementById("exportCsv").addEventListener("click", downloadFilteredCsv);
  const jsonBtn = document.getElementById("exportJson");
  if (jsonBtn) jsonBtn.addEventListener("click", downloadFilteredJson);
  const clipBtn = document.getElementById("exportClipboard");
  if (clipBtn) clipBtn.addEventListener("click", () => {
    copyTableToClipboard();
    clipBtn.textContent = "Copied!";
    setTimeout(() => { clipBtn.textContent = "Copy to clipboard"; }, 2000);
  });
};

const revealSections = () => {
  const reveals = document.querySelectorAll(".reveal");
  // Use IntersectionObserver for lazy reveal
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -50px 0px" });
    reveals.forEach((section) => observer.observe(section));
  } else {
    // Fallback: staggered reveal
    reveals.forEach((section, index) => {
      setTimeout(() => section.classList.add("is-visible"), 120 * index);
    });
  }
};

const renderFreshness = (summary) => {
  const el = document.getElementById("freshness");
  if (!el) return;
  const info = summary.last_update_info || {};
  const lastUtc = info.last_update_utc || summary.generated_at;
  if (!lastUtc) { el.textContent = ""; return; }
  try {
    const then = new Date(lastUtc);
    const now = new Date();
    const diffMs = now - then;
    const diffHrs = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffHrs < 1) {
      el.textContent = "Updated less than 1 hour ago";
    } else if (diffHrs < 24) {
      el.textContent = `Updated ${diffHrs} hour${diffHrs > 1 ? "s" : ""} ago`;
    } else {
      el.textContent = `Updated ${diffDays} day${diffDays > 1 ? "s" : ""} ago`;
    }
    const sources = info.sources_active || [];
    if (sources.length > 1) {
      el.textContent += ` (${sources.length} sources)`;
    }
  } catch {
    el.textContent = "";
  }
};

// ══════════════════════════════════════════════════════════════════════════════
// 24. Dataset change handler
// ══════════════════════════════════════════════════════════════════════════════
const onDatasetChange = async (datasetKey) => {
  // Clear cross-filters when switching datasets (stale filters cause empty results)
  if (Object.keys(FilterState.get()).length > 0) FilterState.clearAll();
  // Reset lazy chart tracking so all charts re-render with new data
  renderedCharts.clear();
  // Reset condition focus (stale condition may not exist in new dataset)
  focusCondition = "";
  const focusEl = document.getElementById("focusCondition");
  if (focusEl) focusEl.value = "";
  currentDataset = datasetKey;
  updateDownloadLinks(datasetKey);
  const prevError = document.getElementById("datasetError");
  if (prevError) prevError.remove();
  const data = await loadDataset(datasetKey);
  currentSummary = data.summary;
  renderSummary(data.summary);
  renderFreshness(data.summary);
  updateFocusOptions(
    sortByMentions(data.summary.conditions || [], "mention_count").map((item) => item.condition)
  );
  datasetRows = data.rows;
  datasetArms = data.armsMap || {};
  datasetDetail = data.detailIndex || {};
  applyFocus();
  applyFilters();
  if (selectedNctId && datasetDetail[selectedNctId]) {
    renderDetail(selectedNctId);
  } else {
    renderDetail(null);
    selectedNctId = null;
  }
  // TruthCert badge
  const config = datasetConfig[datasetKey];
  const capsule = config ? await loadCapsule(config.capsule) : null;
  renderBadge(capsule);

  // Enrichment data
  enrichmentData = config ? await loadEnrichment(config.enrichment) : null;
  renderSourceCoverage(enrichmentData);

  // Plotly charts
  renderPlotlyCharts(data.summary, data.rows);
};

// ══════════════════════════════════════════════════════════════════════════════
// 25. Init
// ══════════════════════════════════════════════════════════════════════════════
const init = async () => {
  // Dark mode (before anything else renders)
  initDarkMode();

  // Offline badge + service worker
  initOffline();

  // Virtual table setup
  initVirtualTable();

  // Global search
  initGlobalSearch();

  // FilterState listeners
  FilterState.onChange((state) => {
    renderFilterChips(state);
    applyFilters();
    // Re-render charts with cross-filter
    if (currentSummary && datasetRows.length > 0) {
      renderPlotlyCharts(currentSummary, datasetRows);
    }
  });

  // Sidebar close handlers
  const sidebarClose = document.getElementById("sidebarClose");
  const sidebarBackdrop = document.getElementById("sidebarBackdrop");
  if (sidebarClose) sidebarClose.addEventListener("click", closeSidebar);
  if (sidebarBackdrop) sidebarBackdrop.addEventListener("click", closeSidebar);

  // Escape: close tour first, then sidebar
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (tourActive) {
        endTour();
      } else {
        closeSidebar();
      }
    }
  });

  // Explorer filters
  initExplorer();

  // Dataset select
  const datasetSelect = document.getElementById("datasetSelect");
  datasetSelect.addEventListener("change", (event) => {
    onDatasetChange(event.target.value).catch((error) => {
      console.error(error);
      const existing = document.getElementById("datasetError");
      if (existing) existing.remove();
      const msg = document.createElement("p");
      msg.id = "datasetError";
      msg.className = "note";
      msg.textContent = `Failed to load dataset (${error.message}). Check data files.`;
      document.querySelector("main").appendChild(msg);
    });
  });

  // Focus condition select
  const focusSelect = document.getElementById("focusCondition");
  focusSelect.addEventListener("change", (event) => {
    focusCondition = event.target.value;
    applyFocus();
    applyFilters();
  });

  // Bar metric toggle
  const barMetricSelect = document.getElementById("barMetric");
  if (barMetricSelect) {
    barMetricSelect.addEventListener("change", (event) => {
      currentBarMetric = event.target.value;
      const rows = focusCondition
        ? datasetRows.filter((r) =>
            (r.conditions || "").toLowerCase().includes(focusCondition.toLowerCase()))
        : datasetRows;
      const stats = aggregateRows(rows);
      const barMetric = currentBarMetric || "study_count";
      const keywords = sortByMentions(stats.keywords || [], barMetric);
      const conditions = sortByMentions(stats.conditions || [], barMetric);
      const outcomes = sortByMentions(stats.outcome_types || [], barMetric);
      renderBars(document.getElementById("keywordBars"), keywords, "keyword", barMetric, 12);
      renderBars(document.getElementById("conditionBars"), conditions, "condition", barMetric, 12);
      renderBars(document.getElementById("outcomeBars"), outcomes, "outcome_type", barMetric, 6);
    });
  }

  // Add skeleton placeholders to chart containers before data loads
  addSkeletons();

  // Load initial dataset
  await onDatasetChange(currentDataset);
  revealSections();

  // Start guided tour (first-time only)
  setTimeout(() => startTour(), 1500);

  // Auto-refresh every 60 minutes
  setInterval(() => {
    delete datasetCache[currentDataset];
    onDatasetChange(currentDataset).catch(() => {});
  }, 60 * 60 * 1000);
};

init().catch((error) => {
  const message = document.createElement("p");
  message.className = "note";
  message.textContent = `Unable to load summary data (${error.message}).`;
  document.querySelector("main").appendChild(message);
});
