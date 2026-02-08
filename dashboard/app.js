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

const parseCsv = (text) => {
  // RFC 4180 compliant parser: handles quoted fields with embedded
  // newlines, commas, and escaped double quotes.
  // Strip BOM if present (common in Excel-exported CSVs)
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
        // Normalize \r\n to \n inside quoted fields; skip bare \r
      } else {
        current += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      row.push(current);
      current = "";
    } else if (char === "\r") {
      // skip \r, handled with \n
    } else if (char === "\n") {
      row.push(current);
      current = "";
      rows.push(row);
      row = [];
    } else {
      current += char;
    }
  }
  // Push last field/row if text doesn't end with newline
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

const buildArmsMap = (rows) => {
  const map = {};
  rows.forEach((row) => {
    const nctId = (row.nct_id || "").trim();
    if (!nctId) return;
    if (!map[nctId]) {
      map[nctId] = [];
    }
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
        outcomes: [],
        _outcomeKeys: new Set(),
      };
    }
    const normalizedKeyword = row.normalized_keyword || row.keyword || "";
    const normalizedUnit = row.normalized_unit || row.unit_raw || "";
    const outcomeKey = [
      row.measure,
      normalizedKeyword,
      normalizedUnit,
      row.outcome_type,
    ].join("\0");
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
  // Release dedup sets — no longer needed after build
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
      if (row.has_placebo_arm === "True") {
        keywordStats.placebo_ids.add(nctId);
      }
    }

    const outcomeType = row.outcome_type || "unspecified";
    const outcomeStats = increment(outcomeMap, outcomeType);
    outcomeStats.mention_count += 1;
    if (nctId) {
      outcomeStats.study_ids.add(nctId);
      if (row.has_placebo_arm === "True") {
        outcomeStats.placebo_ids.add(nctId);
      }
    }

    const unit = row.normalized_unit || row.unit_raw || "Unspecified";
    const unitStats = increment(unitMap, unit);
    unitStats.mention_count += 1;
    if (nctId) {
      unitStats.study_ids.add(nctId);
      if (row.has_placebo_arm === "True") {
        unitStats.placebo_ids.add(nctId);
      }
    }

    (row.conditions || "")
      .split(";")
      .map((item) => item.trim())
      .filter(Boolean)
      .forEach((condition) => {
        const conditionStats = increment(conditionMap, condition);
        conditionStats.mention_count += 1;
        if (nctId) {
          conditionStats.study_ids.add(nctId);
          if (row.has_placebo_arm === "True") {
            conditionStats.placebo_ids.add(nctId);
          }
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

const renderBars = (container, items, labelKey, valueKey, maxItems) => {
  container.innerHTML = "";
  const slice = items.slice(0, maxItems);
  const maxValue = slice.reduce((max, item) => Math.max(max, item[valueKey] || 0), 0) || 1;

  slice.forEach((item) => {
    const row = document.createElement("div");
    row.className = "bar-row";

    const label = document.createElement("div");
    label.textContent = item[labelKey];
    label.title = item[labelKey];

    const track = document.createElement("div");
    track.className = "bar-track";

    const fill = document.createElement("div");
    fill.className = "bar-fill";
    const width = (item[valueKey] / maxValue) * 100;
    fill.style.width = `${width}%`;

    track.appendChild(fill);

    const value = document.createElement("div");
    value.className = "bar-value";
    value.textContent = formatNumber(item[valueKey]);

    row.appendChild(label);
    row.appendChild(track);
    row.appendChild(value);
    container.appendChild(row);
  });
};

const fetchJson = async (path) => {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
};

const fetchCsv = async (path) => {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
};

const loadCapsule = async (path) => {
  if (!path) return null;
  try {
    return await fetchJson(path);
  } catch {
    return null;
  }
};

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

  // Badge pill
  const badge = capsule.badge || "none";
  pill.textContent = badge;
  pill.className = `badge-pill badge-${sanitizeCssClass(badge)}`;

  // Capsule ID and pipeline version
  capsuleId.textContent = capsule.capsule_id || "";
  pipelineVer.textContent = capsule.pipeline_version
    ? `git:${capsule.pipeline_version} | ${capsule.machine_id || ""}`
    : "";

  // Badge reasons (use textContent to prevent XSS from external data)
  const reasons = capsule.badge_reasons || [];
  reasonsEl.innerHTML = "";
  reasons.forEach((r) => {
    const div = document.createElement("div");
    div.textContent = r;
    reasonsEl.appendChild(div);
  });

  // Validators (use textContent to prevent XSS)
  extraEl.style.display = "";
  const validations = capsule.validations || [];
  validatorsEl.innerHTML = "";
  validations.forEach((v) => {
    const div = document.createElement("div");
    div.className = v.passed ? "validator-pass" : "validator-fail";
    // severity and rule_id come from capsule JSON — render via textContent (safe)
    const icon = v.passed ? "PASS" : "FAIL";
    div.textContent = `[${v.severity}] ${v.rule_id}: ${icon} — ${v.message}`;
    validatorsEl.appendChild(div);
  });

  // Drift events (use textContent to prevent XSS)
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

  // Abstentions (use textContent to prevent XSS)
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

const updateDownloadLinks = (datasetKey) => {
  const config = datasetConfig[datasetKey];
  if (!config) return;
  document.getElementById("downloadCsv").setAttribute("href", config.map);
  document.getElementById("downloadSummary").setAttribute("href", config.summary);
};

const renderSummary = (summary) => {
  document.getElementById("generatedAt").textContent = summary.generated_at || "Unknown";

  const totals = summary.totals || {};
  const isSubset = summary.label && summary.label !== "broad";
  document.getElementById("totalStudiesLabel").textContent = isSubset
    ? `ICU RCTs (${summary.label} subset)`
    : "Total ICU RCTs";
  document.getElementById("totalStudies").textContent = formatNumber(totals.total_studies);
  document.getElementById("hemoStudies").textContent = formatNumber(totals.studies_with_hemo_mentions);
  document.getElementById("placeboStudies").textContent = formatNumber(totals.studies_with_placebo);
  document.getElementById("hemoPlaceboStudies").textContent = formatNumber(totals.studies_with_hemo_and_placebo);
  document.getElementById("totalMentions").textContent = formatNumber(totals.total_hemo_mentions);

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

  const keywords = sortByMentions(stats.keywords || [], "mention_count");
  const conditions = sortByMentions(stats.conditions || [], "mention_count");
  const outcomes = sortByMentions(stats.outcome_types || [], "mention_count");

  // Default to study_count for evidence-gap-map relevance (editor review #16).
  // study_count shows unique trials per category; mention_count inflates
  // categories with many time-point outcomes.
  const barMetric = currentBarMetric || "study_count";
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

const renderTable = (rows) => {
  const tbody = document.querySelector("#resultsTable tbody");
  tbody.innerHTML = "";

  if (rows.length === 0) {
    const emptyRow = document.createElement("tr");
    const emptyCell = document.createElement("td");
    emptyCell.colSpan = 7;
    emptyCell.textContent = "No results match the filters.";
    emptyRow.appendChild(emptyCell);
    tbody.appendChild(emptyRow);
    return;
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.dataset.nctId = row.nct_id;
    if (row.nct_id === selectedNctId) {
      tr.classList.add("is-selected");
    }
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

    tr.addEventListener("click", () => {
      const previous = document.querySelector("#resultsTable tbody tr.is-selected");
      if (previous) {
        previous.classList.remove("is-selected");
      }
      tr.classList.add("is-selected");
      selectedNctId = row.nct_id;
      renderDetail(row.nct_id);
    });

    tbody.appendChild(tr);
  });
};

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
      const intervention = arm.intervention ? ` — ${arm.intervention}` : "";
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
      const keyword = outcome.normalized_keyword ? ` — ${outcome.normalized_keyword}` : "";
      li.textContent = `${outcome.measure}${unit}${keyword} [${outcome.outcome_type}]`;
      outcomesEl.appendChild(li);
    });
  }

  // Render enrichment source badges
  renderDetailSources(nctId);
};

