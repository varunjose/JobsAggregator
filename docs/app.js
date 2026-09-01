const $ = (id) => document.getElementById(id);

function hoursAgo(iso) {
  if (!iso) return "unknown posted date";
  const t = new Date(iso);
  const h = Math.max(0, (Date.now() - t.getTime()) / 36e5);
  if (h < 1) return `${Math.round(h * 60)}m ago`;
  if (h < 24) return `${Math.round(h)}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function salary(job) {
  if (!job.salary_min && !job.salary_max) return "";
  const fmt = (n) => n ? `$${Math.round(n / 1000)}k` : "";
  if (job.salary_min && job.salary_max) return `${fmt(job.salary_min)}–${fmt(job.salary_max)}`;
  return fmt(job.salary_min || job.salary_max);
}

function render(jobs, meta) {
  const q = $("q").value.trim().toLowerCase();
  const ats = $("ats").value;
  const remote = $("remote").checked;
  const minScore = Number($("minscore").value);
  $("minscore-val").textContent = String(minScore);

  const shown = jobs.filter((j) => {
    if (ats && j.ats !== ats) return false;
    if (remote && !j.remote) return false;
    if ((j.score || 0) < minScore) return false;
    if (!q) return true;
    const blob = `${j.title} ${j.company} ${j.location} ${j.description}`.toLowerCase();
    return blob.includes(q);
  });

  $("stat-jobs").textContent = String(shown.length);
  $("stat-run").textContent = meta.finished_at
    ? new Date(meta.finished_at).toLocaleString()
    : "not run yet";
  $("stat-window").textContent = `${meta.posted_within_hours || 24}h`;
  const mix = meta.ats_breakdown || {};
  $("mix").textContent = Object.keys(mix).length
    ? "ATS mix: " + Object.entries(mix).map(([k, v]) => `${k} ${v}`).join(" · ")
    : "";

  const list = $("list");
  list.innerHTML = "";
  $("empty").hidden = shown.length > 0;
  for (const job of shown) {
    const el = document.createElement("article");
    el.className = "card";
    const pay = salary(job);
    el.innerHTML = `
      <div class="card-top">
        <h2>${escapeHtml(job.title)}</h2>
        <span class="score">${(job.score || 0).toFixed(1)}</span>
      </div>
      <div class="company">${escapeHtml(job.company)}</div>
      <div class="meta">
        <span>${escapeHtml(job.location || "Location n/a")}</span>
        <span class="badge">${escapeHtml(job.ats)}</span>
        <span>${escapeHtml(job.source)}</span>
        <span>${hoursAgo(job.posted_at)}</span>
        ${job.remote ? "<span class='badge'>remote</span>" : ""}
        ${pay ? `<span>${pay}</span>` : ""}
      </div>
      <p class="desc">${escapeHtml(job.description || "")}</p>
      <div class="actions">
        <a href="${escapeAttr(job.apply_url || job.original_url)}" target="_blank" rel="noopener">Apply</a>
        <a class="secondary" href="${escapeAttr(job.original_url || job.apply_url)}" target="_blank" rel="noopener">Posting</a>
      </div>
    `;
    list.appendChild(el);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/`/g, "");
}

async function boot() {
  const [jobs, meta] = await Promise.all([
    fetch("./jobs.json").then((r) => (r.ok ? r.json() : [])).catch(() => []),
    fetch("./meta.json").then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  ]);
  const ats = ["", ...Array.from(new Set(jobs.map((j) => j.ats))).sort()];
  $("ats").innerHTML = ats.map((a) => `<option value="${a}">${a || "All ATS"}</option>`).join("");
  const redraw = () => render(jobs, meta);
  ["q", "ats", "remote", "minscore"].forEach((id) => $(id).addEventListener("input", redraw));
  redraw();
}

boot();
