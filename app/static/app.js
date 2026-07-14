/* Tzlvt clone — vanilla JS, no build step.
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
  emptyState: $("empty-state"),
  today: $("today"),
  perDay: $("per-day"),
  overNote: $("over-note"),
  rebase: $("rebase"),
  nextDaily: $("next-daily"),
  wasDaily: $("was-daily"),
  preview: $("preview"),
  previewValue: $("preview-value"),
  remaining: $("remaining"),
  daysLeft: $("days-left"),
  spend: $("spend"),
  expenseForm: $("expense-form"),
  expenseAmount: $("expense-amount"),
  expenseComment: $("expense-comment"),
  history: $("history"),
  expenseList: $("expense-list"),
  settings: $("settings"),
  periodForm: $("period-form"),
  periodAmount: $("period-amount"),
  periodStart: $("period-start"),
  periodEnd: $("period-end"),
  toast: $("toast"),
};

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
    throw new Error(body.detail ? JSON.stringify(body.detail) : `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ---- rendering -------------------------------------------------------------

function renderBudget(budget) {
  const hasPeriod = budget !== null;
  el.emptyState.classList.toggle("hidden", hasPeriod);
  el.today.classList.toggle("hidden", !hasPeriod);
  el.spend.classList.toggle("hidden", !hasPeriod);
  el.history.classList.toggle("hidden", !hasPeriod);
  if (!hasPeriod) {
    el.settings.open = true;
    return;
  }
  // Today's number drops 1:1 with spending. Once it hits 0, further spending
  // eats the overall budget: show 0 plus the rebased daily budget in red,
  // exactly like the original app.
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

function renderExpenses(expenses) {
  el.expenseList.replaceChildren(
    ...(expenses || []).map((e) => {
      const li = document.createElement("li");

      const amount = document.createElement("span");
      amount.className = "expense-amount";
      amount.textContent = "−" + fmt(e.amount);

      const info = document.createElement("div");
      info.className = "expense-info";
      const comment = document.createElement("div");
      comment.className = "expense-comment";
      comment.textContent = e.comment || "";
      const when = document.createElement("div");
      when.className = "expense-date";
      when.textContent = e.created_at.slice(0, 10);
      info.append(comment, when);

      const del = document.createElement("button");
      del.className = "delete";
      del.type = "button";
      del.setAttribute("aria-label", "Delete expense");
      del.textContent = "×";
      del.addEventListener("click", () => deleteExpense(e.id));

      li.append(amount, info, del);
      return li;
    })
  );
}

function renderPreview(budget) {
  const show = budget && budget.preview_after !== undefined && budget.preview_after !== null;
  el.preview.classList.toggle("hidden", !show);
  if (show) {
    el.previewValue.textContent = fmt(budget.preview_after);
    el.previewValue.classList.toggle("negative", Number(budget.preview_after) < 0);
  }
}

// ---- data flow --------------------------------------------------------------

async function refresh() {
  const [budget, expenses] = await Promise.all([api("/budget"), api("/expenses")]);
  renderBudget(budget);
  renderExpenses(expenses);
}

// Live "after this purchase" preview while typing.
let previewTimer;
el.expenseAmount.addEventListener("input", () => {
  clearTimeout(previewTimer);
  const raw = el.expenseAmount.value.trim();
  if (!validAmount(raw)) {
    renderPreview(null);
    return;
  }
  previewTimer = setTimeout(async () => {
    try {
      renderPreview(await api(`/budget?pending=${encodeURIComponent(raw)}`));
    } catch {
      renderPreview(null);
    }
  }, 150);
});

el.expenseForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const amount = el.expenseAmount.value.trim();
  if (!validAmount(amount)) {
    toast("Enter an amount like 250 or 99.90");
    return;
  }
  try {
    await api("/expenses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount, comment: el.expenseComment.value.trim() || null }),
    });
    el.expenseForm.reset();
    renderPreview(null);
    await refresh();
    el.expenseAmount.focus();
  } catch (err) {
    toast(err.message);
  }
});

async function deleteExpense(id) {
  try {
    await api(`/expenses/${id}`, { method: "DELETE" });
    await refresh();
  } catch (err) {
    toast(err.message);
  }
}

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
    await api("/period", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        total_amount: amount,
        start_date: el.periodStart.value,
        end_date: el.periodEnd.value,
      }),
    });
    el.settings.open = false;
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

// Inside Telegram the .xlsx link needs the auth header, so fetch it as a blob.
$("download").addEventListener("click", async (event) => {
  if (!(tg && tg.initData)) return; // plain browser: let the link work as-is
  event.preventDefault();
  try {
    const resp = await fetch("/export.xlsx", { headers: authHeaders() });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const url = URL.createObjectURL(await resp.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = "tzlvt-export.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    toast(err.message);
  }
});

// ---- init --------------------------------------------------------------------

(function init() {
  // Sensible defaults for the period form: today → end of month.
  const today = new Date();
  const iso = (d) => d.toISOString().slice(0, 10);
  el.periodStart.value = iso(today);
  el.periodEnd.value = iso(new Date(today.getFullYear(), today.getMonth() + 1, 0));
  refresh().catch((err) => toast(err.message));
})();
