/* FinApp — vanilla JS, no build step.
   All numbers come from the API as strings; we only format for display. */

"use strict";

const $ = (id) => document.getElementById(id);

// ---- Telegram Mini App layer (no-op in a normal browser) --------------------

const tg = window.Telegram && window.Telegram.WebApp;
if (tg && tg.initData) {
  tg.ready();
  if (tg.expand) tg.expand();
  // Nudge our palette toward the client theme; the dark design already fits.
  const theme = tg.themeParams || {};
  if (theme.bg_color) {
    document.documentElement.style.setProperty("--bg", theme.bg_color);
  }
  if (theme.secondary_bg_color) {
    document.documentElement.style.setProperty("--surface", theme.secondary_bg_color);
  }
}

function authHeaders() {
  return tg && tg.initData ? { Authorization: `tma ${tg.initData}` } : {};
}

const el = {
  loginScreen: $("login-screen"),
  loginForm: $("login-form"),
  loginUsername: $("login-username"),
  loginPassword: $("login-password"),
  loginError: $("login-error"),
  logout: $("logout"),
  // main view
  mainHeader: $("main-header"),
  periodSelect: $("period-select"),
  periodSummary: $("period-summary"),
  newPeriod: $("new-period"),
  openSettings: $("open-settings"),
  emptyState: $("empty-state"),
  emptyOpenSettings: $("empty-open-settings"),
  today: $("today"),
  todayNumbers: $("today-numbers"),
  perDay: $("per-day"),
  overNote: $("over-note"),
  rebase: $("rebase"),
  nextDaily: $("next-daily"),
  wasDaily: $("was-daily"),
  preview: $("preview"),
  previewLabel: $("preview-label"),
  previewValue: $("preview-value"),
  remaining: $("remaining"),
  daysLeft: $("days-left"),
  spentState: $("spent-state"),
  spentOpenSettings: $("spent-open-settings"),
  spend: $("spend"),
  kindToggle: $("kind-toggle"),
  operationForm: $("operation-form"),
  operationAmount: $("operation-amount"),
  operationComment: $("operation-comment"),
  operationSubmit: $("operation-submit"),
  undo: $("undo"),
  openHistory: $("open-history"),
  // history view
  historyBack: $("history-back"),
  operationList: $("operation-list"),
  historyEmpty: $("history-empty"),
  download: $("download"),
  // settings view
  settingsBack: $("settings-back"),
  settingsTitle: $("settings-title"),
  settingsCancel: $("settings-cancel"),
  periodForm: $("period-form"),
  periodAmount: $("period-amount"),
  periodStart: $("period-start"),
  periodEnd: $("period-end"),
  perDayHint: $("per-day-hint"),
  // shared
  toast: $("toast"),
  savingsPrompt: $("savings-prompt"),
  savedAmount: $("saved-amount"),
  choiceSpend: $("choice-spend"),
  choiceSpendCaption: $("choice-spend-caption"),
  choiceIncrease: $("choice-increase"),
  choiceIncreaseCaption: $("choice-increase-caption"),
};

// ---- state ---------------------------------------------------------------------

let kind = "expense"; // what the form submits: 'expense' | 'income'
let lastBudget = null; // latest budget payload (for client-side income preview)
let lastPeriod = null; // latest period payload (prefills Budget Settings)
let lastOperation = null; // {id, amount} of the just-added op, for Undo
let periods = []; // [{period, budget}], newest first
let selectedPeriodId = Number(localStorage.getItem("selectedPeriodId")) || null;
let newPeriodMode = false;

// ---- views ---------------------------------------------------------------------

const views = {
  main: $("view-main"),
  history: $("view-history"),
  settings: $("view-settings"),
};

function showView(name) {
  for (const [key, section] of Object.entries(views)) {
    section.classList.toggle("hidden", key !== name);
  }
  if (name === "settings") prefillSettings();
  window.scrollTo(0, 0);
}