const csvEscape = (value) => {
  let text = String(value ?? "");
  // Guard against CSV formula injection in Excel/Sheets.
  // Note: '-' excluded to match Python _csv_safe() — too many false positives
  // in medical data (e.g. '-0.5 mmHg').
  if (/^[=+@\t\r]/.test(text)) {
    text = "'" + text;
  }
  // Escape embedded double quotes and wrap if needed
  if (text.includes(",") || text.includes('"') || text.includes("\n") || text.includes("\r")) {
    return '"' + text.replace(/"/g, '""') + '"';
  }
  return text;
};

const downloadFilteredCsv = () => {
  const rows = currentFilteredRows || [];
  if (!rows.length) {
    return;
  }
  const headers = [
    "nct_id",
    "measure",
    "normalized_keyword",
    "keyword",
    "normalized_unit",
    "outcome_type",
    "conditions",
    "has_placebo_arm",
  ];
  const lines = [headers.join(",")];
  rows.forEach((row) => {
    const record = headers.map((key) => csvEscape(row[key] || ""));
    lines.push(record.join(","));
  });

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  const blobUrl = URL.createObjectURL(blob);
  link.href = blobUrl;
  link.download = `filtered_hemodynamics_${currentDataset}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(blobUrl);
};

const loadEnrichment = async (path) => {
  if (!path) return null;
  try {
    return await fetchJson(path);
  } catch {
    return null;
  }
};

const renderSourceCoverage = (enrichment) => {
  const section = document.getElementById("provenanceSection");
  const container = document.getElementById("sourceCoverage");
  if (!enrichment || enrichment.trial_count === 0) {
    section.style.display = "none";
    return;
  }

  const coverage = enrichment.source_coverage;
  if (!coverage || typeof coverage !== "object") {
    section.style.display = "none";
    return;
  }
  section.style.display = "";
  container.innerHTML = "";
  const totalTrials = enrichment.trial_count || 1;
  const sources = Object.entries(coverage).sort((a, b) => b[1] - a[1]);

  sources.forEach(([source, count]) => {
    const row = document.createElement("div");
    row.className = "source-coverage-row";

    const label = document.createElement("div");
    const badge = document.createElement("span");
    badge.className = `source-badge source-badge-${sanitizeCssClass(source)}`;
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
  if (sources.length === 0) {
    sourcesDiv.style.display = "none";
    return;
  }

  sourcesDiv.style.display = "";
  badgesDiv.innerHTML = "";
  linksDiv.innerHTML = "";

  // Render source badges
  sources.forEach((source) => {
    const badge = document.createElement("span");
    badge.className = `source-badge source-badge-${sanitizeCssClass(source)}`;
    badge.textContent = source;
    badgesDiv.appendChild(badge);
  });

  // Render PubMed links (validate PMID is numeric to prevent XSS)
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
    if (pmids.length > 5) {
      pubmedLine.appendChild(document.createTextNode(` (+${pmids.length - 5} more)`));
    }
    linksDiv.appendChild(pubmedLine);
  }

  // OA badge
  if (trial.is_oa) {
    const oaLine = document.createElement("div");
    const oaBadge = document.createElement("span");
    oaBadge.className = "oa-badge oa-badge-open";
    oaBadge.textContent = "OA";
    oaLine.textContent = "Open Access ";
    oaLine.appendChild(oaBadge);
    if (trial.oa_status) {
      oaLine.appendChild(document.createTextNode(` (${trial.oa_status})`));
    }
    linksDiv.appendChild(oaLine);
  }

  // Citations
  if (trial.cited_by_total > 0) {
    const citLine = document.createElement("div");
    citLine.textContent = `Cited by: ${formatNumber(trial.cited_by_total)}`;
    linksDiv.appendChild(citLine);
  }

  // MeSH terms
  const mesh = trial.mesh_terms || [];
  if (mesh.length > 0) {
    const meshLine = document.createElement("div");
    meshLine.textContent = `MeSH: ${mesh.slice(0, 5).join(", ")}${mesh.length > 5 ? " ..." : ""}`;
    linksDiv.appendChild(meshLine);
  }

  // FAERS reactions
  const faers = trial.faers_top_reactions || [];
  if (faers.length > 0) {
    const faersLine = document.createElement("div");
    faersLine.textContent = `FAERS signals: ${faers
      .slice(0, 3)
      .map((f) => `${f.reaction} (${formatNumber(f.count)})`)
      .join(", ")}`;
    linksDiv.appendChild(faersLine);
  }

  // WHO ICTRP
  const whoIds = trial.who_trial_id || [];
  if (whoIds.length > 0) {
    const whoLine = document.createElement("div");
    whoLine.textContent = `WHO ICTRP: ${whoIds.join(", ")}`;
    if (trial.who_countries) {
      whoLine.textContent += ` — ${trial.who_countries}`;
    }
    linksDiv.appendChild(whoLine);
  }
};

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
        (row.conditions || "").toLowerCase().includes(focusCondition.toLowerCase())
      )
    : datasetRows;
  const stats = aggregateRows(rows);
  renderCharts(stats);

  const statsEl = document.getElementById("focusStats");
  if (!focusCondition) {
    statsEl.textContent = "Showing all conditions.";
  } else {
    statsEl.textContent = `${focusCondition} — ${formatNumber(
      stats.totals.total_hemo_mentions
    )} mentions, ${formatNumber(stats.totals.studies_with_hemo_mentions)} trials`;
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

  const filtered = datasetRows.filter((row) => {
    if (focusCondition) {
      const conditions = (row.conditions || "").toLowerCase();
      if (!conditions.includes(focusCondition.toLowerCase())) {
        return false;
      }
    }
    if (keywordValue) {
      const kw = (row.normalized_keyword || row.keyword || "").toLowerCase();
      const raw = (row.keyword || "").toLowerCase();
      if (!kw.includes(keywordValue) && !raw.includes(keywordValue)) {
        return false;
      }
    }
    if (conditionValue) {
      const conditions = (row.conditions || "").toLowerCase();
      if (!conditions.includes(conditionValue)) {
        return false;
      }
    }
    if (outcomeValue && row.outcome_type !== outcomeValue) {
      return false;
    }
    if (unitValue && (row.normalized_unit || row.unit_raw || "Unspecified") !== unitValue) {
      return false;
    }
    if (placeboOnly && row.has_placebo_arm !== "True") {
      return false;
    }
    return true;
  });

  const normalizeSortValue = (value) => {
    if (typeof value === "string") {
      return value.toLowerCase();
    }
    if (value === undefined || value === null) {
      return "";
    }
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

  currentFilteredRows = filtered;
  renderTable(filtered.slice(0, rowLimit));
};

const loadDataset = async (datasetKey) => {
  if (datasetCache[datasetKey]) {
    return datasetCache[datasetKey];
  }
  const config = datasetConfig[datasetKey];
  if (!config) {
    throw new Error("Unknown dataset");
  }
  const summary = await fetchJson(config.summary);
  const csvText = await fetchCsv(config.map);
  const rows = parseCsv(csvText);
  let armsRows = [];
  if (config.arms) {
    try {
      const armsText = await fetchCsv(config.arms);
      armsRows = parseCsv(armsText);
    } catch {
      // Arms data is supplementary — degrade gracefully
      armsRows = [];
    }
  }
  const armsMap = buildArmsMap(armsRows);
  const detailIndex = buildDetailIndex(rows);
  datasetCache[datasetKey] = { summary, rows, armsMap, detailIndex };
  return datasetCache[datasetKey];
};

const initExplorer = () => {
  [
    "keywordFilter",
    "conditionFilter",
    "outcomeFilter",
    "unitFilter",
    "placeboOnly",
    "sortBy",
    "sortDir",
    "rowLimit",
  ].forEach((id) => {
    const element = document.getElementById(id);
    element.addEventListener("input", applyFilters);
    element.addEventListener("change", applyFilters);
  });

  document.getElementById("exportCsv").addEventListener("click", () => {
    downloadFilteredCsv();
  });
};

const revealSections = () => {
  const reveals = document.querySelectorAll(".reveal");
  reveals.forEach((section, index) => {
    setTimeout(() => section.classList.add("is-visible"), 120 * index);
  });
};

const onDatasetChange = async (datasetKey) => {
  currentDataset = datasetKey;
  updateDownloadLinks(datasetKey);
  const prevError = document.getElementById("datasetError");
  if (prevError) prevError.remove();
  const data = await loadDataset(datasetKey);
  renderSummary(data.summary);
  updateFocusOptions(
    sortByMentions(data.summary.conditions || [], "mention_count").map(
      (item) => item.condition
    )
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
};

const init = async () => {
  initExplorer();
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
  const focusSelect = document.getElementById("focusCondition");
  focusSelect.addEventListener("change", (event) => {
    focusCondition = event.target.value;
    applyFocus();
    applyFilters();
  });
  const barMetricSelect = document.getElementById("barMetric");
  if (barMetricSelect) {
    barMetricSelect.addEventListener("change", (event) => {
      currentBarMetric = event.target.value;
      applyFocus();
    });
  }

  await onDatasetChange(currentDataset);
  revealSections();
};

init().catch((error) => {
  const message = document.createElement("p");
  message.className = "note";
  message.textContent = `Unable to load summary data (${error.message}).`;
  document.querySelector("main").appendChild(message);
});
