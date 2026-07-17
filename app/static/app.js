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
  loginTitle: $("login-title"),
  loginSubtitle: $("login-subtitle"),
  loginForm: $("login-form"),
  displayNameField: $("display-name-field"),
  loginDisplayName: $("login-display-name"),
  loginUsername: $("login-username"),
  loginPassword: $("login-password"),
  loginError: $("login-error"),
  logout: $("logout"),
  workspaceBar: $("workspace-bar"),
  workspaceSelect: $("workspace-select"),
  createWorkspace: $("create-workspace"),
  inviteMember: $("invite-member"),
  workspaceLogout: $("workspace-logout"),
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
  categoryRow: $("category-row"),
  operationCategory: $("operation-category"),
  newCategory: $("new-category"),
  categoryWarning: $("category-warning"),
  goalRow: $("goal-row"),
  operationGoal: $("operation-goal"),
  newGoal: $("new-goal"),
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
  clonePlanField: $("clone-plan-field"),
  clonePlan: $("clone-plan"),
  poolPlansCard: $("pool-plans-card"),
  poolPlanList: $("pool-plan-list"),
  settingsNewPool: $("settings-new-pool"),
  goalPlansCard: $("goal-plans-card"),
  goalPlanList: $("goal-plan-list"),
  settingsNewGoal: $("settings-new-goal"),
  categoryLimitsCard: $("category-limits-card"),
  categoryLimitList: $("category-limit-list"),
  settingsNewCategory: $("settings-new-category"),
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
let workspaces = [];
let selectedWorkspaceId = Number(localStorage.getItem("selectedWorkspaceId")) || 1;
let webAuthActive = false;
const inviteToken = new URLSearchParams(location.search).get("invite");
let categories = [];
let categoryPlans = [];
let pools = [];
let poolPlans = [];
let goals = [];
let goalPlans = [];

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

function query(params) {
  const values = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null) values.set(key, value);
  }
  const rendered = values.toString();
  return rendered ? `?${rendered}` : "";
}

function workspacePath(path = "") {
  return `/api/v1/workspaces/${selectedWorkspaceId}${path}`;
}

function periodPath(path = "") {
  return workspacePath(`/periods/${selectedPeriodId}${path}`);
}

function renderWorkspaces() {
  el.workspaceSelect.replaceChildren(
    ...workspaces.map((workspace) => {
      const option = document.createElement("option");
      option.value = workspace.id;
      option.textContent = workspace.name;
      option.selected = workspace.id === selectedWorkspaceId;
      return option;
    })
  );
  const current = workspaces.find((w) => w.id === selectedWorkspaceId);
  el.inviteMember.classList.toggle(
    "hidden", !current || current.kind !== "shared" || current.role !== "owner"
  );
}

async function loadWorkspaces() {
  if (!webAuthActive) {
    selectedWorkspaceId = 1;
    return;
  }
  workspaces = (await api("/api/v1/workspaces")) || [];
  if (!workspaces.some((w) => w.id === selectedWorkspaceId)) {
    selectedWorkspaceId = workspaces[0] ? workspaces[0].id : 1;
  }
  localStorage.setItem("selectedWorkspaceId", selectedWorkspaceId);
  renderWorkspaces();
  el.workspaceBar.classList.remove("hidden");
}

