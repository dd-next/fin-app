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
  nextCursor: null,
  planRules: [],
  planOccurrences: [],
  planLinkTransactions: [],
  trackerPeriods: [],
  trackerSummary: null,
  trackerPrompt: null,
  selectedTrackerPeriodId: null,
  periodProposal: null,
  quickPreviewTimer: null,
  activeView: "accounts",
  activeAccount: null,
  sharingAccount: null,
  editingTransaction: null,
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

function formatNumber(value) {
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
  fraction = fraction.replace(/0+$/, "");
  integer = integer.replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${integer || "0"}${fraction ? `.${fraction}` : ""}`;
}

function formatMoney(value, code) {
  return `${formatNumber(value)} ${code}`;
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
    const categories = await api(`/api/v1/workspaces/${workspaceId}/categories`);
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
    state.planRules = [];
    state.planOccurrences = [];
    state.trackerPeriods = [];
    state.trackerSummary = null;
    state.trackerPrompt = null;
    state.selectedTrackerPeriodId = null;
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
    const [summary, page, planRules, planOccurrences, trackerPeriods] = await Promise.all([
      api("/api/v1/accounts/summary"),
      api("/api/v1/transactions?limit=50"),
      api(`/api/v1/workspaces/${workspaceId}/plan-rules`),
      api(`/api/v1/workspaces/${workspaceId}/plan-occurrences`),
      api(`/api/v1/workspaces/${workspaceId}/budget-periods`),
    ]);
    state.summary = summary;
    state.accounts = summary.accounts;
    state.transactions = page.items;
    state.nextCursor = page.next_cursor;
    state.planRules = planRules;
    state.planOccurrences = planOccurrences;
    state.trackerPeriods = trackerPeriods;
    const knownTrackerIds = new Set(trackerPeriods.map((period) => period.id));
    if (!knownTrackerIds.has(Number(state.selectedTrackerPeriodId))) {
      state.selectedTrackerPeriodId = trackerPeriods.find((period) => period.status === "current")?.id || trackerPeriods[0]?.id || null;
    }
    state.trackerSummary = state.selectedTrackerPeriodId
      ? await api(`/api/v1/workspaces/${workspaceId}/budget-periods/${state.selectedTrackerPeriodId}`)
      : null;
    const selectedCurrent = state.trackerSummary?.period.status === "current";
    state.trackerPrompt = selectedCurrent
      ? await api(`/api/v1/workspaces/${workspaceId}/tracker/savings-prompt`)
      : null;
    const workspaceIds = [...new Set(state.accounts.map((account) => account.workspace_id))];
    await Promise.all([
      categoriesFor(state.context.workspace.id),
      ...workspaceIds.map((workspaceId) => categoriesFor(workspaceId)),
    ]);
    renderAccounts();
    renderFilterOptions();
    renderTransactions();
    renderPlan();
    renderTracker();
  } catch (error) {
    toast(error.message);
  } finally {
    setLoading(false);
  }
}

function switchView(view, updateUrl = true) {
  const allowed = ["accounts", "transactions", "tracker", "plan", "analytics"];
  state.activeView = allowed.includes(view) ? view : "accounts";
  document.querySelectorAll(".app-view").forEach((section) => section.classList.add("hidden"));
  $(`view-${state.activeView}`).classList.remove("hidden");
  document.querySelectorAll(".primary-nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.activeView);
  });
  if (updateUrl) {
    const url = new URL(window.location.href);
    if (state.activeView === "accounts") url.searchParams.delete("view");
    else url.searchParams.set("view", state.activeView);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
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
        : `${formatNumber(account.valued_balance)} ${base}`;
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
  const items = state.accounts.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}` }));
  selectOptions($("filter-account"), items, { placeholder: "All accounts" });
  const visibleWorkspaceIds = new Set([
    state.context.workspace.id,
    ...state.accounts.map((account) => account.workspace_id),
  ]);
  const categories = [...visibleWorkspaceIds].flatMap(
    (workspaceId) => state.categories.get(workspaceId) || []
  );
  const unique = [...new Map(categories.map((category) => [category.id, category])).values()];
  if ($("filter-category")) {
    selectOptions($("filter-category"), unique.map((category) => ({ value: category.id, label: category.name })), { placeholder: "All categories" });
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
  const categories = await categoriesFor(workspaceId);
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
    const complete = document.createElement("button");
    complete.type = "button";
    complete.textContent = occurrence.rule.kind === "income" ? "Receive" : "Pay";
    complete.addEventListener("click", () => openPlanAction(occurrence));
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
    actions.append(complete, link, skip);
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

function renderTracker() {
  const summary = state.trackerSummary;
  $("tracker-empty").classList.toggle("hidden", Boolean(summary));
  $("tracker-content").classList.toggle("hidden", !summary);
  if (!summary) return;
  const period = summary.period;
  const code = period.base_asset.code;
  $("tracker-available").textContent = formatMoney(summary.available_today, code);
  $("tracker-remaining").textContent = formatMoney(summary.remaining_money, code);
  $("tracker-commitments-total").textContent = formatMoney(period.commitments_total, code);
  $("tracker-days-left").textContent = `${summary.days_remaining} ${summary.days_remaining === 1 ? "day" : "days"} left · ${formatMoney(summary.spent_total, code)} spent`;
  $("tracker-today-detail").textContent = `${formatMoney(summary.spent_today, code)} spent today · ${formatMoney(summary.budget_today, code)} budget`;
  $("tracker-period-heading").textContent = `${period.status[0].toUpperCase()}${period.status.slice(1)} period`;
  $("tracker-period-range").textContent = `${localDate(period.start_date)} – ${localDate(period.end_date)}`;
  $("tracker-pace").innerHTML = `
    <article><span>Daily base</span><strong>${formatMoney(summary.daily_base, code)}</strong></article>
    <article><span>Daily pool</span><strong>${formatMoney(period.daily_pool, code)}</strong></article>
    <article><span>Tomorrow now</span><strong>${formatMoney(summary.next_daily, code)}</strong></article>`;

  const commitmentNodes = period.commitments.map((commitment) => {
    const card = document.createElement("article");
    card.className = `commitment-card ${commitment.status}`;
    const comparison = commitment.status === "fulfilled"
      ? `Planned ${formatMoney(commitment.planned_amount, code)} · actual ${formatMoney(commitment.actual_amount, code)}`
      : `${localDate(commitment.due_date)} · ${commitment.status}`;
    card.innerHTML = `<div><strong>${escapeHtml(commitment.name)}</strong><span>${comparison}</span></div><strong>${formatMoney(commitment.effective_amount, code)}</strong>`;
    return card;
  });
  $("tracker-commitment-list").replaceChildren(...commitmentNodes);
  $("tracker-commitment-count").textContent = String(period.commitments.length);
  $("tracker-no-commitments").classList.toggle("hidden", period.commitments.length > 0);

  selectOptions($("tracker-period-select"), state.trackerPeriods.map((item) => ({
    value: item.id,
    label: `${localDate(item.start_date)} – ${localDate(item.end_date)} · ${item.status}`,
  })), { selected: period.id });
  const current = period.status === "current";
  $("quick-expense-form").classList.toggle("hidden", !current);
  $("tracker-close-period").classList.toggle("hidden", period.status === "ended");
  const prompt = state.trackerPrompt;
  $("tracker-savings-prompt").classList.toggle("hidden", !current || !prompt?.required);
  if (prompt?.required) {
    $("tracker-carry-copy").textContent = `${formatMoney(prompt.carry_amount, code)} can stay available today or be redistributed.`;
  }
  if (current) {
    const accounts = ownedPlanAccounts().filter((account) => canUseAccount(account, "expense"));
    selectOptions($("quick-expense-account"), accounts.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}` })), { placeholder: "Choose account" });
    updateQuickExpenseCategories();
  }
}

async function updateQuickExpenseCategories() {
  const account = accountById($("quick-expense-account").value);
  const workspaceId = account?.workspace_id || state.context.workspace.id;
  const categories = (state.categories.get(workspaceId) || []).filter((item) => ["expense", "both"].includes(item.kind));
  selectOptions($("quick-expense-category"), categories.map((item) => ({ value: item.id, label: item.name })), { placeholder: "Uncategorized" });
}

async function selectTrackerPeriod(periodId) {
  if (!periodId) return;
  setLoading(true);
  try {
    const workspaceId = state.context.workspace.id;
    state.selectedTrackerPeriodId = Number(periodId);
    state.trackerSummary = await api(`/api/v1/workspaces/${workspaceId}/budget-periods/${periodId}`);
    state.trackerPrompt = state.trackerSummary.period.status === "current"
      ? await api(`/api/v1/workspaces/${workspaceId}/tracker/savings-prompt`)
      : null;
    renderTracker();
  } catch (error) { toast(error.message); }
  finally { setLoading(false); }
}

function openBudgetPeriod(proposal = null) {
  state.periodProposal = proposal;
  $("budget-period-form").reset();
  $("budget-period-error").textContent = "";
  $("budget-opening-transaction").value = proposal?.opening_transaction_id || "";
  $("budget-opening-occurrence").value = proposal?.opening_plan_occurrence_id || "";
  $("budget-start-date").value = proposal?.start_date || todayValue();
  $("budget-end-date").value = proposal?.end_date || "";
  $("budget-funding-amount").value = proposal?.funding_amount || "";
  $("budget-base-code").textContent = proposal?.base_asset.code || state.context.workspace.base_asset.code;
  $("budget-period-title").textContent = proposal?.opening_transaction_id ? "Confirm income period" : "Start a period";
  $("budget-proposal-notice").classList.toggle("hidden", !proposal?.opening_transaction_id);
  if (proposal?.opening_transaction_id) {
    $("budget-proposal-notice").className = "notice warning";
    $("budget-proposal-notice").textContent = proposal.needs_end_date
      ? "Income received. Choose an end date because no later expected income is planned."
      : `Income received. The suggested period ends on ${localDate(proposal.end_date)}, before the next planned income.`;
  }
  const commitments = proposal?.commitments || [];
  const nodes = commitments.map((item) => {
    const card = document.createElement("article");
    card.className = "commitment-card";
    const amount = item.planned_amount === null ? "Needs equivalent" : formatMoney(item.planned_amount, proposal.base_asset.code);
    card.innerHTML = `<div><strong>${escapeHtml(item.name)}</strong><span>${localDate(item.due_date)} · ${escapeHtml(item.type.replaceAll("_", " "))}</span></div><strong>${amount}</strong>`;
    if (item.needs_base_amount) {
      const label = document.createElement("label");
      label.innerHTML = `${proposal.base_asset.code} equivalent<input inputmode="decimal" required data-commitment-base="${item.plan_occurrence_id}">`;
      card.append(label);
    }
    return card;
  });
  $("budget-proposal-commitment-list").replaceChildren(...nodes);
  $("budget-proposal-commitments").classList.toggle("hidden", commitments.length === 0);
  $("budget-period-dialog").showModal();
}

async function saveBudgetPeriod(event) {
  event.preventDefault();
  $("budget-period-error").textContent = "";
  const body = {
    start_date: $("budget-start-date").value,
    end_date: $("budget-end-date").value,
    funding_amount: $("budget-funding-amount").value,
    confirmed: true,
    commitment_base_amounts: {},
  };
  if ($("budget-opening-transaction").value) body.opening_transaction_id = Number($("budget-opening-transaction").value);
  if ($("budget-opening-occurrence").value) body.opening_plan_occurrence_id = Number($("budget-opening-occurrence").value);
  $("budget-proposal-commitment-list").querySelectorAll("[data-commitment-base]").forEach((input) => {
    body.commitment_base_amounts[input.dataset.commitmentBase] = input.value;
  });
  try {
    const result = await api(`/api/v1/workspaces/${state.context.workspace.id}/budget-periods`, { method: "POST", body: JSON.stringify(body) });
    state.selectedTrackerPeriodId = result.period.id;
    $("budget-period-dialog").close();
    toast("Tracker period created");
    await refreshAll();
    switchView("tracker");
  } catch (error) { $("budget-period-error").textContent = error.message; }
}

async function apiWithBaseAmount(path, method, body) {
  try {
    return await api(path, { method, body: JSON.stringify(body) });
  } catch (error) {
    if (error.status !== 422 || !String(error.message).includes("base_amount in")) throw error;
    const equivalent = window.prompt(`${error.message}. Enter the Tracker equivalent:`);
    if (!equivalent) throw error;
    body.base_amount = equivalent;
    return api(path, { method, body: JSON.stringify(body) });
  }
}

async function apiWithEndedPeriodConfirmation(path, method, body) {
  try {
    return await apiWithBaseAmount(path, method, body);
  } catch (error) {
    if (
      error.status !== 409
      || !String(error.message).includes("explicit confirmation")
      || !window.confirm("This changes an ended Tracker period. Continue and recompute its history?")
    ) throw error;
    body.confirm_ended_period = true;
    return apiWithBaseAmount(path, method, body);
  }
}

async function updateQuickPreview() {
  clearTimeout(state.quickPreviewTimer);
  const amount = $("quick-expense-amount").value.trim();
  if (!amount || !state.trackerSummary || state.trackerSummary.period.status !== "current") {
    $("quick-preview").textContent = "Enter an amount";
    return;
  }
  state.quickPreviewTimer = setTimeout(async () => {
    try {
      const result = await api(`/api/v1/workspaces/${state.context.workspace.id}/tracker/preview?pending=${encodeURIComponent(amount)}`);
      $("quick-preview").textContent = `${formatMoney(result.available_after, result.period.base_asset.code)} left today`;
    } catch (error) { $("quick-preview").textContent = error.message; }
  }, 180);
}

async function saveQuickExpense(event) {
  event.preventDefault();
  $("quick-expense-error").textContent = "";
  const body = {
    account_id: Number(requiredValue("quick-expense-account", "Account")),
    amount: requiredValue("quick-expense-amount", "Amount"),
    category_id: $("quick-expense-category").value ? Number($("quick-expense-category").value) : null,
    note: $("quick-expense-note").value.trim() || null,
    local_date: todayValue(),
  };
  try {
    await apiWithBaseAmount("/api/v1/transactions/expense", "POST", body);
    $("quick-expense-form").reset();
    $("quick-preview").textContent = "Enter an amount";
    toast("Expense added");
    await refreshAll();
    switchView("tracker");
  } catch (error) { $("quick-expense-error").textContent = error.message; }
}

async function trackerSavingsDecision(choice) {
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/tracker/savings-decision`, { method: "POST", body: JSON.stringify({ choice }) });
    toast(choice === "keep" ? "Carry kept for today" : "Carry spread across the remaining days");
    await refreshAll();
    switchView("tracker");
  } catch (error) { toast(error.message); }
}

