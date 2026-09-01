const $ = (selector) => document.querySelector(selector);

const state = {
  query: "",
  hours: 24,
  freshness: "posted",
  category: "",
  jobState: "",
  remote: false,
  minFit: 0,
  minSalary: "",
  sort: "newest",
  limit: 20,
  offset: 0,
  total: 0,
  jobs: new Map(),
};

const elements = {
  search: $("#search-input"),
  hours: $("#hours-filter"),
  freshness: $("#freshness-filter"),
  category: $("#category-filter"),
  state: $("#state-filter"),
  remote: $("#remote-filter"),
  fit: $("#fit-filter"),
  fitOutput: $("#fit-output"),
  salary: $("#salary-filter"),
  sort: $("#sort-filter"),
  list: $("#jobs-list"),
  empty: $("#empty-state"),
  summary: $("#result-summary"),
  activeFilters: $("#active-filters"),
  pagination: $("#pagination"),
  previous: $("#previous-page"),
  next: $("#next-page"),
  pageLabel: $("#page-label"),
  drawer: $("#job-drawer"),
  drawerBackdrop: $("#drawer-backdrop"),
  drawerContent: $("#drawer-content"),
  toast: $("#toast"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.origin);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    return escapeHtml(parsed.href);
  } catch (_) {
    return null;
  }
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value || 0);
}