function renderOperations(operations) {
  const items = operations || [];
  el.historyEmpty.classList.toggle("hidden", items.length > 0);
  el.operationList.replaceChildren(
    ...items.map((op) => {
      const li = document.createElement("li");
      const income = op.kind === "income" || op.kind === "transfer_from_goal";

      const amount = document.createElement("span");
      amount.className = "op-amount" + (income ? " income" : "");
      amount.textContent = (income ? "+" : "−") + fmt(op.amount);

      const info = document.createElement("div");
      info.className = "op-info";
      const comment = document.createElement("div");
      comment.className = "op-comment";
      comment.textContent = op.comment || "";
      const category = categories.find((item) => item.id === op.category_id);
      if (category) {
        comment.textContent = op.comment ? `${category.name} · ${op.comment}` : category.name;
      }
      const goal = goals.find((item) => item.id === op.savings_goal_id);
      if (goal) {
        const action = op.kind === "transfer_to_goal" ? "Saved to" : "Withdrawn from";
        comment.textContent = op.comment
          ? `${action} ${goal.name} · ${op.comment}`
          : `${action} ${goal.name}`;
      }
      const when = document.createElement("div");
      when.className = "op-date";
      when.textContent = `${op.occurred_on} · ${fmtWhen(op.created_at)}`;
      info.append(comment, when);

      const edit = document.createElement("button");
      edit.className = "edit-operation";
      edit.type = "button";
      edit.setAttribute("aria-label", "Edit operation");
      edit.textContent = "Edit";
      edit.addEventListener("click", () => editOperation(op));

      const del = document.createElement("button");
      del.className = "delete";
      del.type = "button";
      del.setAttribute("aria-label", "Delete operation");
      del.textContent = "×";
      del.addEventListener("click", () => deleteOperation(op.id));

      li.append(amount, info, edit, del);
      return li;
    })
  );
}

function renderCategories() {
  const selected = el.operationCategory.value;
  const options = [new Option("Uncategorized", "")];
  for (const category of categories) options.push(new Option(category.name, category.id));
  el.operationCategory.replaceChildren(...options);
  if ([...el.operationCategory.options].some((o) => o.value === selected)) {
    el.operationCategory.value = selected;
  }
}

function renderGoals() {
  const selected = el.operationGoal.value;
  el.operationGoal.replaceChildren(
    ...goals.map((goal) => new Option(`${goal.name} · ${fmt(goal.balance)}`, goal.id))
  );
  if ([...el.operationGoal.options].some((option) => option.value === selected)) {
    el.operationGoal.value = selected;
  }
}

function renderCategoryPlans() {
  el.categoryLimitsCard.classList.toggle(
    "hidden", !selectedPeriodId || newPeriodMode
  );
  const plansByCategory = new Map(
    categoryPlans.map((plan) => [plan.category.id, plan])
  );
  el.categoryLimitList.replaceChildren(
    ...categories.map((category) => {
      const plan = plansByCategory.get(category.id);
      const row = document.createElement("label");
      row.className = "limit-item with-pool";
      const text = document.createElement("span");
      text.textContent = category.name;
      const meta = document.createElement("span");
      meta.className = "limit-meta" + (plan && plan.over_limit ? " over" : "");
      meta.textContent = plan ? `${fmt(plan.spent)} spent` : "No spending";
      text.append(document.createElement("br"), meta);
      const input = document.createElement("input");
      input.type = "text";
      input.inputMode = "decimal";
      input.placeholder = "No limit";
      input.value = plan && plan.limit_amount !== null ? plan.limit_amount : "";
      const poolSelect = document.createElement("select");
      poolSelect.append(new Option("No pool", ""));
      for (const poolPlan of poolPlans) {
        poolSelect.append(new Option(poolPlan.pool.name, poolPlan.id));
      }
      poolSelect.value = plan && plan.pool_plan_id ? String(plan.pool_plan_id) : "";
      const save = () => saveCategoryPlan(category.id, input.value, poolSelect.value);
      input.addEventListener("change", save);
      poolSelect.addEventListener("change", save);
      row.append(text, input, poolSelect);
      return row;
    })
  );
}

async function saveCategoryPlan(categoryId, raw, poolPlanId) {
  if (raw.trim() && !validAmount(raw)) {
    toast("Enter a positive limit or leave it blank");
    renderCategoryPlans();
    return;
  }
  try {
    await api(
      periodPath(`/category-plans/${categoryId}`),
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          limit_amount: raw.trim() || null,
          pool_plan_id: poolPlanId ? Number(poolPlanId) : null,
        }),
      }
    );
    await refresh();
  } catch (error) {
    toast(error.message);
    await refresh();
  }
}

