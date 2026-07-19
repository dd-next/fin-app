const $ = (id) => document.getElementById(id);

const state = {
  registerMode: false,
  context: null,
  lastUserId: null,
  assets: [],
  accounts: [],
  summary: null,
  categories: new Map(),
  transactions: [],
  transactionPeriods: [],
  nextCursor: null,
  planRules: [],
  planOccurrences: [],
  planLinkTransactions: [],
  operationsAccountId: null,
  operationsAction: "spend",
  operationsPeriods: [],
  operationsPeriodAccountId: null,
  operationsPeriodLoading: false,
  operationsPeriodError: null,
  operationsPeriodRequestId: 0,
  operationsUndoCandidate: null,
  operationsUndoLoading: false,
  operationsUndoRequestId: 0,
  operationsCommandLoading: false,
  periodCommandLoading: false,
  activeView: "accounts",
  activeAccount: null,
  sharingAccount: null,
  viewingTransaction: null,
  editingTransaction: null,
  transactionDeleteLoading: false,
  toastTimer: null,
};

const pendingInvite = new URLSearchParams(window.location.search).get("invite");

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload && payload.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join("; ")
      : detail || "Request failed";
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value, precision = null) {
  if (value === null || value === undefined) return "—";
  let raw = String(value);
  let sign = "";
  if (raw.startsWith("-")) {
    sign = "−";
    raw = raw.slice(1);
  } else if (raw.startsWith("+")) {
    sign = "+";
    raw = raw.slice(1);
  }
  let [integer, fraction = ""] = raw.split(".");
  if (precision === null) fraction = fraction.replace(/0+$/, "");
  else if (fraction.length < precision) fraction = fraction.padEnd(precision, "0");
  integer = integer.replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${integer || "0"}${fraction ? `.${fraction}` : ""}`;
}

function formatMoney(value, code) {
  const precision = assetByCode(code)?.decimals ?? null;
  return `${formatNumber(value, precision)} ${code}`;
}

function localDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function todayValue() {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60000).toISOString().slice(0, 10);
}

function dateValueAfter(start, days) {
  const value = new Date(`${start}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function setLoading(value) {
  $("page-loading").classList.toggle("hidden", !value);
}

function toast(message) {
  clearTimeout(state.toastTimer);
  $("toast").textContent = message;
  $("toast").classList.remove("hidden");
  state.toastTimer = setTimeout(() => $("toast").classList.add("hidden"), 3600);
}

function accountById(id) {
  return state.accounts.find((account) => account.id === Number(id));
}

function assetByCode(code) {
  return state.assets.find((asset) => asset.code === code);
}

function canUseAccount(account, action) {
  const roles = {
    view: ["owner", "editor", "contributor", "viewer"],
    expense: ["owner", "editor", "contributor"],
    income: ["owner", "editor"],
    edit: ["owner", "editor"],
    owner: ["owner"],
  };
  return account && roles[action].includes(account.access_role);
}

function selectOptions(select, items, { placeholder = null, selected = null } = {}) {
  const previous = selected === null ? select.value : String(selected ?? "");
  const nodes = [];
  if (placeholder !== null) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = placeholder;
    nodes.push(option);
  }
  for (const item of items) {
    const option = document.createElement("option");
    option.value = String(item.value);
    option.textContent = item.label;
    option.disabled = Boolean(item.disabled);
    nodes.push(option);
  }
  select.replaceChildren(...nodes);
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}

function showAuth() {
  state.context = null;
  $("auth-card").classList.remove("hidden");
  $("app-shell").classList.add("hidden");
  if (pendingInvite) {
    document.querySelector(".auth-copy").textContent = "Log in or create an account to accept your account invitation.";
  }
}

async function categoriesFor(workspaceId) {
  if (state.categories.has(workspaceId)) return state.categories.get(workspaceId);
  try {
    const categories = await api(`/api/v1/workspaces/${workspaceId}/categories?include_archived=true`);
    state.categories.set(workspaceId, categories);
    return categories;
  } catch (error) {
    if (error.status === 404) return [];
    throw error;
  }
}

async function acceptPendingInvitation() {
  if (!pendingInvite) return;
  try {
    const access = await api(`/api/v1/account-invitations/${encodeURIComponent(pendingInvite)}/accept`, { method: "POST" });
    toast(`Invitation accepted · ${access.role}`);
  } catch (error) {
    toast(error.message);
  }
  const clean = new URL(window.location.href);
  clean.searchParams.delete("invite");
  window.history.replaceState({}, "", `${clean.pathname}${clean.search}${clean.hash}`);
}

async function showApp(context) {
  if (state.lastUserId !== null && state.lastUserId !== context.user.id) {
    state.categories.clear();
    state.accounts = [];
    state.transactions = [];
    state.transactionPeriods = [];
    state.planRules = [];
    state.planOccurrences = [];
    state.operationsAccountId = null;
    state.operationsAction = "spend";
    state.operationsPeriods = [];
    state.operationsPeriodAccountId = null;
    state.operationsPeriodError = null;
    state.operationsPeriodRequestId += 1;
    state.operationsUndoCandidate = null;
    state.operationsUndoRequestId += 1;
  }
  state.lastUserId = context.user.id;
  state.context = context;
  $("auth-card").classList.add("hidden");
  $("app-shell").classList.remove("hidden");
  $("workspace-name").textContent = context.workspace.name;
  $("profile-summary").textContent = context.user.display_name;
  $("profile-name").textContent = context.user.display_name;
  $("profile-username").textContent = `@${context.user.username}`;
  await acceptPendingInvitation();
  await refreshAll();
  switchView(new URLSearchParams(window.location.search).get("view") || "accounts", false);
}

async function refreshAll() {
  setLoading(true);
  try {
    if (!state.assets.length) state.assets = await api("/api/v1/assets");
    const workspaceId = state.context.workspace.id;
    const [summary, page, planRules, planOccurrences] = await Promise.all([
      api("/api/v1/accounts/summary"),
      api("/api/v1/transactions?limit=50"),
      api(`/api/v1/workspaces/${workspaceId}/plan-rules`),
      api(`/api/v1/workspaces/${workspaceId}/plan-occurrences`),
    ]);
    state.summary = summary;
    state.accounts = summary.accounts;
    state.transactions = page.items;
    state.nextCursor = page.next_cursor;
    state.planRules = planRules;
    state.planOccurrences = planOccurrences;
    const workspaceIds = [...new Set(state.accounts.map((account) => account.workspace_id))];
    await Promise.all([
      categoriesFor(state.context.workspace.id),
      ...workspaceIds.map((workspaceId) => categoriesFor(workspaceId)),
    ]);
    const ownedAccounts = state.accounts.filter((account) => canUseAccount(account, "owner"));
    const periodLists = await Promise.all(ownedAccounts.map(async (account) => ({
      account,
      periods: await api(`/api/v1/accounts/${account.id}/periods?scope=all`),
    })));
    state.transactionPeriods = periodLists.flatMap(({ account, periods }) => (
      periods.map((period) => ({ ...period, account }))
    ));
    renderAccounts();
    renderFilterOptions();
    renderTransactions();
    renderPlan();
    renderOperationsNavigation();
  } catch (error) {
    toast(error.message);
  } finally {
    setLoading(false);
  }
}

