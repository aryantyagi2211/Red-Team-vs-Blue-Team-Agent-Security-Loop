const elements = {
  runSelect: document.querySelector("#run-select"),
  startForm: document.querySelector("#start-form"),
  startButton: document.querySelector("#start-button"),
  notice: document.querySelector("#notice"),
  recordedBanner: document.querySelector("#recorded-banner"),
  baselineHoldout: document.querySelector("#baseline-holdout"),
  finalHoldout: document.querySelector("#final-holdout"),
  holdoutChange: document.querySelector("#holdout-change"),
  targetName: document.querySelector("#target-name"),
  runStatus: document.querySelector("#run-status"),
  runProgress: document.querySelector("#run-progress"),
  runId: document.querySelector("#run-id-label"),
  roundEmpty: document.querySelector("#round-empty"),
  categoryEmpty: document.querySelector("#category-empty"),
  diffList: document.querySelector("#diff-list"),
};

const categoryNames = {
  prompt_leak: "Prompt leak",
  instruction_override: "Instruction override",
  indirect_injection: "Indirect injection",
  data_exfiltration: "Data exfiltration",
};
let roundChart;
let categoryChart;
let pollTimer;

function showNotice(message, isError = false) {
  elements.notice.textContent = message;
  elements.notice.classList.toggle("error", isError);
  elements.notice.hidden = !message;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return body;
}

function formatPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function friendlyTarget(target) {
  return target === "calendar_assistant"
    ? "Calendar assistant"
    : target === "memo_assistant"
      ? "Memo assistant"
      : target;
}

function setRunStatus(status, progress) {
  const labels = {
    running: "RUNNING",
    ok: "COMPLETE",
    done: "COMPLETE",
    error: "ERROR",
    cancelled: "CANCELLED",
  };
  elements.runStatus.textContent = labels[status] || String(status).toUpperCase();
  const current = progress?.round;
  const step = progress?.step?.replaceAll("_", " ");
  elements.runProgress.textContent = current === undefined
    ? (status === "running" ? "Starting evaluation…" : "Recorded evaluation")
    : `Round ${current}${step ? ` · ${step}` : ""}`;
}

function destroyCharts() {
  roundChart?.destroy();
  categoryChart?.destroy();
  roundChart = undefined;
  categoryChart = undefined;
}