function renderPoolPlans() {
  el.poolPlansCard.classList.toggle("hidden", !selectedPeriodId || newPeriodMode);
  const plansByPool = new Map(poolPlans.map((plan) => [plan.pool.id, plan]));
  el.poolPlanList.replaceChildren(
    ...pools.map((pool) => {
      const plan = plansByPool.get(pool.id);
      const row = document.createElement("label");
      row.className = "limit-item";
      const text = document.createElement("span");
      text.textContent = pool.name;
      const meta = document.createElement("span");
      meta.className = "limit-meta" + (plan && plan.over_limit ? " over" : "");
      meta.textContent = plan ? `${fmt(plan.spent)} spent` : "Not allocated";
      text.append(document.createElement("br"), meta);
      const input = document.createElement("input");
      input.type = "text";
      input.inputMode = "decimal";
      input.placeholder = "Allocation";
      input.value = plan ? plan.allocated_amount : "";
      input.addEventListener("change", () => savePoolPlan(pool.id, input.value));
      row.append(text, input);
      return row;
    })
  );
}

function renderGoalPlans() {
  el.goalPlansCard.classList.toggle("hidden", !selectedPeriodId || newPeriodMode);
  const plansByGoal = new Map(goalPlans.map((plan) => [plan.goal.id, plan]));
  el.goalPlanList.replaceChildren(
    ...goals.map((goal) => {
      const plan = plansByGoal.get(goal.id);
      const row = document.createElement("label");
      row.className = "limit-item";
      const text = document.createElement("span");
      text.textContent = goal.name;
      const meta = document.createElement("span");
      meta.className = "limit-meta" + (plan && plan.over_plan ? " over" : "");
      meta.textContent = `${fmt(goal.balance)} / ${fmt(goal.target_amount)} saved`;
      text.append(document.createElement("br"), meta);
      const input = document.createElement("input");
      input.type = "text";
      input.inputMode = "decimal";
      input.placeholder = "Planned";
      input.value = plan ? plan.planned_amount : "";
      input.addEventListener("change", () => saveGoalPlan(goal.id, input.value));
      row.append(text, input);
      return row;
    })
  );
}

async function saveGoalPlan(goalId, raw) {
  if (!validAmount(raw)) {
    toast("Planned contribution must be a positive amount");
    renderGoalPlans();
    return;
  }
  try {
    await api(periodPath(`/goal-plans/${goalId}`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ planned_amount: raw.trim() }),
    });
    await refresh();
  } catch (error) {
    toast(error.message);
    await refresh();
  }
}

async function savePoolPlan(poolId, raw) {
  if (!validAmount(raw)) {
    toast("Pool allocation must be a positive amount");
    renderPoolPlans();
    return;
  }
  try {
    await api(periodPath(`/pool-plans/${poolId}`), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ allocated_amount: raw.trim() }),
    });
    await refresh();
  } catch (error) {
    toast(error.message);
    await refresh();
  }
}

function renderCategoryPreview(raw) {
  if (kind === "transfer_to_goal") {
    const goalId = Number(el.operationGoal.value);
    const plan = goalPlans.find((item) => item.goal.id === goalId);
    const predicted = plan && validAmount(raw) ? Number(plan.contributed) + Number(raw) : null;
    const over = plan && predicted > Number(plan.planned_amount);
    el.categoryWarning.classList.toggle("hidden", !over);
    if (over) {
      el.categoryWarning.textContent =
        `${plan.goal.name} planned contribution will be exceeded by ` +
        fmt(predicted - Number(plan.planned_amount));
    }
    return;
  }
  if (kind !== "expense") {
    el.categoryWarning.classList.add("hidden");
    return;
  }
  const categoryId = Number(el.operationCategory.value);
  const plan = categoryPlans.find((item) => item.category.id === categoryId);
  const predicted = plan && validAmount(raw) ? Number(plan.spent) + Number(raw) : null;
  const messages = [];
  if (plan && plan.limit_amount !== null && predicted > Number(plan.limit_amount)) {
    messages.push(
      `${plan.category.name} will exceed its limit by ${fmt(predicted - Number(plan.limit_amount))}`
    );
  }
  const poolPlan = plan && poolPlans.find((item) => item.id === plan.pool_plan_id);
  if (poolPlan && Number(poolPlan.spent) + Number(raw) > Number(poolPlan.allocated_amount)) {
    messages.push(
      `${poolPlan.pool.name} pool will exceed its allocation by ` +
      fmt(Number(poolPlan.spent) + Number(raw) - Number(poolPlan.allocated_amount))
    );
  }
  el.categoryWarning.classList.toggle("hidden", messages.length === 0);
  el.categoryWarning.textContent = messages.join(" · ");
}