function switchView(view, updateUrl = true) {
  const allowed = ["accounts", "transactions", "operations", "plan", "analytics"];
  state.activeView = allowed.includes(view) ? view : "accounts";
  document.querySelectorAll(".app-view").forEach((section) => section.classList.add("hidden"));
  $(`view-${state.activeView}`).classList.remove("hidden");
  document.querySelectorAll(".primary-nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.activeView);
  });
  if (state.activeView === "operations") renderOperationsNavigation();
  if (updateUrl) {
    const url = new URL(window.location.href);
    if (state.activeView === "accounts") url.searchParams.delete("view");
    else url.searchParams.set("view", state.activeView);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

const OPERATION_ACTIONS = ["spend", "add-funds", "transfer", "scan"];

function operationsStorageKey(kind) {
  return `finapp:v2:operations:${state.context?.user.id || "guest"}:${kind}`;
}

function readOperationsPreference(kind) {
  try {
    return window.localStorage.getItem(operationsStorageKey(kind));
  } catch (_error) {
    return null;
  }
}

function writeOperationsPreference(kind, value) {
  try {
    window.localStorage.setItem(operationsStorageKey(kind), String(value));
  } catch (_error) {
    // Private browsing or disabled storage must not block financial actions.
  }
}

function setOperationsAction(action, { persist = true, focus = false } = {}) {
  state.operationsAction = OPERATION_ACTIONS.includes(action) ? action : "spend";
  document.querySelectorAll("[data-operation-action]").forEach((button) => {
    const active = button.dataset.operationAction === state.operationsAction;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
    if (active && focus) button.focus();
  });
  for (const item of OPERATION_ACTIONS) {
    $(`operation-panel-${item}`).classList.toggle("hidden", item !== state.operationsAction);
  }
  if (persist) writeOperationsPreference("action", state.operationsAction);
}

function renderOperationsNavigation() {
  if (!state.context) return;
  const accountItems = state.accounts.map((account) => ({
    value: account.id,
    label: `${account.name} · ${account.asset.code}${account.is_shared ? ` · ${account.access_role}` : ""}`,
  }));
  const storedAccountId = Number(readOperationsPreference("account"));
  const currentIsValid = state.accounts.some((account) => account.id === Number(state.operationsAccountId));
  const storedIsValid = state.accounts.some((account) => account.id === storedAccountId);
  state.operationsAccountId = currentIsValid
    ? Number(state.operationsAccountId)
    : storedIsValid
      ? storedAccountId
      : state.accounts[0]?.id || null;
  selectOptions($("operations-account"), accountItems, {
    placeholder: accountItems.length ? null : "No accessible accounts",
    selected: state.operationsAccountId,
  });
  $("operations-account").disabled = !accountItems.length;
  if (state.operationsAccountId !== null) {
    $("operations-account").value = String(state.operationsAccountId);
    writeOperationsPreference("account", state.operationsAccountId);
  }
  const storedAction = readOperationsPreference("action");
  const action = OPERATION_ACTIONS.includes(state.operationsAction)
    && state.operationsAction !== "spend"
    ? state.operationsAction
    : OPERATION_ACTIONS.includes(storedAction)
      ? storedAction
      : "spend";
  setOperationsAction(action, { persist: false });
  void renderOperationsForms();
  void loadOperationsPeriods();
  void loadOperationsUndoCandidate();
}

function selectedOperationsAccount() {
  return accountById(state.operationsAccountId);
}

function renderOperationsUndo() {
  const candidate = state.operationsUndoCandidate;
  const button = $("operations-undo");
  button.classList.toggle("hidden", !candidate);
  button.disabled = state.operationsUndoLoading || !candidate;
  button.textContent = candidate
    ? `↶ Undo ${candidate.type.replaceAll("_", " ")}`
    : "↶ Undo";
  button.setAttribute(
    "aria-label",
    candidate ? `Undo latest ${candidate.type} operation` : "No operation to undo",
  );
}

async function loadOperationsUndoCandidate() {
  const account = selectedOperationsAccount();
  const accountId = account?.id || null;
  const requestId = ++state.operationsUndoRequestId;
  state.operationsUndoCandidate = null;
  state.operationsUndoLoading = Boolean(account);
  renderOperationsUndo();
  if (!account) return;
  try {
    const candidate = await api(`/api/v1/operations/accounts/${accountId}/undo`);
    if (
      requestId !== state.operationsUndoRequestId
      || selectedOperationsAccount()?.id !== accountId
    ) return;
    state.operationsUndoCandidate = candidate;
  } catch (error) {
    if (
      requestId === state.operationsUndoRequestId
      && selectedOperationsAccount()?.id === accountId
      && ![403, 404].includes(error.status)
    ) toast(error.message);
  } finally {
    if (
      requestId === state.operationsUndoRequestId
      && selectedOperationsAccount()?.id === accountId
    ) {
      state.operationsUndoLoading = false;
      renderOperationsUndo();
    }
  }
}

async function undoLatestOperation() {
  const account = selectedOperationsAccount();
  const transaction = state.operationsUndoCandidate;
  if (
    !account
    || !transaction
    || !window.confirm(`Undo your latest ${transaction.type} operation? Balances and periods will be recalculated.`)
  ) return;
  state.operationsUndoLoading = true;
  renderOperationsUndo();
  try {
    await api(`/api/v1/operations/accounts/${account.id}/undo`, {
      method: "POST",
      body: JSON.stringify({
        transaction_id: transaction.id,
        confirm_ended_period: true,
      }),
    });
    state.operationsUndoCandidate = null;
    renderOperationsUndo();
    toast("Operation undone");
    await refreshAll();
    switchView("operations");
  } catch (error) {
    toast(error.message);
    await loadOperationsUndoCandidate();
  } finally {
    state.operationsUndoLoading = false;
    renderOperationsUndo();
  }
}

async function updateOperationsCategories(account) {
  if (!account) return;
  const accountId = account.id;
  const categories = await categoriesFor(account.workspace_id);
  if (selectedOperationsAccount()?.id !== accountId) return;
  const choices = (kind) => categories
    .filter((category) => !category.archived_at && [kind, "both"].includes(category.kind))
    .map((category) => ({ value: category.id, label: category.name }));
  selectOptions($("operations-spend-category"), choices("expense"), { placeholder: "Uncategorized" });
  selectOptions($("operations-add-category"), choices("income"), { placeholder: "Uncategorized" });
}

function updateOperationsTransferMode() {
  const source = selectedOperationsAccount();
  const target = accountById($("operations-transfer-to").value);
  const exchange = Boolean(source && target && source.asset.id !== target.asset.id);
  $("operations-transfer-amount").required = !exchange;
  $("operations-exchange-from").required = exchange;
  $("operations-exchange-to").required = exchange;
  $("operations-fee-account").required = exchange && $("operations-has-fee").checked;
  $("operations-fee-amount").required = exchange && $("operations-has-fee").checked;
  $("operations-transfer-amount-field").classList.toggle("hidden", exchange);
  $("operations-exchange-from-field").classList.toggle("hidden", !exchange);
  $("operations-exchange-to-field").classList.toggle("hidden", !exchange);
  $("operations-fee").classList.toggle("hidden", !exchange);
  if (!exchange) {
    $("operations-has-fee").checked = false;
    $("operations-fee-fields").classList.add("hidden");
  }
  $("operations-transfer-mode").textContent = !source || !target
    ? "Choose a destination account."
    : exchange
      ? `Cross-asset exchange · ${source.asset.code} → ${target.asset.code}`
      : `Same-asset transfer · ${source.asset.code}`;
  $("operations-transfer-submit").textContent = exchange ? "Save exchange" : "Save transfer";
}

function setOperationsCommandLoading(value) {
  state.operationsCommandLoading = value;
  for (const id of ["operations-spend-form", "operations-add-form", "operations-transfer-form"]) {
    $(id).setAttribute("aria-busy", String(value));
  }
  for (const id of ["operations-spend-submit", "operations-add-submit", "operations-transfer-submit"]) {
    if (value) $(id).disabled = true;
  }
  if (!value) {
    const account = selectedOperationsAccount();
    const hasTarget = state.accounts.some((item) => (
      account
      && item.id !== account.id
      && item.workspace_id === account.workspace_id
      && canUseAccount(item, "edit")
    ));
    $("operations-spend-submit").disabled = !canUseAccount(account, "expense");
    $("operations-add-submit").disabled = !canUseAccount(account, "income");
    $("operations-transfer-submit").disabled = !canUseAccount(account, "edit") || !hasTarget;
  }
}

async function renderOperationsForms() {
  const account = selectedOperationsAccount();
  for (const id of ["operations-spend-date", "operations-add-date", "operations-transfer-date"]) {
    if (!$(id).value) $(id).value = todayValue();
  }
  const spendAllowed = canUseAccount(account, "expense");
  const incomeAllowed = canUseAccount(account, "income");
  const transferAllowed = canUseAccount(account, "edit");
  $("operations-spend-submit").disabled = state.operationsCommandLoading || !spendAllowed;
  $("operations-add-submit").disabled = state.operationsCommandLoading || !incomeAllowed;
  $("operations-spend-error").textContent = account && !spendAllowed ? "You cannot record spending on this account." : "";
  $("operations-add-error").textContent = account && !incomeAllowed ? "You cannot add funds to this account." : "";

  const targets = state.accounts.filter((item) => (
    account
    && item.id !== account.id
    && item.workspace_id === account.workspace_id
    && canUseAccount(item, "edit")
  ));
  selectOptions($("operations-transfer-to"), targets.map((item) => ({
    value: item.id,
    label: `${item.name} · ${item.asset.code}`,
  })), { placeholder: targets.length ? "Choose destination" : "No eligible destination" });
  const feeAccounts = state.accounts.filter((item) => (
    account
    && item.workspace_id === account.workspace_id
    && canUseAccount(item, "edit")
  ));
  selectOptions($("operations-fee-account"), feeAccounts.map((item) => ({
    value: item.id,
    label: `${item.name} · ${item.asset.code}`,
  })), { placeholder: "Choose fee account", selected: account?.id });
  $("operations-transfer-submit").disabled = state.operationsCommandLoading || !transferAllowed || !targets.length;
  $("operations-transfer-error").textContent = account && !transferAllowed ? "You cannot transfer from this account." : "";
  updateOperationsTransferMode();
  try {
    await updateOperationsCategories(account);
  } catch (error) {
    toast(error.message);
  }
}

function currentOperationsPeriod() {
  return state.operationsPeriods.find((period) => period.status === "current") || null;
}

function renderOperationsPeriodHistory() {
  const account = selectedOperationsAccount();
  $("period-history-account").textContent = account
    ? `${account.name} · ${account.asset.code}`
    : "No account selected";
  const nodes = state.operationsPeriods.map((period) => {
    const row = document.createElement("article");
    row.className = "period-history-row";
    row.innerHTML = `
      <div><strong>${localDate(period.start_date)} – ${localDate(period.end_date)}</strong><span>${escapeHtml(period.status)} · Funding ${escapeHtml(formatMoney(period.funding_amount, period.asset.code))} · Remaining ${escapeHtml(formatMoney(period.remaining, period.asset.code))}</span></div>
      <div class="period-actions"></div>`;
    const actions = row.querySelector(".period-actions");
    if (period.status !== "closed") {
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "button-secondary";
      edit.textContent = "Edit";
      edit.disabled = state.periodCommandLoading;
      edit.addEventListener("click", () => openPeriodDialog(period));
      const close = document.createElement("button");
      close.type = "button";
      close.className = "button-secondary";
      close.textContent = "Close";
      close.disabled = state.periodCommandLoading;
      close.addEventListener("click", () => closeOperationsPeriod(period));
      actions.append(edit, close);
    }
    return row;
  });
  $("period-history-list").replaceChildren(...nodes);
  $("period-history-empty").classList.toggle("hidden", nodes.length > 0);
}

function renderOperationsPeriod() {
  const account = selectedOperationsAccount();
  const owner = canUseAccount(account, "owner");
  const current = owner ? currentOperationsPeriod() : null;
  const ready = owner
    && !state.operationsPeriodLoading
    && !state.operationsPeriodError
    && !state.periodCommandLoading;
  const unavailable = !current;
  $("operations-period").setAttribute(
    "aria-busy",
    String(state.operationsPeriodLoading || state.periodCommandLoading),
  );
  $("operations-period-available").textContent = unavailable
    ? "N/A"
    : formatMoney(current.available_today, current.asset.code);
  $("operations-period-remaining").textContent = unavailable
    ? "N/A"
    : formatMoney(current.remaining, current.asset.code);
  $("operations-period-planned").textContent = unavailable
    ? "N/A"
    : formatMoney(current.planned, current.asset.code);
  $("operations-add-period").classList.toggle("hidden", !ready || Boolean(current));
  $("operations-edit-period").classList.toggle("hidden", !ready || !current);
  $("operations-close-period").classList.toggle("hidden", !ready || !current);
  $("operations-period-history").classList.toggle("hidden", !ready);
  $("operations-period-retry").classList.toggle("hidden", !owner || !state.operationsPeriodError);
  if (!account) {
    $("operations-period-status").textContent = "Select an account to see its period.";
  } else if (!owner) {
    $("operations-period-status").textContent = "Period information is available only to the account owner.";
  } else if (state.operationsPeriodLoading) {
    $("operations-period-status").textContent = "Loading period…";
  } else if (state.operationsPeriodError) {
    $("operations-period-status").textContent = "Period data could not be loaded. Try again.";
  } else if (current) {
    $("operations-period-status").textContent = `${localDate(current.start_date)} – ${localDate(current.end_date)} · Funding ${formatMoney(current.funding_amount, current.asset.code)}`;
  } else {
    const upcoming = state.operationsPeriods.filter((period) => period.status === "upcoming").length;
    $("operations-period-status").textContent = upcoming
      ? `No current period · ${upcoming} upcoming`
      : "No current period. Add one when you are ready.";
  }
  renderOperationsPeriodHistory();
}

async function loadOperationsPeriods() {
  const account = selectedOperationsAccount();
  const requestedAccountId = account?.id || null;
  const requestId = ++state.operationsPeriodRequestId;
  state.operationsPeriodAccountId = requestedAccountId;
  state.operationsPeriods = [];
  state.operationsPeriodError = null;
  state.operationsPeriodLoading = Boolean(account && canUseAccount(account, "owner"));
  renderOperationsPeriod();
  if (!state.operationsPeriodLoading) return;
  try {
    const periods = await api(`/api/v1/accounts/${requestedAccountId}/periods?scope=all`);
    if (
      requestId !== state.operationsPeriodRequestId
      || selectedOperationsAccount()?.id !== requestedAccountId
    ) return;
    state.operationsPeriods = periods;
  } catch (error) {
    if (
      requestId === state.operationsPeriodRequestId
      && selectedOperationsAccount()?.id === requestedAccountId
    ) state.operationsPeriodError = error.message;
  } finally {
    if (
      requestId === state.operationsPeriodRequestId
      && selectedOperationsAccount()?.id === requestedAccountId
    ) {
      state.operationsPeriodLoading = false;
      renderOperationsPeriod();
    }
  }
}

function openPeriodDialog(period = null) {
  const account = selectedOperationsAccount();
  if (!account || !canUseAccount(account, "owner") || state.periodCommandLoading) return;
  if ($("period-history-dialog").open) $("period-history-dialog").close();
  $("period-id").value = period?.id || "";
  $("period-account-id").value = account.id;
  $("period-dialog-title").textContent = period ? "Edit period" : "Add period";
  $("period-account-name").textContent = `${account.name} · ${account.asset.code}`;
  $("period-start").value = period?.start_date || todayValue();
  $("period-end").value = period?.end_date || dateValueAfter(todayValue(), 29);
  $("period-funding").value = period?.funding_amount ?? account.balance;
  $("period-error").textContent = "";
  $("period-dialog").showModal();
}

async function saveOperationsPeriod(event) {
  event.preventDefault();
  if (state.periodCommandLoading) return;
  $("period-error").textContent = "";
  try {
    const periodId = $("period-id").value;
    const accountId = Number(requiredValue("period-account-id", "Account"));
    if (selectedOperationsAccount()?.id !== accountId) throw new Error("Selected account changed");
    const body = {
      start_date: requiredValue("period-start", "Start date"),
      end_date: requiredValue("period-end", "End date"),
      funding_amount: requiredValue("period-funding", "Funding amount"),
    };
    setPeriodCommandLoading(true);
    if (periodId) {
      await apiWithEndedPeriodConfirmation(
        `/api/v1/account-periods/${periodId}`,
        "PATCH",
        body,
        "This period needs explicit confirmation. Continue?",
      );
    } else {
      await apiCommand(`/api/v1/accounts/${accountId}/periods`, "POST", body);
    }
    $("period-dialog").close();
    toast(periodId ? "Period updated" : "Period added");
    await loadOperationsPeriods();
  } catch (error) {
    $("period-error").textContent = error.message;
  } finally {
    setPeriodCommandLoading(false);
  }
}

async function closeOperationsPeriod(period) {
  if (
    !period
    || state.periodCommandLoading
    || !window.confirm("Close this period? Closed periods are read-only.")
  ) return;
  setPeriodCommandLoading(true);
  try {
    await api(`/api/v1/account-periods/${period.id}/close`, { method: "POST" });
    toast("Period closed");
    await loadOperationsPeriods();
  } catch (error) {
    toast(error.message);
  } finally {
    setPeriodCommandLoading(false);
  }
}

function setPeriodCommandLoading(value) {
  state.periodCommandLoading = value;
  $("period-form").setAttribute("aria-busy", String(value));
  $("period-save").disabled = value;
  renderOperationsPeriod();
}

function openPeriodHistory() {
  if (
    !canUseAccount(selectedOperationsAccount(), "owner")
    || state.periodCommandLoading
  ) return;
  renderOperationsPeriodHistory();
  $("period-history-dialog").showModal();
}

async function saveOperationsSingle(event, kind) {
  event.preventDefault();
  if (state.operationsCommandLoading) return;
  const prefix = kind === "spend" ? "operations-spend" : "operations-add";
  const account = selectedOperationsAccount();
  $(`${prefix}-error`).textContent = "";
  if (!account) return $(`${prefix}-error`).textContent = "Choose an account.";
  try {
    const body = {
      account_id: account.id,
      amount: requiredValue(`${prefix}-amount`, "Amount"),
      category_id: $(`${prefix}-category`).value ? Number($(`${prefix}-category`).value) : null,
      local_date: $(`${prefix}-date`).value || null,
      note: $(`${prefix}-note`).value.trim() || null,
    };
    const route = kind === "spend"
      ? "/api/v1/operations/spend"
      : "/api/v1/operations/add-funds";
    setOperationsCommandLoading(true);
    await apiWithEndedPeriodConfirmation(
      route,
      "POST",
      body,
    );
    $(`${prefix}-amount`).value = "";
    $(`${prefix}-note`).value = "";
    toast(kind === "spend" ? "Spending saved" : "Funds added");
    await refreshAll();
    switchView("operations");
  } catch (error) {
    $(`${prefix}-error`).textContent = error.message;
  } finally {
    setOperationsCommandLoading(false);
  }
}

async function saveOperationsTransfer(event) {
  event.preventDefault();
  if (state.operationsCommandLoading) return;
  $("operations-transfer-error").textContent = "";
  const source = selectedOperationsAccount();
  const target = accountById($("operations-transfer-to").value);
  if (!source || !target) return $("operations-transfer-error").textContent = "Choose both accounts.";
  try {
    const exchange = source.asset.id !== target.asset.id;
    const body = {
      from_account_id: source.id,
      to_account_id: target.id,
      local_date: $("operations-transfer-date").value || null,
      note: $("operations-transfer-note").value.trim() || null,
    };
    let route = "/api/v1/operations/transfer";
    if (exchange) {
      route = "/api/v1/operations/exchange";
      body.from_amount = requiredValue("operations-exchange-from", "From amount");
      body.to_amount = requiredValue("operations-exchange-to", "To amount");
      if ($("operations-has-fee").checked) {
        body.fee = {
          account_id: Number(requiredValue("operations-fee-account", "Fee account")),
          amount: requiredValue("operations-fee-amount", "Fee amount"),
        };
      }
    } else {
      body.amount = requiredValue("operations-transfer-amount", "Amount");
    }
    setOperationsCommandLoading(true);
    await apiWithEndedPeriodConfirmation(route, "POST", body);
    for (const id of ["operations-transfer-amount", "operations-exchange-from", "operations-exchange-to", "operations-fee-amount", "operations-transfer-note"]) $(id).value = "";
    $("operations-has-fee").checked = false;
    $("operations-fee-fields").classList.add("hidden");
    toast(exchange ? "Exchange saved" : "Transfer saved");
    await refreshAll();
    switchView("operations");
  } catch (error) {
    $("operations-transfer-error").textContent = error.message;
  } finally {
    setOperationsCommandLoading(false);
  }
}

function accountGroup(account) {
  if (["reserve", "savings"].includes(account.purpose)) return "Savings";
  if (account.asset.kind === "crypto" || ["crypto_wallet", "exchange"].includes(account.storage_type)) return "Crypto";
  if (account.storage_type === "cash") return "Cash";
  return "Banks & cards";
}

function accountIcon(account) {
  if (["reserve", "savings"].includes(account.purpose)) return "◇";
  if (account.asset.kind === "crypto") return "₿";
  if (account.storage_type === "cash") return "¤";
  return "▣";
}

function renderAccounts() {
  if (!state.summary) return;
  const base = state.summary.base_asset.code;
  $("net-worth").textContent = formatMoney(state.summary.net_worth, base);
  $("available-total").textContent = formatMoney(state.summary.available, base);
  $("net-worth-code").textContent = `Valued in ${base} across visible accounts`;
  const unvalued = state.summary.unvalued;
  $("unvalued-warning").classList.toggle("hidden", !unvalued.length);
  $("unvalued-warning").textContent = unvalued.length
    ? `Not included in totals — no exchange rate yet: ${unvalued.map((item) => formatMoney(item.total, item.asset.code)).join(", ")}. Add an exchange to establish a rate.`
    : "";

  const grouped = new Map();
  for (const account of state.accounts) {
    const group = accountGroup(account);
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group).push(account);
  }
  const order = ["Banks & cards", "Cash", "Crypto", "Savings"];
  const sections = [];
  for (const group of order) {
    const accounts = grouped.get(group) || [];
    if (!accounts.length) continue;
    const section = document.createElement("section");
    section.className = "account-group";
    section.innerHTML = `<div class="group-heading"><h3>${group}</h3><span>${accounts.length} ${accounts.length === 1 ? "account" : "accounts"}</span></div><div class="account-grid"></div>`;
    const grid = section.querySelector(".account-grid");
    for (const account of accounts) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "account-card";
      button.dataset.accountId = account.id;
      const valued = account.valued_balance === null
        ? "Not valued"
        : formatMoney(account.valued_balance, base);
      button.innerHTML = `
        <span class="account-top"><span class="account-icon">${accountIcon(account)}</span>${account.is_shared ? `<span class="badge shared">${escapeHtml(account.access_role)}</span>` : ""}</span>
        <span class="account-name">${escapeHtml(account.name)}</span>
        <strong>${formatMoney(account.balance, account.asset.code)}</strong>
        <small>${account.include_in_available ? valued : `Protected · ${valued}`}</small>`;
      button.addEventListener("click", () => openAccountDetail(account.id));
      grid.append(button);
    }
    sections.push(section);
  }
  $("account-groups").replaceChildren(...sections);
  $("accounts-empty").classList.toggle("hidden", state.accounts.length > 0);
}