// ---- helpers ---------------------------------------------------------------

function fmt(value) {
  const n = Number(value);
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function validAmount(raw) {
  return /^\d+(\.\d{1,2})?$/.test(raw.trim());
}

// "Today, 13:10" / "Yesterday, 09:02" / "12 Jul, 09:02" (English)
function fmtWhen(iso) {
  const d = new Date(iso);
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const startOfDay = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(d)) / 86400000);
  if (diffDays === 0) return `Today, ${time}`;
  if (diffDays === 1) return `Yesterday, ${time}`;
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return `${day}, ${time}`;
}

let toastTimer;
function toast(message) {
  el.toast.textContent = message;
  el.toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.toast.classList.add("hidden"), 3000);
}

async function api(path, options) {
  options = options || {};
  options.headers = { ...authHeaders(), ...(options.headers || {}) };
  const resp = await fetch(path, options);
  if (!resp.ok) {
    if (resp.status === 404) return null;
    const body = await resp.json().catch(() => ({}));
    const error = new Error(body.detail ? JSON.stringify(body.detail) : `HTTP ${resp.status}`);
    error.status = resp.status;
    throw error;
  }
  return resp.json();
}

// ---- rendering -------------------------------------------------------------

function renderBudget(budget) {
  lastBudget = budget;
  const hasPeriod = budget !== null;
  el.emptyState.classList.toggle("hidden", hasPeriod);
  el.mainHeader.classList.toggle("hidden", !hasPeriod);
  el.today.classList.toggle("hidden", !hasPeriod);
  el.spend.classList.toggle("hidden", !hasPeriod);
  el.openHistory.classList.toggle("hidden", !hasPeriod);
  if (!hasPeriod) return;

  // Whole budget gone → big red "Spent" replaces the numbers. Adding an
  // income makes remaining_money positive again and recovers automatically.
  const allSpent = Number(budget.remaining_money) <= 0;
  el.todayNumbers.classList.toggle("hidden", allSpent);
  el.spentState.classList.toggle("hidden", !allSpent);
  if (allSpent) return;

  // Today's number drops 1:1 with spending. Once it hits 0, further spending
  // eats the overall budget: show 0 plus the rebased daily budget in red
  // (the reference behavior).
  const over = Number(budget.per_day_today) <= 0;
  el.perDay.textContent = fmt(over ? 0 : budget.per_day_today);
  el.overNote.classList.toggle("hidden", !over);
  const showRebase = over && budget.days_remaining > 1;
  el.rebase.classList.toggle("hidden", !showRebase);
  if (showRebase) {
    el.nextDaily.textContent = fmt(budget.next_daily);
    el.wasDaily.textContent = fmt(budget.daily_base);
  }
  el.remaining.textContent = fmt(budget.remaining_money);
  const d = budget.days_remaining;
  el.daysLeft.textContent = d === 1 ? "last day" : `${d} days left`;
}

function renderPeriod(period, budget) {
  lastPeriod = period;
  if (period && budget) {
    const days = budget.days_total;
    el.periodSummary.textContent =
      `${fmt(period.total_amount)} for ${days} ${days === 1 ? "day" : "days"}`;
    el.spend.classList.toggle("hidden", period.status !== "current");
  }
}

function renderPeriodOptions() {
  el.periodSelect.replaceChildren(
    ...periods.map(({ period }) => {
      const option = document.createElement("option");
      option.value = period.id;
      option.textContent = `${period.start_date} — ${period.end_date} · ${period.status}`;
      option.selected = period.id === selectedPeriodId;
      return option;
    })
  );
}

function selectedQuery() {
  return selectedPeriodId ? `?period_id=${selectedPeriodId}` : "";
}