function renderPreview(value) {
  const show = value !== undefined && value !== null && !Number.isNaN(Number(value));
  el.preview.classList.toggle("hidden", !show);
  if (show) {
    el.previewLabel.textContent =
      kind === "income" ? "after this top-up:" :
      kind === "transfer_from_goal" ? "after this withdrawal:" :
      kind === "transfer_to_goal" ? "after saving:" : "after this purchase:";
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
    await api(periodPath(`/operations/${id}`), { method: "DELETE" });
    await refresh();
  } catch (err) {
    toast(err.message);
  }
});

// ---- data flow --------------------------------------------------------------

async function refresh() {
  periods = (await api(workspacePath("/periods"))) || [];
  if (!periods.some(({ period }) => period.id === selectedPeriodId)) {
    const preferred = periods.find(({ period }) => period.status === "current") || periods[0];
    selectedPeriodId = preferred ? preferred.period.id : null;
  }
  if (selectedPeriodId) localStorage.setItem("selectedPeriodId", selectedPeriodId);
  else localStorage.removeItem("selectedPeriodId");
  renderPeriodOptions();
  const periodWithBudget = periods.find(({ period }) => period.id === selectedPeriodId) || null;
  const [
    loadedCategories,
    loadedPools,
    loadedGoals,
    operations,
    loadedPlans,
    loadedPoolPlans,
    loadedGoalPlans,
  ] = await Promise.all([
    api(workspacePath("/categories")),
    api(workspacePath("/pools")),
    api(workspacePath("/savings-goals")),
    selectedPeriodId ? api(periodPath("/operations")) : Promise.resolve([]),
    selectedPeriodId
      ? api(periodPath("/category-plans"))
      : Promise.resolve([]),
    selectedPeriodId
      ? api(periodPath("/pool-plans"))
      : Promise.resolve([]),
    selectedPeriodId
      ? api(periodPath("/goal-plans"))
      : Promise.resolve([]),
  ]);
  categories = loadedCategories || [];
  pools = loadedPools || [];
  goals = loadedGoals || [];
  categoryPlans = loadedPlans || [];
  poolPlans = loadedPoolPlans || [];
  goalPlans = loadedGoalPlans || [];
  renderCategories();
  renderGoals();
  renderPoolPlans();
  renderGoalPlans();
  renderCategoryPlans();
  renderBudget(periodWithBudget && periodWithBudget.budget);
  renderPeriod(
    periodWithBudget && periodWithBudget.period,
    periodWithBudget && periodWithBudget.budget
  );
  renderOperations(operations);
  el.download.href = selectedPeriodId ? periodPath("/export.xlsx") : "#";
}

// ---- entry mode toggle (Expense | Income) -------------------------------------

function setKind(next) {
  kind = next;
  for (const btn of el.kindToggle.querySelectorAll(".seg")) {
    const active = btn.dataset.kind === kind;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", String(active));
  }
  const addsToPeriod = kind === "income" || kind === "transfer_from_goal";
  const isTransfer = kind === "transfer_to_goal" || kind === "transfer_from_goal";
  el.spend.classList.toggle("income-mode", addsToPeriod);
  el.categoryRow.classList.toggle("hidden", kind !== "expense");
  el.goalRow.classList.toggle("hidden", !isTransfer);
  el.operationSubmit.textContent =
    kind === "income" ? "Received" :
    kind === "transfer_to_goal" ? "Saved" :
    kind === "transfer_from_goal" ? "Withdrawn" : "Spent";
  el.operationSubmit.classList.toggle("income", addsToPeriod);
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
  renderCategoryPreview(raw);
  if (!validAmount(raw) || !lastBudget) {
    renderPreview(null);
    return;
  }
  if (kind === "income" || kind === "transfer_from_goal") {
    renderPreview(Number(lastBudget.per_day_today) + Number(raw));
    return;
  }
  previewTimer = setTimeout(async () => {
    try {
      const b = await api(periodPath(`/budget${query({ pending: raw })}`));
      renderPreview(b && b.preview_after);
    } catch {
      renderPreview(null);
    }
  }, 150);
}
el.operationAmount.addEventListener("input", updatePreview);
el.operationCategory.addEventListener("change", updatePreview);
el.operationGoal.addEventListener("change", updatePreview);