function renderFilterOptions() {
  const selectedAccount = $("filter-account").value;
  const selectedPeriod = $("filter-period").value;
  const selectedCategory = $("filter-category")?.value || "";
  const items = state.accounts.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}` }));
  selectOptions($("filter-account"), items, { placeholder: "All accounts", selected: selectedAccount });
  selectOptions($("filter-period"), state.transactionPeriods.map((period) => ({
    value: period.id,
    label: `${period.account.name} · ${localDate(period.start_date)} – ${localDate(period.end_date)} · ${period.status}`,
  })), { placeholder: "All periods", selected: selectedPeriod });
  const visibleWorkspaceIds = new Set([
    state.context.workspace.id,
    ...state.accounts.map((account) => account.workspace_id),
  ]);
  const categories = [...visibleWorkspaceIds].flatMap(
    (workspaceId) => state.categories.get(workspaceId) || []
  );
  const unique = [...new Map(categories.map((category) => [category.id, category])).values()];
  if ($("filter-category")) {
    selectOptions($("filter-category"), unique.map((category) => ({
      value: category.id,
      label: `${category.name}${category.archived_at ? " (archived)" : ""}`,
    })), { placeholder: "All categories", selected: selectedCategory });
  }
  if ($("filter-period").value) syncTransactionFilterPair("period");
}

function syncTransactionFilterPair(changed) {
  const period = state.transactionPeriods.find(
    (item) => item.id === Number($("filter-period").value),
  );
  if (changed === "period" && period) {
    $("filter-account").value = String(period.account_id);
  } else if (
    changed === "account"
    && period
    && Number($("filter-account").value) !== period.account_id
  ) {
    $("filter-period").value = "";
  }
}

async function openAccountDetail(accountId) {
  const account = accountById(accountId);
  if (!account) return;
  state.activeAccount = account;
  $("account-detail-title").textContent = account.name;
  $("account-detail-body").innerHTML = `<div class="empty-state"><p>Loading account history…</p></div>`;
  $("account-detail-dialog").showModal();
  try {
    const page = await api(`/api/v1/transactions?account_id=${account.id}&limit=10`);
    const canEdit = canUseAccount(account, "edit");
    const isOwner = account.access_role === "owner";
    const actions = [
      canEdit ? `<button type="button" data-account-action="edit">Edit details</button>` : "",
      isOwner ? `<button type="button" class="button-secondary" data-account-action="reconcile">Reconcile</button>` : "",
      isOwner ? `<button type="button" class="button-secondary" data-account-action="share">Share</button>` : "",
      isOwner ? `<button type="button" class="button-danger" data-account-action="archive">Archive</button>` : "",
      `<button type="button" class="button-secondary" data-account-action="history">Full history</button>`,
    ].join("");
    const history = page.items.length
      ? page.items.map((transaction) => `<div class="mini-transaction"><span><strong>${escapeHtml(transactionTitle(transaction))}</strong><br><small>${localDate(transaction.local_date)}</small></span><strong>${transactionAmount(transaction)}</strong></div>`).join("")
      : `<p class="muted">No transactions on this account.</p>`;
    $("account-detail-body").innerHTML = `
      <div class="detail-hero"><span><small>${escapeHtml(account.storage_type.replaceAll("_", " "))} · ${escapeHtml(account.purpose)}</small><br><strong>${formatMoney(account.balance, account.asset.code)}</strong></span><span class="badge ${account.is_shared ? "shared" : ""}">${escapeHtml(account.access_role)}</span></div>
      <div class="detail-actions">${actions}</div>
      <h3>Recent history</h3><div class="detail-history">${history}</div>`;
    $("account-detail-body").querySelectorAll("[data-account-action]").forEach((button) => {
      button.addEventListener("click", () => accountDetailAction(button.dataset.accountAction));
    });
  } catch (error) {
    $("account-detail-body").innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`;
  }
}