function drawCharts(rounds) {
  destroyCharts();
  elements.roundEmpty.hidden = rounds.length > 0;
  elements.categoryEmpty.hidden = rounds.length > 0;
  if (!rounds.length) {
    return;
  }
  if (typeof Chart === "undefined") {
    elements.roundEmpty.hidden = false;
    elements.categoryEmpty.hidden = false;
    elements.roundEmpty.textContent = "The local chart library is unavailable.";
    elements.categoryEmpty.textContent = "The local chart library is unavailable.";
    showNotice("Charts could not load. Check that the vendored dashboard assets are available.", true);
    return;
  }

  const axis = {
    min: 0,
    max: 1,
    ticks: { color: "#aab8c5", callback: (value) => `${Math.round(value * 100)}%` },
    grid: { color: "rgba(170, 184, 197, .13)" },
  };
  roundChart = new Chart(document.querySelector("#round-chart"), {
    type: "line",
    data: {
      labels: rounds.map((round) => `Round ${round.round}`),
      datasets: [
        {
          label: "Train ASR",
          data: rounds.map((round) => round.train_asr),
          borderColor: "#65a8ff",
          backgroundColor: "#65a8ff",
          tension: 0.25,
        },
        {
          label: "Holdout ASR",
          data: rounds.map((round) => round.holdout_asr),
          borderColor: "#ff7e83",
          backgroundColor: "#ff7e83",
          tension: 0.25,
        },
        {
          label: "Utility pass rate",
          data: rounds.map((round) => round.utility_pass_rate),
          borderColor: "#45d5c3",
          backgroundColor: "#45d5c3",
          borderDash: [6, 4],
          tension: 0.25,
        },
      ],
    },
    options: {
      maintainAspectRatio: false,
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#dce6ee", usePointStyle: true, padding: 20 } },
        tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatPercent(context.parsed.y)}` } },
      },
      scales: { y: { ...axis, title: { display: true, text: "Rate", color: "#aab8c5" } }, x: { ticks: { color: "#aab8c5" }, grid: { display: false } } },
    },
  });

  const baseline = rounds[0].holdout_asr_by_category || {};
  const final = rounds[rounds.length - 1].holdout_asr_by_category || {};
  const categories = [...new Set([...Object.keys(baseline), ...Object.keys(final)])].sort();
  if (!categories.length) {
    elements.categoryEmpty.hidden = false;
    elements.categoryEmpty.textContent = "Category metrics are not available for this run yet.";
    return;
  }
  categoryChart = new Chart(document.querySelector("#category-chart"), {
    type: "bar",
    data: {
      labels: categories.map((category) => categoryNames[category] || category),
      datasets: [
        { label: "Baseline holdout", data: categories.map((category) => baseline[category] ?? 0), backgroundColor: "#ff7e83", borderRadius: 4 },
        { label: "Final holdout", data: categories.map((category) => final[category] ?? 0), backgroundColor: "#45d5c3", borderRadius: 4 },
      ],
    },
    options: {
      indexAxis: "y",
      maintainAspectRatio: false,
      responsive: true,
      plugins: {
        legend: { labels: { color: "#dce6ee", usePointStyle: true, padding: 15 } },
        tooltip: { callbacks: { label: (context) => `${context.dataset.label}: ${formatPercent(context.parsed.x)}` } },
      },
      scales: { x: { ...axis }, y: { ticks: { color: "#dce6ee" }, grid: { display: false } } },
    },
  });
}

function renderHeadline(data) {
  const rounds = data.rounds;
  if (!rounds.length) {
    elements.baselineHoldout.textContent = "—";
    elements.finalHoldout.textContent = "—";
    elements.holdoutChange.textContent = "Holdout metrics are not available yet.";
    return;
  }
  const baseline = rounds[0].holdout_asr;
  const final = rounds[rounds.length - 1].holdout_asr;
  elements.baselineHoldout.textContent = formatPercent(baseline);
  elements.finalHoldout.textContent = formatPercent(final);
  const delta = Math.round((baseline - final) * 100);
  elements.holdoutChange.textContent = delta > 0
    ? `${delta} percentage-point reduction from baseline`
    : delta < 0
      ? `${Math.abs(delta)} percentage-point increase from baseline`
      : "No change in holdout ASR from baseline";
}

function renderDiffs(diffs) {
  elements.diffList.replaceChildren();
  if (!diffs.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No prompt patch was recorded for this run.";
    elements.diffList.append(empty);
    return;
  }
  for (const diff of diffs) {
    const details = document.createElement("details");
    details.className = "diff-item";
    const summary = document.createElement("summary");
    summary.textContent = diff.name;
    const pre = document.createElement("pre");
    for (const line of diff.text.split("\n")) {
      const span = document.createElement("span");
      span.textContent = `${line}\n`;
      if (line.startsWith("+") && !line.startsWith("+++")) span.className = "added";
      if (line.startsWith("-") && !line.startsWith("---")) span.className = "removed";
      pre.append(span);
    }
    details.append(summary, pre);
    elements.diffList.append(details);
  }
}

async function refreshRun(runId) {
  const data = await requestJson(`/dashboard/runs/${encodeURIComponent(runId)}`);
  elements.recordedBanner.hidden = !data.recorded;
  elements.targetName.textContent = friendlyTarget(data.target);
  elements.runId.textContent = data.recorded ? "recorded sample" : data.run_id;
  setRunStatus(data.status, data.progress);
  renderHeadline(data);
  drawCharts(data.rounds);
  const { diffs } = await requestJson(`/dashboard/runs/${encodeURIComponent(runId)}/diffs`);
  renderDiffs(diffs);
  return data;
}

async function loadRuns(preferredRunId) {
  const { runs } = await requestJson("/dashboard/runs");
  const previous = preferredRunId || elements.runSelect.value;
  elements.runSelect.replaceChildren();
  for (const run of runs) {
    const option = document.createElement("option");
    option.value = run.run_id;
    const statusLabel = { ok: "COMPLETE", done: "COMPLETE", running: "RUNNING", error: "ERROR", cancelled: "CANCELLED" };
    const kind = run.recorded ? "RECORDED" : statusLabel[run.status] || run.status.toUpperCase();
    option.textContent = `${kind} · ${friendlyTarget(run.target)} · ${run.run_id}`;
    elements.runSelect.append(option);
  }
  const selected = runs.find((run) => run.run_id === previous) || runs[0];
  if (selected) {
    elements.runSelect.value = selected.run_id;
    const data = await refreshRun(selected.run_id);
    if (data.status === "running") startPolling(selected.run_id);
  }
}

function startPolling(runId) {
  window.clearTimeout(pollTimer);
  pollTimer = window.setTimeout(async () => {
    try {
      const data = await refreshRun(runId);
      if (data.status === "running") startPolling(runId);
      else await loadRuns(runId);
    } catch (error) {
      showNotice(error.message, true);
    }
  }, 1500);
}

elements.runSelect.addEventListener("change", async () => {
  window.clearTimeout(pollTimer);
  try {
    const data = await refreshRun(elements.runSelect.value);
    if (data.status === "running") startPolling(data.run_id);
    showNotice("");
  } catch (error) {
    showNotice(error.message, true);
  }
});

elements.startForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.startButton.disabled = true;
  showNotice("Starting a local sandbox evaluation…");
  try {
    const formData = new FormData(elements.startForm);
    const body = {
      target: formData.get("target"),
      rounds: Number(formData.get("rounds")),
    };
    const result = await requestJson("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    await loadRuns(result.run_id);
    showNotice(`Run ${result.run_id} started. Results update as rounds finish.`);
    startPolling(result.run_id);
  } catch (error) {
    showNotice(error.message, true);
  } finally {
    elements.startButton.disabled = false;
  }
});

loadRuns().catch((error) => {
  showNotice(`Could not load saved runs: ${error.message}`, true);
  elements.targetName.textContent = "Dashboard data unavailable";
  elements.runStatus.textContent = "ERROR";
  elements.roundEmpty.hidden = false;
  elements.categoryEmpty.hidden = false;
  elements.roundEmpty.textContent = "Dashboard run data could not be loaded.";
  elements.categoryEmpty.textContent = "Dashboard run data could not be loaded.";
});