function relativeTime(value) {
  if (!value) return "Unknown";
  const then = new Date(value);
  const seconds = Math.max(0, Math.floor((Date.now() - then.getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  const days = Math.floor(seconds / 86400);
  return `${days}d ago`;
}

function formatDate(value) {
  if (!value) return "Not supplied";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function salaryLabel(job) {
  if (job.salary_min == null && job.salary_max == null) return "Salary not listed";
  const compact = (value) => {
    if (job.salary_period === "hour") return `$${Math.round(value)}`;
    if (value >= 1000) return `$${Math.round(value / 1000)}k`;
    return `$${Math.round(value)}`;
  };
  const low = job.salary_min ?? job.salary_max;
  const high = job.salary_max ?? job.salary_min;
  const range = low === high ? compact(low) : `${compact(low)}–${compact(high)}`;
  return `${range}/${job.salary_period === "hour" ? "hr" : "yr"}`;
}

function initials(company) {
  return String(company || "?")
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function freshnessLabel(job) {
  if (job.posted_at) {
    return `<span class="freshness verified">Posted ${relativeTime(job.posted_at)}</span>`;
  }
  return `<span class="freshness discovered">First seen ${relativeTime(job.first_seen_at)}</span>`;
}

function renderJob(job) {
  const tags = [
    job.remote ? '<span class="tag remote">Remote</span>' : "",
    job.category ? `<span class="tag">${escapeHtml(job.category)}</span>` : "",
    job.employment_type ? `<span class="tag">${escapeHtml(job.employment_type)}</span>` : "",
    ...(job.skills || []).slice(0, 4).map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`),
  ].join("");
  const sourceCount = job.sources?.length || 1;
  return `
    <article class="job-card" tabindex="0" data-job-id="${escapeHtml(job.id)}">
      <div class="job-topline">
        <div>
          <div class="company-row">
            <span class="company-avatar">${escapeHtml(initials(job.company))}</span>
            ${escapeHtml(job.company)}
          </div>
          <h3>${escapeHtml(job.title)}</h3>
          <p class="job-location">${escapeHtml(job.location || "Location not supplied")}</p>
        </div>
        <span class="fit-score">${job.fit_score}</span>
      </div>
      <p class="job-description">${escapeHtml(job.description || "No description was supplied by this source.")}</p>
      <div class="tag-row">${tags}</div>
      <div class="job-footer">
        <div class="provenance">
          <span>via</span>
          <strong>${escapeHtml(job.ats || job.primary_provider)}</strong>
          ${sourceCount > 1 ? `<span class="source-count">${sourceCount} sources</span>` : ""}
        </div>
        <div class="job-meta">
          <span class="salary">${escapeHtml(salaryLabel(job))}</span>
          <span>•</span>
          ${freshnessLabel(job)}
        </div>
      </div>
    </article>`;
}

function queryParams() {
  const params = new URLSearchParams({
    hours: state.hours,
    freshness: state.freshness,
    sort: state.sort,
    limit: state.limit,
    offset: state.offset,
  });
  if (state.query) params.set("q", state.query);
  if (state.category) params.set("category", state.category);
  if (state.jobState) params.set("state", state.jobState);
  if (state.remote) params.set("remote", "true");
  if (state.minFit) params.set("min_fit", state.minFit);
  if (state.minSalary) params.set("min_salary", state.minSalary);
  return params;
}

async function loadJobs() {
  elements.list.innerHTML = [1, 2, 3].map(() => '<article class="job-card skeleton-card"></article>').join("");
  elements.empty.hidden = true;
  try {
    const response = await fetch(`/api/jobs?${queryParams()}`);
    if (!response.ok) throw new Error(`Jobs API returned ${response.status}`);
    const data = await response.json();
    state.total = data.total;
    state.jobs.clear();
    data.items.forEach((job) => state.jobs.set(job.id, job));
    elements.list.innerHTML = data.items.map(renderJob).join("");
    elements.list.hidden = data.items.length === 0;
    elements.empty.hidden = data.items.length !== 0;
    const noun = data.total === 1 ? "job" : "jobs";
    elements.summary.textContent = `${formatNumber(data.total)} ${noun} across the U.S. market`;
    renderPagination();
    renderActiveFilters();
  } catch (error) {
    elements.list.innerHTML = "";
    elements.empty.hidden = false;
    elements.empty.querySelector("h3").textContent = "Could not load jobs";
    elements.empty.querySelector("p").textContent = error.message;
    showToast("The job feed could not be loaded.");
  }
}

function renderPagination() {
  const totalPages = Math.max(1, Math.ceil(state.total / state.limit));
  const currentPage = Math.floor(state.offset / state.limit) + 1;
  elements.pagination.hidden = state.total <= state.limit;
  elements.pageLabel.textContent = `Page ${currentPage} of ${totalPages}`;
  elements.previous.disabled = currentPage <= 1;
  elements.next.disabled = currentPage >= totalPages;
}

function renderActiveFilters() {
  const labels = [];
  if (state.query) labels.push(`Search: ${state.query}`);
  if (state.category) labels.push(state.category);
  if (state.jobState) labels.push(state.jobState);
  if (state.remote) labels.push("Remote");
  if (state.minFit) labels.push(`Fit ${state.minFit}+`);
  if (state.minSalary) labels.push(`Salary $${Number(state.minSalary) / 1000}k+`);
  elements.activeFilters.innerHTML = labels
    .map((label) => `<span class="filter-chip">${escapeHtml(label)}</span>`)
    .join("");
}

async function loadStats() {
  try {
    const response = await fetch("/api/stats?hours=24");
    if (!response.ok) throw new Error("stats unavailable");
    const data = await response.json();
    $("#stat-fresh").textContent = formatNumber(data.fresh_jobs);
    $("#stat-companies").textContent = formatNumber(data.companies);
    $("#stat-remote").textContent = formatNumber(data.remote_jobs);
    $("#stat-fit").textContent = formatNumber(data.high_fit_jobs);
  } catch (_) {
    ["#stat-fresh", "#stat-companies", "#stat-remote", "#stat-fit"].forEach((id) => {
      $(id).textContent = "0";
    });
  }
}

async function loadSources() {
  try {
    const response = await fetch("/api/sources");
    if (!response.ok) throw new Error("sources unavailable");
    const data = await response.json();
    const active = data.items.filter((source) => source.configured);
    $("#source-count").textContent = `${active.length} active`;
    $("#source-list").innerHTML = active.length
      ? active.map((source) => `<span class="source-badge">${escapeHtml(source.provider)}</span>`).join("")
      : '<span class="source-badge">Setup required</span>';
    const completed = active.filter((source) => source.last_run?.status === "completed");
    const status = $("#live-status");
    status.querySelector(".status-dot").classList.toggle("online", active.length > 0);
    status.querySelector("span:last-child").textContent = active.length
      ? `${active.length} sources · ${completed.length} synced`
      : "No source configured";
  } catch (_) {
    $("#source-count").textContent = "Offline";
  }
}

function detailItem(label, value) {
  return `<div class="detail-item"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value || "Not supplied")}</strong></div>`;
}

function openDrawer(job) {
  if (!job) return;
  const applyUrl = safeUrl(job.apply_url);
  const originalUrl = safeUrl(job.original_url);
  const sources = (job.sources || [])
    .map(
      (source) => `
        <div class="source-record">
          <strong>${escapeHtml(source.provider)}${source.ats ? ` · ${escapeHtml(source.ats)}` : ""}</strong>
          <span>${source.is_active ? "Active" : "Closed"}</span>
          <small>Posted: ${escapeHtml(formatDate(source.posted_at))} · Discovered: ${escapeHtml(formatDate(source.discovered_at))}</small>
        </div>`,
    )
    .join("");
  const tags = (job.skills || []).map((skill) => `<span class="tag">${escapeHtml(skill)}</span>`).join("");
  const experience = job.experience_min == null
    ? "Not detected"
    : `${job.experience_min}${job.experience_max !== job.experience_min ? `–${job.experience_max}` : "+"} years`;
  elements.drawerContent.innerHTML = `
    <div class="drawer-company">${escapeHtml(job.company)}</div>
    <h2 class="drawer-title">${escapeHtml(job.title)}</h2>
    <p class="drawer-subtitle">${escapeHtml(job.location || "Location not supplied")} · ${escapeHtml(job.category)}</p>
    <div class="drawer-actions">
      ${applyUrl ? `<a class="button button-primary" href="${applyUrl}" target="_blank" rel="noopener noreferrer">Apply on source ↗</a>` : ""}
      ${originalUrl && originalUrl !== applyUrl ? `<a class="button button-secondary" href="${originalUrl}" target="_blank" rel="noopener noreferrer">Original post</a>` : ""}
    </div>
    <section class="drawer-section">
      <div class="detail-grid">
        ${detailItem("Fit score", `${job.fit_score}/100`)}
        ${detailItem("Compensation", salaryLabel(job))}
        ${detailItem("Freshness", job.posted_at ? `Posted ${relativeTime(job.posted_at)}` : `First seen ${relativeTime(job.first_seen_at)}`)}
        ${detailItem("Experience", experience)}
        ${detailItem("Workplace", job.workplace_type || (job.remote ? "Remote" : "Not supplied"))}
        ${detailItem("Visa signal", job.visa_signal.replaceAll("_", " "))}
      </div>
    </section>
    ${tags ? `<section class="drawer-section"><h3>Detected skills</h3><div class="tag-row">${tags}</div></section>` : ""}
    <section class="drawer-section">
      <h3>Job description</h3>
      <div class="drawer-description">${escapeHtml(job.description || "No description was supplied by this source.")}</div>
    </section>
    <section class="drawer-section">
      <h3>Source provenance</h3>
      ${sources || "No source records available."}
    </section>`;
  elements.drawerBackdrop.hidden = false;
  elements.drawer.setAttribute("aria-hidden", "false");
  requestAnimationFrame(() => elements.drawer.classList.add("open"));
  document.body.style.overflow = "hidden";
}

function closeDrawer() {
  elements.drawer.classList.remove("open");
  elements.drawer.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
  setTimeout(() => {
    elements.drawerBackdrop.hidden = true;
  }, 240);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => elements.toast.classList.remove("show"), 3500);
}

function resetFilters() {
  state.query = "";
  state.hours = 24;
  state.freshness = "posted";
  state.category = "";
  state.jobState = "";
  state.remote = false;
  state.minFit = 0;
  state.minSalary = "";
  state.sort = "newest";
  state.offset = 0;
  elements.search.value = "";
  elements.hours.value = "24";
  elements.freshness.value = "posted";
  elements.category.value = "";
  elements.state.value = "";
  elements.remote.checked = false;
  elements.fit.value = "0";
  elements.fitOutput.value = "0";
  elements.salary.value = "";
  elements.sort.value = "newest";
  loadJobs();
}

async function triggerSync() {
  const headers = {};
  const key = window.prompt("Admin key (leave blank if local development has no key):");
  if (key === null) return;
  if (key) headers["X-Admin-Key"] = key;
  try {
    const response = await fetch("/api/sync", { method: "POST", headers });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Sync request failed");
    showToast("Sync accepted. New jobs will appear shortly.");
    setTimeout(loadSources, 2500);
  } catch (error) {
    showToast(error.message);
  }
}

function debounce(callback, delay = 300) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => callback(...args), delay);
  };
}

elements.search.addEventListener(
  "input",
  debounce(() => {
    state.query = elements.search.value.trim();
    state.offset = 0;
    loadJobs();
  }),
);

[
  [elements.hours, "hours", Number],
  [elements.freshness, "freshness", String],
  [elements.category, "category", String],
  [elements.salary, "minSalary", String],
  [elements.sort, "sort", String],
].forEach(([element, key, transform]) => {
  element.addEventListener("change", () => {
    state[key] = transform(element.value);
    state.offset = 0;
    loadJobs();
  });
});

elements.state.addEventListener(
  "input",
  debounce(() => {
    state.jobState = elements.state.value.trim().toUpperCase();
    state.offset = 0;
    loadJobs();
  }),
);

elements.remote.addEventListener("change", () => {
  state.remote = elements.remote.checked;
  state.offset = 0;
  loadJobs();
});

elements.fit.addEventListener("input", () => {
  elements.fitOutput.value = elements.fit.value;
});

elements.fit.addEventListener(
  "change",
  () => {
    state.minFit = Number(elements.fit.value);
    state.offset = 0;
    loadJobs();
  },
);

elements.list.addEventListener("click", (event) => {
  const card = event.target.closest("[data-job-id]");
  if (card) openDrawer(state.jobs.get(card.dataset.jobId));
});

elements.list.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    const card = event.target.closest("[data-job-id]");
    if (card) {
      event.preventDefault();
      openDrawer(state.jobs.get(card.dataset.jobId));
    }
  }
});

elements.previous.addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  loadJobs();
  elements.list.scrollIntoView({ behavior: "smooth", block: "start" });
});

elements.next.addEventListener("click", () => {
  state.offset += state.limit;
  loadJobs();
  elements.list.scrollIntoView({ behavior: "smooth", block: "start" });
});

$("#clear-filters").addEventListener("click", resetFilters);
$("#empty-clear").addEventListener("click", resetFilters);
$("#drawer-close").addEventListener("click", closeDrawer);
elements.drawerBackdrop.addEventListener("click", closeDrawer);
$("#sync-button").addEventListener("click", triggerSync);

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    elements.search.focus();
  }
  if (event.key === "Escape") closeDrawer();
});

Promise.all([loadJobs(), loadStats(), loadSources()]);