async function accountDetailAction(action) {
  const account = state.activeAccount;
  if (!account) return;
  if (action === "edit") openAccountForm(account);
  if (action === "reconcile") {
    $("reconcile-account-id").value = account.id;
    $("reconcile-balance").value = account.balance;
    $("reconcile-note").value = "";
    $("reconcile-error").textContent = "";
    $("reconcile-dialog").showModal();
  }
  if (action === "share") openSharing(account);
  if (action === "history") {
    $("account-detail-dialog").close();
    $("filter-account").value = String(account.id);
    syncTransactionFilterPair("account");
    await loadTransactions(false);
    switchView("transactions");
  }
  if (action === "archive") {
    if (!window.confirm(`Archive ${account.name}? Its history will be preserved.`)) return;
    try {
      await api(`/api/v1/accounts/${account.id}/archive`, { method: "POST" });
      $("account-detail-dialog").close();
      toast("Account archived");
      await refreshAll();
    } catch (error) { toast(error.message); }
  }
}

function openAccountForm(account = null) {
  $("account-form").reset();
  $("account-error").textContent = "";
  $("account-id").value = account ? account.id : "";
  $("account-dialog-title").textContent = account ? "Edit account" : "Add account";
  $("save-account").textContent = account ? "Save changes" : "Add account";
  selectOptions($("account-asset"), state.assets.map((asset) => ({ value: asset.code, label: `${asset.code} · ${asset.name}` })));
  $("account-asset-field").classList.toggle("hidden", Boolean(account));
  $("opening-balance-field").classList.toggle("hidden", Boolean(account));
  if (account) {
    $("account-name").value = account.name;
    $("account-storage").value = account.storage_type;
    $("account-purpose").value = account.purpose;
    $("account-institution").value = account.institution || "";
    $("account-available").checked = account.include_in_available;
  } else {
    $("account-asset").value = state.context.workspace.base_asset.code;
    $("account-opening").value = "0";
    $("account-available").checked = true;
  }
  $("account-dialog").showModal();
}

async function saveAccount(event) {
  event.preventDefault();
  $("account-error").textContent = "";
  const accountId = $("account-id").value;
  const body = {
    name: $("account-name").value.trim(),
    storage_type: $("account-storage").value,
    purpose: $("account-purpose").value,
    institution: $("account-institution").value.trim() || null,
    include_in_available: $("account-available").checked,
  };
  if (!accountId) {
    body.asset_code = $("account-asset").value;
    body.opening_balance = $("account-opening").value;
  }
  try {
    await api(accountId ? `/api/v1/accounts/${accountId}` : "/api/v1/accounts", {
      method: accountId ? "PATCH" : "POST",
      body: JSON.stringify(body),
    });
    $("account-dialog").close();
    if ($("account-detail-dialog").open) $("account-detail-dialog").close();
    toast(accountId ? "Account updated" : "Account added");
    await refreshAll();
  } catch (error) { $("account-error").textContent = error.message; }
}

async function saveReconcile(event) {
  event.preventDefault();
  $("reconcile-error").textContent = "";
  try {
    await api(`/api/v1/accounts/${$("reconcile-account-id").value}/reconcile`, {
      method: "POST",
      body: JSON.stringify({ target_balance: $("reconcile-balance").value, note: $("reconcile-note").value.trim() || null }),
    });
    $("reconcile-dialog").close();
    if ($("account-detail-dialog").open) $("account-detail-dialog").close();
    toast("Balance reconciled");
    await refreshAll();
  } catch (error) { $("reconcile-error").textContent = error.message; }
}

async function openSharing(account) {
  state.sharingAccount = account;
  $("sharing-title").textContent = `Share ${account.name}`;
  $("invite-result").classList.add("hidden");
  $("sharing-error").textContent = "";
  $("access-list").innerHTML = `<p class="muted">Loading access…</p>`;
  $("sharing-dialog").showModal();
  await loadAccess();
}

async function loadAccess() {
  try {
    const rows = await api(`/api/v1/accounts/${state.sharingAccount.id}/access`);
    const nodes = rows.map((row) => {
      const wrapper = document.createElement("div");
      wrapper.className = "access-row";
      wrapper.innerHTML = `<div><strong>${escapeHtml(row.user.display_name)}</strong><span>@${escapeHtml(row.user.username)}</span></div>`;
      if (row.role === "owner") {
        wrapper.insertAdjacentHTML("beforeend", `<span class="badge">Owner</span>`);
      } else {
        const select = document.createElement("select");
        select.setAttribute("aria-label", `Role for ${row.user.display_name}`);
        selectOptions(select, ["editor", "contributor", "viewer"].map((role) => ({ value: role, label: role[0].toUpperCase() + role.slice(1) })), { selected: row.role });
        select.addEventListener("change", async () => {
          try {
            await api(`/api/v1/accounts/${state.sharingAccount.id}/access/${row.user.id}`, { method: "PATCH", body: JSON.stringify({ role: select.value }) });
            toast("Access updated");
            await refreshAll();
          } catch (error) { toast(error.message); await loadAccess(); }
        });
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "button-danger";
        remove.textContent = "Remove";
        remove.addEventListener("click", async () => {
          if (!window.confirm(`Remove access for ${row.user.display_name}?`)) return;
          try {
            await api(`/api/v1/accounts/${state.sharingAccount.id}/access/${row.user.id}`, { method: "DELETE" });
            toast("Access removed");
            await loadAccess();
          } catch (error) { toast(error.message); }
        });
        wrapper.append(select, remove);
      }
      return wrapper;
    });
    $("access-list").replaceChildren(...nodes);
  } catch (error) { $("sharing-error").textContent = error.message; }
}