async function closeTrackerPeriod() {
  const period = state.trackerSummary?.period;
  if (!period || !window.confirm("Close this period now? Its history will remain available.")) return;
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/budget-periods/${period.id}/close`, { method: "POST" });
    toast("Period closed");
    await refreshAll();
  } catch (error) { toast(error.message); }
}

async function showTrackerTransactions() {
  const period = state.trackerSummary?.period;
  if (!period) return;
  $("filter-from").value = period.start_date;
  $("filter-to").value = period.end_date;
  await loadTransactions(false);
  switchView("transactions");
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
    placeholder: "Choose when paying",
    selected: rule?.default_from_account_id ?? $("plan-rule-from-account").value,
  });
  selectOptions($("plan-rule-to-account"), accounts, {
    placeholder: "Choose when receiving",
    selected: rule?.default_to_account_id ?? $("plan-rule-to-account").value,
  });
  const categories = (await categoriesFor(state.context.workspace.id)).filter((category) => {
    const expected = kind === "income" ? "income" : "expense";
    return category.kind === "both" || category.kind === expected;
  });
  selectOptions($("plan-rule-category"), categories.map((category) => ({ value: category.id, label: category.name })), {
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
  if (!window.confirm(`Archive ${rule.name}? Open occurrences will be removed.`)) return;
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/plan-rules/${rule.id}/archive`, { method: "POST" });
    toast("Plan rule archived");
    await refreshAll();
  } catch (error) { toast(error.message); }
}