async function createCategoryFromPrompt() {
  const name = window.prompt("Category name");
  if (!name || !name.trim()) return;
  try {
    const category = await api(workspacePath("/categories"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    await refresh();
    el.operationCategory.value = String(category.id);
    updatePreview();
  } catch (error) {
    toast(error.message);
  }
}

el.newCategory.addEventListener("click", createCategoryFromPrompt);
el.settingsNewCategory.addEventListener("click", createCategoryFromPrompt);

el.settingsNewPool.addEventListener("click", async () => {
  const name = window.prompt("Pool name", "Home");
  if (!name || !name.trim()) return;
  try {
    await api(workspacePath("/pools"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    await refresh();
  } catch (error) {
    toast(error.message);
  }
});

async function createGoalFromPrompt() {
  const name = window.prompt("Savings goal name", "Emergency fund");
  if (!name || !name.trim()) return;
  const target = window.prompt("Target amount", "3000");
  if (!target || !validAmount(target)) {
    toast("Target must be a positive amount");
    return;
  }
  try {
    const goal = await api(workspacePath("/savings-goals"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), target_amount: target.trim() }),
    });
    await refresh();
    el.operationGoal.value = String(goal.id);
  } catch (error) {
    toast(error.message);
  }
}

el.newGoal.addEventListener("click", createGoalFromPrompt);
el.settingsNewGoal.addEventListener("click", createGoalFromPrompt);

el.operationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const amount = el.operationAmount.value.trim();
  if (!validAmount(amount)) {
    toast("Enter an amount like 250 or 99.90");
    return;
  }
  try {
    const body = await api(periodPath("/operations"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        amount,
        kind,
        comment: el.operationComment.value.trim() || null,
        category_id:
          kind === "expense" && el.operationCategory.value
            ? Number(el.operationCategory.value)
            : null,
        savings_goal_id:
          (kind === "transfer_to_goal" || kind === "transfer_from_goal") &&
          el.operationGoal.value
            ? Number(el.operationGoal.value)
            : null,
      }),
    });
    el.operationForm.reset();
    renderPreview(null);
    showUndo({ id: body.operation.id, amount: body.operation.amount });
    if (body.warnings && body.warnings.length) {
      toast(
        body.warnings
          .map((warning) => `${warning.name} exceeded by ${fmt(warning.over_by)}`)
          .join(" · ")
      );
    }
    await refresh();
    el.operationAmount.focus();
  } catch (err) {
    toast(err.message);
  }
});

async function deleteOperation(id) {
  showUndo(null);
  try {
    const confirmEnded = lastPeriod && lastPeriod.status === "ended";
    if (confirmEnded && !window.confirm("Delete this operation from an ended period?")) return;
    await api(
      periodPath(`/operations/${id}${query({ confirm_ended: confirmEnded || null })}`),
      { method: "DELETE" }
    );
    await refresh();
  } catch (err) {
    toast(err.message);
  }
}