async function createInvitation(event) {
  event.preventDefault();
  $("sharing-error").textContent = "";
  try {
    const invitation = await api(`/api/v1/accounts/${state.sharingAccount.id}/invitations`, {
      method: "POST", body: JSON.stringify({ role: $("invitation-role").value }),
    });
    const invite = new URL(window.location.origin);
    invite.searchParams.set("invite", invitation.token);
    $("invite-url").value = invite.toString();
    $("invite-result").classList.remove("hidden");
  } catch (error) { $("sharing-error").textContent = error.message; }
}

async function copyInvitation() {
  try {
    await navigator.clipboard.writeText($("invite-url").value);
    toast("Invite link copied");
  } catch (_error) {
    $("invite-url").select();
    document.execCommand("copy");
    toast("Invite link copied");
  }
}

async function openCategories() {
  document.querySelector(".profile-menu").removeAttribute("open");
  $("category-name").value = "";
  $("category-error").textContent = "";
  $("categories-dialog").showModal();
  await renderCategoryManager();
}

async function renderCategoryManager() {
  const workspaceId = state.context.workspace.id;
  const categories = (await categoriesFor(workspaceId)).filter((category) => !category.archived_at);
  const nodes = categories.map((category) => {
    const row = document.createElement("div");
    row.className = "category-row";
    row.innerHTML = `<div><strong>${escapeHtml(category.name)}</strong><br><span>${escapeHtml(category.kind)}</span></div>`;
    const rename = document.createElement("button");
    rename.type = "button";
    rename.className = "button-secondary";
    rename.textContent = "Rename";
    rename.addEventListener("click", async () => {
      const name = window.prompt("Category name", category.name);
      if (!name || name.trim() === category.name) return;
      try {
        await api(`/api/v1/workspaces/${workspaceId}/categories/${category.id}`, {
          method: "PATCH", body: JSON.stringify({ name: name.trim() }),
        });
        state.categories.delete(workspaceId);
        await renderCategoryManager();
        renderFilterOptions();
        toast("Category renamed");
      } catch (error) { $("category-error").textContent = error.message; }
    });
    const archive = document.createElement("button");
    archive.type = "button";
    archive.className = "button-danger";
    archive.textContent = "Archive";
    archive.addEventListener("click", async () => {
      if (!window.confirm(`Archive ${category.name}? Existing transactions keep it.`)) return;
      try {
        await api(`/api/v1/workspaces/${workspaceId}/categories/${category.id}/archive`, { method: "POST" });
        state.categories.delete(workspaceId);
        await renderCategoryManager();
        renderFilterOptions();
        toast("Category archived");
      } catch (error) { $("category-error").textContent = error.message; }
    });
    row.append(rename, archive);
    return row;
  });
  $("category-list").replaceChildren(...nodes);
  if (!nodes.length) $("category-list").innerHTML = `<p class="muted">No categories yet.</p>`;
}

async function createCategory(event) {
  event.preventDefault();
  $("category-error").textContent = "";
  const workspaceId = state.context.workspace.id;
  try {
    await api(`/api/v1/workspaces/${workspaceId}/categories`, {
      method: "POST",
      body: JSON.stringify({ name: $("category-name").value.trim(), kind: $("category-kind").value }),
    });
    $("category-name").value = "";
    state.categories.delete(workspaceId);
    await renderCategoryManager();
    renderFilterOptions();
    toast("Category added");
  } catch (error) { $("category-error").textContent = error.message; }
}

function planKindLabel(kind) {
  return {
    income: "Upcoming income",
    required_expense: "Required spending",
    subscription: "Subscriptions",
    reserve_transfer: "Reserve transfers",
    other_expense: "Other expenses",
  }[kind] || kind;
}

function planKindIcon(kind) {
  return { income: "↑", required_expense: "!", subscription: "↻", reserve_transfer: "◇", other_expense: "↓" }[kind] || "·";
}

function planOccurrenceById(id) {
  return state.planOccurrences.find((item) => item.id === Number(id));
}

function planOccurrenceNode(occurrence) {
  const row = document.createElement("article");
  row.className = `plan-item ${occurrence.status}`;
  const actual = occurrence.actual_amount === null
    ? ""
    : `<small>Planned ${formatMoney(occurrence.planned_amount, occurrence.rule.asset.code)} · actual ${formatMoney(occurrence.actual_amount, occurrence.rule.asset.code)}</small>`;
  row.innerHTML = `
    <div class="plan-item-main"><strong>${escapeHtml(occurrence.rule.name)}</strong><span>${localDate(occurrence.due_date)} · ${escapeHtml(planKindLabel(occurrence.rule.kind))} · ${escapeHtml(occurrence.status)}</span></div>
    <div class="plan-item-amount"><strong>${formatMoney(occurrence.planned_amount, occurrence.rule.asset.code)}</strong>${actual}</div>
    <div class="plan-item-actions"></div>`;
  const actions = row.querySelector(".plan-item-actions");
  if (["planned", "overdue"].includes(occurrence.status)) {
    const link = document.createElement("button");
    link.type = "button";
    link.className = "button-secondary";
    link.textContent = "Link";
    link.addEventListener("click", () => openPlanLink({ occurrence }));
    const skip = document.createElement("button");
    skip.type = "button";
    skip.className = "button-quiet";
    skip.textContent = "Skip";
    skip.addEventListener("click", () => skipPlanOccurrence(occurrence));
    actions.append(link, skip);
  } else {
    const badge = document.createElement("span");
    badge.className = `badge ${occurrence.status}`;
    badge.textContent = occurrence.status;
    actions.append(badge);
  }
  return row;
}

function renderPlan() {
  const open = state.planOccurrences.filter((item) => ["planned", "overdue"].includes(item.status));
  const completed = state.planOccurrences.filter((item) => item.status === "completed");
  $("plan-open-count").textContent = String(open.length);
  $("plan-completed-count").textContent = String(completed.length);
  $("plan-rule-count").textContent = `${state.planRules.length} active`;
  const filter = $("plan-status-filter").value;
  let visible = state.planOccurrences;
  if (filter === "open") visible = open;
  if (filter === "completed") visible = completed;
  if (filter === "skipped") visible = state.planOccurrences.filter((item) => item.status === "skipped");

  const groups = [
    ["Overdue", visible.filter((item) => item.status === "overdue"), "!"],
    ...["income", "required_expense", "subscription", "reserve_transfer", "other_expense"].map((kind) => [
      planKindLabel(kind),
      visible.filter((item) => !["overdue", "completed", "skipped"].includes(item.status) && item.rule.kind === kind),
      planKindIcon(kind),
    ]),
    ["Completed", visible.filter((item) => item.status === "completed"), "✓"],
    ["Skipped", visible.filter((item) => item.status === "skipped"), "−"],
  ];
  const sections = groups.filter(([, items]) => items.length).map(([title, items, icon]) => {
    const section = document.createElement("section");
    section.className = "plan-group";
    section.innerHTML = `<h3><span>${icon}</span>${escapeHtml(title)}</h3><div class="plan-list"></div>`;
    const list = section.querySelector(".plan-list");
    for (const occurrence of items) list.append(planOccurrenceNode(occurrence));
    return section;
  });
  $("plan-occurrence-groups").replaceChildren(...sections);
  $("plan-empty").classList.toggle("hidden", state.planRules.length > 0);
  $("plan-occurrence-groups").classList.toggle("hidden", sections.length === 0);

  const ruleNodes = state.planRules.map((rule) => {
    const card = document.createElement("article");
    card.className = "rule-card";
    card.innerHTML = `<div><strong>${escapeHtml(rule.name)}</strong><span>${formatMoney(rule.amount, rule.asset.code)} · ${escapeHtml(rule.recurrence)} · from ${localDate(rule.first_due_date)}</span></div><div class="rule-actions"></div>`;
    const actions = card.querySelector(".rule-actions");
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "Edit";
    edit.title = "Edit rule";
    edit.addEventListener("click", () => openPlanRule(rule));
    const archive = document.createElement("button");
    archive.type = "button";
    archive.textContent = "×";
    archive.title = "Archive rule";
    archive.addEventListener("click", () => archivePlanRule(rule));
    actions.append(edit, archive);
    return card;
  });
  $("plan-rule-list").replaceChildren(...ruleNodes);
  $("plan-rules-section").classList.toggle("hidden", state.planRules.length === 0);
}

async function apiCommand(path, method, body) {
  return api(path, { method, body: JSON.stringify(body) });
}

async function apiWithEndedPeriodConfirmation(
  path,
  method,
  body,
  confirmation = "This transaction needs explicit confirmation. Continue?",
) {
  try {
    return await apiCommand(path, method, body);
  } catch (error) {
    if (
      error.status !== 409
      || !String(error.message).includes("explicit confirmation")
      || !window.confirm(confirmation)
    ) throw error;
    body.confirm_ended_period = true;
    return apiCommand(path, method, body);
  }
}

function ownedPlanAccounts(assetCode = null) {
  return state.accounts.filter((account) => (
    account.workspace_id === state.context.workspace.id
    && account.access_role === "owner"
    && (!assetCode || account.asset.code === assetCode)
  ));
}