function openPlanAction(occurrence) {
  const rule = occurrence.rule;
  const accounts = ownedPlanAccounts(rule.asset.code).map((account) => ({ value: account.id, label: account.name }));
  $("plan-action-occurrence-id").value = occurrence.id;
  $("plan-action-title").textContent = rule.kind === "income" ? `Receive ${rule.name}` : `Pay ${rule.name}`;
  $("complete-plan-item").textContent = rule.kind === "income" ? "Confirm income" : "Confirm payment";
  $("plan-action-amount").value = occurrence.planned_amount;
  $("plan-action-date").value = todayValue();
  $("plan-action-note").value = "";
  $("plan-action-error").textContent = "";
  selectOptions($("plan-action-account"), accounts, { placeholder: "Choose account", selected: rule.kind === "income" ? rule.default_to_account_id : rule.default_from_account_id });
  selectOptions($("plan-action-from-account"), accounts, { placeholder: "Choose source", selected: rule.default_from_account_id });
  selectOptions($("plan-action-to-account"), accounts, { placeholder: "Choose target", selected: rule.default_to_account_id });
  $("plan-action-account-field").classList.toggle("hidden", rule.kind === "reserve_transfer");
  $("plan-action-from-field").classList.toggle("hidden", rule.kind !== "reserve_transfer");
  $("plan-action-to-field").classList.toggle("hidden", rule.kind !== "reserve_transfer");
  $("plan-action-dialog").showModal();
}

