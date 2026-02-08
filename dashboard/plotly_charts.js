/**
 * PlotlyCharts — 12 interactive Plotly.js visualizations for the ICU Living Evidence Map.
 *
 * 7 original charts (treemap, heatmap, timeseries, choropleth, sunburst, PRISMA-S, co-occurrence)
 * + 5 new charts (bubble matrix, forest plot, sankey, radar, force network)
 * + chart export toolbar + dark mode awareness + FilterState integration.
 */
/* eslint-disable no-unused-vars */
const PlotlyCharts = (() => {
  "use strict";

  // ── Color palette ─────────────────────────────────────────────────
  const COLORS = {
    accent: "#e2674a",
    accent2: "#2a5569",
    accent3: "#f4b36b",
    paper: "#f7f1e7",
    ink: "#1b1a19",
    muted: "#6f5f52",
    teal: "#9ac2c7",
  };

  const CATEGORY = [
    "#e2674a", "#2a5569", "#f4b36b", "#9ac2c7",
    "#c94444", "#8e44ad", "#27ae60", "#326599",
    "#e67e22", "#7f8c8d", "#2d8659", "#d4956a",
  ];

  const RdYlGn = [[0, "#d73027"], [0.25, "#fc8d59"], [0.5, "#fee08b"], [0.75, "#d9ef8b"], [1, "#1a9850"]];

  // ── Dark mode detection ───────────────────────────────────────────
  const isDark = () => document.documentElement.getAttribute("data-theme") === "dark";

  const getThemeColors = () => {
    const dark = isDark();
    return {
      paper: dark ? "rgba(0,0,0,0)" : "rgba(255,255,255,0)",
      plot: dark ? "rgba(26,29,46,0.6)" : "rgba(255,255,255,0.6)",
      text: dark ? "#e8eaed" : COLORS.ink,
      muted: dark ? "#9aa0a6" : COLORS.muted,
      gridColor: dark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)",
    };
  };

  const formatNumber = (value) => {
    const num = Number(value || 0);
    return Number.isFinite(num) ? num.toLocaleString("en-US") : "0";
  };

  const defaultLayout = (title) => {
    const tc = getThemeColors();
    return {
      title: { text: title, font: { family: "Palatino Linotype, serif", size: 18, color: tc.text } },
      paper_bgcolor: tc.paper,
      plot_bgcolor: tc.plot,
      font: { family: "Palatino Linotype, serif", color: tc.text },
      margin: { t: 50, b: 40, l: 50, r: 20 },
    };
  };

  const defaultConfig = { responsive: true, displayModeBar: false };

  // ── Chart Export Toolbar ──────────────────────────────────────────
  function addExportToolbar(containerId, chartId) {
    const toolbarEl = document.getElementById(`toolbar-${containerId}`);
    if (!toolbarEl || toolbarEl.children.length > 0) return;

    const chartEl = document.getElementById(chartId);
    if (!chartEl) return;

    const buttons = [
      { label: "PNG", title: "Download PNG (2x)", fn: () => Plotly.downloadImage(chartEl, { format: "png", scale: 2, filename: chartId }) },
      { label: "SVG", title: "Download SVG", fn: () => Plotly.downloadImage(chartEl, { format: "svg", filename: chartId }) },
    ];

    buttons.forEach(({ label, title, fn }) => {
      const btn = document.createElement("button");
      btn.textContent = label;
      btn.title = title;
      btn.setAttribute("aria-label", title);
      btn.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
      toolbarEl.appendChild(btn);
    });
  }

  // ── FilterState integration ───────────────────────────────────────
  // Charts call this when a data point is clicked to set cross-filter
  function emitFilter(key, value) {
    if (typeof FilterState !== "undefined" && FilterState.set) {
      FilterState.set(key, value);
    }
  }

  // Purge old Plotly instance before re-plotting (prevents memory leaks + click handler accumulation)
  function safePlot(el, data, layout, config) {
    if (el.data) Plotly.purge(el);
    return Plotly.newPlot(el, data, layout, config);
  }

  // ── 1. Treemap — Keywords by canonical category ───────────────────
  function renderTreemap(containerId, summary) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;

    const keywords = summary.normalized_keywords || [];
    if (keywords.length === 0) { el.textContent = "No keyword data."; return; }

    const labels = ["Hemodynamic Keywords"];
    const parents = [""];
    const values = [0];
    const colors = [getThemeColors().paper];

    keywords.forEach((item) => {
      labels.push(item.keyword);
      parents.push("Hemodynamic Keywords");
      values.push(item.study_count || item.mention_count || 1);
      const placeboRatio = item.placebo_study_count && item.study_count
        ? item.placebo_study_count / item.study_count : 0;
      colors.push(placeboRatio > 0.3 ? COLORS.accent2 : placeboRatio > 0.1 ? COLORS.accent3 : COLORS.teal);
    });

    const data = [{
      type: "treemap",
      labels, parents, values,
      marker: { colors },
      textinfo: "label+value",
      hovertemplate: "<b>%{label}</b><br>Studies: %{value}<extra></extra>",
      branchvalues: "total",
    }];

    const layout = { ...defaultLayout("Hemodynamic Keyword Treemap"), margin: { t: 50, b: 10, l: 10, r: 10 } };

    safePlot(el, data, layout, defaultConfig).then(() => {
      addExportToolbar("treemap", containerId);
      el.on("plotly_click", (d) => {
        if (d.points && d.points[0] && d.points[0].label !== "Hemodynamic Keywords") {
          emitFilter("keyword", d.points[0].label);
        }
      });
    });
  }

  // ── 2. Heatmap — Keyword x Condition ──────────────────────────────
  function renderHeatmap(containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;
    if (!rows || rows.length === 0) { el.textContent = "No data."; return; }

    const kwCounts = {};
    const condCounts = {};
    const pairCounts = {};

    rows.forEach((row) => {
      const kw = row.normalized_keyword || row.keyword || "";
      if (!kw || kw === "Unmapped") return;
      const conditions = (row.conditions || "").split(";").map((s) => s.trim()).filter(Boolean);
      kwCounts[kw] = (kwCounts[kw] || 0) + 1;
      conditions.forEach((cond) => {
        condCounts[cond] = (condCounts[cond] || 0) + 1;
        const key = `${kw}\0${cond}`;
        pairCounts[key] = (pairCounts[key] || 0) + 1;
      });
    });

    const topKw = Object.entries(kwCounts).sort((a, b) => b[1] - a[1]).slice(0, 12).map((e) => e[0]);
    const topCond = Object.entries(condCounts).sort((a, b) => b[1] - a[1]).slice(0, 15).map((e) => e[0]);
    if (topKw.length === 0 || topCond.length === 0) { el.textContent = "Insufficient data."; return; }

    const z = topKw.map((kw) => topCond.map((cond) => pairCounts[`${kw}\0${cond}`] || 0));
    // Add annotation text in cells
    const annotations = [];
    topKw.forEach((kw, yi) => {
      topCond.forEach((cond, xi) => {
        const val = z[yi][xi];
        if (val > 0) {
          annotations.push({
            x: cond, y: kw, text: String(val),
            showarrow: false, font: { size: 10, color: val > 5 ? "#fff" : getThemeColors().text },
          });
        }
      });
    });

    const tc = getThemeColors();
    const data = [{
      type: "heatmap", z, x: topCond, y: topKw,
      colorscale: isDark()
        ? [[0, "#1a1d2e"], [0.5, "#8e5a2b"], [1, "#e2674a"]]
        : [[0, "#f7f1e7"], [0.5, "#f4b36b"], [1, "#e2674a"]],
      hovertemplate: "<b>%{y}</b> x <b>%{x}</b><br>Count: %{z}<extra></extra>",
    }];

    const layout = {
      ...defaultLayout("Keyword x Condition Heatmap"),
      annotations,
      xaxis: { tickangle: -45, automargin: true, tickfont: { size: 10 } },
      yaxis: { automargin: true, tickfont: { size: 11 } },
      margin: { t: 50, b: 120, l: 180, r: 20 },
    };

    safePlot(el, data, layout, defaultConfig).then(() => {
      addExportToolbar("heatmap", containerId);
      el.on("plotly_click", (d) => {
        if (d.points && d.points[0]) {
          emitFilter("keyword", d.points[0].y);
        }
      });
    });
  }

  // ── 3. Time series — Trial registrations by year ──────────────────
  function renderTimeSeries(containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;
    if (!rows || rows.length === 0) { el.textContent = "No data."; return; }

    const yearAll = {};
    const yearPlacebo = {};
    const seen = {};
    const seenPlacebo = {};

    rows.forEach((row) => {
      const nctId = row.nct_id || "";
      const startDate = row.start_date || "";
      if (!startDate || startDate.length < 4) return;
      const year = startDate.slice(0, 4);
      if (!/^\d{4}$/.test(year)) return;
      if (!seen[nctId]) { seen[nctId] = true; yearAll[year] = (yearAll[year] || 0) + 1; }
      if (row.has_placebo_arm === "True" && !seenPlacebo[nctId]) {
        seenPlacebo[nctId] = true; yearPlacebo[year] = (yearPlacebo[year] || 0) + 1;
      }
    });

    const years = Object.keys({ ...yearAll, ...yearPlacebo }).sort();
    if (years.length === 0) { el.textContent = "No year data."; return; }

    // Compute cumulative
    let cumAll = 0;
    let cumPlacebo = 0;
    const cumAllArr = years.map((y) => { cumAll += yearAll[y] || 0; return cumAll; });
    const cumPlaceboArr = years.map((y) => { cumPlacebo += yearPlacebo[y] || 0; return cumPlacebo; });

    const data = [
      { x: years, y: years.map((y) => yearAll[y] || 0), type: "scatter", mode: "lines+markers", name: "All trials", line: { color: COLORS.accent2, width: 2 }, marker: { size: 6 } },
      { x: years, y: years.map((y) => yearPlacebo[y] || 0), type: "scatter", mode: "lines+markers", name: "Placebo subset", line: { color: COLORS.accent, width: 2 }, marker: { size: 6 } },
      { x: years, y: cumAllArr, type: "scatter", mode: "lines", name: "Cumulative (all)", line: { color: COLORS.accent2, width: 1, dash: "dot" }, visible: "legendonly" },
      { x: years, y: cumPlaceboArr, type: "scatter", mode: "lines", name: "Cumulative (placebo)", line: { color: COLORS.accent, width: 1, dash: "dot" }, visible: "legendonly" },
    ];

    const tc = getThemeColors();
    const layout = {
      ...defaultLayout("Trial Registrations by Year"),
      xaxis: { title: "Start year", dtick: 5, gridcolor: tc.gridColor },
      yaxis: { title: "Number of trials", gridcolor: tc.gridColor },
      legend: { x: 0.02, y: 0.98 },
    };

    safePlot(el, data, layout, defaultConfig).then(() => addExportToolbar("timeSeries", containerId));
  }

  // ── 4. Geographic choropleth ──────────────────────────────────────
  function renderChoropleth(containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;
    if (!rows || rows.length === 0) { el.textContent = "No data."; return; }

    const countryCounts = {};
    const seen = {};
    rows.forEach((row) => {
      const nctId = row.nct_id || "";
      (row.countries || "").split(";").map((s) => s.trim()).filter(Boolean).forEach((country) => {
        const key = `${nctId}\0${country}`;
        if (!seen[key]) { seen[key] = true; countryCounts[country] = (countryCounts[country] || 0) + 1; }
      });
    });

    const names = Object.keys(countryCounts);
    if (names.length === 0) { el.textContent = "No country data."; return; }

    const tc = getThemeColors();
    const data = [{
      type: "choropleth", locationmode: "country names",
      locations: names, z: names.map((n) => countryCounts[n]),
      text: names.map((n) => `${n}: ${countryCounts[n]} trials`),
      colorscale: isDark()
        ? [[0, "#1a1d2e"], [0.5, "#8e5a2b"], [1, "#2a5569"]]
        : [[0, "#f7f1e7"], [0.5, "#f4b36b"], [1, "#2a5569"]],
      colorbar: { title: "Trials", thickness: 15 },
      hovertemplate: "<b>%{location}</b><br>Trials: %{z}<extra></extra>",
    }];

    const layout = {
      ...defaultLayout("Geographic Distribution of ICU Trials"),
      geo: { showframe: false, showcoastlines: true, coastlinecolor: tc.muted,
        projection: { type: "natural earth" }, bgcolor: tc.paper,
        landcolor: isDark() ? "#242736" : "#f0ede6",
      },
      margin: { t: 50, b: 10, l: 10, r: 10 },
    };

    safePlot(el, data, layout, defaultConfig).then(() => {
      addExportToolbar("choropleth", containerId);
      el.on("plotly_click", (d) => {
        if (d.points && d.points[0]) emitFilter("country", d.points[0].location);
      });
    });
  }

  // ── 5. Sunburst — outcome hierarchy ───────────────────────────────
  function renderSunburst(containerId, summary) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;

    const keywords = summary.normalized_keywords || [];
    if (keywords.length === 0) { el.textContent = "No keyword data."; return; }

    const labels = ["ICU Outcomes"];
    const parents = [""];
    const values = [0];

    keywords.forEach((item) => {
      labels.push(item.keyword);
      parents.push("ICU Outcomes");
      values.push(item.study_count || 1);
    });

    const tc = getThemeColors();
    const data = [{
      type: "sunburst", labels, parents, values,
      branchvalues: "total",
      marker: { colors: labels.map((_, i) => i === 0 ? (isDark() ? "#1a1d2e" : COLORS.paper) : CATEGORY[i % CATEGORY.length]) },
      hovertemplate: "<b>%{label}</b><br>Studies: %{value}<extra></extra>",
      textinfo: "label",
    }];

    const layout = { ...defaultLayout("Hemodynamic Outcome Hierarchy"), margin: { t: 50, b: 10, l: 10, r: 10 } };
    safePlot(el, data, layout, defaultConfig).then(() => addExportToolbar("sunburst", containerId));
  }

  // ── 6. PRISMA-S flow (SVG) ────────────────────────────────────────
  function renderPrismaFlow(containerId, summary) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const flow = summary.prisma_flow || {};
    const ctgov = flow.ctgov_retrieved || flow.retrieved_from_api || 0;
    const who = flow.who_ictrp_retrieved || 0;
    const pubmed = flow.pubmed_retrieved || 0;
    const afterDedup = flow.total_after_dedup || flow.valid_nct_ids || ctgov;
    const withHemo = flow.with_hemodynamic_outcomes || 0;
    const withPlacebo = flow.with_placebo_arms || 0;
    const hemoPlacebo = flow.with_hemo_and_placebo || 0;
    const excluded = flow.excluded_no_hemo || 0;
    const searchDate = flow.search_date_utc ? flow.search_date_utc.slice(0, 10) : "N/A";

    const tc = getThemeColors();
    const boxFill = isDark() ? "#242736" : "white";
    const highlightFill = isDark() ? "#1e2a3a" : "#f0f7fa";
    const greenFill = isDark() ? "#1e3a2a" : "#e8f5e9";
    const redFill = isDark() ? "#3a1e1e" : "#fdf2f0";

    const boxStyle = `rx="8" ry="8" fill="${boxFill}" stroke="${COLORS.accent2}" stroke-width="1.5"`;
    const textStyle = `font-family="Palatino Linotype, serif" font-size="13" fill="${tc.text}" text-anchor="middle"`;
    const smallStyle = `font-family="Palatino Linotype, serif" font-size="11" fill="${tc.muted}" text-anchor="middle"`;
    const arrowStyle = `stroke="${COLORS.accent2}" stroke-width="1.5" marker-end="url(#prisma-arrowhead)"`;

    el.innerHTML = `
      <svg viewBox="0 0 720 440" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:720px;margin:0 auto;display:block" role="img" aria-label="PRISMA-S flow diagram">
        <defs>
          <marker id="prisma-arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="${COLORS.accent2}" />
          </marker>
        </defs>
        <text x="360" y="24" font-family="Palatino Linotype, serif" font-size="16" font-weight="bold" fill="${tc.text}" text-anchor="middle">PRISMA-S Flow Diagram (searched ${searchDate})</text>
        <rect x="20" y="45" width="200" height="55" ${boxStyle} />
        <text x="120" y="68" ${textStyle} font-weight="bold">ClinicalTrials.gov</text>
        <text x="120" y="86" ${smallStyle}>${formatNumber(ctgov)} records</text>
        <rect x="260" y="45" width="200" height="55" ${boxStyle} />
        <text x="360" y="68" ${textStyle} font-weight="bold">WHO ICTRP</text>
        <text x="360" y="86" ${smallStyle}>${formatNumber(who)} records</text>
        <rect x="500" y="45" width="200" height="55" ${boxStyle} />
        <text x="600" y="68" ${textStyle} font-weight="bold">PubMed</text>
        <text x="600" y="86" ${smallStyle}>${formatNumber(pubmed)} records</text>
        <line x1="120" y1="100" x2="120" y2="130" ${arrowStyle} />
        <line x1="360" y1="100" x2="360" y2="130" ${arrowStyle} />
        <line x1="600" y1="100" x2="600" y2="130" ${arrowStyle} />
        <line x1="120" y1="130" x2="600" y2="130" stroke="${COLORS.accent2}" stroke-width="1.5" />
        <line x1="360" y1="130" x2="360" y2="155" ${arrowStyle} />
        <rect x="210" y="155" width="300" height="55" rx="8" ry="8" fill="${highlightFill}" stroke="${COLORS.accent2}" stroke-width="1.5" />
        <text x="360" y="178" ${textStyle} font-weight="bold">After deduplication</text>
        <text x="360" y="196" ${smallStyle}>${formatNumber(afterDedup)} unique trials</text>
        <line x1="360" y1="210" x2="360" y2="245" ${arrowStyle} />
        <rect x="520" y="245" width="180" height="50" rx="8" ry="8" fill="${redFill}" stroke="${COLORS.accent2}" stroke-width="1.5" />
        <text x="610" y="266" ${smallStyle}>Excluded (no hemo):</text>
        <text x="610" y="282" ${smallStyle} font-weight="bold">${formatNumber(excluded)}</text>
        <line x1="510" y1="270" x2="520" y2="270" ${arrowStyle} />
        <rect x="210" y="245" width="300" height="55" ${boxStyle} />
        <text x="360" y="268" ${textStyle} font-weight="bold">With hemodynamic outcomes</text>
        <text x="360" y="286" ${smallStyle}>${formatNumber(withHemo)} trials</text>
        <line x1="360" y1="300" x2="360" y2="335" ${arrowStyle} />
        <rect x="110" y="335" width="220" height="55" rx="8" ry="8" fill="${highlightFill}" stroke="${COLORS.accent2}" stroke-width="1.5" />
        <text x="220" y="358" ${textStyle} font-weight="bold">Placebo-arm trials</text>
        <text x="220" y="376" ${smallStyle}>${formatNumber(withPlacebo)} trials</text>
        <rect x="380" y="335" width="230" height="55" rx="8" ry="8" fill="${greenFill}" stroke="${COLORS.accent2}" stroke-width="1.5" />
        <text x="495" y="358" ${textStyle} font-weight="bold">Hemo + Placebo</text>
        <text x="495" y="376" ${smallStyle}>${formatNumber(hemoPlacebo)} trials</text>
        <line x1="300" y1="320" x2="220" y2="335" ${arrowStyle} />
        <line x1="420" y1="320" x2="495" y2="335" ${arrowStyle} />
        <text x="360" y="420" ${smallStyle} font-style="italic">Adapted PRISMA-S flow for evidence gap mapping. Not a full PRISMA 2020 diagram.</text>
      </svg>`;
  }

  // ── 7. Force-directed keyword network (replaces co-occurrence bubble) ─
  function renderNetwork(containerId, summary) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;

    const cooccurrence = summary.keyword_cooccurrence || [];
    if (cooccurrence.length === 0) { el.textContent = "No co-occurrence data."; return; }
    const keywords = summary.normalized_keywords || [];

    // Build node set and edge list
    const nodeSet = new Set();
    const top20 = cooccurrence.slice(0, 20);
    top20.forEach((item) => { nodeSet.add(item.keyword_a); nodeSet.add(item.keyword_b); });
    const nodes = [...nodeSet];
    const nodeIndex = {};
    nodes.forEach((n, i) => { nodeIndex[n] = i; });

    // Keyword study counts for node sizing
    const kwMap = {};
    keywords.forEach((kw) => { kwMap[kw.keyword] = kw.study_count || 1; });

    // Fruchterman-Reingold layout (100 iterations)
    const N = nodes.length;
    const pos = nodes.map((_, i) => {
      const angle = (2 * Math.PI * i) / Math.max(N, 1);
      return [150 * Math.cos(angle), 150 * Math.sin(angle)];
    });
    const area = 400 * 400;
    const k = Math.sqrt(area / Math.max(N, 1));

    for (let iter = 0; iter < 100; iter++) {
      const disp = pos.map(() => [0, 0]);
      const temp = 200 * (1 - iter / 100);

      // Repulsive forces
      for (let i = 0; i < N; i++) {
        for (let j = i + 1; j < N; j++) {
          let dx = pos[i][0] - pos[j][0];
          let dy = pos[i][1] - pos[j][1];
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.01);
          const force = (k * k) / dist;
          dx = (dx / dist) * force;
          dy = (dy / dist) * force;
          disp[i][0] += dx; disp[i][1] += dy;
          disp[j][0] -= dx; disp[j][1] -= dy;
        }
      }

      // Attractive forces
      top20.forEach((edge) => {
        const i = nodeIndex[edge.keyword_a];
        const j = nodeIndex[edge.keyword_b];
        if (i === undefined || j === undefined) return;
        let dx = pos[i][0] - pos[j][0];
        let dy = pos[i][1] - pos[j][1];
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 0.01);
        const force = (dist * dist) / k;
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        disp[i][0] -= dx; disp[i][1] -= dy;
        disp[j][0] += dx; disp[j][1] += dy;
      });

      // Apply with temperature
      for (let i = 0; i < N; i++) {
        const dl = Math.max(Math.sqrt(disp[i][0] ** 2 + disp[i][1] ** 2), 0.01);
        pos[i][0] += (disp[i][0] / dl) * Math.min(dl, temp);
        pos[i][1] += (disp[i][1] / dl) * Math.min(dl, temp);
      }
    }

    // Build edge traces
    const edgeX = [];
    const edgeY = [];
    top20.forEach((edge) => {
      const i = nodeIndex[edge.keyword_a];
      const j = nodeIndex[edge.keyword_b];
      if (i === undefined || j === undefined) return;
      edgeX.push(pos[i][0], pos[j][0], null);
      edgeY.push(pos[i][1], pos[j][1], null);
    });

    const maxSize = Math.max(...nodes.map((n) => kwMap[n] || 1), 1);
    const tc = getThemeColors();

    const data = [
      {
        x: edgeX, y: edgeY, mode: "lines", type: "scatter",
        line: { color: tc.muted, width: 1 },
        hoverinfo: "none", showlegend: false,
      },
      {
        x: nodes.map((_, i) => pos[i][0]),
        y: nodes.map((_, i) => pos[i][1]),
        mode: "markers+text", type: "scatter",
        text: nodes,
        textposition: "top center",
        textfont: { size: 10, color: tc.text },
        marker: {
          size: nodes.map((n) => 10 + ((kwMap[n] || 1) / maxSize) * 30),
          color: nodes.map((n) => kwMap[n] || 1),
          colorscale: [[0, COLORS.accent3], [1, COLORS.accent2]],
          showscale: true,
          colorbar: { title: "Studies", thickness: 12 },
        },
        hovertemplate: "<b>%{text}</b><br>Studies: %{marker.color}<extra></extra>",
        showlegend: false,
      },
    ];

    const layout = {
      ...defaultLayout("Keyword Co-occurrence Network"),
      xaxis: { visible: false },
      yaxis: { visible: false },
      margin: { t: 50, b: 10, l: 10, r: 10 },
    };

    safePlot(el, data, layout, defaultConfig).then(() => {
      addExportToolbar("network", containerId);
      el.on("plotly_click", (d) => {
        if (d.points && d.points[0] && d.points[0].text) {
          emitFilter("keyword", d.points[0].text);
        }
      });
    });
  }

  // ── 8. Evidence Bubble Matrix (NEW — flagship) ────────────────────
  function renderBubbleMatrix(containerId, rows, summary) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;
    if (!rows || rows.length === 0) { el.textContent = "No data."; return; }

    // Build keyword x outcome_type cross-tabulation
    const kwCounts = {};
    const otCounts = {};
    const pairData = {};

    rows.forEach((row) => {
      const kw = row.normalized_keyword || row.keyword || "";
      if (!kw || kw === "Unmapped") return;
      const ot = row.outcome_type || "unspecified";
      const nctId = row.nct_id || "";
      kwCounts[kw] = (kwCounts[kw] || 0) + 1;
      otCounts[ot] = (otCounts[ot] || 0) + 1;

      const key = `${kw}\0${ot}`;
      if (!pairData[key]) pairData[key] = { count: 0, studies: new Set(), placebo: new Set() };
      pairData[key].count++;
      if (nctId) {
        pairData[key].studies.add(nctId);
        if (row.has_placebo_arm === "True") pairData[key].placebo.add(nctId);
      }
    });

    const topKw = Object.entries(kwCounts).sort((a, b) => b[1] - a[1]).slice(0, 15).map((e) => e[0]);
    const topOt = Object.entries(otCounts).sort((a, b) => b[1] - a[1]).slice(0, 8).map((e) => e[0]);
    if (topKw.length === 0 || topOt.length === 0) { el.textContent = "Insufficient data."; return; }

    const x = [];
    const y = [];
    const sizes = [];
    const colors = [];
    const texts = [];
    let maxStudy = 1;

    topKw.forEach((kw) => {
      topOt.forEach((ot) => {
        const key = `${kw}\0${ot}`;
        const pd = pairData[key];
        if (pd && pd.studies.size > 0) {
          const studyCount = pd.studies.size;
          if (studyCount > maxStudy) maxStudy = studyCount;
        }
      });
    });

    topKw.forEach((kw) => {
      topOt.forEach((ot) => {
        const key = `${kw}\0${ot}`;
        const pd = pairData[key];
        if (!pd || pd.studies.size === 0) return;
        x.push(kw);
        y.push(ot);
        const studyCount = pd.studies.size;
        sizes.push(studyCount);
        const placeboRatio = pd.placebo.size / Math.max(studyCount, 1);
        colors.push(placeboRatio);
        texts.push(`${kw} x ${ot}<br>Studies: ${studyCount}<br>Placebo: ${Math.round(placeboRatio * 100)}%`);
      });
    });

    if (sizes.length === 0) { el.textContent = "No intersection data."; return; }

    const tc = getThemeColors();
    const data = [{
      x, y, mode: "markers", type: "scatter",
      marker: {
        size: sizes.map((s) => 8 + (s / maxStudy) * 52),
        color: colors, colorscale: RdYlGn,
        showscale: true, colorbar: { title: "Placebo %", thickness: 12 },
        line: { color: tc.muted, width: sizes.map((s) => s < 5 ? 2 : 1) },
        opacity: 0.85,
      },
      text: texts,
      hovertemplate: "%{text}<extra></extra>",
    }];

    const layout = {
      ...defaultLayout("Evidence Bubble Matrix"),
      xaxis: { tickangle: -45, automargin: true, tickfont: { size: 10 }, type: "category" },
      yaxis: { automargin: true, tickfont: { size: 11 }, type: "category" },
      margin: { t: 50, b: 120, l: 140, r: 20 },
    };

    safePlot(el, data, layout, defaultConfig).then(() => {
      addExportToolbar("bubbleMatrix", containerId);
      el.on("plotly_click", (d) => {
        if (d.points && d.points[0]) emitFilter("keyword", d.points[0].x);
      });
    });
  }

  // ── 9. Interactive Forest Plot (NEW) ──────────────────────────────
  function renderForestPlot(containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;
    if (!rows || rows.length === 0) { el.textContent = "No data."; return; }

    // Aggregate per keyword: study count, placebo %, I² proxy
    const kwData = {};
    rows.forEach((row) => {
      const kw = row.normalized_keyword || row.keyword || "";
      if (!kw || kw === "Unmapped") return;
      const nctId = row.nct_id || "";
      if (!kwData[kw]) kwData[kw] = { studies: new Set(), placebo: new Set(), mentions: 0 };
      kwData[kw].mentions++;
      if (nctId) {
        kwData[kw].studies.add(nctId);
        if (row.has_placebo_arm === "True") kwData[kw].placebo.add(nctId);
      }
    });

    const sorted = Object.entries(kwData)
      .map(([kw, d]) => ({
        keyword: kw,
        studyCount: d.studies.size,
        placeboCount: d.placebo.size,
        mentions: d.mentions,
        // I² proxy: mentions/studies ratio — higher ratio = more heterogeneous measurement
        heterogeneity: d.studies.size > 0 ? d.mentions / d.studies.size : 0,
      }))
      .filter((d) => d.studyCount >= 2)
      .sort((a, b) => b.studyCount - a.studyCount)
      .slice(0, 20);

    if (sorted.length === 0) { el.textContent = "Insufficient data for forest plot."; return; }

    const tc = getThemeColors();
    const keywords = sorted.map((d) => d.keyword);
    const studyCounts = sorted.map((d) => d.studyCount);
    const maxCount = Math.max(...studyCounts, 1);

    // I² color: green < 25%, yellow 25-75%, red > 75% (normalized as mentions/study ratio)
    const maxHet = Math.max(...sorted.map((d) => d.heterogeneity), 1);
    const barColors = sorted.map((d) => {
      const ratio = d.heterogeneity / maxHet;
      if (ratio < 0.33) return "#388e3c";
      if (ratio < 0.67) return "#f57c00";
      return "#d32f2f";
    });

    const data = [{
      type: "bar",
      y: keywords,
      x: studyCounts,
      orientation: "h",
      marker: { color: barColors, line: { color: tc.muted, width: 1 } },
      text: sorted.map((d) => `${d.studyCount} studies (${d.placeboCount} placebo, ${d.mentions} mentions)`),
      hovertemplate: "<b>%{y}</b><br>%{text}<extra></extra>",
    }];

    // Add vertical line at median (spread to avoid mutating bar-data array)
    const median = [...studyCounts].sort((a, b) => a - b)[Math.floor(studyCounts.length / 2)];

    const layout = {
      ...defaultLayout("Keyword Evidence Forest"),
      xaxis: { title: "Number of studies", gridcolor: tc.gridColor },
      yaxis: { automargin: true, tickfont: { size: 11 }, autorange: "reversed" },
      margin: { t: 50, b: 50, l: 180, r: 20 },
      shapes: [{
        type: "line", x0: median, x1: median, y0: -0.5, y1: sorted.length - 0.5,
        line: { color: tc.muted, width: 1, dash: "dash" },
      }],
      annotations: [{
        x: median, y: sorted.length - 0.5, text: `Median: ${median}`,
        showarrow: false, font: { size: 10, color: tc.muted }, yshift: 15,
      }],
    };

    safePlot(el, data, layout, defaultConfig).then(() => {
      addExportToolbar("forestPlot", containerId);
      el.on("plotly_click", (d) => {
        if (d.points && d.points[0]) emitFilter("keyword", d.points[0].y);
      });
    });
  }

  // ── 10. Sankey Flow Diagram (NEW) ─────────────────────────────────
  function renderSankey(containerId, rows) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;
    if (!rows || rows.length === 0) { el.textContent = "No data."; return; }

    // Source → Phase → Keyword flow (single pass, proper dedup)
    const phaseMap = {};
    const kwMap = {};
    const sourcePhase = {};
    const phaseKw = {};
    const seen = {};

    let anonIdx = 0;
    rows.forEach((row) => {
      anonIdx++;
      const nctId = row.nct_id || "";
      const phase = (row.phase || "Not Stated").replace(/PHASE/gi, "Phase").replace(/NA/i, "Not Stated");
      const kw = row.normalized_keyword || row.keyword || "";
      if (!kw || kw === "Unmapped") return;

      // Source → Phase: count unique studies per phase
      if (nctId && !seen[`sp\0${nctId}`]) {
        seen[`sp\0${nctId}`] = true;
        phaseMap[phase] = (phaseMap[phase] || 0) + 1;
        const spKey = `ClinicalTrials.gov→${phase}`;
        sourcePhase[spKey] = (sourcePhase[spKey] || 0) + 1;
      }

      // Keyword count: unique study-keyword pairs (deterministic fallback for missing NCT IDs)
      const kwKey = `kw\0${nctId || `_r${anonIdx}`}\0${kw}`;
      if (!seen[kwKey]) {
        seen[kwKey] = true;
        kwMap[kw] = (kwMap[kw] || 0) + 1;
      }

      // Phase → Keyword: unique study per phase-keyword pair
      const pkKey = `pk\0${nctId || `_r${anonIdx}`}\0${phase}\0${kw}`;
      if (!seen[pkKey]) {
        seen[pkKey] = true;
        const pkLinkKey = `${phase}→${kw}`;
        phaseKw[pkLinkKey] = (phaseKw[pkLinkKey] || 0) + 1;
      }
    });

    // Build nodes
    const topKw = Object.entries(kwMap).sort((a, b) => b[1] - a[1]).slice(0, 10).map((e) => e[0]);
    const phases = Object.keys(phaseMap);
    const nodeLabels = ["ClinicalTrials.gov", ...phases, ...topKw];
    const nodeIdx = {};
    nodeLabels.forEach((n, i) => { nodeIdx[n] = i; });

    const source = [];
    const target = [];
    const value = [];

    // Source → phase links
    Object.entries(sourcePhase).forEach(([key, count]) => {
      const [src, tgt] = key.split("→");
      if (nodeIdx[src] !== undefined && nodeIdx[tgt] !== undefined) {
        source.push(nodeIdx[src]); target.push(nodeIdx[tgt]); value.push(count);
      }
    });

    // Phase → keyword links
    Object.entries(phaseKw).forEach(([key, count]) => {
      const [src, tgt] = key.split("→");
      if (nodeIdx[src] !== undefined && nodeIdx[tgt] !== undefined) {
        source.push(nodeIdx[src]); target.push(nodeIdx[tgt]); value.push(count);
      }
    });

    if (source.length === 0) { el.textContent = "Insufficient data for Sankey."; return; }

    const tc = getThemeColors();
    const nodeColors = nodeLabels.map((_, i) => CATEGORY[i % CATEGORY.length]);

    const data = [{
      type: "sankey",
      orientation: "h",
      node: {
        pad: 15, thickness: 20, line: { color: tc.muted, width: 0.5 },
        label: nodeLabels, color: nodeColors,
      },
      link: {
        source, target, value,
        color: source.map((s) => `${CATEGORY[s % CATEGORY.length]}40`),
      },
    }];

    const layout = {
      ...defaultLayout("Evidence Pipeline Flow"),
      margin: { t: 50, b: 10, l: 10, r: 10 },
    };

    safePlot(el, data, layout, defaultConfig).then(() => addExportToolbar("sankey", containerId));
  }

  // ── 11. Radar/Spider Chart (NEW) ──────────────────────────────────
  function renderRadar(containerId, summary, rows) {
    const el = document.getElementById(containerId);
    if (!el || typeof Plotly === "undefined") return;

    const keywords = (summary.normalized_keywords || []).slice(0, 5);
    if (keywords.length === 0) { el.textContent = "No data for radar."; return; }

    const maxStudy = Math.max(...keywords.map((k) => k.study_count || 1), 1);
    const maxMention = Math.max(...keywords.map((k) => k.mention_count || 1), 1);

    // Compute recency: % of studies from last 5 years
    const currentYear = new Date().getFullYear();
    const kwRecency = {};
    const kwSampleSizes = {};
    if (rows) {
      const seenByKw = {};
      rows.forEach((row) => {
        const kw = row.normalized_keyword || "";
        const nctId = row.nct_id || "";
        if (!kw || !nctId) return;
        const key = `${kw}\0${nctId}`;
        if (seenByKw[key]) return;
        seenByKw[key] = true;
        if (!kwRecency[kw]) kwRecency[kw] = { recent: 0, total: 0 };
        kwRecency[kw].total++;
        const year = parseInt((row.start_date || "").slice(0, 4), 10);
        if (year && year >= currentYear - 5) kwRecency[kw].recent++;
      });
    }

    const axes = ["Study Count", "Mention Density", "Placebo %", "Recency (5yr)", "Outcome Diversity"];
    const tc = getThemeColors();
    const traces = keywords.map((kw, i) => {
      const studyNorm = (kw.study_count || 0) / maxStudy;
      const mentionNorm = (kw.mention_count || 0) / maxMention;
      const placeboNorm = kw.study_count > 0 ? (kw.placebo_study_count || 0) / kw.study_count : 0;
      const rec = kwRecency[kw.keyword] || { recent: 0, total: 1 };
      const recencyNorm = rec.total > 0 ? rec.recent / rec.total : 0;
      const diversityNorm = mentionNorm > 0 ? Math.min(1, studyNorm / mentionNorm) : 0;

      return {
        type: "scatterpolar",
        r: [studyNorm, mentionNorm, placeboNorm, recencyNorm, diversityNorm, studyNorm],
        theta: [...axes, axes[0]],
        fill: "toself",
        fillcolor: `${CATEGORY[i]}20`,
        line: { color: CATEGORY[i], width: 2 },
        name: kw.keyword,
      };
    });

    const layout = {
      ...defaultLayout("Keyword Evidence Profiles (Top 5)"),
      polar: {
        radialaxis: { visible: true, range: [0, 1], tickfont: { size: 9 }, gridcolor: tc.gridColor },
        angularaxis: { tickfont: { size: 10 } },
        bgcolor: tc.plot,
      },
      legend: { x: 0, y: -0.2, orientation: "h", font: { size: 10 } },
      margin: { t: 60, b: 60, l: 60, r: 60 },
    };

    safePlot(el, traces, layout, defaultConfig).then(() => addExportToolbar("radar", containerId));
  }

  // ── Public API ────────────────────────────────────────────────────
  return {
    renderTreemap,
    renderHeatmap,
    renderTimeSeries,
    renderChoropleth,
    renderSunburst,
    renderPrismaFlow,
    renderNetwork,
    renderBubbleMatrix,
    renderForestPlot,
    renderSankey,
    renderRadar,
    // Expose for theme change re-render
    addExportToolbar,
  };
})();