async function updatePlanRuleFields(rule = null) {
  const kind = $("plan-rule-kind").value;
  const assetCode = $("plan-rule-asset").value;
  const accounts = ownedPlanAccounts(assetCode).map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}` }));
  selectOptions($("plan-rule-from-account"), accounts, {
    placeholder: "Choose source",
    selected: rule?.default_from_account_id ?? $("plan-rule-from-account").value,
  });
  selectOptions($("plan-rule-to-account"), accounts, {
    placeholder: "Choose target",
    selected: rule?.default_to_account_id ?? $("plan-rule-to-account").value,
  });
  const selectedCategoryId = Number(rule?.category_id ?? $("plan-rule-category").value);
  const categories = (await categoriesFor(state.context.workspace.id)).filter((category) => {
    const expected = kind === "income" ? "income" : "expense";
    const selected = category.id === selectedCategoryId;
    return selected || (!category.archived_at && (category.kind === "both" || category.kind === expected));
  });
  selectOptions($("plan-rule-category"), categories.map((category) => ({
    value: category.id,
    label: `${category.name}${category.archived_at ? " (archived)" : ""}`,
    disabled: Boolean(category.archived_at),
  })), {
    placeholder: "Uncategorized",
    selected: rule?.category_id ?? $("plan-rule-category").value,
  });
  $("plan-rule-category-field").classList.toggle("hidden", kind === "reserve_transfer");
  $("plan-rule-from-field").classList.toggle("hidden", kind === "income");
  $("plan-rule-to-field").classList.toggle("hidden", !["income", "reserve_transfer"].includes(kind));
}

async function openPlanRule(rule = null) {
  $("plan-rule-form").reset();
  $("plan-rule-error").textContent = "";
  $("plan-rule-id").value = rule ? rule.id : "";
  $("plan-rule-title").textContent = rule ? "Edit rule" : "Add rule";
  $("save-plan-rule").textContent = rule ? "Save changes" : "Save rule";
  selectOptions($("plan-rule-asset"), state.assets.map((asset) => ({ value: asset.code, label: `${asset.code} · ${asset.name}` })));
  $("plan-rule-asset").value = rule ? rule.asset.code : state.context.workspace.base_asset.code;
  $("plan-rule-kind").value = rule ? rule.kind : "required_expense";
  $("plan-rule-name").value = rule ? rule.name : "";
  $("plan-rule-amount").value = rule ? rule.amount : "";
  $("plan-rule-recurrence").value = rule ? rule.recurrence : "monthly";
  $("plan-rule-date").value = rule ? rule.first_due_date : todayValue();
  $("plan-rule-required").checked = rule ? rule.is_required : true;
  await updatePlanRuleFields(rule);
  $("plan-rule-dialog").showModal();
}

async function savePlanRule(event) {
  event.preventDefault();
  $("plan-rule-error").textContent = "";
  const workspaceId = state.context.workspace.id;
  const ruleId = $("plan-rule-id").value;
  const kind = $("plan-rule-kind").value;
  const body = {
    kind,
    name: $("plan-rule-name").value.trim(),
    amount: $("plan-rule-amount").value,
    asset_code: $("plan-rule-asset").value,
    recurrence: $("plan-rule-recurrence").value,
    first_due_date: $("plan-rule-date").value,
    category_id: kind === "reserve_transfer" || !$("plan-rule-category").value ? null : Number($("plan-rule-category").value),
    default_from_account_id: kind === "income" || !$("plan-rule-from-account").value ? null : Number($("plan-rule-from-account").value),
    default_to_account_id: !["income", "reserve_transfer"].includes(kind) || !$("plan-rule-to-account").value ? null : Number($("plan-rule-to-account").value),
    is_required: $("plan-rule-required").checked,
  };
  try {
    await api(ruleId ? `/api/v1/workspaces/${workspaceId}/plan-rules/${ruleId}` : `/api/v1/workspaces/${workspaceId}/plan-rules`, {
      method: ruleId ? "PATCH" : "POST", body: JSON.stringify(body),
    });
    $("plan-rule-dialog").close();
    toast(ruleId ? "Plan rule updated" : "Plan rule added");
    await refreshAll();
    switchView("plan");
  } catch (error) { $("plan-rule-error").textContent = error.message; }
}

async function archivePlanRule(rule) {
  if (!window.confirm(`Archive ${rule.name}? Open items will be skipped.`)) return;
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/plan-rules/${rule.id}/archive`, { method: "POST" });
    toast("Plan rule archived");
    await refreshAll();
  } catch (error) { toast(error.message); }
}

async function skipPlanOccurrence(occurrence) {
  if (!window.confirm(`Skip ${occurrence.rule.name} on ${localDate(occurrence.due_date)}?`)) return;
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/plan-occurrences/${occurrence.id}/skip`, { method: "POST" });
    toast("Plan item skipped");
    await refreshAll();
  } catch (error) { toast(error.message); }
}

function transactionMatchesOccurrence(transaction, occurrence) {
  const expected = occurrence.rule.kind === "income" ? "income" : occurrence.rule.kind === "reserve_transfer" ? "transfer" : "expense";
  return transaction.type === expected
    && transaction.status === "posted"
    && !transaction.plan_occurrence_id
    && transaction.legs.length > 0
    && transaction.legs.every((leg) => leg.asset.code === occurrence.rule.asset.code);
}

async function openPlanLink({ occurrence = null, transaction = null }) {
  $("plan-link-error").textContent = "";
  const workspaceId = state.context.workspace.id;
  const page = await api(`/api/v1/transactions?workspace_id=${workspaceId}&status=posted&limit=100`);
  state.planLinkTransactions = page.items;
  let occurrences = state.planOccurrences.filter((item) => ["planned", "overdue"].includes(item.status));
  if (transaction) occurrences = occurrences.filter((item) => transactionMatchesOccurrence(transaction, item));
  let transactions = state.planLinkTransactions.filter((item) => !item.plan_occurrence_id);
  if (occurrence) transactions = transactions.filter((item) => transactionMatchesOccurrence(item, occurrence));
  selectOptions($("plan-link-occurrence"), occurrences.map((item) => ({ value: item.id, label: `${item.rule.name} · ${localDate(item.due_date)} · ${formatMoney(item.planned_amount, item.rule.asset.code)}` })), { placeholder: "Choose plan item", selected: occurrence?.id });
  selectOptions($("plan-link-transaction"), transactions.map((item) => ({ value: item.id, label: `#${item.id} · ${transactionTitle(item)} · ${localDate(item.local_date)} · ${transactionAmount(item)}` })), { placeholder: "Choose transaction", selected: transaction?.id });
  $("plan-link-dialog").showModal();
}

async function linkPlanTransaction(event) {
  event.preventDefault();
  $("plan-link-error").textContent = "";
  const occurrenceId = $("plan-link-occurrence").value;
  const transactionId = $("plan-link-transaction").value;
  if (!occurrenceId || !transactionId) {
    $("plan-link-error").textContent = "Choose both a plan item and a transaction";
    return;
  }
  try {
    await apiWithEndedPeriodConfirmation(
      `/api/v1/workspaces/${state.context.workspace.id}/plan-occurrences/${occurrenceId}/link-transaction`,
      "POST",
      { transaction_id: Number(transactionId) },
    );
    $("plan-link-dialog").close();
    toast("Transaction linked to Plan");
    await refreshAll();
  } catch (error) { $("plan-link-error").textContent = error.message; }
}

function transactionTitle(transaction) {
  const category = [...state.categories.values()].flat().find((item) => item.id === transaction.category_id);
  if (transaction.note) return transaction.note;
  if (transaction.counterparty) return transaction.counterparty;
  if (category) return `${category.name}${category.archived_at ? " (archived)" : ""}`;
  return transaction.type[0].toUpperCase() + transaction.type.slice(1);
}

function transactionAmount(transaction) {
  const legs = transaction.legs;
  if (!legs.length) return "Hidden";
  if (["expense", "income", "adjustment"].includes(transaction.type)) {
    const leg = legs[0];
    const prefix = transaction.type === "income" || (transaction.type === "adjustment" && !String(leg.amount).startsWith("-")) ? "+" : "";
    return `${prefix}${formatMoney(leg.amount, leg.asset.code)}`;
  }
  const negative = legs.find((leg) => String(leg.amount).startsWith("-"));
  const positive = legs.find((leg) => !String(leg.amount).startsWith("-"));
  if (negative && positive) return `${formatMoney(negative.amount, negative.asset.code)} → ${formatMoney(positive.amount, positive.asset.code)}`;
  const leg = legs[0];
  return `${formatMoney(leg.amount, leg.asset.code)} · partial`;
}

function canEditTransaction(transaction) {
  if (transaction.status === "deleted" || transaction.has_hidden_legs) return false;
  if (!transaction.legs.length) return false;
  return transaction.legs.every((leg) => {
    if (leg.account_id === null) return transaction.created_by_user_id === state.context.user.id;
    const account = accountById(leg.account_id);
    return transaction.type === "adjustment" ? canUseAccount(account, "owner") : canUseAccount(account, "edit");
  });
}