async function completePlanOccurrence(event) {
  event.preventDefault();
  $("plan-action-error").textContent = "";
  const occurrence = planOccurrenceById($("plan-action-occurrence-id").value);
  const reserve = occurrence.rule.kind === "reserve_transfer";
  const body = {
    amount: $("plan-action-amount").value,
    local_date: $("plan-action-date").value,
    note: $("plan-action-note").value.trim() || null,
  };
  if (reserve) {
    body.from_account_id = Number($("plan-action-from-account").value);
    body.to_account_id = Number($("plan-action-to-account").value);
  } else {
    body.account_id = Number($("plan-action-account").value);
  }
  const action = occurrence.rule.kind === "income" ? "receive" : "pay";
  try {
    const result = await apiWithEndedPeriodConfirmation(
      `/api/v1/workspaces/${state.context.workspace.id}/plan-occurrences/${occurrence.id}/${action}`,
      "POST",
      body,
    );
    $("plan-action-dialog").close();
    toast(action === "receive" ? "Income received" : "Plan item paid");
    await refreshAll();
    switchView("plan");
    if (result.period_proposal) openBudgetPeriod(result.period_proposal);
  } catch (error) { $("plan-action-error").textContent = error.message; }
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
    const result = await apiWithEndedPeriodConfirmation(
      `/api/v1/workspaces/${state.context.workspace.id}/plan-occurrences/${occurrenceId}/link-transaction`,
      "POST",
      { transaction_id: Number(transactionId) },
    );
    $("plan-link-dialog").close();
    toast("Transaction linked to Plan");
    await refreshAll();
    if (result.period_proposal) openBudgetPeriod(result.period_proposal);
  } catch (error) { $("plan-link-error").textContent = error.message; }
}