async function editOperation(operation) {
  const amount = window.prompt("Amount", operation.amount);
  if (amount === null) return;
  if (!validAmount(amount)) {
    toast("Enter an amount like 250 or 99.90");
    return;
  }
  const occurredOn = window.prompt("Financial date (YYYY-MM-DD)", operation.occurred_on);
  if (occurredOn === null) return;
  const comment = window.prompt("Comment", operation.comment || "");
  if (comment === null) return;
  const confirmEnded = lastPeriod && lastPeriod.status === "ended";
  if (confirmEnded && !window.confirm("Recalculate this ended period?")) return;
  try {
    await api(
      periodPath(
        `/operations/${operation.id}${query({ confirm_ended: confirmEnded || null })}`
      ),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: amount.trim(),
          occurred_on: occurredOn.trim(),
          comment: comment.trim() || null,
        }),
      }
    );
    await refresh();
  } catch (error) {
    toast(error.message);
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
  el.clonePlanField.classList.toggle(
    "hidden", !newPeriodMode || !selectedPeriodId
  );
  renderPoolPlans();
  renderGoalPlans();
  renderCategoryPlans();
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
    const cloneFrom =
      newPeriodMode && el.clonePlan.checked && selectedPeriodId
        ? selectedPeriodId
        : null;
    let path = workspacePath(`/periods${query({ clone_from_period_id: cloneFrom })}`);
    let method = "POST";
    if (!newPeriodMode && selectedPeriodId) {
      path = periodPath();
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
    p = await api(workspacePath("/savings-prompt"));
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
    await api(workspacePath("/savings-decision"), {
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

el.workspaceSelect.addEventListener("change", async () => {
  selectedWorkspaceId = Number(el.workspaceSelect.value);
  localStorage.setItem("selectedWorkspaceId", selectedWorkspaceId);
  selectedPeriodId = null;
  showUndo(null);
  renderWorkspaces();
  await refresh();
});

el.createWorkspace.addEventListener("click", async () => {
  const name = window.prompt("Shared workspace name", "Family");
  if (!name || !name.trim()) return;
  try {
    const workspace = await api("/api/v1/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }),
    });
    await loadWorkspaces();
    selectedWorkspaceId = workspace.id;
    localStorage.setItem("selectedWorkspaceId", selectedWorkspaceId);
    renderWorkspaces();
    selectedPeriodId = null;
    await refresh();
  } catch (error) {
    toast(error.message);
  }
});

el.inviteMember.addEventListener("click", async () => {
  try {
    const invite = await api(`/api/v1/workspaces/${selectedWorkspaceId}/invites`, {
      method: "POST",
    });
    const url = `${location.origin}/?invite=${encodeURIComponent(invite.token)}`;
    if (navigator.clipboard) await navigator.clipboard.writeText(url);
    window.prompt("Invite link (valid for 7 days)", url);
  } catch (error) {
    toast(error.message);
  }
});

el.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  el.loginError.classList.add("hidden");
  try {
    const path = inviteToken
      ? `/api/v1/invites/${encodeURIComponent(inviteToken)}/accept`
      : "/api/v1/auth/login";
    await api(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: el.loginUsername.value.trim(),
        password: el.loginPassword.value,
        ...(inviteToken ? { display_name: el.loginDisplayName.value.trim() || null } : {}),
      }),
    });
    el.loginForm.reset();
    el.loginScreen.classList.add("hidden");
    history.replaceState({}, "", location.pathname);
    await loadWorkspaces();
    await startApp();
  } catch (error) {
    el.loginError.textContent = "Invalid username or password";
    el.loginError.classList.remove("hidden");
  }
});

async function logout() {
  await api("/api/v1/auth/logout", { method: "POST" });
  el.workspaceBar.classList.add("hidden");
  el.loginScreen.classList.remove("hidden");
  el.loginUsername.focus();
}
el.logout.addEventListener("click", logout);
el.workspaceLogout.addEventListener("click", logout);

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
    const config = await api("/api/v1/auth/config");
    if (config && config.enabled) {
      webAuthActive = true;
      el.logout.classList.remove("hidden");
      if (inviteToken) {
        el.loginTitle.textContent = "Join family";
        el.loginSubtitle.textContent = "Create your FinApp account";
        el.displayNameField.classList.remove("hidden");
        el.loginScreen.classList.remove("hidden");
        el.loginUsername.focus();
        return;
      }
      try {
        await api("/api/v1/auth/me");
      } catch (error) {
        if (error.status === 401) {
          el.loginScreen.classList.remove("hidden");
          el.loginUsername.focus();
          return;
        }
        throw error;
      }
      await loadWorkspaces();
    }
    await startApp();
  } catch (error) {
    toast(error.message);
  }
})();