function openTransactionDetails(transaction) {
  state.viewingTransaction = transaction;
  const author = transaction.created_by_user_id === state.context.user.id
    ? "You"
    : `User #${transaction.created_by_user_id}`;
  const movements = transaction.legs.length
    ? transaction.legs.map((leg) => {
      const account = accountById(leg.account_id);
      const accountName = account ? account.name : leg.account_id === null ? "Unassigned" : "Accessible account";
      return `<li><span>${escapeHtml(accountName)}</span><strong>${formatMoney(leg.amount, leg.asset.code)}</strong></li>`;
    }).join("")
    : "<li><span>No visible movements</span></li>";
  $("transaction-detail-body").innerHTML = `
    <dl class="transaction-detail-grid">
      <div><dt>Status</dt><dd>${escapeHtml(transaction.status[0].toUpperCase() + transaction.status.slice(1))}</dd></div>
      <div><dt>Type</dt><dd>${escapeHtml(transaction.type[0].toUpperCase() + transaction.type.slice(1))}</dd></div>
      <div><dt>Financial date</dt><dd>${escapeHtml(localDate(transaction.local_date))}</dd></div>
      <div><dt>Created by</dt><dd>${escapeHtml(author)}</dd></div>
      <div><dt>Amount</dt><dd>${transactionAmount(transaction)}</dd></div>
      <div><dt>Counterparty</dt><dd>${escapeHtml(transaction.counterparty || "—")}</dd></div>
      <div class="span-two"><dt>Note</dt><dd>${escapeHtml(transaction.note || "—")}</dd></div>
    </dl>
    <h3>Visible movements</h3><ul class="transaction-detail-legs">${movements}</ul>`;
  $("transaction-detail-hidden").classList.toggle("hidden", !transaction.has_hidden_legs);
  $("correct-transaction").classList.toggle("hidden", !canEditTransaction(transaction));
  $("correct-transaction").disabled = !canEditTransaction(transaction);
  $("transaction-detail-dialog").showModal();
}

function renderTransactions() {
  const nodes = state.transactions.map((transaction) => {
    const row = document.createElement("article");
    row.className = `transaction-row ${transaction.type}`;
    const icon = { expense: "↓", income: "↑", transfer: "⇄", exchange: "↻", adjustment: "±" }[transaction.type];
    const author = transaction.created_by_user_id === state.context.user.id ? "You" : `User #${transaction.created_by_user_id}`;
    row.innerHTML = `
      <span class="transaction-icon" aria-hidden="true">${icon}</span>
      <span class="transaction-main"><strong>${escapeHtml(transactionTitle(transaction))}</strong><span>${localDate(transaction.local_date)} · ${author}${transaction.has_hidden_legs ? ` · <span class="hidden-leg">hidden movement</span>` : ""}</span></span>
      <span class="transaction-amount">${transactionAmount(transaction)}</span>
      <span class="transaction-actions"></span>`;
    const actions = row.querySelector(".transaction-actions");
    const details = document.createElement("button");
    details.type = "button";
    details.textContent = "Details";
    details.addEventListener("click", () => openTransactionDetails(transaction));
    actions.append(details);
    if (transaction.status === "unassigned" && transaction.created_by_user_id === state.context.user.id) {
      const assign = document.createElement("button");
      assign.type = "button";
      assign.textContent = "Assign";
      assign.addEventListener("click", () => assignTransaction(transaction));
      actions.append(assign);
    }
    if (canEditTransaction(transaction)) {
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "icon-button transaction-delete";
      deleteButton.textContent = "×";
      deleteButton.title = "Delete";
      deleteButton.setAttribute("aria-label", `Delete ${transaction.type} transaction`);
      deleteButton.disabled = state.transactionDeleteLoading;
      deleteButton.addEventListener("click", () => deleteTransaction(transaction, deleteButton, row));
      actions.append(deleteButton);
    }
    if (transaction.plan_occurrence_id) {
      const planBadge = document.createElement("span");
      planBadge.className = "badge";
      planBadge.textContent = "Plan";
      actions.prepend(planBadge);
    } else if (
      transaction.workspace_id === state.context.workspace.id
      && transaction.status === "posted"
      && ["expense", "income", "transfer"].includes(transaction.type)
    ) {
      const linkPlan = document.createElement("button");
      linkPlan.type = "button";
      linkPlan.textContent = "Plan";
      linkPlan.addEventListener("click", () => openPlanLink({ transaction }));
      actions.append(linkPlan);
    }
    if (transaction.status !== "posted") {
      const badge = document.createElement("span");
      badge.className = `badge ${transaction.status}`;
      badge.textContent = transaction.status[0].toUpperCase() + transaction.status.slice(1);
      actions.prepend(badge);
    }
    return row;
  });
  $("transaction-list").replaceChildren(...nodes);
  $("transactions-empty").classList.toggle("hidden", state.transactions.length > 0);
  $("load-more").classList.toggle("hidden", !state.nextCursor);
}

function transactionQuery(cursor = null) {
  const query = new URLSearchParams({ limit: "50" });
  const values = {
    account_id: $("filter-account").value,
    period_id: $("filter-period").value,
    type: $("filter-type").value,
    category_id: $("filter-category")?.value || "",
    status: $("filter-status")?.value || "",
    date_from: $("filter-from").value,
    date_to: $("filter-to").value,
  };
  for (const [key, value] of Object.entries(values)) if (value) query.set(key, value);
  if (cursor) query.set("cursor", cursor);
  return query.toString();
}

async function loadTransactions(append = false) {
  setLoading(true);
  try {
    const page = await api(`/api/v1/transactions?${transactionQuery(append ? state.nextCursor : null)}`);
    state.transactions = append ? [...state.transactions, ...page.items] : page.items;
    state.nextCursor = page.next_cursor;
    renderTransactions();
  } catch (error) { toast(error.message); }
  finally { setLoading(false); }
}

function accountItems(action) {
  return state.accounts.filter((account) => canUseAccount(account, action)).map((account) => ({
    value: account.id,
    label: `${account.name} · ${account.asset.code}${account.is_shared ? ` · ${account.access_role}` : ""}`,
  }));
}

async function updateTransactionCategories(selected = null) {
  const type = $("transaction-type").value;
  const account = accountById($("transaction-account").value);
  const workspaceId = account ? account.workspace_id : state.context.workspace.id;
  const categories = (await categoriesFor(workspaceId)).filter((category) => (
    category.id === Number(selected)
    || (!category.archived_at && (category.kind === "both" || category.kind === type))
  ));
  selectOptions($("transaction-category"), categories.map((category) => ({
    value: category.id,
    label: `${category.name}${category.archived_at ? " (archived)" : ""}`,
    disabled: Boolean(category.archived_at),
  })), { placeholder: "Uncategorized", selected });
}

async function updateTransactionFields({ preserve = true } = {}) {
  const type = $("transaction-type").value;
  const single = ["expense", "income", "adjustment"].includes(type);
  $("single-fields").classList.toggle("hidden", !single);
  $("multi-fields").classList.toggle("hidden", single);
  $("category-field").classList.toggle("hidden", !["expense", "income"].includes(type));
  $("fee-fields").classList.toggle("hidden", type !== "exchange" || Boolean(state.editingTransaction));
  $("to-amount-field").classList.toggle("hidden", type === "transfer");
  $("single-amount-field").childNodes[0].textContent = type === "adjustment" ? "Delta" : "Amount";
  $("from-amount-field").childNodes[0].textContent = type === "transfer" ? "Amount" : "From amount";

  const currentAccount = preserve ? $("transaction-account").value : "";
  const currentFrom = preserve ? $("transaction-from-account").value : "";
  const currentTo = preserve ? $("transaction-to-account").value : "";
  const action = type === "expense" ? "expense" : type === "income" ? "income" : type === "adjustment" ? "owner" : "edit";
  const singleAccounts = accountItems(action);
  selectOptions($("transaction-account"), singleAccounts, {
    placeholder: type === "adjustment" ? "Choose account" : "Unassigned",
    selected: currentAccount || (!preserve && singleAccounts.length ? singleAccounts[0].value : ""),
  });
  const editable = accountItems("edit");
  selectOptions($("transaction-from-account"), editable, {
    placeholder: "Choose account",
    selected: currentFrom || (!preserve && editable.length ? editable[0].value : ""),
  });
  selectOptions($("transaction-to-account"), editable, {
    placeholder: "Choose account",
    selected: currentTo || (!preserve && editable.length > 1 ? editable[1].value : ""),
  });
  selectOptions($("transaction-fee-account"), editable, {
    placeholder: "Choose account",
    selected: !preserve && editable.length ? editable[0].value : null,
  });
  selectOptions($("transaction-asset"), state.assets.map((asset) => ({ value: asset.code, label: `${asset.code} · ${asset.name}` })));
  if (!preserve) $("transaction-asset").value = state.context.workspace.base_asset.code;
  $("single-asset-field").classList.toggle("hidden", Boolean($("transaction-account").value) || type === "adjustment");
  if (state.editingTransaction && type === "adjustment") $("transaction-account").disabled = true;
  else $("transaction-account").disabled = false;
  await updateTransactionCategories();
}

async function openTransactionForm(transaction = null) {
  if (!transaction) return;
  state.editingTransaction = transaction;
  $("transaction-form").reset();
  $("transaction-error").textContent = "";
  $("transaction-id").value = transaction ? transaction.id : "";
  $("transaction-dialog-title").textContent = "Transaction details";
  $("save-transaction").textContent = "Save correction";
  $("transaction-type").disabled = true;
  $("transaction-type").value = transaction.type;
  $("transaction-date").value = transaction.local_date;
  await updateTransactionFields({ preserve: false });
  $("transaction-counterparty").value = transaction.counterparty || "";
  $("transaction-note").value = transaction.note || "";
  const negative = transaction.legs.find((leg) => String(leg.amount).startsWith("-"));
  const positive = transaction.legs.find((leg) => !String(leg.amount).startsWith("-"));
  if (["expense", "income", "adjustment"].includes(transaction.type)) {
    const leg = transaction.legs[0];
    $("transaction-account").value = leg.account_id === null ? "" : String(leg.account_id);
    $("transaction-asset").value = leg.asset.code;
    $("transaction-amount").value = transaction.type === "expense" ? String(leg.amount).replace("-", "") : leg.amount;
    $("single-asset-field").classList.toggle("hidden", leg.account_id !== null || transaction.type === "adjustment");
  } else if (negative && positive) {
    $("transaction-from-account").value = String(negative.account_id);
    $("transaction-to-account").value = String(positive.account_id);
    $("transaction-from-amount").value = String(negative.amount).replace("-", "");
    $("transaction-to-amount").value = positive.amount;
  }
  await updateTransactionCategories(transaction.category_id);
  $("transaction-dialog").showModal();
}