function transactionTitle(transaction) {
  const category = [...state.categories.values()].flat().find((item) => item.id === transaction.category_id);
  if (transaction.note) return transaction.note;
  if (transaction.counterparty) return transaction.counterparty;
  if (category) return category.name;
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
  if (transaction.status === "voided" || transaction.has_hidden_legs) return false;
  if (!transaction.legs.length) return false;
  return transaction.legs.every((leg) => {
    if (leg.account_id === null) return transaction.created_by_user_id === state.context.user.id;
    const account = accountById(leg.account_id);
    return transaction.type === "adjustment" ? canUseAccount(account, "owner") : canUseAccount(account, "edit");
  });
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
    if (transaction.status === "unassigned" && transaction.created_by_user_id === state.context.user.id) {
      const assign = document.createElement("button");
      assign.type = "button";
      assign.textContent = "Assign";
      assign.addEventListener("click", () => assignTransaction(transaction));
      actions.append(assign);
    }
    if (canEditTransaction(transaction)) {
      const edit = document.createElement("button");
      edit.type = "button";
      edit.textContent = "Edit";
      edit.addEventListener("click", () => openTransactionForm(transaction));
      const voidButton = document.createElement("button");
      voidButton.type = "button";
      voidButton.textContent = "Void";
      voidButton.addEventListener("click", () => voidTransaction(transaction));
      actions.append(edit, voidButton);
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
      badge.textContent = transaction.status;
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
  const categories = (await categoriesFor(workspaceId)).filter((category) => category.kind === "both" || category.kind === type);
  selectOptions($("transaction-category"), categories.map((category) => ({ value: category.id, label: category.name })), { placeholder: "Uncategorized", selected });
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
  state.editingTransaction = transaction;
  $("transaction-form").reset();
  $("transaction-error").textContent = "";
  $("transaction-id").value = transaction ? transaction.id : "";
  $("transaction-dialog-title").textContent = transaction ? "Edit transaction" : "Add transaction";
  $("save-transaction").textContent = transaction ? "Save changes" : "Save transaction";
  $("transaction-type").disabled = Boolean(transaction);
  $("transaction-type").value = transaction ? transaction.type : "expense";
  $("transaction-date").value = transaction ? transaction.local_date : todayValue();
  await updateTransactionFields({ preserve: false });
  if (transaction) {
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
  }
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
        if (transactionId) {
          body.from_amount = amount;
          body.to_amount = amount;
        } else {
          body.amount = amount;
        }
      } else {
        body.from_amount = requiredValue("transaction-from-amount", "From amount");
        body.to_amount = requiredValue("transaction-to-amount", "To amount");
        if (!transactionId && $("transaction-has-fee").checked) {
          body.fee = {
            account_id: Number(requiredValue("transaction-fee-account", "Fee account")),
            amount: requiredValue("transaction-fee-amount", "Fee amount"),
          };
        }
      }
    }
    const route = transactionId ? `/api/v1/transactions/${transactionId}` : `/api/v1/transactions/${type}`;
    try {
      await apiWithBaseAmount(route, transactionId ? "PATCH" : "POST", body);
    } catch (error) {
      if (
        error.status !== 409
        || !String(error.message).includes("explicit confirmation")
        || !window.confirm("This transaction correction requires confirmation. Continue?")
      ) throw error;
      body.confirm_ended_period = true;
      await apiWithBaseAmount(route, transactionId ? "PATCH" : "POST", body);
    }
    $("transaction-dialog").close();
    toast(transactionId ? "Transaction updated" : "Transaction added");
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