function renderOperations(operations) {
  const items = operations || [];
  el.historyEmpty.classList.toggle("hidden", items.length > 0);
  el.operationList.replaceChildren(
    ...items.map((op) => {
      const li = document.createElement("li");
      const income = op.kind === "income";

      const amount = document.createElement("span");
      amount.className = "op-amount" + (income ? " income" : "");
      amount.textContent = (income ? "+" : "−") + fmt(op.amount);

      const info = document.createElement("div");
      info.className = "op-info";
      const comment = document.createElement("div");
      comment.className = "op-comment";
      comment.textContent = op.comment || "";
      const when = document.createElement("div");
      when.className = "op-date";
      when.textContent = fmtWhen(op.created_at);
      info.append(comment, when);

      const del = document.createElement("button");
      del.className = "delete";
      del.type = "button";
      del.setAttribute("aria-label", "Delete operation");
      del.textContent = "×";
      del.addEventListener("click", () => deleteOperation(op.id));

      li.append(amount, info, del);
      return li;
    })
  );
}

function renderPreview(value) {
  const show = value !== undefined && value !== null && !Number.isNaN(Number(value));
  el.preview.classList.toggle("hidden", !show);
  if (show) {
    el.previewLabel.textContent =
      kind === "income" ? "after this top-up:" : "after this purchase:";
    el.previewValue.textContent = fmt(value);
    el.previewValue.classList.toggle("negative", Number(value) < 0);
  }
}

// ---- undo last operation ------------------------------------------------------

function showUndo(operation) {
  lastOperation = operation;
  el.undo.classList.toggle("hidden", !operation);
  if (operation) {
    el.undo.textContent = `‹ Undo ${fmt(operation.amount)}`;
  }
}