function requiredValue(id, label) {
  const value = $(id).value.trim();
  if (!value) throw new Error(`${label} is required`);
  return value;
}

async function saveTransaction(event) {
  event.preventDefault();
  $("transaction-error").textContent = "";
  const transactionId = $("transaction-id").value;
  if (!transactionId) return;
  const type = $("transaction-type").value;
  const body = {
    local_date: $("transaction-date").value || null,
    counterparty: $("transaction-counterparty").value.trim() || null,
    note: $("transaction-note").value.trim() || null,
  };
  try {
    if (["expense", "income"].includes(type)) {
      body.account_id = $("transaction-account").value ? Number($("transaction-account").value) : null;
      if (!body.account_id) body.asset_code = $("transaction-asset").value;
      body.amount = requiredValue("transaction-amount", "Amount");
      body.category_id = $("transaction-category").value ? Number($("transaction-category").value) : null;
    } else if (type === "adjustment") {
      body.account_id = Number(requiredValue("transaction-account", "Account"));
      body.delta = requiredValue("transaction-amount", "Delta");
    } else {
      body.from_account_id = Number(requiredValue("transaction-from-account", "From account"));
      body.to_account_id = Number(requiredValue("transaction-to-account", "To account"));
      if (type === "transfer") {
        const amount = requiredValue("transaction-from-amount", "Amount");
        body.from_amount = amount;
        body.to_amount = amount;
      } else {
        body.from_amount = requiredValue("transaction-from-amount", "From amount");
        body.to_amount = requiredValue("transaction-to-amount", "To amount");
      }
    }
    const route = `/api/v1/transactions/${transactionId}`;
    try {
      await apiCommand(route, "PATCH", body);
    } catch (error) {
      if (
        error.status !== 409
        || !String(error.message).includes("explicit confirmation")
        || !window.confirm("This transaction correction requires confirmation. Continue?")
      ) throw error;
      body.confirm_ended_period = true;
      await apiCommand(route, "PATCH", body);
    }
    $("transaction-dialog").close();
    toast("Transaction updated");
    await refreshAll();
  } catch (error) { $("transaction-error").textContent = error.message; }
}

async function assignTransaction(transaction) {
  const choices = state.accounts.filter((account) => account.asset.code === transaction.legs[0].asset.code && canUseAccount(account, transaction.type === "expense" ? "expense" : "income"));
  if (!choices.length) return toast(`No accessible ${transaction.legs[0].asset.code} account`);
  const labels = choices.map((account) => `${account.id}: ${account.name}`).join("\n");
  const value = window.prompt(`Assign to an account:\n${labels}`, String(choices[0].id));
  if (!value) return;
  try {
    await api(`/api/v1/transactions/${transaction.id}/assign-account`, { method: "POST", body: JSON.stringify({ account_id: Number(value) }) });
    toast("Transaction assigned");
    await refreshAll();
  } catch (error) { toast(error.message); }
}

async function deleteTransaction(transaction, button, row) {
  if (state.transactionDeleteLoading) return;
  if (!window.confirm(`Delete this ${transaction.type}? It will remain in history as Deleted but will no longer affect balances or periods.`)) return;
  state.transactionDeleteLoading = true;
  document.querySelectorAll(".transaction-delete").forEach((item) => { item.disabled = true; });
  button.disabled = true;
  row.setAttribute("aria-busy", "true");
  try {
    try {
      await api(`/api/v1/transactions/${transaction.id}/delete`, { method: "POST" });
    } catch (error) {
      if (
        error.status !== 409
        || !String(error.message).includes("explicit confirmation")
        || !window.confirm("Deleting this shared or historical transaction requires confirmation. Continue?")
      ) throw error;
      await api(`/api/v1/transactions/${transaction.id}/delete`, {
        method: "POST",
        body: JSON.stringify({ confirm_ended_period: true }),
      });
    }
    toast("Transaction deleted");
    await refreshAll();
  } catch (error) { toast(error.message); }
  finally {
    state.transactionDeleteLoading = false;
    document.querySelectorAll(".transaction-delete").forEach((item) => { item.disabled = false; });
    if (row.isConnected) row.setAttribute("aria-busy", "false");
  }
}

document.querySelectorAll("[data-close]").forEach((button) => {
  button.addEventListener("click", () => $(button.dataset.close).close());
});
document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});
document.querySelectorAll(".primary-nav button").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
document.querySelectorAll("[data-operation-action]").forEach((button) => {
  button.addEventListener("click", () => setOperationsAction(button.dataset.operationAction));
  button.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const current = OPERATION_ACTIONS.indexOf(state.operationsAction);
    const next = event.key === "Home"
      ? 0
      : event.key === "End"
        ? OPERATION_ACTIONS.length - 1
        : (current + (event.key === "ArrowRight" ? 1 : -1) + OPERATION_ACTIONS.length) % OPERATION_ACTIONS.length;
    setOperationsAction(OPERATION_ACTIONS[next], { focus: true });
  });
});
$("operations-account").addEventListener("change", () => {
  const account = accountById($("operations-account").value);
  state.operationsAccountId = account?.id || null;
  if (state.operationsAccountId !== null) writeOperationsPreference("account", state.operationsAccountId);
  void renderOperationsForms();
  void loadOperationsPeriods();
  void loadOperationsUndoCandidate();
});
$("operations-spend-form").addEventListener("submit", (event) => saveOperationsSingle(event, "spend"));
$("operations-add-form").addEventListener("submit", (event) => saveOperationsSingle(event, "add-funds"));
$("operations-transfer-form").addEventListener("submit", saveOperationsTransfer);
$("operations-transfer-to").addEventListener("change", updateOperationsTransferMode);
$("operations-has-fee").addEventListener("change", () => {
  $("operations-fee-fields").classList.toggle("hidden", !$("operations-has-fee").checked);
  updateOperationsTransferMode();
});
$("operations-add-period").addEventListener("click", () => openPeriodDialog());
$("operations-edit-period").addEventListener("click", () => openPeriodDialog(currentOperationsPeriod()));
$("operations-close-period").addEventListener("click", () => closeOperationsPeriod(currentOperationsPeriod()));
$("operations-period-history").addEventListener("click", openPeriodHistory);
$("operations-period-retry").addEventListener("click", loadOperationsPeriods);
$("period-form").addEventListener("submit", saveOperationsPeriod);
$("operations-undo").addEventListener("click", undoLatestOperation);

$("toggle-auth").addEventListener("click", () => {
  state.registerMode = !state.registerMode;
  $("display-field").classList.toggle("hidden", !state.registerMode);
  $("submit-auth").textContent = state.registerMode ? "Create account" : "Log in";
  $("toggle-auth").textContent = state.registerMode ? "I have an account" : "Create account";
  $("password").autocomplete = state.registerMode ? "new-password" : "current-password";
  $("auth-error").textContent = "";
});

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("auth-error").textContent = "";
  const body = { username: $("username").value, password: $("password").value };
  if (state.registerMode && $("display-name").value.trim()) body.display_name = $("display-name").value.trim();
  try {
    await showApp(await api(`/api/v1/auth/${state.registerMode ? "register" : "login"}`, { method: "POST", body: JSON.stringify(body) }));
  } catch (error) { $("auth-error").textContent = error.message; }
});

$("logout").addEventListener("click", async () => {
  await api("/api/v1/auth/logout", { method: "POST" });
  document.querySelector(".profile-menu").removeAttribute("open");
  showAuth();
});

$("manage-categories").addEventListener("click", openCategories);
$("category-form").addEventListener("submit", createCategory);
$("add-plan-rule").addEventListener("click", () => openPlanRule());
$("empty-add-plan-rule").addEventListener("click", () => openPlanRule());
$("plan-rule-kind").addEventListener("change", () => updatePlanRuleFields());
$("plan-rule-asset").addEventListener("change", () => updatePlanRuleFields());
$("plan-rule-form").addEventListener("submit", savePlanRule);
$("plan-link-form").addEventListener("submit", linkPlanTransaction);
$("plan-status-filter").addEventListener("change", renderPlan);

$("add-account").addEventListener("click", () => openAccountForm());
$("empty-add-account").addEventListener("click", () => openAccountForm());
$("account-form").addEventListener("submit", saveAccount);
$("reconcile-form").addEventListener("submit", saveReconcile);
$("invitation-form").addEventListener("submit", createInvitation);
$("copy-invite").addEventListener("click", copyInvitation);
$("empty-open-operations").addEventListener("click", () => switchView("operations"));
$("transaction-type").addEventListener("change", () => updateTransactionFields({ preserve: false }));
$("transaction-account").addEventListener("change", async () => {
  $("single-asset-field").classList.toggle("hidden", Boolean($("transaction-account").value) || $("transaction-type").value === "adjustment");
  await updateTransactionCategories($("transaction-category").value || null);
});
$("transaction-has-fee").addEventListener("change", () => $("fee-details").classList.toggle("hidden", !$("transaction-has-fee").checked));
$("transaction-form").addEventListener("submit", saveTransaction);
$("correct-transaction").addEventListener("click", () => {
  const transaction = state.viewingTransaction;
  if (!transaction || !canEditTransaction(transaction)) return;
  $("transaction-detail-dialog").close();
  void openTransactionForm(transaction);
});
$("transaction-filters").addEventListener("submit", (event) => { event.preventDefault(); loadTransactions(false); });
$("filter-account").addEventListener("change", () => syncTransactionFilterPair("account"));
$("filter-period").addEventListener("change", () => syncTransactionFilterPair("period"));
$("clear-filters").addEventListener("click", () => { $("transaction-filters").reset(); loadTransactions(false); });
$("load-more").addEventListener("click", () => loadTransactions(true));

window.addEventListener("popstate", () => switchView(new URLSearchParams(window.location.search).get("view") || "accounts", false));
api("/api/v1/auth/me").then(showApp).catch(showAuth);