async function voidTransaction(transaction) {
  if (!window.confirm(`Void this ${transaction.type}? Balances will be recalculated.`)) return;
  try {
    try {
      await api(`/api/v1/transactions/${transaction.id}/void`, { method: "POST" });
    } catch (error) {
      if (
        error.status !== 409
        || !String(error.message).includes("explicit confirmation")
        || !window.confirm("Voiding this shared or historical transaction requires confirmation. Continue?")
      ) throw error;
      await api(`/api/v1/transactions/${transaction.id}/void`, {
        method: "POST",
        body: JSON.stringify({ confirm_ended_period: true }),
      });
    }
    toast("Transaction voided");
    await refreshAll();
  } catch (error) { toast(error.message); }
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
$("plan-action-form").addEventListener("submit", completePlanOccurrence);
$("plan-link-form").addEventListener("submit", linkPlanTransaction);
$("plan-status-filter").addEventListener("change", renderPlan);
$("add-budget-period").addEventListener("click", () => openBudgetPeriod());
$("empty-add-budget-period").addEventListener("click", () => openBudgetPeriod());
$("budget-period-form").addEventListener("submit", saveBudgetPeriod);
$("tracker-period-select").addEventListener("change", () => selectTrackerPeriod($("tracker-period-select").value));
$("quick-expense-account").addEventListener("change", updateQuickExpenseCategories);
$("quick-expense-amount").addEventListener("input", updateQuickPreview);
$("quick-expense-form").addEventListener("submit", saveQuickExpense);
$("tracker-keep-carry").addEventListener("click", () => trackerSavingsDecision("keep"));
$("tracker-redistribute").addEventListener("click", () => trackerSavingsDecision("redistribute"));
$("tracker-view-transactions").addEventListener("click", showTrackerTransactions);
$("tracker-close-period").addEventListener("click", closeTrackerPeriod);

$("add-account").addEventListener("click", () => openAccountForm());
$("empty-add-account").addEventListener("click", () => openAccountForm());
$("account-form").addEventListener("submit", saveAccount);
$("reconcile-form").addEventListener("submit", saveReconcile);
$("invitation-form").addEventListener("submit", createInvitation);
$("copy-invite").addEventListener("click", copyInvitation);
$("add-transaction").addEventListener("click", () => openTransactionForm());
$("empty-add-transaction").addEventListener("click", () => openTransactionForm());
$("transaction-type").addEventListener("change", () => updateTransactionFields({ preserve: false }));
$("transaction-account").addEventListener("change", async () => {
  $("single-asset-field").classList.toggle("hidden", Boolean($("transaction-account").value) || $("transaction-type").value === "adjustment");
  await updateTransactionCategories();
});
$("transaction-has-fee").addEventListener("change", () => $("fee-details").classList.toggle("hidden", !$("transaction-has-fee").checked));
$("transaction-form").addEventListener("submit", saveTransaction);
$("transaction-filters").addEventListener("submit", (event) => { event.preventDefault(); loadTransactions(false); });
$("clear-filters").addEventListener("click", () => { $("transaction-filters").reset(); loadTransactions(false); });
$("load-more").addEventListener("click", () => loadTransactions(true));

window.addEventListener("popstate", () => switchView(new URLSearchParams(window.location.search).get("view") || "accounts", false));
api("/api/v1/auth/me").then(showApp).catch(showAuth);
