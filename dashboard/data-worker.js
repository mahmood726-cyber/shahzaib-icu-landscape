/* ─────────────────────────────────────────────────────────────────────────────
 * data-worker.js — Web Worker for CSV parsing + data aggregation
 *
 * Offloads heavy data processing to a background thread so the main thread
 * stays free for smooth 60fps rendering.
 *
 * Messages:
 *   IN:  { type: "parse", csv: string }
 *   OUT: { type: "parsed", rows: object[], aggregation: object }
 * ────────────────────────────────────────────────────────────────────────── */

/* eslint-env worker */

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
        // skip
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

const aggregate = (rows) => {
  const keywordCounts = {};
  const conditionCounts = {};
  const countryCounts = {};
  const yearCounts = {};
  const cooccurrence = {};
  const studyIds = new Set();

  rows.forEach((row) => {
    const nctId = row.nct_id || "";
    if (nctId) studyIds.add(nctId);

    const kw = row.normalized_keyword || row.keyword || "";
    if (kw && kw !== "Unmapped") {
      keywordCounts[kw] = (keywordCounts[kw] || 0) + 1;
    }

    (row.conditions || "").split(";").map((s) => s.trim()).filter(Boolean).forEach((cond) => {
      conditionCounts[cond] = (conditionCounts[cond] || 0) + 1;
    });

    (row.countries || "").split(";").map((s) => s.trim()).filter(Boolean).forEach((country) => {
      countryCounts[country] = (countryCounts[country] || 0) + 1;
    });

    const year = (row.start_date || "").slice(0, 4);
    if (/^\d{4}$/.test(year)) {
      yearCounts[year] = (yearCounts[year] || 0) + 1;
    }
  });

  // Build co-occurrence matrix (top 20 keyword pairs)
  const kwByStudy = {};
  rows.forEach((row) => {
    const nctId = row.nct_id || "";
    const kw = row.normalized_keyword || "";
    if (!nctId || !kw || kw === "Unmapped") return;
    if (!kwByStudy[nctId]) kwByStudy[nctId] = new Set();
    kwByStudy[nctId].add(kw);
  });

  Object.values(kwByStudy).forEach((kwSet) => {
    const keywords = [...kwSet];
    for (let i = 0; i < keywords.length; i++) {
      for (let j = i + 1; j < keywords.length; j++) {
        const key = [keywords[i], keywords[j]].sort().join("\0");
        cooccurrence[key] = (cooccurrence[key] || 0) + 1;
      }
    }
  });

  const topCooccurrence = Object.entries(cooccurrence)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([key, count]) => {
      const [a, b] = key.split("\0");
      return { keyword_a: a, keyword_b: b, shared_studies: count };
    });

  return {
    keywordCounts,
    conditionCounts,
    countryCounts,
    yearCounts,
    cooccurrence: topCooccurrence,
    totalStudies: studyIds.size,
    totalRows: rows.length,
  };
};

self.addEventListener("message", (event) => {
  const { type, csv } = event.data;

  if (type === "parse") {
    // Post progress
    self.postMessage({ type: "progress", percent: 10 });

    const rows = parseCsv(csv);
    self.postMessage({ type: "progress", percent: 60 });

    const aggregation = aggregate(rows);
    self.postMessage({ type: "progress", percent: 100 });

    self.postMessage({ type: "parsed", rows, aggregation });
  }
});