el.undo.addEventListener("click", async () => {
  if (!lastOperation) return;
  const id = lastOperation.id;
  showUndo(null);
  try {
    await api(`/operations/${id}`, { method: "DELETE" });
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

// ---- data flow --------------------------------------------------------------

async function refresh() {
  periods = (await api("/periods")) || [];
  if (!periods.some(({ period }) => period.id === selectedPeriodId)) {
    const preferred = periods.find(({ period }) => period.status === "current") || periods[0];
    selectedPeriodId = preferred ? preferred.period.id : null;
  }
  if (selectedPeriodId) localStorage.setItem("selectedPeriodId", selectedPeriodId);
  else localStorage.removeItem("selectedPeriodId");
  renderPeriodOptions();
  const periodWithBudget = periods.find(({ period }) => period.id === selectedPeriodId) || null;
  const operations = selectedPeriodId
    ? await api(`/operations${selectedQuery()}`)
    : [];
  renderBudget(periodWithBudget && periodWithBudget.budget);
  renderPeriod(
    periodWithBudget && periodWithBudget.period,
    periodWithBudget && periodWithBudget.budget
  );
  renderOperations(operations);
  el.download.href = selectedPeriodId
    ? `/export.xlsx?period_id=${selectedPeriodId}`
    : "/export.xlsx";
}

// ---- entry mode toggle (Expense | Income) -------------------------------------

function setKind(next) {
  kind = next;
  for (const btn of el.kindToggle.querySelectorAll(".seg")) {
    const active = btn.dataset.kind === kind;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  }
  el.spend.classList.toggle("income-mode", kind === "income");
  el.operationSubmit.textContent = kind === "income" ? "Received" : "Spent";
  el.operationSubmit.classList.toggle("income", kind === "income");
  updatePreview();
}

el.kindToggle.addEventListener("click", (event) => {
  const btn = event.target.closest(".seg");
  if (btn) setKind(btn.dataset.kind);
});

// Live "after this operation" preview while typing. Expenses ask the server
// (?pending=X); incomes are computed client-side from the latest budget.
let previewTimer;
function updatePreview() {
  clearTimeout(previewTimer);
  const raw = el.operationAmount.value.trim();
  if (!validAmount(raw) || !lastBudget) {
    renderPreview(null);
    return;
  }
  if (kind === "income") {
    renderPreview(Number(lastBudget.per_day_today) + Number(raw));
    return;
  }
  previewTimer = setTimeout(async () => {
    try {
      const separator = selectedPeriodId ? "&" : "?";
      const b = await api(
        `/budget${selectedQuery()}${separator}pending=${encodeURIComponent(raw)}`
      );
      renderPreview(b && b.preview_after);
    } catch {
      renderPreview(null);
    }
  }, 150);
}
el.operationAmount.addEventListener("input", updatePreview);

el.operationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const amount = el.operationAmount.value.trim();
  if (!validAmount(amount)) {
    toast("Enter an amount like 250 or 99.90");
    return;
  }
  try {
    const body = await api(`/operations${selectedQuery()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        amount,
        kind,
        comment: el.operationComment.value.trim() || null,
      }),
    });
    el.operationForm.reset();
    renderPreview(null);
    showUndo({ id: body.operation.id, amount: body.operation.amount });
    await refresh();
    el.operationAmount.focus();
  } catch (err) {
    toast(err.message);
  }
});

async function deleteOperation(id) {
  showUndo(null);
  try {
    await api(`/operations/${id}`, { method: "DELETE" });
    await refresh();
  } catch (err) {
    toast(err.message);
  }
}

// ---- navigation -----------------------------------------------------------------

el.openHistory.addEventListener("click", () => showView("history"));
el.historyBack.addEventListener("click", () => showView("main"));
el.openSettings.addEventListener("click", () => {
  newPeriodMode = false;
  showView("settings");
});
el.newPeriod.addEventListener("click", () => {
  newPeriodMode = true;
  showView("settings");
});
el.emptyOpenSettings.addEventListener("click", () => {
  newPeriodMode = true;
  showView("settings");
});
el.spentOpenSettings.addEventListener("click", () => {
  newPeriodMode = false;
  showView("settings");
});
el.settingsBack.addEventListener("click", () => showView("main"));
el.settingsCancel.addEventListener("click", () => showView("main"));

// ---- Budget Settings ------------------------------------------------------------

function prefillSettings() {
  const iso = (d) => d.toISOString().slice(0, 10);
  el.settingsTitle.textContent = newPeriodMode ? "New Budget Period" : "Budget Settings";
  if (lastPeriod && !newPeriodMode) {
    el.periodAmount.value = lastPeriod.total_amount;
    el.periodStart.value = lastPeriod.start_date;
    el.periodEnd.value = lastPeriod.end_date;
  } else {
    // Sensible defaults: today → end of month.
    const today = new Date();
    el.periodAmount.value = "";
    el.periodStart.value = iso(today);
    el.periodEnd.value = iso(new Date(today.getFullYear(), today.getMonth() + 1, 0));
  }
  updatePerDayHint();
}

// Live "{X} per day" hint under the amount while typing (client-side).
function updatePerDayHint() {
  const raw = el.periodAmount.value.trim();
  const start = new Date(el.periodStart.value);
  const end = new Date(el.periodEnd.value);
  const days = Math.round((end - start) / 86400000) + 1;
  const ok = validAmount(raw) && Number.isFinite(days) && days >= 1;
  el.perDayHint.classList.toggle("hidden", !ok);
  if (ok) {
    el.perDayHint.textContent = `${fmt(Number(raw) / days)} per day`;
  }
}
el.periodAmount.addEventListener("input", updatePerDayHint);
el.periodStart.addEventListener("input", updatePerDayHint);
el.periodEnd.addEventListener("input", updatePerDayHint);

el.periodForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const amount = el.periodAmount.value.trim();
  if (!validAmount(amount)) {
    toast("Enter an amount like 30000 or 30000.50");
    return;
  }
  if (el.periodEnd.value < el.periodStart.value) {
    toast("End date must be on or after the start date");
    return;
  }
  try {
    let path = "/period";
    let method = "POST";
    if (!newPeriodMode && selectedPeriodId) {
      path = `/periods/${selectedPeriodId}`;
      method = "PATCH";
      if (lastPeriod && lastPeriod.status === "ended") {
        if (!window.confirm("This period has ended. Recalculate its history?")) return;
        path += "?confirm_ended=true";
      }
    }
    const saved = await api(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        total_amount: amount,
        start_date: el.periodStart.value,
        end_date: el.periodEnd.value,
      }),
    });
    selectedPeriodId = saved.period.id;
    localStorage.setItem("selectedPeriodId", selectedPeriodId);
    newPeriodMode = false;
    showUndo(null); // a new period invalidates the last-operation undo
    await refresh();
    showView("main");
  } catch (err) {
    toast(err.message);
  }
});

// Inside Telegram the .xlsx link needs the auth header, so fetch it as a blob.
el.download.addEventListener("click", async (event) => {
  if (!(tg && tg.initData)) return; // plain browser: let the link work as-is
  event.preventDefault();
  try {
    const resp = await fetch(el.download.href, { headers: authHeaders() });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const url = URL.createObjectURL(await resp.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = "finapp-export.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    toast(err.message);
  }
});

// ---- next-day savings decision -------------------------------------------------

async function maybeShowSavingsPrompt() {
  let p;
  try {
    p = await api("/savings-prompt");
  } catch {
    return; // never block the app on the prompt
  }
  if (!p || !p.show) return;
  const base = Number(p.spend_today_value) - Number(p.saved);
  el.savedAmount.textContent = fmt(p.saved);
  el.choiceSpendCaption.textContent =
    `${fmt(p.spend_today_value)} instead of ${fmt(base)} today`;
  el.choiceIncreaseCaption.textContent =
    `${fmt(p.increase_daily_value)} instead of ${fmt(base)} per day`;
  el.savingsPrompt.classList.remove("hidden");
}

async function decideSavings(choice) {
  el.savingsPrompt.classList.add("hidden");
  try {
    await api("/savings-decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ choice }),
    });
    await refresh();
  } catch (err) {
    toast(err.message);
  }
}

el.choiceSpend.addEventListener("click", () => decideSavings("spend_today"));
el.choiceIncrease.addEventListener("click", () => decideSavings("increase_daily"));

el.periodSelect.addEventListener("change", async () => {
  selectedPeriodId = Number(el.periodSelect.value);
  localStorage.setItem("selectedPeriodId", selectedPeriodId);
  showUndo(null);
  await refresh();
});

el.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  el.loginError.classList.add("hidden");
  try {
    await api("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: el.loginUsername.value.trim(),
        password: el.loginPassword.value,
      }),
    });
    el.loginForm.reset();
    el.loginScreen.classList.add("hidden");
    await startApp();
  } catch (error) {
    el.loginError.textContent = "Invalid username or password";
    el.loginError.classList.remove("hidden");
  }
});

el.logout.addEventListener("click", async () => {
  await api("/auth/logout", { method: "POST" });
  el.loginScreen.classList.remove("hidden");
  el.loginUsername.focus();
});

// ---- init --------------------------------------------------------------------

async function startApp() {
  prefillSettings();
  await refresh();
  const selected = periods.find(({ period }) => period.id === selectedPeriodId);
  if (selected && selected.period.status === "current") {
    await maybeShowSavingsPrompt();
  }
  const v = new URLSearchParams(location.search).get("view");
  if (v && views[v]) showView(v);
}

(async function init() {
  try {
    const config = await api("/auth/config");
    if (config && config.enabled) {
      el.logout.classList.remove("hidden");
      try {
        await api("/auth/me");
      } catch (error) {
        if (error.status === 401) {
          el.loginScreen.classList.remove("hidden");
          el.loginUsername.focus();
          return;
        }
        throw error;
      }
    }
    await startApp();
  } catch (error) {
    toast(error.message);
  }
})();
