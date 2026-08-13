const $ = (id) => document.getElementById(id);

const state = {
  registerMode: false,
  context: null,
  lastUserId: null,
  assets: [],
  accounts: [],
  summary: null,
  manualRates: [],
  categories: new Map(),
  transactions: [],
  transactionFeedItems: [],
  transactionFeedCursor: null,
  transactionFeedFilter: "all",
  transactionAdvancedActive: false,
  transactionAdvancedCount: 0,
  transactionFeedLoading: false,
  transactionSwipeKey: null,
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
  activeAccountPage: null,
  activeAccountError: null,
  sharingAccount: null,
  sharingRows: [],
  sharingError: "",
  invitationRole: "viewer",
  invitationUrl: "",
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

function moneyParts(value, code) {
  return { value: formatNumber(value, assetByCode(code)?.decimals ?? null), code: String(code) };
}

function moneyMarkup(value, code) {
  const parts = moneyParts(value, code);
  return `<span class="mobile-money"><span class="mobile-money-value">${escapeHtml(parts.value)}</span><span class="mobile-money-code">${escapeHtml(parts.code)}</span></span>`;
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

function isMobileViewport() {
  return window.matchMedia("(max-width: 640px)").matches;
}

function roleLabel(role) {
  return `${role[0].toUpperCase()}${role.slice(1)}`;
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
    state.transactionFeedItems = [];
    state.transactionFeedCursor = null;
    state.transactionFeedFilter = "all";
    state.transactionAdvancedActive = false;
    state.transactionAdvancedCount = 0;
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
    for (const id of [
      "operations-spend-amount", "operations-spend-note",
      "operations-add-amount", "operations-add-note",
      "operations-transfer-amount", "operations-transfer-note",
      "operations-exchange-from", "operations-exchange-to", "operations-fee-amount",
    ]) $(id).value = "";
    $("operations-transfer-to").value = "";
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
    const transactionUrl = isMobileViewport() && state.transactionAdvancedActive
      ? `/api/v1/transactions?${transactionQuery()}`
      : "/api/v1/transactions?limit=50";
    const [summary, page, feedPage, planRules, planOccurrences] = await Promise.all([
      api("/api/v1/accounts/summary"),
      api(transactionUrl),
      api(`/api/v1/transaction-feed?filter=${encodeURIComponent(state.transactionFeedFilter)}&limit=50`),
      api(`/api/v1/workspaces/${workspaceId}/plan-rules`),
      api(`/api/v1/workspaces/${workspaceId}/plan-occurrences`),
    ]);
    state.summary = summary;
    state.accounts = summary.accounts;
    state.transactions = page.items;
    state.nextCursor = page.next_cursor;
    state.transactionFeedItems = feedPage.items;
    state.transactionFeedCursor = feedPage.next_cursor;
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

const mobileOverlayState = {
  stack: [],
  rootOpener: null,
  lastTabBackward: false,
};

function mobileOverlayFocusable(panel) {
  return [...panel.querySelectorAll('button:not([disabled]):not([hidden]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')];
}

function setMobileOverlayBackground(active) {
  document.querySelectorAll("#app-shell > .topbar, .app-view").forEach((element) => {
    element.inert = active;
    if (active) element.setAttribute("aria-hidden", "true");
    else element.removeAttribute("aria-hidden");
  });
}

function renderMobileOverlay() {
  const entry = mobileOverlayState.stack.at(-1) || null;
  const active = Boolean(entry);
  const root = $("mobile-overlay-root");
  const sheet = $("mobile-sheet");
  const confirmation = $("mobile-confirm");
  document.body.classList.toggle("overlay-active", active);
  root.hidden = !active;
  sheet.hidden = !active || entry.kind !== "sheet";
  confirmation.hidden = !active || entry.kind !== "confirmation";
  if (!active) {
    setMobileOverlayBackground(false);
    return;
  }

  let panel;
  if (entry.kind === "sheet") {
    panel = sheet;
    $("mobile-sheet-kicker").textContent = entry.kicker;
    $("mobile-sheet-title").textContent = entry.title;
    $("mobile-sheet-body").replaceChildren(entry.buildBody());
    const footer = $("mobile-sheet-footer");
    footer.replaceChildren();
    if (entry.secondaryLabel) {
      const secondary = document.createElement("button");
      secondary.type = "button";
      secondary.className = "mobile-button-secondary";
      secondary.textContent = entry.secondaryLabel;
      secondary.addEventListener("click", async () => {
        if (!entry.onSecondary) {
          closeMobileOverlay();
          return;
        }
        if (entry.actionTaken) return;
        entry.actionTaken = true;
        secondary.disabled = true;
        try { await entry.onSecondary(); }
        finally { entry.actionTaken = false; secondary.disabled = false; }
      });
      footer.append(secondary);
    }
    if (entry.primaryLabel) {
      const primary = document.createElement("button");
      primary.type = "button";
      primary.className = "mobile-button-sheet-primary";
      primary.textContent = entry.primaryLabel;
      primary.addEventListener("click", async () => {
        if (entry.actionTaken) return;
        entry.actionTaken = true;
        primary.disabled = true;
        try { await entry.onPrimary?.(); }
        finally { entry.actionTaken = false; primary.disabled = false; }
      });
      footer.append(primary);
    }
  } else {
    panel = confirmation;
  }

  requestAnimationFrame(() => {
    if (mobileOverlayState.stack.at(-1) !== entry) return;
    const focusables = mobileOverlayFocusable(panel);
    (panel.querySelector("[autofocus]") || focusables[0] || panel).focus();
    setMobileOverlayBackground(active);
  });
}

function openMobileSheet(config, opener = document.activeElement) {
  if (!window.matchMedia("(max-width: 640px)").matches) return;
  if (!mobileOverlayState.stack.length) mobileOverlayState.rootOpener = opener;
  const parentContext = mobileOverlayState.stack.at(-1)?.context || null;
  mobileOverlayState.stack.push({
    kind: "sheet",
    kicker: String(config.kicker || ""),
    title: String(config.title || ""),
    buildBody: config.buildBody,
    secondaryLabel: config.secondaryLabel || "",
    onSecondary: config.onSecondary,
    primaryLabel: config.primaryLabel || "",
    onPrimary: config.onPrimary,
    context: config.context || parentContext,
    returnFocusSelector: config.returnFocusSelector || "",
    opener,
    openerId: opener?.id || "",
    actionTaken: false,
  });
  renderMobileOverlay();
}

function closeMobileOverlay({ restoreFocus = true } = {}) {
  if (mobileOverlayState.stack.at(-1)?.actionTaken) return;
  const closed = mobileOverlayState.stack.pop();
  const hasParent = Boolean(mobileOverlayState.stack.length);
  const rootFocusTarget = mobileOverlayState.rootOpener;
  renderMobileOverlay();
  if (!mobileOverlayState.stack.length) {
    mobileOverlayState.rootOpener = null;
    setMobileOverlayBackground(false);
  }
  if (restoreFocus) requestAnimationFrame(() => {
    const focusTarget = hasParent
      ? (closed?.returnFocusSelector && document.querySelector(closed.returnFocusSelector))
        || (closed?.opener?.isConnected ? closed.opener : null)
        || (closed?.openerId && document.getElementById(closed.openerId))
      : rootFocusTarget;
    if (focusTarget?.isConnected) focusTarget.focus();
  });
}

function closeAllMobileOverlays({ restoreFocus = false } = {}) {
  const focusTarget = mobileOverlayState.rootOpener;
  mobileOverlayState.stack.length = 0;
  mobileOverlayState.rootOpener = null;
  renderMobileOverlay();
  if (restoreFocus && focusTarget?.isConnected) requestAnimationFrame(() => focusTarget.focus());
}

function openMobileChoose({ title, options, onSelect, returnFocusSelector = "" }, opener = document.activeElement) {
  openMobileSheet({
    kicker: "CHOOSE",
    title,
    returnFocusSelector,
    buildBody: () => {
      const list = document.createElement("div");
      list.className = "mobile-option-list";
      for (const option of options) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "mobile-option";
        button.dataset.value = String(option.value);
        button.innerHTML = `<span></span><span class="mobile-option-current" aria-hidden="true">${option.current ? "✓" : ""}</span>`;
        button.firstElementChild.textContent = option.label;
        if (option.disabled) button.setAttribute("aria-disabled", "true");
        button.addEventListener("click", () => {
          if (option.disabled) return;
          onSelect(button.dataset.value);
          closeMobileOverlay();
        });
        list.append(button);
      }
      return list;
    },
  }, opener);
}

function openMobileConfirmation({ title, body, actionLabel = "Done", variant = "accent", onAction, closeParentsOnSuccess = 0 }, opener = document.activeElement) {
  if (!window.matchMedia("(max-width: 640px)").matches) return;
  if (!mobileOverlayState.stack.length) mobileOverlayState.rootOpener = opener;
  const entry = { kind: "confirmation", title, body, variant, actionTaken: false, opener, openerId: opener?.id || "", closeParentsOnSuccess, context: mobileOverlayState.stack.at(-1)?.context || null };
  mobileOverlayState.stack.push(entry);
  $("mobile-confirm-title").textContent = title;
  $("mobile-confirm-body").textContent = body;
  $("mobile-confirm-error").textContent = "";
  $("mobile-confirm-error").classList.add("hidden");
  const cancel = $("mobile-confirm-cancel");
  const action = $("mobile-confirm-action");
  cancel.hidden = variant === "saved";
  action.textContent = actionLabel;
  action.className = variant === "destructive"
    ? "mobile-button-destructive-confirm"
    : "mobile-button-sheet-primary";
  action.onclick = async () => {
    if (entry.actionTaken) return;
    entry.actionTaken = true;
    action.disabled = true;
    try {
      await onAction?.();
      entry.actionTaken = false;
      if (mobileOverlayState.stack.at(-1) === entry) {
        closeMobileOverlay({ restoreFocus: variant !== "saved" });
        for (let index = 0; index < entry.closeParentsOnSuccess; index += 1) {
          closeMobileOverlay({ restoreFocus: false });
        }
      }
    } catch (error) {
      $("mobile-confirm-error").textContent = error.message;
      $("mobile-confirm-error").classList.remove("hidden");
    } finally {
      entry.actionTaken = false;
      action.disabled = false;
    }
  };
  renderMobileOverlay();
}

function trapMobileOverlayFocus(event) {
  if (!mobileOverlayState.stack.length) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeMobileOverlay();
    return;
  }
  if (event.key !== "Tab") return;
  mobileOverlayState.lastTabBackward = event.shiftKey;
  const panel = $("mobile-confirm").hidden ? $("mobile-sheet") : $("mobile-confirm");
  const focusables = mobileOverlayFocusable(panel);
  if (!focusables.length) {
    event.preventDefault();
    panel.focus();
    return;
  }
  const first = focusables[0];
  const last = focusables.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function openOperationsAccountChoose() {
  openMobileChoose({
    title: "Account",
    options: state.accounts.map((account) => ({
      value: account.id,
      label: `${account.name} · ${account.asset.code}`,
      current: account.id === state.operationsAccountId,
      disabled: false,
    })),
    onSelect: (value) => {
      $("operations-account").value = String(value);
      $("operations-account").dispatchEvent(new Event("change", { bubbles: true }));
    },
  }, $("operations-account-overlay-trigger"));
}

function runMobileOverlayVerificationScenario(name) {
  if (!new URLSearchParams(window.location.search).has("verify-overlay")) return;
  const opener = $("operations-account-overlay-trigger");
  if (name === "nested") {
    openMobileSheet({
      kicker: "VERIFY",
      title: "Parent sheet",
      buildBody: () => {
        const button = document.createElement("button");
        button.type = "button";
        button.id = "overlay-verify-nested-opener";
        button.textContent = "Open nested choose";
        button.addEventListener("click", () => openMobileChoose({
          title: "Nested choice",
          options: [
            { value: "disabled", label: "Disabled option", disabled: true, current: false },
            { value: "enabled", label: "Enabled option", disabled: false, current: true },
          ],
          onSelect: (value) => document.documentElement.setAttribute("data-overlay-result", value),
        }, button));
        return button;
      },
    }, opener);
  } else if (name === "confirmation") {
    openMobileConfirmation({
      title: "Verify action?",
      body: "This verification changes only an in-memory counter.",
      actionLabel: "Verify",
      variant: "destructive",
      onAction: async () => {
        const current = document.documentElement.getAttribute("data-overlay-action-count");
        document.documentElement.setAttribute("data-overlay-action-count", current ? "2" : "1");
        await new Promise((resolve) => window.setTimeout(resolve, 80));
      },
    }, opener);
  } else if (name === "saved") {
    openMobileConfirmation({ title: "Saved", body: "Verification saved.", variant: "saved" }, opener);
  } else if (name === "accent") {
    openMobileConfirmation({ title: "Continue?", body: "This verification has no persistent effect.", actionLabel: "Continue", variant: "accent" }, opener);
  }
}

document.addEventListener("finapp:verify-overlay", (event) => {
  runMobileOverlayVerificationScenario(event.detail);
});
$("mobile-overlay-verify-trigger").addEventListener("click", () => {
  runMobileOverlayVerificationScenario(new URLSearchParams(window.location.search).get("verify-overlay"));
});
if (new URLSearchParams(window.location.search).has("verify-overlay")) {
  $("mobile-overlay-verify-trigger").classList.remove("overlay-verify-trigger");
  $("mobile-overlay-verify-trigger").classList.add("overlay-verify-active");
  $("mobile-overlay-verify-trigger").textContent = "Run overlay verification";
  window.setTimeout(() => {
    runMobileOverlayVerificationScenario(new URLSearchParams(window.location.search).get("verify-overlay"));
  }, 0);
}

function switchView(view, updateUrl = true) {
  closeAllMobileOverlays();
  const allowed = ["accounts", "transactions", "operations", "plan", "analytics"];
  state.activeView = allowed.includes(view) ? view : "accounts";
  document.querySelectorAll(".app-view").forEach((section) => section.classList.add("hidden"));
  $(`view-${state.activeView}`).classList.remove("hidden");
  document.querySelectorAll(".primary-nav button").forEach((button) => {
    const current = button.dataset.view === state.activeView;
    button.classList.toggle("active", current);
    if (current) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  if (updateUrl) {
    const url = new URL(window.location.href);
    if (state.activeView === "accounts") url.searchParams.delete("view");
    else url.searchParams.set("view", state.activeView);
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  }
  $("app-shell").scrollTop = 0;
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
  if (isMobileViewport() && document.activeElement instanceof HTMLElement) document.activeElement.blur();
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
  if (isMobileViewport()) updateMobileOperationsSubmitState();
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
  renderOperationsAccountBalance();
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

function operationsTransferTargets(account = selectedOperationsAccount()) {
  const requiredAction = isMobileViewport() ? "owner" : "edit";
  return state.accounts.filter((item) => (
    account
    && item.id !== account.id
    && item.workspace_id === account.workspace_id
    && canUseAccount(item, requiredAction)
  ));
}

function isPositiveDecimalInput(value) {
  const raw = String(value || "").trim();
  return /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(raw)
    && /[1-9]/.test(raw.replace(".", ""));
}

function updateMobileOperationsSubmitState() {
  if (!isMobileViewport()) return;
  const account = selectedOperationsAccount();
  const target = accountById($("operations-transfer-to").value);
  $("operations-spend-submit").disabled = state.operationsCommandLoading
    || !canUseAccount(account, "expense")
    || !isPositiveDecimalInput($("operations-spend-amount").value);
  $("operations-add-submit").disabled = state.operationsCommandLoading
    || !canUseAccount(account, "income")
    || !isPositiveDecimalInput($("operations-add-amount").value);
  $("operations-transfer-submit").disabled = state.operationsCommandLoading
    || !canUseAccount(account, "owner")
    || !target
    || !operationsTransferTargets(account).some((item) => item.id === target.id)
    || !isPositiveDecimalInput($("operations-transfer-amount").value);
}

function renderMobileOperationsControls() {
  const account = selectedOperationsAccount();
  const code = account?.asset.code || "";
  for (const kind of ["spend", "add", "transfer"]) {
    $(`operations-${kind}-currency`).textContent = code;
  }
  for (const kind of ["spend", "add"]) {
    const select = $(`operations-${kind}-category`);
    $(`operations-${kind}-category-mobile`).textContent = select.selectedOptions[0]?.textContent || "Uncategorized";
  }
  for (const kind of ["spend", "add", "transfer"]) {
    const date = $(`operations-${kind}-date`).value;
    $(`operations-${kind}-date-mobile`).textContent = date ? localDate(date) : "Date";
  }
  const target = accountById($("operations-transfer-to").value);
  $("operations-transfer-to-mobile").textContent = target
    ? `${target.name} · ${target.asset.code}`
    : "Choose destination";
  updateMobileOperationsSubmitState();
}

function openMobileOperationsCategory(kind, opener) {
  const select = $(`operations-${kind}-category`);
  openMobileChoose({
    title: "Category",
    returnFocusSelector: `#operations-${kind}-category-mobile`,
    options: [...select.options].map((option) => ({
      value: option.value,
      label: option.textContent,
      current: option.value === select.value,
      disabled: option.disabled,
    })),
    onSelect: (value) => {
      select.value = value;
      renderMobileOperationsControls();
    },
  }, opener);
}

function openMobileOperationsDate(kind, opener) {
  const input = $(`operations-${kind}-date`);
  openMobileDateChoose({
    label: "Date",
    value: input.value || todayValue(),
    returnFocusSelector: `#operations-${kind}-date-mobile`,
    onSelect: (value) => {
      input.value = value;
      renderMobileOperationsControls();
    },
  }, opener);
}

function openMobileOperationsDestination(opener) {
  const select = $("operations-transfer-to");
  const targets = operationsTransferTargets();
  if (!targets.length) return;
  openMobileChoose({
    title: "Destination",
    returnFocusSelector: "#operations-transfer-to-mobile",
    options: targets.map((account) => ({
      value: account.id,
      label: `${account.name} · ${account.asset.code}`,
      current: account.id === Number(select.value),
    })),
    onSelect: (value) => {
      select.value = value;
      updateOperationsTransferMode();
      renderMobileOperationsControls();
    },
  }, opener);
}

function renderOperationsAccountBalance() {
  const selectedAccount = selectedOperationsAccount();
  $("operations-account-overlay-label").textContent = selectedAccount?.name || "Choose account";
  $("operations-account-balance").innerHTML = selectedAccount
    ? moneyMarkup(selectedAccount.balance, selectedAccount.asset.code)
    : "—";
  renderMobileOperationsControls();
}

function renderOperationsUndo() {
  const candidate = state.operationsUndoCandidate;
  const button = $("operations-undo");
  button.classList.toggle("hidden", !candidate);
  button.disabled = state.operationsUndoLoading || !candidate;
  button.textContent = isMobileViewport()
    ? "↶"
    : candidate
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

async function performOperationsUndo(account, transaction) {
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
    await refreshAll();
    if (!isMobileViewport()) {
      toast("Operation undone");
      switchView("operations");
    }
  } catch (error) {
    if (!isMobileViewport()) toast(error.message);
    await loadOperationsUndoCandidate();
    throw error;
  } finally {
    state.operationsUndoLoading = false;
    renderOperationsUndo();
  }
}

async function undoLatestOperation() {
  const account = selectedOperationsAccount();
  const transaction = state.operationsUndoCandidate;
  if (!account || !transaction) return;
  if (isMobileViewport()) {
    openMobileConfirmation({
      title: "Undo this operation?",
      body: "The latest operation is marked Deleted. Balances and periods are recalculated.",
      actionLabel: "Undo",
      variant: "destructive",
      onAction: () => performOperationsUndo(account, transaction),
    }, $("operations-undo"));
    return;
  }
  if (!window.confirm(`Undo your latest ${transaction.type} operation? Balances and periods will be recalculated.`)) return;
  try { await performOperationsUndo(account, transaction); } catch (_error) { /* surfaced by toast */ }
}

async function updateOperationsCategories(account) {
  if (!account) return;
  const accountId = account.id;
  const categories = await categoriesFor(account.workspace_id);
  if (selectedOperationsAccount()?.id !== accountId) return;
  const choices = (kind) => categories
    .filter((category) => !category.archived_at && [kind, "both"].includes(category.kind))
    .map((category) => ({ value: category.id, label: category.name }));
  const spendChoices = choices("expense");
  const incomeChoices = choices("income");
  const spendDefault = isMobileViewport()
    ? spendChoices.find((item) => item.label.toLowerCase() === "groceries")?.value
    : null;
  const incomeDefault = isMobileViewport()
    ? incomeChoices.find((item) => item.label.toLowerCase() === "salary")?.value
    : null;
  const spendSelected = spendChoices.some((item) => String(item.value) === $("operations-spend-category").value)
    ? $("operations-spend-category").value
    : spendDefault;
  const incomeSelected = incomeChoices.some((item) => String(item.value) === $("operations-add-category").value)
    ? $("operations-add-category").value
    : incomeDefault;
  selectOptions($("operations-spend-category"), spendChoices, {
    placeholder: "Uncategorized",
    selected: spendSelected,
  });
  selectOptions($("operations-add-category"), incomeChoices, {
    placeholder: "Uncategorized",
    selected: incomeSelected,
  });
  renderMobileOperationsControls();
}

function updateOperationsTransferMode() {
  const source = selectedOperationsAccount();
  const target = accountById($("operations-transfer-to").value);
  const exchange = Boolean(source && target && source.asset.id !== target.asset.id);
  if (isMobileViewport()) {
    $("operations-transfer-amount").required = true;
    $("operations-exchange-from").required = false;
    $("operations-exchange-to").required = false;
    $("operations-fee-account").required = false;
    $("operations-fee-amount").required = false;
    $("operations-transfer-amount-field").classList.remove("hidden");
    $("operations-exchange-from-field").classList.add("hidden");
    $("operations-exchange-to-field").classList.add("hidden");
    $("operations-fee").classList.add("hidden");
    $("operations-transfer-submit").textContent = "Save transfer";
    $("operations-transfer-mode").textContent = "";
    renderMobileOperationsControls();
    return;
  }
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
  renderMobileOperationsControls();
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
    const hasTarget = operationsTransferTargets(account).length > 0;
    $("operations-spend-submit").disabled = !canUseAccount(account, "expense");
    $("operations-add-submit").disabled = !canUseAccount(account, "income");
    $("operations-transfer-submit").disabled = !canUseAccount(account, isMobileViewport() ? "owner" : "edit") || !hasTarget;
    updateMobileOperationsSubmitState();
  }
}

async function renderOperationsForms() {
  const account = selectedOperationsAccount();
  for (const id of ["operations-spend-date", "operations-add-date", "operations-transfer-date"]) {
    if (!$(id).value) $(id).value = todayValue();
  }
  const spendAllowed = canUseAccount(account, "expense");
  const incomeAllowed = canUseAccount(account, "income");
  const transferAllowed = canUseAccount(account, isMobileViewport() ? "owner" : "edit");
  $("operations-spend-submit").disabled = state.operationsCommandLoading || !spendAllowed;
  $("operations-add-submit").disabled = state.operationsCommandLoading || !incomeAllowed;
  $("operations-spend-error").textContent = account && !spendAllowed ? "You cannot record spending on this account." : "";
  $("operations-add-error").textContent = account && !incomeAllowed ? "You cannot add funds to this account." : "";

  const targets = operationsTransferTargets(account);
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
  $("operations-transfer-error").textContent = account && !transferAllowed
    ? isMobileViewport()
      ? "Mobile Transfer is available only to the account owner."
      : "You cannot transfer from this account."
    : "";
  updateOperationsTransferMode();
  try {
    await updateOperationsCategories(account);
  } catch (error) {
    toast(error.message);
  }
  renderMobileOperationsControls();
}

function currentOperationsPeriod() {
  return state.operationsPeriods.find((period) => period.status === "current") || null;
}

function calendarDayNumber(value) {
  const [year, month, day] = String(value).split("-").map(Number);
  return Date.UTC(year, month - 1, day) / 86400000;
}

function renderOperationsPeriodHistory() {
  const account = selectedOperationsAccount();
  $("period-history-account").textContent = account
    ? `${account.name} · ${account.asset.code}`
    : "No account selected";
  const nodes = state.operationsPeriods.map((period) => {
    const row = document.createElement("article");
    row.className = "period-history-row";
    const facts = [`Opening ${formatMoney(period.opening_balance, period.asset.code)}`];
    if (period.status === "current") {
      facts.push(`Current ${formatMoney(period.current_balance, period.asset.code)}`);
    } else if (period.status === "closed") {
      facts.push(`Closing ${formatMoney(period.closing_balance, period.asset.code)}`);
    }
    row.innerHTML = `
      <div><strong>${localDate(period.start_date)} – ${localDate(period.end_date)}</strong><span>${escapeHtml(period.status)} · ${escapeHtml(facts.join(" · "))}</span></div>
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
  $("operations-period").classList.toggle("is-active", Boolean(current));
  $("operations-period").classList.toggle("is-absent", !current);
  const daysLeft = current
    ? Math.max(0, calendarDayNumber(current.end_date) - calendarDayNumber(todayValue()) + 1)
    : 0;
  $("operations-period-card-title").textContent = current
    ? `Period · ${daysLeft}d`
    : state.operationsPeriodLoading
      ? "Loading period…"
      : state.operationsPeriodError
        ? "Period unavailable"
        : "No period";
  $("operations-period-mobile-value").innerHTML = current
    ? moneyMarkup(current.available_today, current.asset.code)
    : "N/A";
  const showMobileState = owner && !current && (state.operationsPeriodLoading || state.operationsPeriodError);
  $("operations-period-mobile-state").classList.toggle("hidden", !showMobileState);
  $("operations-period-mobile-state-copy").textContent = state.operationsPeriodLoading
    ? "Loading…"
    : state.operationsPeriodError
      ? "Could not load period."
      : "";
  $("operations-period-retry-mobile").classList.toggle("hidden", !state.operationsPeriodError);
  $("operations-period-retry-mobile").disabled = state.operationsPeriodLoading || state.periodCommandLoading;
  $("operations-period").setAttribute(
    "aria-busy",
    String(state.operationsPeriodLoading || state.periodCommandLoading),
  );
  $("operations-period-available").textContent = unavailable
    ? "N/A"
    : formatMoney(current.available_today, current.asset.code);
  $("operations-period-current-balance").textContent = unavailable
    ? "N/A"
    : formatMoney(current.current_balance, current.asset.code);
  $("operations-add-period").classList.toggle("hidden", !ready || Boolean(current));
  $("operations-add-period-mobile").classList.toggle("hidden", !ready || Boolean(current));
  $("operations-add-period-mobile").disabled = isMobileViewport();
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
    $("operations-period-status").textContent = `${localDate(current.start_date)} – ${localDate(current.end_date)}`;
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
    };
    setPeriodCommandLoading(true);
    if (periodId) {
      await apiCommand(`/api/v1/account-periods/${periodId}`, "PATCH", body);
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

function clearMobileOperationsDraft(kind) {
  if (kind === "spend" || kind === "add") {
    $(`operations-${kind}-amount`).value = "";
    $(`operations-${kind}-note`).value = "";
  } else {
    $("operations-transfer-amount").value = "";
    $("operations-transfer-note").value = "";
    $("operations-transfer-to").value = "";
  }
  renderMobileOperationsControls();
}

async function finishMobileOperation(kind, account, body) {
  switchView("operations");
  const current = accountById(account.id) || account;
  const messages = {
    spend: `The expense was written to ${current.name} · ${current.asset.code}. Available today was recalculated.`,
    add: `The funds were added to ${current.name} · ${current.asset.code}. Balance and Available today were recalculated.`,
    transfer: "The transfer was recorded. Both accounts were updated — total capital is unchanged.",
  };
  openMobileConfirmation({
    title: "Saved",
    body: messages[kind],
    variant: "saved",
    onAction: async () => {
      clearMobileOperationsDraft(kind);
      await refreshAll();
      switchView("operations");
    },
  }, document.activeElement);
}

async function mobileOperationCommand(path, body, confirmationTitle, confirmationBody, onConfirmed) {
  try {
    await apiCommand(path, "POST", body);
    return true;
  } catch (error) {
    if (error.status !== 409 || !String(error.message).includes("explicit confirmation")) throw error;
    openMobileConfirmation({
      title: confirmationTitle,
      body: confirmationBody,
      actionLabel: "Continue",
      onAction: async () => {
        setOperationsCommandLoading(true);
        try {
          await apiCommand(path, "POST", { ...body, confirm_ended_period: true });
          await onConfirmed();
        } finally {
          setOperationsCommandLoading(0);
        }
      },
    }, document.activeElement);
    return false;
  }
}

async function saveOperationsSingle(event, kind) {
  event.preventDefault();
  if (state.operationsCommandLoading) return;
  const prefix = kind === "spend" ? "operations-spend" : "operations-add";
  const account = selectedOperationsAccount();
  $(`${prefix}-error`).textContent = "";
  if (!account) return $(`${prefix}-error`).textContent = "Choose an account.";
  try {
    if (!isPositiveDecimalInput($(`${prefix}-amount`).value)) throw new Error("Enter an amount greater than zero.");
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
    if (isMobileViewport()) {
      const completed = await mobileOperationCommand(
        route,
        body,
        "Save this operation?",
        "It changes an ended account period. Balances and period history will be recalculated.",
        () => finishMobileOperation(kind === "spend" ? "spend" : "add", account, body),
      );
      if (!completed) return;
      await finishMobileOperation(kind === "spend" ? "spend" : "add", account, body);
      return;
    }
    await apiWithEndedPeriodConfirmation(route, "POST", body);
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
    if (isMobileViewport() && (!canUseAccount(source, "owner") || !canUseAccount(target, "owner"))) {
      throw new Error("Mobile Transfer is available only to the account owner.");
    }
    const exchange = source.asset.id !== target.asset.id;
    const body = {
      from_account_id: source.id,
      to_account_id: target.id,
      local_date: $("operations-transfer-date").value || null,
      note: $("operations-transfer-note").value.trim() || null,
    };
    let route = "/api/v1/operations/transfer";
    if (isMobileViewport()) {
      const fromAmount = requiredValue("operations-transfer-amount", "Amount");
      if (!isPositiveDecimalInput(fromAmount)) throw new Error("Enter an amount greater than zero.");
      setOperationsCommandLoading(true);
      const quote = await api("/api/v1/operations/transfer/quotes", {
        method: "POST",
        body: JSON.stringify({
          from_account_id: source.id,
          to_account_id: target.id,
          from_amount: fromAmount,
          rate_source: "manual",
        }),
      });
      route = `/api/v1/operations/transfer/quotes/${quote.id}/execute`;
      delete body.from_account_id;
      delete body.to_account_id;
    } else if (exchange) {
      route = "/api/v1/operations/exchange";
      body.from_amount = requiredValue("operations-exchange-from", "From amount");
      body.to_amount = requiredValue("operations-exchange-to", "To amount");
      if ($("operations-has-fee").checked) {
        body.fee = {
          account_id: Number(requiredValue("operations-fee-account", "Fee account")),
          amount: requiredValue("operations-fee-amount", "Fee amount"),
        };
      }
    } else body.amount = requiredValue("operations-transfer-amount", "Amount");
    setOperationsCommandLoading(true);
    if (isMobileViewport()) {
      const completed = await mobileOperationCommand(
        route,
        body,
        "Save this transfer?",
        "It changes an ended account period. Both account histories will be recalculated.",
        () => finishMobileOperation("transfer", source, body),
      );
      if (!completed) return;
      await finishMobileOperation("transfer", source, body);
      return;
    }
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
  if (account.storage_type === "cash") return "Cash";
  if (account.asset.kind === "crypto" || ["crypto_wallet", "exchange"].includes(account.storage_type)) return "Crypto";
  return "Bank";
}

function accountIcon(account) {
  if (accountGroup(account) === "Cash") return "¤";
  if (accountGroup(account) === "Crypto") return "₿";
  return "▣";
}

function openSetRateEntry(opener = document.activeElement) {
  const event = new CustomEvent("finapp:open-set-rate", {
    cancelable: true,
    detail: { opener },
  });
  if (!document.dispatchEvent(event)) return;
  void openRateSettings(opener, state.summary?.unvalued[0]?.asset.code || null);
}

function renderAccounts() {
  if (!state.summary) return;
  const base = state.summary.base_asset.code;
  $("net-worth").innerHTML = moneyMarkup(state.summary.net_worth, base);
  $("available-total").innerHTML = moneyMarkup(state.summary.available, base);
  $("net-worth-code").textContent = `Valued in ${base} across visible accounts`;
  const unvalued = state.summary.unvalued;
  $("unvalued-warning").classList.toggle("hidden", !unvalued.length);
  $("unvalued-warning").innerHTML = unvalued.length
    ? `<span class="mobile-rate-warning-icon" aria-hidden="true">!</span><span class="mobile-rate-warning-text">${unvalued.length} ${unvalued.length === 1 ? "asset has" : "assets have"} no rate — set one</span><span class="mobile-rate-warning-chevron" aria-hidden="true">›</span>`
    : "";

  const grouped = new Map();
  for (const account of state.accounts) {
    const group = accountGroup(account);
    if (!grouped.has(group)) grouped.set(group, []);
    grouped.get(group).push(account);
  }
  const order = ["Cash", "Bank", "Crypto"];
  const sections = [];
  for (const group of order) {
    const accounts = grouped.get(group) || [];
    if (!accounts.length) continue;
    const section = document.createElement("section");
    section.className = "account-group";
    section.innerHTML = `<div class="group-heading mobile-group-header"><h3>${group}</h3><span class="mobile-group-count">${accounts.length} ${accounts.length === 1 ? "account" : "accounts"}</span></div><div class="account-grid"></div>`;
    const grid = section.querySelector(".account-grid");
    for (const account of accounts) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "account-card mobile-list-row mobile-interactive";
      button.dataset.accountId = account.id;
      const valued = account.valued_balance === null
        ? "Not valued"
        : moneyMarkup(account.valued_balance, base);
      const valueLine = account.valued_balance === null
        ? "Not valued"
        : account.include_in_available
          ? `≈ ${valued}`
          : `protected · ${valued}`;
      button.innerHTML = `
        <span class="account-top"><span class="account-icon mobile-leading-icon">${accountIcon(account)}</span>${account.is_shared ? `<span class="badge shared">${escapeHtml(account.access_role)}</span>` : ""}</span>
        <span class="account-main"><span class="account-name mobile-row-title mobile-truncate">${escapeHtml(account.name)}</span><span class="account-mobile-meta">${escapeHtml(account.storage_type.replaceAll("_", " "))}</span></span>
        <span class="account-trailing"><strong>${moneyMarkup(account.balance, account.asset.code)}</strong><small>${valueLine}</small></span>`;
      button.addEventListener("click", () => openAccountDetail(account.id, button));
      grid.append(button);
    }
    sections.push(section);
  }
  $("account-groups").replaceChildren(...sections);
  $("accounts-empty").classList.toggle("hidden", state.accounts.length > 0);
  $("accounts-add-row").classList.toggle("hidden", state.accounts.length === 0);
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

function storageLabel(value) {
  return {
    bank: "Bank account",
    card: "Card",
    cash: "Cash",
    e_wallet: "E-wallet",
    crypto_wallet: "Crypto wallet",
    exchange: "Exchange",
    virtual: "Virtual",
  }[value] || value.replaceAll("_", " ");
}

function purposeLabel(value) {
  return value ? `${value[0].toUpperCase()}${value.slice(1)}` : "—";
}

function mobileChoiceField({ label, value, id, onOpen }) {
  const field = document.createElement("div");
  field.className = "mobile-sheet-field";
  const caption = document.createElement("span");
  caption.className = "mobile-sheet-field-label";
  caption.textContent = label;
  const button = document.createElement("button");
  button.type = "button";
  button.id = id;
  button.className = "mobile-field-sheet mobile-interactive";
  button.innerHTML = `<span class="mobile-field-sheet-value"></span><span class="mobile-field-chevron" aria-hidden="true">›</span>`;
  button.querySelector(".mobile-field-sheet-value").textContent = value;
  button.addEventListener("click", onOpen);
  field.append(caption, button);
  return field;
}

function mobileAccountDetailBody(account) {
  const body = document.createElement("div");
  body.className = "mobile-account-detail";
  const base = state.summary.base_asset.code;
  const valued = account.valued_balance === null
    ? "Not valued"
    : moneyMarkup(account.valued_balance, base);
  const summary = document.createElement("dl");
  summary.className = "mobile-readonly-list";
  summary.innerHTML = `
    <div><dt>Balance</dt><dd>${moneyMarkup(account.balance, account.asset.code)}</dd></div>
    <div><dt>Valued amount</dt><dd>${valued}</dd></div>
    <div><dt>Type</dt><dd>${escapeHtml(`${storageLabel(account.storage_type)} · ${purposeLabel(account.purpose)}`)}</dd></div>
    <div><dt>Availability</dt><dd>${account.include_in_available ? "Available" : "protected"}</dd></div>`;
  body.append(summary);

  const actions = document.createElement("div");
  actions.className = "mobile-account-actions";
  const addAction = (label, action, className = "mobile-button-inline") => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `${className} mobile-interactive`;
    button.textContent = label;
    button.addEventListener("click", action);
    actions.append(button);
  };
  if (canUseAccount(account, "owner")) {
    addAction("Reconcile", () => openMobileReconcile(account, document.activeElement));
  }
  addAction("Full history", () => openAccountHistory(account));
  if (canUseAccount(account, "owner")) {
    addAction("Archive", () => openMobileArchive(account, document.activeElement), "mobile-button-destructive-inline");
  }
  body.append(actions);

  const heading = document.createElement("h3");
  heading.className = "mobile-sheet-section-title";
  heading.textContent = "RECENT HISTORY";
  body.append(heading);
  const history = document.createElement("div");
  history.className = "mobile-account-history";
  if (state.activeAccountError) {
    const error = document.createElement("p");
    error.className = "form-error";
    error.setAttribute("role", "alert");
    error.textContent = state.activeAccountError;
    history.append(error);
  } else if (!state.activeAccountPage) {
    history.innerHTML = '<p class="muted" role="status">Loading account history…</p>';
  } else if (!state.activeAccountPage.items.length) {
    history.innerHTML = '<p class="muted">No transactions on this account.</p>';
  } else {
    for (const transaction of state.activeAccountPage.items) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "mobile-account-history-row mobile-interactive";
      row.innerHTML = `<span><strong>${escapeHtml(transactionTitle(transaction))}</strong><small>${escapeHtml(localDate(transaction.local_date))}</small></span><span>${escapeHtml(transactionAmount(transaction))}</span>`;
      row.addEventListener("click", () => {
        closeAllMobileOverlays();
        openTransactionDetails(transaction);
      });
      history.append(row);
    }
  }
  body.append(history);
  return body;
}

function openMobileAccountDetail(account, opener) {
  state.activeAccount = account;
  state.activeAccountPage = null;
  state.activeAccountError = null;
  openMobileSheet({
    kicker: "ACCOUNT",
    title: account.name,
    buildBody: () => mobileAccountDetailBody(account),
    secondaryLabel: canUseAccount(account, "owner") ? "Share" : "",
    onSecondary: () => openSharing(account, document.activeElement),
    primaryLabel: canUseAccount(account, "edit") ? "Edit details" : "",
    onPrimary: () => openMobileAccountForm(account, document.activeElement),
  }, opener);
  void api(`/api/v1/transactions?account_id=${account.id}&limit=10`).then((page) => {
    if (state.activeAccount?.id !== account.id) return;
    state.activeAccountPage = page;
    const entry = mobileOverlayState.stack.at(-1);
    if (entry?.kind === "sheet" && entry.title === account.name) renderMobileOverlay();
  }).catch((error) => {
    if (state.activeAccount?.id !== account.id) return;
    state.activeAccountError = error.message;
    const entry = mobileOverlayState.stack.at(-1);
    if (entry?.kind === "sheet" && entry.title === account.name) renderMobileOverlay();
  });
}

function buildMobileAccountFormBody(account, draft) {
  const body = document.createElement("div");
  body.className = "mobile-account-form";
  const nameField = document.createElement("label");
  nameField.className = "mobile-sheet-field";
  nameField.innerHTML = '<span class="mobile-sheet-field-label">Name</span><input id="mobile-account-name" class="mobile-field" maxlength="100" autocomplete="off">';
  const nameInput = nameField.querySelector("input");
  nameInput.value = draft.name;
  nameInput.addEventListener("input", () => { draft.name = nameInput.value; });
  body.append(nameField);

  const storageOptions = [
    ["bank", "Bank account"], ["card", "Card"], ["cash", "Cash"],
    ["e_wallet", "E-wallet"], ["crypto_wallet", "Crypto wallet"],
    ["exchange", "Exchange"], ["virtual", "Virtual"],
  ];
  body.append(mobileChoiceField({
    label: "Storage",
    value: storageLabel(draft.storage_type),
    id: "mobile-account-storage",
    onOpen: () => openMobileChoose({
      title: "Storage",
      returnFocusSelector: "#mobile-account-storage",
      options: storageOptions.map(([value, label]) => ({ value, label, current: draft.storage_type === value })),
      onSelect: (value) => { draft.storage_type = value; },
    }, document.activeElement),
  }));

  const purposeOptions = ["spending", "reserve", "savings", "investment"];
  body.append(mobileChoiceField({
    label: "Purpose",
    value: purposeLabel(draft.purpose),
    id: "mobile-account-purpose",
    onOpen: () => openMobileChoose({
      title: "Purpose",
      returnFocusSelector: "#mobile-account-purpose",
      options: purposeOptions.map((value) => ({ value, label: purposeLabel(value), current: draft.purpose === value })),
      onSelect: (value) => { draft.purpose = value; },
    }, document.activeElement),
  }));

  if (!account) {
    const asset = assetByCode(draft.asset_code);
    body.append(mobileChoiceField({
      label: "Asset",
      value: asset ? `${asset.code} · ${asset.name}` : draft.asset_code,
      id: "mobile-account-asset",
      onOpen: () => openMobileChoose({
        title: "Asset",
        returnFocusSelector: "#mobile-account-asset",
        options: state.assets.map((item) => ({
          value: item.code,
          label: `${item.code} · ${item.name}`,
          current: draft.asset_code === item.code,
        })),
        onSelect: (value) => { draft.asset_code = value; },
      }, document.activeElement),
    }));
    const openingField = document.createElement("label");
    openingField.className = "mobile-sheet-field";
    openingField.innerHTML = '<span class="mobile-sheet-field-label">Opening balance</span><input id="mobile-account-opening" class="mobile-field" inputmode="decimal">';
    const openingInput = openingField.querySelector("input");
    openingInput.value = draft.opening_balance;
    openingInput.addEventListener("input", () => { draft.opening_balance = openingInput.value; });
    body.append(openingField);
  } else {
    const institutionField = document.createElement("label");
    institutionField.className = "mobile-sheet-field";
    institutionField.innerHTML = '<span class="mobile-sheet-field-label">Institution</span><input id="mobile-account-institution" class="mobile-field" maxlength="100" placeholder="Optional">';
    const institutionInput = institutionField.querySelector("input");
    institutionInput.value = draft.institution;
    institutionInput.addEventListener("input", () => { draft.institution = institutionInput.value; });
    body.append(institutionField);
  }

  const toggle = document.createElement("label");
  toggle.className = "mobile-sheet-toggle";
  toggle.innerHTML = '<span>Include in Available</span><input id="mobile-account-available" type="checkbox">';
  const checkbox = toggle.querySelector("input");
  checkbox.checked = draft.include_in_available;
  checkbox.addEventListener("change", () => { draft.include_in_available = checkbox.checked; });
  body.append(toggle);
  const error = document.createElement("p");
  error.className = "form-error";
  error.setAttribute("role", "alert");
  error.textContent = draft.error;
  body.append(error);
  return body;
}

function openMobileAccountForm(account = null, opener = document.activeElement) {
  const draft = {
    name: account?.name || "",
    storage_type: account?.storage_type || "bank",
    purpose: account?.purpose || "spending",
    asset_code: account?.asset.code || state.context.workspace.base_asset.code,
    opening_balance: "0",
    institution: account?.institution || "",
    include_in_available: account?.include_in_available ?? true,
    error: "",
  };
  openMobileSheet({
    kicker: "ACCOUNT",
    title: account ? "Edit account" : "Add account",
    secondaryLabel: "Cancel",
    primaryLabel: account ? "Save changes" : "Add account",
    buildBody: () => buildMobileAccountFormBody(account, draft),
    onPrimary: async () => {
      draft.error = "";
      if (!draft.name.trim()) draft.error = "Name is required.";
      if (!account && !draft.opening_balance.trim()) draft.error = "Opening balance is required.";
      if (draft.error) {
        renderMobileOverlay();
        return;
      }
      const payload = {
        name: draft.name.trim(),
        storage_type: draft.storage_type,
        purpose: draft.purpose,
        institution: account ? draft.institution.trim() || null : null,
        include_in_available: draft.include_in_available,
      };
      if (!account) {
        payload.asset_code = draft.asset_code;
        payload.opening_balance = draft.opening_balance.trim();
      }
      try {
        await api(account ? `/api/v1/accounts/${account.id}` : "/api/v1/accounts", {
          method: account ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        });
        await refreshAll();
        const savedOpener = mobileOverlayState.rootOpener || opener;
        closeAllMobileOverlays();
        openMobileConfirmation({
          title: "Saved",
          body: account ? `${draft.name.trim()} was updated.` : `${draft.name.trim()} was added to Accounts.`,
          variant: "saved",
        }, savedOpener);
      } catch (error) {
        draft.error = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
}

function openMobileReconcile(account, opener = document.activeElement) {
  const draft = { target_balance: account.balance, note: "", error: "" };
  openMobileSheet({
    kicker: "BALANCE CORRECTION",
    title: "Reconcile account",
    secondaryLabel: "Cancel",
    primaryLabel: "Save correction",
    buildBody: () => {
      const body = document.createElement("div");
      body.className = "mobile-account-form";
      body.innerHTML = `
        <label class="mobile-sheet-field"><span class="mobile-sheet-field-label">Actual balance</span><input id="mobile-reconcile-balance" class="mobile-field" inputmode="decimal"></label>
        <label class="mobile-sheet-field"><span class="mobile-sheet-field-label">Note</span><input id="mobile-reconcile-note" class="mobile-field" maxlength="500" placeholder="Counted cash"></label>
        <p class="mobile-sheet-hint">A correction entry is written to history. Existing transactions are untouched.</p>
        <p class="form-error" role="alert"></p>`;
      const balance = body.querySelector("#mobile-reconcile-balance");
      const note = body.querySelector("#mobile-reconcile-note");
      balance.value = draft.target_balance;
      note.value = draft.note;
      balance.addEventListener("input", () => { draft.target_balance = balance.value; });
      note.addEventListener("input", () => { draft.note = note.value; });
      body.querySelector(".form-error").textContent = draft.error;
      return body;
    },
    onPrimary: async () => {
      draft.error = "";
      if (!draft.target_balance.trim()) {
        draft.error = "Actual balance is required.";
        renderMobileOverlay();
        return;
      }
      try {
        await api(`/api/v1/accounts/${account.id}/reconcile`, {
          method: "POST",
          body: JSON.stringify({ target_balance: draft.target_balance.trim(), note: draft.note.trim() || null }),
        });
        await refreshAll();
        const savedOpener = mobileOverlayState.rootOpener || opener;
        closeAllMobileOverlays();
        openMobileConfirmation({
          title: "Saved",
          body: `${account.name} was reconciled. The correction was written to history.`,
          variant: "saved",
        }, savedOpener);
      } catch (error) {
        draft.error = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
}

function openMobileArchive(account, opener = document.activeElement) {
  openMobileConfirmation({
    title: "Archive this account?",
    body: "It disappears from Accounts and stops counting toward Total capital. History is kept.",
    actionLabel: "Archive",
    variant: "destructive",
    onAction: async () => {
      await api(`/api/v1/accounts/${account.id}/archive`, { method: "POST" });
      closeAllMobileOverlays();
      toast("Account archived");
      await refreshAll();
    },
  }, opener);
}

async function openAccountHistory(account) {
  const previousAccount = $("filter-account").value;
  const previousPeriod = $("filter-period").value;
  $("filter-account").value = String(account.id);
  syncTransactionFilterPair("account");
  if (isMobileViewport()) {
    state.transactionAdvancedActive = true;
    state.transactionAdvancedCount = 1;
  }
  const loaded = await loadTransactions(false);
  if (!loaded) {
    $("filter-account").value = previousAccount;
    $("filter-period").value = previousPeriod;
    state.transactionAdvancedActive = false;
    state.transactionAdvancedCount = 0;
    return;
  }
  closeAllMobileOverlays();
  switchView("transactions");
}

async function openAccountDetail(accountId, opener = document.activeElement) {
  const account = accountById(accountId);
  if (!account) return;
  if (isMobileViewport()) {
    openMobileAccountDetail(account, opener);
    return;
  }
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
  if (isMobileViewport()) {
    openMobileAccountForm(account, document.activeElement);
    return;
  }
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

function mobileProfileBody() {
  const body = document.createElement("div");
  body.className = "mobile-profile-body";
  const identity = document.createElement("div");
  identity.className = "mobile-profile-identity";
  identity.innerHTML = `<strong>${escapeHtml(state.context.user.display_name)}</strong><span>@${escapeHtml(state.context.user.username)}</span>`;
  body.append(identity);
  const rows = document.createElement("div");
  rows.className = "mobile-settings-list";
  const addRow = (label, meta, action, { destructive = false } = {}) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `mobile-settings-row mobile-interactive${destructive ? " is-destructive" : ""}`;
    button.innerHTML = `<span><strong>${escapeHtml(label)}</strong>${meta ? `<small>${escapeHtml(meta)}</small>` : ""}</span><span aria-hidden="true">›</span>`;
    button.addEventListener("click", action);
    rows.append(button);
  };
  addRow("Manage categories", "Create, rename, and archive", () => openCategories(document.activeElement));
  addRow("Exchange rates", "Manual rates", () => openRateSettings(document.activeElement));
  addRow("Workspace", state.context.workspace.name, () => {});
  addRow("Log out", "This device", () => openLogoutConfirmation(document.activeElement), { destructive: true });
  rows.lastElementChild.previousElementSibling.disabled = true;
  body.append(rows);
  return body;
}

function openMobileProfile(opener = document.activeElement) {
  openMobileSheet({
    kicker: "ACCOUNT",
    title: state.context.user.username,
    buildBody: mobileProfileBody,
  }, opener);
}

function openLogoutConfirmation(opener = document.activeElement) {
  openMobileConfirmation({
    title: `Log out of ${state.context.user.username}?`,
    body: "You will be signed out on this device. Your data stays safely in your workspace.",
    actionLabel: "Log out",
    variant: "destructive",
    onAction: async () => {
      await api("/api/v1/auth/logout", { method: "POST" });
      closeAllMobileOverlays();
      showAuth();
    },
  }, opener);
}

function categoryKindLabel(kind) {
  return { expense: "Expense", income: "Income", both: "Both" }[kind] || kind;
}

function mobileCategoriesBody() {
  const body = document.createElement("div");
  body.className = "mobile-category-manager";
  const heading = document.createElement("p");
  heading.className = "mobile-sheet-section-title";
  heading.textContent = "ALL CATEGORIES · TAP TO EDIT";
  body.append(heading);
  const categories = (state.categories.get(state.context.workspace.id) || [])
    .filter((category) => !category.archived_at);
  const list = document.createElement("div");
  list.className = "mobile-settings-list";
  for (const category of categories) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "mobile-settings-row mobile-interactive";
    row.innerHTML = `<span><strong>${escapeHtml(category.name)}</strong><small>${escapeHtml(categoryKindLabel(category.kind))}</small></span><span aria-hidden="true">›</span>`;
    row.addEventListener("click", () => openMobileCategoryForm(category, row));
    list.append(row);
  }
  if (!categories.length) list.innerHTML = '<p class="muted">No categories yet.</p>';
  body.append(list);
  return body;
}

async function openMobileCategories(opener = document.activeElement) {
  const workspaceId = state.context.workspace.id;
  state.categories.delete(workspaceId);
  try { await categoriesFor(workspaceId); }
  catch (error) { toast(error.message); return; }
  openMobileSheet({
    kicker: "SETTINGS",
    title: "Categories",
    buildBody: mobileCategoriesBody,
    primaryLabel: "Add category",
    onPrimary: () => openMobileCategoryForm(null, document.activeElement),
  }, opener);
}

function buildMobileCategoryForm(category, draft) {
  const body = document.createElement("div");
  body.className = "mobile-account-form";
  const name = document.createElement("label");
  name.className = "mobile-sheet-field";
  name.innerHTML = '<span class="mobile-sheet-field-label">Name</span><input id="mobile-category-name" class="mobile-field" maxlength="100">';
  name.querySelector("input").value = draft.name;
  name.querySelector("input").addEventListener("input", (event) => { draft.name = event.target.value; });
  body.append(name);
  body.append(mobileChoiceField({
    label: "Kind",
    value: categoryKindLabel(draft.kind),
    id: "mobile-category-kind",
    onOpen: () => openMobileChoose({
      title: "Kind",
      returnFocusSelector: "#mobile-category-kind",
      options: ["expense", "income", "both"].map((value) => ({ value, label: categoryKindLabel(value), current: draft.kind === value })),
      onSelect: (value) => { draft.kind = value; },
    }, document.activeElement),
  }));
  if (!category) {
    const hint = document.createElement("p");
    hint.className = "mobile-sheet-hint";
    hint.textContent = "A category only groups transactions. Renaming it later keeps every past entry attached.";
    body.append(hint);
  } else {
    const archive = document.createElement("button");
    archive.type = "button";
    archive.className = "mobile-button-destructive-inline mobile-interactive";
    archive.textContent = "Archive category";
    archive.addEventListener("click", () => openMobileConfirmation({
      title: `Archive ${category.name}?`,
      body: "Existing transactions keep their category and nothing is removed from balances.",
      actionLabel: "Archive",
      variant: "destructive",
      closeParentsOnSuccess: 1,
      onAction: async () => {
        await api(`/api/v1/workspaces/${state.context.workspace.id}/categories/${category.id}/archive`, { method: "POST" });
        state.categories.delete(state.context.workspace.id);
        await categoriesFor(state.context.workspace.id);
        renderFilterOptions();
      },
    }, archive));
    body.append(archive);
  }
  const error = document.createElement("p");
  error.className = "form-error";
  error.setAttribute("role", "alert");
  error.textContent = draft.error;
  body.append(error);
  return body;
}

function openMobileCategoryForm(category = null, opener = document.activeElement) {
  const draft = { name: category?.name || "", kind: category?.kind || "expense", error: "" };
  openMobileSheet({
    kicker: "SETTINGS",
    title: category ? "Edit category" : "Add category",
    secondaryLabel: "Cancel",
    primaryLabel: category ? "Save changes" : "Add category",
    buildBody: () => buildMobileCategoryForm(category, draft),
    onPrimary: async () => {
      draft.error = "";
      if (!draft.name.trim()) {
        draft.error = "Name is required.";
        renderMobileOverlay();
        return;
      }
      try {
        const workspaceId = state.context.workspace.id;
        await api(category
          ? `/api/v1/workspaces/${workspaceId}/categories/${category.id}`
          : `/api/v1/workspaces/${workspaceId}/categories`, {
          method: category ? "PATCH" : "POST",
          body: JSON.stringify({ name: draft.name.trim(), kind: draft.kind }),
        });
        state.categories.delete(workspaceId);
        await categoriesFor(workspaceId);
        const current = mobileOverlayState.stack.at(-1);
        if (current) current.actionTaken = false;
        closeMobileOverlay({ restoreFocus: false });
        renderFilterOptions();
      } catch (error) {
        draft.error = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
}

function rateForAsset(code) {
  return state.manualRates.find((rate) => rate.from_asset.code === code) || null;
}

async function loadManualRates() {
  state.manualRates = await api(`/api/v1/workspaces/${state.context.workspace.id}/valuation-rates`);
  return state.manualRates;
}

function ratePairLabel(code) {
  return `${code} → ${state.context.workspace.base_asset.code}`;
}

function buildMobileRateBody(draft) {
  const body = document.createElement("div");
  body.className = "mobile-account-form";
  const choices = state.assets.filter((asset) => asset.code !== state.context.workspace.base_asset.code);
  body.append(mobileChoiceField({
    label: "Pair",
    value: ratePairLabel(draft.assetCode),
    id: "mobile-rate-pair",
    onOpen: () => openMobileChoose({
      title: "Pair",
      returnFocusSelector: "#mobile-rate-pair",
      options: choices.map((asset) => ({ value: asset.code, label: ratePairLabel(asset.code), current: asset.code === draft.assetCode })),
      onSelect: (value) => {
        draft.assetCode = value;
        draft.rate = rateForAsset(value)?.rate || "";
      },
    }, document.activeElement),
  }));
  body.append(mobileChoiceField({
    label: "Source",
    value: "Manual value",
    id: "mobile-rate-source",
    onOpen: () => openMobileChoose({
      title: "Source",
      returnFocusSelector: "#mobile-rate-source",
      options: [
        { value: "manual", label: "Manual value", current: true },
        { value: "auto", label: "Auto · Coming soon", disabled: true },
      ],
      onSelect: () => {},
    }, document.activeElement),
  }));
  const rate = document.createElement("label");
  rate.className = "mobile-sheet-field";
  rate.innerHTML = '<span class="mobile-sheet-field-label">Rate</span><input id="mobile-rate-value" class="mobile-field" inputmode="decimal" autocomplete="off">';
  rate.querySelector("input").value = draft.rate;
  rate.querySelector("input").addEventListener("input", (event) => { draft.rate = event.target.value; });
  body.append(rate);
  const hint = document.createElement("p");
  hint.className = "mobile-sheet-hint";
  hint.textContent = "Rates apply to Total capital and Available. Without a rate an asset shows as Not valued.";
  body.append(hint);
  if (rateForAsset(draft.assetCode)) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "mobile-button-destructive-inline mobile-interactive";
    remove.textContent = "Delete rate";
    remove.addEventListener("click", () => openMobileConfirmation({
      title: `Delete ${ratePairLabel(draft.assetCode)} rate?`,
      body: "The asset becomes Not valued until another manual rate or exchange supplies a value.",
      actionLabel: "Delete",
      variant: "destructive",
      onAction: async () => {
        await api(`/api/v1/workspaces/${state.context.workspace.id}/valuation-rates/${draft.assetCode}`, { method: "DELETE" });
        await refreshAll();
        await loadManualRates();
        closeAllMobileOverlays();
        openMobileConfirmation({ title: "Saved", body: `${ratePairLabel(draft.assetCode)} rate was deleted.`, variant: "saved" }, draft.opener);
      },
    }, remove));
    body.append(remove);
  }
  const error = document.createElement("p");
  error.className = "form-error";
  error.setAttribute("role", "alert");
  error.textContent = draft.error;
  body.append(error);
  return body;
}

async function openMobileRateSettings(opener = document.activeElement, preferredAsset = null) {
  try { await loadManualRates(); }
  catch (error) { toast(error.message); return; }
  const choices = state.assets.filter((asset) => asset.code !== state.context.workspace.base_asset.code);
  if (!choices.length) return toast("No rate pairs are available");
  const assetCode = choices.some((asset) => asset.code === preferredAsset) ? preferredAsset : choices[0].code;
  const draft = { assetCode, rate: rateForAsset(assetCode)?.rate || "", error: "", opener };
  openMobileSheet({
    kicker: "EXCHANGE",
    title: "Set a rate",
    secondaryLabel: "Cancel",
    primaryLabel: "Save rate",
    buildBody: () => buildMobileRateBody(draft),
    onPrimary: async () => {
      draft.error = "";
      if (!draft.rate.trim()) {
        draft.error = "Rate is required.";
        renderMobileOverlay();
        return;
      }
      try {
        await api(`/api/v1/workspaces/${state.context.workspace.id}/valuation-rates/${draft.assetCode}`, {
          method: "PUT",
          body: JSON.stringify({ rate: draft.rate.trim() }),
        });
        await refreshAll();
        await loadManualRates();
        closeAllMobileOverlays();
        openMobileConfirmation({ title: "Saved", body: `${ratePairLabel(draft.assetCode)} rate was saved.`, variant: "saved" }, opener);
      } catch (error) {
        draft.error = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
}

async function openRateSettings(opener = document.activeElement, preferredAsset = null) {
  if (isMobileViewport()) return openMobileRateSettings(opener, preferredAsset);
  document.querySelector(".profile-menu").removeAttribute("open");
  try { await loadManualRates(); }
  catch (error) { return toast(error.message); }
  const choices = state.assets.filter((asset) => asset.code !== state.context.workspace.base_asset.code);
  selectOptions($("rate-asset"), choices.map((asset) => ({ value: asset.code, label: ratePairLabel(asset.code) })), { selected: preferredAsset || choices[0]?.code });
  renderDesktopRateValue();
  $("rate-error").textContent = "";
  $("rate-dialog").showModal();
}

function renderDesktopRateValue() {
  const existing = rateForAsset($("rate-asset").value);
  $("rate-value").value = existing?.rate || "";
  $("delete-rate").classList.toggle("hidden", !existing);
}

async function saveDesktopRate(event) {
  event.preventDefault();
  $("rate-error").textContent = "";
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/valuation-rates/${$("rate-asset").value}`, {
      method: "PUT",
      body: JSON.stringify({ rate: $("rate-value").value.trim() }),
    });
    $("rate-dialog").close();
    await refreshAll();
    toast("Rate saved");
  } catch (error) { $("rate-error").textContent = error.message; }
}

async function deleteDesktopRate() {
  $("rate-error").textContent = "";
  try {
    await api(`/api/v1/workspaces/${state.context.workspace.id}/valuation-rates/${$("rate-asset").value}`, { method: "DELETE" });
    $("rate-dialog").close();
    await refreshAll();
    toast("Rate deleted");
  } catch (error) { $("rate-error").textContent = error.message; }
}

function isActiveSharingContext(context) {
  return mobileOverlayState.stack.at(-1)?.context === context;
}

function mobileSharingBody(context) {
  const sharingAccount = context.account;
  const body = document.createElement("div");
  body.className = "mobile-sharing-body";
  body.append(mobileChoiceField({
    label: "Role",
    value: roleLabel(state.invitationRole),
    id: "mobile-invitation-role",
    onOpen: () => openMobileChoose({
      title: "Role",
      returnFocusSelector: "#mobile-invitation-role",
      options: [
        ...["viewer", "contributor", "editor"].map((value) => ({ value, label: roleLabel(value), current: state.invitationRole === value })),
        { value: "owner", label: "Owner · Coming soon", disabled: true },
      ],
      onSelect: (value) => { state.invitationRole = value; },
    }, document.activeElement),
  }));
  if (state.invitationUrl) {
    const invite = document.createElement("div");
    invite.className = "mobile-invite-result";
    const value = document.createElement("input");
    value.className = "mobile-field";
    value.readOnly = true;
    value.value = state.invitationUrl;
    value.setAttribute("aria-label", "Invitation link");
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "mobile-button-inline mobile-interactive";
    copy.textContent = "Copy link";
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(state.invitationUrl); }
      catch (_error) { value.select(); document.execCommand("copy"); }
      toast("Invite link copied");
    });
    invite.append(value, copy);
    body.append(invite);
  }
  const heading = document.createElement("p");
  heading.className = "mobile-sheet-section-title";
  heading.textContent = "PEOPLE";
  body.append(heading);
  const people = document.createElement("div");
  people.className = "mobile-people-list";
  if (!state.sharingRows.length && !state.sharingError) {
    people.innerHTML = '<p class="muted" role="status">Loading access…</p>';
  }
  for (const row of state.sharingRows) {
    const item = document.createElement("div");
    item.className = "mobile-person-row";
    item.innerHTML = `<span><strong>${escapeHtml(row.user.display_name)}</strong><small>@${escapeHtml(row.user.username)}</small></span>`;
    if (row.role === "owner") {
      const owner = document.createElement("span");
      owner.className = "mobile-role-label";
      owner.textContent = "Owner · Coming soon";
      item.append(owner);
    } else {
      const role = document.createElement("button");
      role.type = "button";
      role.className = "mobile-role-button mobile-interactive";
      role.textContent = `${roleLabel(row.role)} ›`;
      role.addEventListener("click", () => openMobileChoose({
        title: "Role",
        returnFocusSelector: ".mobile-role-button",
        options: [
          ...["viewer", "contributor", "editor"].map((value) => ({ value, label: roleLabel(value), current: row.role === value })),
          { value: "owner", label: "Owner · Coming soon", disabled: true },
        ],
        onSelect: async (value) => {
          try {
            await api(`/api/v1/accounts/${sharingAccount.id}/access/${row.user.id}`, { method: "PATCH", body: JSON.stringify({ role: value }) });
            await loadMobileAccess(context);
          } catch (error) {
            if (!isActiveSharingContext(context)) return;
            state.sharingError = error.message;
            renderMobileOverlay();
          }
        },
      }, role));
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "mobile-person-remove mobile-interactive";
      remove.setAttribute("aria-label", `Remove ${row.user.display_name}`);
      remove.textContent = "×";
      remove.addEventListener("click", () => openMobileConfirmation({
        title: `Remove ${row.user.display_name}?`,
        body: `They will no longer see or use ${sharingAccount.name}. Existing transaction history is kept.`,
        actionLabel: "Remove",
        variant: "destructive",
        onAction: async () => {
          await api(`/api/v1/accounts/${sharingAccount.id}/access/${row.user.id}`, { method: "DELETE" });
          await loadMobileAccess(context);
        },
      }, remove));
      item.append(role, remove);
    }
    people.append(item);
  }
  body.append(people);
  const error = document.createElement("p");
  error.className = "form-error";
  error.setAttribute("role", "alert");
  error.textContent = state.sharingError;
  body.append(error);
  return body;
}

async function loadMobileAccess(context) {
  const accountId = context.account.id;
  try {
    const rows = await api(`/api/v1/accounts/${accountId}/access`);
    if (!isActiveSharingContext(context)) return;
    state.sharingRows = rows;
    state.sharingError = "";
  } catch (error) {
    if (!isActiveSharingContext(context)) return;
    state.sharingRows = [];
    state.sharingError = error.message;
  }
  renderMobileOverlay();
}

function openMobileSharing(account, opener = document.activeElement) {
  const context = { kind: "sharing", account };
  state.sharingAccount = account;
  state.sharingRows = [];
  state.sharingError = "";
  state.invitationRole = "viewer";
  state.invitationUrl = "";
  openMobileSheet({
    kicker: "ACCESS",
    title: `Share ${account.name}`,
    context,
    buildBody: () => mobileSharingBody(context),
    primaryLabel: "Create invite link",
    onPrimary: async () => {
      try {
        const invitation = await api(`/api/v1/accounts/${account.id}/invitations`, {
          method: "POST",
          body: JSON.stringify({ role: state.invitationRole }),
        });
        const invite = new URL(window.location.origin);
        invite.searchParams.set("invite", invitation.token);
        state.invitationUrl = invite.toString();
        renderMobileOverlay();
      } catch (error) {
        state.sharingError = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
  void loadMobileAccess(context);
}

async function openSharing(account, opener = document.activeElement) {
  state.sharingAccount = account;
  if (isMobileViewport()) {
    openMobileSharing(account, opener);
    return;
  }
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

async function openCategories(opener = document.activeElement) {
  if (isMobileViewport()) return openMobileCategories(opener);
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
    income: "Expected income",
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

function planOccurrenceNode(occurrence, { label = null, overdueCount = 0 } = {}) {
  const row = document.createElement("article");
  row.className = `plan-item ${occurrence.status}`;
  const actual = occurrence.actual_amount === null
    ? ""
    : `<small>Planned ${formatMoney(occurrence.planned_amount, occurrence.rule.asset.code)} · actual ${formatMoney(occurrence.actual_amount, (occurrence.actual_asset ?? occurrence.rule.asset).code)}</small>`;
  const badge = overdueCount > 1
    ? ` <span class="badge overdue">${overdueCount} overdue</span>`
    : "";
  row.innerHTML = `
    <div class="plan-item-main"><strong>${escapeHtml(label ?? occurrence.rule.name)}</strong><span>${localDate(occurrence.due_date)} · ${escapeHtml(occurrence.status)}${badge}</span></div>
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
    const badgeNode = document.createElement("span");
    badgeNode.className = `badge ${occurrence.status}`;
    badgeNode.textContent = occurrence.status;
    actions.append(badgeNode);
  }
  return row;
}

function ruleOccurrences(rule) {
  return state.planOccurrences.filter((item) => item.plan_rule_id === rule.id);
}

function nearestRuleOccurrences(rule) {
  const occurrences = ruleOccurrences(rule);
  const overdue = occurrences
    .filter((item) => item.status === "overdue")
    .sort((a, b) => (a.due_date < b.due_date ? 1 : -1));
  const future = occurrences
    .filter((item) => item.status === "planned")
    .sort((a, b) => (a.due_date > b.due_date ? 1 : -1));
  return { nearestOverdue: overdue[0] ?? null, overdueCount: overdue.length, nearestFuture: future[0] ?? null };
}

function planRuleCardNode(rule) {
  const card = document.createElement("article");
  card.className = "rule-card plan-rule-card mobile-surface";
  card.innerHTML = `
    <div class="plan-rule-head">
      <div><strong>${escapeHtml(rule.name)}</strong><span class="plan-rule-meta">${planKindIcon(rule.kind)} ${escapeHtml(planKindLabel(rule.kind))} · ${moneyMarkup(rule.amount, rule.asset.code)} · ${escapeHtml(rule.recurrence)}</span></div>
      <div class="rule-actions"></div>
    </div>
    <div class="plan-card-rows"></div>`;
  const actions = card.querySelector(".rule-actions");
  const show = document.createElement("button");
  show.type = "button";
  show.className = "button-quiet";
  show.textContent = "Show";
  show.title = "Show occurrence history";
  show.addEventListener("click", () => openPlanRuleDetail(rule));
  const edit = document.createElement("button");
  edit.type = "button";
  edit.className = "button-quiet";
  edit.textContent = "Edit";
  edit.title = "Edit rule";
  edit.addEventListener("click", () => openPlanRule(rule));
  const archive = document.createElement("button");
  archive.type = "button";
  archive.className = "button-quiet";
  archive.textContent = "×";
  archive.title = "Archive rule";
  archive.setAttribute("aria-label", `Archive ${rule.name}`);
  archive.addEventListener("click", () => archivePlanRule(rule));
  actions.append(show, edit, archive);
  const rows = card.querySelector(".plan-card-rows");
  const { nearestOverdue, overdueCount, nearestFuture } = nearestRuleOccurrences(rule);
  if (nearestOverdue) rows.append(planOccurrenceNode(nearestOverdue, { label: "Overdue", overdueCount }));
  if (nearestFuture) rows.append(planOccurrenceNode(nearestFuture, { label: "Next" }));
  if (!nearestOverdue && !nearestFuture) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No open occurrences";
    rows.append(empty);
  }
  return card;
}

function renderPlan() {
  const open = state.planOccurrences.filter((item) => ["planned", "overdue"].includes(item.status));
  const completed = state.planOccurrences.filter((item) => item.status === "completed");
  $("plan-open-count").textContent = String(open.length);
  $("plan-completed-count").textContent = String(completed.length);
  $("plan-rule-count").textContent = `${state.planRules.length} active`;
  $("plan-rule-cards").replaceChildren(...state.planRules.map((rule) => planRuleCardNode(rule)));
  $("plan-empty").classList.toggle("hidden", state.planRules.length > 0);
  $("plan-rule-cards").classList.toggle("hidden", state.planRules.length === 0);
  if ($("plan-rule-detail-dialog").open) renderPlanRuleDetail();
}

let planDetailRuleId = null;

function openPlanRuleDetail(rule) {
  planDetailRuleId = rule.id;
  $("plan-rule-detail-title").textContent = rule.name;
  $("plan-rule-detail-summary").textContent = `${planKindLabel(rule.kind)} · ${formatMoney(rule.amount, rule.asset.code)} · ${rule.recurrence} · from ${localDate(rule.first_due_date)}`;
  $("plan-detail-filter").value = "all";
  renderPlanRuleDetail();
  $("plan-rule-detail-dialog").showModal();
}

function renderPlanRuleDetail() {
  if (planDetailRuleId === null) return;
  const filter = $("plan-detail-filter").value;
  let items = state.planOccurrences.filter((item) => item.plan_rule_id === planDetailRuleId);
  if (filter === "open") items = items.filter((item) => ["planned", "overdue"].includes(item.status));
  if (filter === "completed") items = items.filter((item) => item.status === "completed");
  if (filter === "skipped") items = items.filter((item) => item.status === "skipped");
  items.sort((a, b) => (a.due_date > b.due_date ? 1 : a.due_date < b.due_date ? -1 : a.id - b.id));
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No occurrences for this filter";
    $("plan-rule-detail-list").replaceChildren(empty);
    return;
  }
  $("plan-rule-detail-list").replaceChildren(...items.map((item) => planOccurrenceNode(item)));
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
    && !transaction.plan_occurrence_id;
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

function transactionDisplayType(transaction) {
  return transaction.type === "exchange"
    ? "Transfer"
    : `${transaction.type[0].toUpperCase()}${transaction.type.slice(1)}`;
}

function transactionCategoryName(transaction) {
  const category = [...state.categories.values()].flat().find((item) => item.id === transaction.category_id);
  return category ? `${category.name}${category.archived_at ? " (archived)" : ""}` : "Uncategorized";
}

function feedTransactionItem(transaction) {
  return {
    kind: "transaction",
    key: `transaction:${transaction.id}`,
    financial_date: transaction.local_date,
    mobile_type: transaction.type === "exchange" ? "transfer" : transaction.type,
    transaction_type: transaction.type,
    transaction,
  };
}

function feedItemTitle(item) {
  return item.kind === "planned" ? item.occurrence.rule.name : transactionTitle(item.transaction);
}

function feedItemStatus(item) {
  if (item.kind === "planned") return "Planned";
  return item.transaction.status === "deleted" ? "Deleted" : "";
}

function signedMoneyMarkup(value, code, sign = "") {
  const raw = String(value).replace(/^[+−-]/, "");
  return moneyMarkup(`${sign}${raw}`, code);
}

function feedItemAmountMarkup(item) {
  if (item.kind === "planned") {
    const occurrence = item.occurrence;
    const kind = occurrence.rule.kind;
    const sign = kind === "income" ? "+" : kind === "reserve_transfer" ? "±" : "−";
    if (sign === "±") {
      const parts = moneyParts(occurrence.planned_amount, occurrence.rule.asset.code);
      return `<span class="mobile-money"><span class="mobile-money-value">±${escapeHtml(parts.value)}</span><span class="mobile-money-code">${escapeHtml(parts.code)}</span></span>`;
    }
    return signedMoneyMarkup(occurrence.planned_amount, occurrence.rule.asset.code, sign);
  }
  const transaction = item.transaction;
  const legs = transaction.legs;
  if (!legs.length) return '<span class="mobile-money-value">Hidden</span>';
  if (["transfer", "exchange"].includes(transaction.type)) {
    const leg = legs.find((candidate) => String(candidate.amount).startsWith("-")) || legs[0];
    const parts = moneyParts(String(leg.amount).replace("-", ""), leg.asset.code);
    return `<span class="mobile-money"><span class="mobile-money-value">±${escapeHtml(parts.value)}</span><span class="mobile-money-code">${escapeHtml(parts.code)}</span></span>`;
  }
  const leg = legs[0];
  const sign = transaction.type === "income"
    || (transaction.type === "adjustment" && !String(leg.amount).startsWith("-"))
    ? "+"
    : "−";
  return signedMoneyMarkup(leg.amount, leg.asset.code, sign);
}

function feedGroupLabel(value) {
  const today = todayValue();
  const yesterdayDate = new Date(`${today}T12:00:00`);
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterday = `${yesterdayDate.getFullYear()}-${String(yesterdayDate.getMonth() + 1).padStart(2, "0")}-${String(yesterdayDate.getDate()).padStart(2, "0")}`;
  if (value === today) return "TODAY";
  if (value === yesterday) return "YESTERDAY";
  return localDate(value).toUpperCase();
}

function canLinkTransactionToPlan(transaction) {
  return transaction.workspace_id === state.context.workspace.id
    && transaction.status === "posted"
    && !transaction.plan_occurrence_id
    && ["expense", "income", "transfer"].includes(transaction.type);
}

async function loadMobileTransactionFeed(append = false) {
  if (state.transactionFeedLoading) return false;
  state.transactionFeedLoading = true;
  setLoading(true);
  try {
    const query = new URLSearchParams({ filter: state.transactionFeedFilter, limit: "50" });
    if (append && state.transactionFeedCursor) query.set("cursor", state.transactionFeedCursor);
    const page = await api(`/api/v1/transaction-feed?${query}`);
    state.transactionFeedItems = append ? [...state.transactionFeedItems, ...page.items] : page.items;
    state.transactionFeedCursor = page.next_cursor;
    renderTransactions();
    return true;
  } catch (error) {
    toast(error.message);
    return false;
  } finally {
    state.transactionFeedLoading = false;
    setLoading(false);
  }
}

function closeTransactionSwipes(except = null) {
  document.querySelectorAll(".mobile-transaction-row.is-swiped").forEach((row) => {
    if (row !== except) row.classList.remove("is-swiped");
  });
}

function enableTransactionSwipe(row, body) {
  let startX = null;
  body.addEventListener("pointerdown", (event) => { startX = event.clientX; });
  body.addEventListener("pointerup", (event) => {
    if (startX === null) return;
    const delta = event.clientX - startX;
    startX = null;
    if (delta < -32) {
      closeTransactionSwipes(row);
      row.classList.add("is-swiped");
    } else if (delta > 24) row.classList.remove("is-swiped");
  });
  body.addEventListener("pointercancel", () => { startX = null; });
  row.addEventListener("focusin", (event) => {
    if (event.target.closest(".mobile-swipe-actions")) {
      closeTransactionSwipes(row);
      row.classList.add("is-swiped");
    }
  });
}

function mobileFeedRow(item) {
  const row = document.createElement("article");
  row.className = `mobile-transaction-row ${item.mobile_type}`;
  row.dataset.feedKey = item.key;
  const actions = document.createElement("div");
  actions.className = "mobile-swipe-actions";
  const transaction = item.kind === "transaction" ? item.transaction : null;
  if (transaction && canLinkTransactionToPlan(transaction)) {
    const plan = document.createElement("button");
    plan.type = "button";
    plan.className = "mobile-swipe-plan mobile-interactive";
    plan.textContent = "Plan";
    plan.addEventListener("click", () => openMobilePlanLink(transaction, plan));
    actions.append(plan);
  }
  if (transaction && canEditTransaction(transaction)) {
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "mobile-swipe-delete mobile-interactive";
    remove.textContent = "Delete";
    remove.addEventListener("click", () => openMobileDeleteTransaction(transaction, remove));
    actions.append(remove);
  }
  const body = document.createElement("button");
  body.type = "button";
  body.className = "mobile-transaction-body mobile-interactive";
  const status = feedItemStatus(item);
  const author = item.kind === "planned"
    ? "Plan"
    : item.transaction.created_by_user_id === state.context.user.id ? "You" : `User #${item.transaction.created_by_user_id}`;
  const icon = item.mobile_type === "income" ? "↑" : item.mobile_type === "expense" ? "↓" : "±";
  body.innerHTML = `
    <span class="mobile-transaction-icon" aria-hidden="true">${icon}</span>
    <span class="mobile-transaction-main"><strong>${escapeHtml(feedItemTitle(item))}</strong><span>${escapeHtml(author)}${status ? `<span class="mobile-status-pill ${status.toLowerCase()}">${escapeHtml(status)}</span>` : ""}</span></span>
    <span class="mobile-transaction-amount">${feedItemAmountMarkup(item)}</span>`;
  body.addEventListener("click", () => {
    if (row.classList.contains("is-swiped")) {
      row.classList.remove("is-swiped");
      return;
    }
    void openFeedItemDetail(item, body);
  });
  row.append(actions, body);
  enableTransactionSwipe(row, body);
  return row;
}

function renderMobileTransactions() {
  const items = state.transactionAdvancedActive
    ? state.transactions.map(feedTransactionItem).sort((left, right) => (
      right.financial_date.localeCompare(left.financial_date)
      || String(right.transaction.occurred_at).localeCompare(String(left.transaction.occurred_at))
      || right.transaction.id - left.transaction.id
    ))
    : state.transactionFeedItems;
  const fragment = document.createDocumentFragment();
  let currentDate = null;
  let group = null;
  for (const item of items) {
    if (item.financial_date !== currentDate) {
      currentDate = item.financial_date;
      group = document.createElement("section");
      group.className = "mobile-transaction-group";
      const heading = document.createElement("h3");
      heading.className = "mobile-transaction-date";
      heading.textContent = feedGroupLabel(currentDate);
      group.append(heading);
      fragment.append(group);
    }
    group.append(mobileFeedRow(item));
  }
  $("transaction-list").replaceChildren(fragment);
  $("transactions-empty").classList.toggle("hidden", items.length > 0);
  const cursor = state.transactionAdvancedActive ? state.nextCursor : state.transactionFeedCursor;
  $("load-more").classList.toggle("hidden", !cursor);
  document.querySelectorAll("[data-feed-filter]").forEach((button) => {
    const active = !state.transactionAdvancedActive && button.dataset.feedFilter === state.transactionFeedFilter;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  $("transaction-filter-count").textContent = String(state.transactionAdvancedCount);
  $("transaction-filter-count").setAttribute("aria-label", `${state.transactionAdvancedCount} active filters`);
  $("transaction-filter-count").classList.toggle("hidden", !state.transactionAdvancedActive || !state.transactionAdvancedCount);
}

async function openFeedItemDetail(item, opener = document.activeElement) {
  try {
    if (item.kind === "planned") {
      const id = item.occurrence.id;
      const detail = await api(`/api/v1/transaction-feed/planned/${id}`);
      openMobilePlannedDetail(detail, opener);
      return;
    }
    const detail = await api(`/api/v1/transaction-feed/transaction/${item.transaction.id}`);
    openMobileTransactionDetails(detail.transaction, opener);
  } catch (error) { toast(error.message); }
}

function mobileTransactionDetailBody(transaction) {
  const body = document.createElement("div");
  body.className = "mobile-transaction-detail";
  const author = transaction.created_by_user_id === state.context.user.id ? "You" : `User #${transaction.created_by_user_id}`;
  const details = document.createElement("dl");
  details.className = "mobile-readonly-list";
  details.innerHTML = `
    <div><dt>Status</dt><dd>${escapeHtml(`${transaction.status[0].toUpperCase()}${transaction.status.slice(1)}`)}</dd></div>
    <div><dt>Type</dt><dd>${escapeHtml(transactionDisplayType(transaction))}</dd></div>
    <div><dt>Amount</dt><dd>${feedItemAmountMarkup(feedTransactionItem(transaction))}</dd></div>
    <div><dt>Financial date</dt><dd>${escapeHtml(localDate(transaction.local_date))}</dd></div>
    <div><dt>Category</dt><dd>${escapeHtml(transactionCategoryName(transaction))}</dd></div>
    <div><dt>Created by</dt><dd>${escapeHtml(author)}</dd></div>`;
  body.append(details);
  if (transaction.status === "unassigned" && transaction.created_by_user_id === state.context.user.id) {
    const assign = document.createElement("button");
    assign.type = "button";
    assign.className = "mobile-button-inline mobile-interactive";
    assign.textContent = "Assign account";
    assign.addEventListener("click", () => openMobileAssignTransaction(transaction, assign));
    body.append(assign);
  }
  const heading = document.createElement("h3");
  heading.className = "mobile-sheet-section-title";
  heading.textContent = "VISIBLE MOVEMENTS";
  body.append(heading);
  const movements = document.createElement("div");
  movements.className = "mobile-transaction-movements";
  if (!transaction.legs.length) movements.innerHTML = '<p class="muted">No visible movements.</p>';
  for (const leg of transaction.legs) {
    const row = document.createElement("div");
    const account = accountById(leg.account_id);
    row.innerHTML = `<span>${escapeHtml(account ? account.name : leg.account_id === null ? "Unassigned" : "Accessible account")}</span><strong>${moneyMarkup(leg.amount, leg.asset.code)}</strong>`;
    movements.append(row);
  }
  body.append(movements);
  if (transaction.has_hidden_legs) {
    const hidden = document.createElement("p");
    hidden.className = "mobile-sheet-hint";
    hidden.textContent = "Some movements are hidden because you only have access to part of this transaction.";
    body.append(hidden);
  }
  return body;
}

function openMobileTransactionDetails(transaction, opener = document.activeElement) {
  state.viewingTransaction = transaction;
  const editable = canEditTransaction(transaction);
  openMobileSheet({
    kicker: "LEDGER ENTRY",
    title: transactionTitle(transaction),
    buildBody: () => mobileTransactionDetailBody(transaction),
    secondaryLabel: editable ? "Delete" : "",
    onSecondary: () => openMobileDeleteTransaction(transaction, document.activeElement),
    primaryLabel: editable ? "Edit" : "",
    onPrimary: () => openMobileTransactionEdit(transaction, document.activeElement),
  }, opener);
}

function openMobileDeleteTransaction(transaction, opener = document.activeElement) {
  const label = transactionDisplayType(transaction).toLowerCase();
  openMobileConfirmation({
    title: `Delete this ${label}?`,
    body: "It stays in history as Deleted but no longer affects balances or periods.",
    actionLabel: "Delete",
    variant: "destructive",
    closeParentsOnSuccess: mobileOverlayState.stack.at(-1)?.kind === "sheet" ? 1 : 0,
    onAction: async () => {
      await api(`/api/v1/transactions/${transaction.id}/delete`, {
        method: "POST",
        body: JSON.stringify({ confirm_ended_period: true }),
      });
      await refreshAll();
      toast("Transaction deleted");
    },
  }, opener);
}

function openMobileAssignTransaction(transaction, opener = document.activeElement) {
  const leg = transaction.legs[0];
  const action = transaction.type === "expense" ? "expense" : "income";
  const choices = state.accounts.filter((account) => account.asset.code === leg.asset.code && canUseAccount(account, action));
  if (!choices.length) return toast(`No accessible ${leg.asset.code} account`);
  openMobileChoose({
    title: "Account",
    options: choices.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}` })),
    onSelect: async (value) => {
      try {
        await api(`/api/v1/transactions/${transaction.id}/assign-account`, {
          method: "POST",
          body: JSON.stringify({ account_id: Number(value) }),
        });
        closeAllMobileOverlays();
        await refreshAll();
        openMobileConfirmation({ title: "Saved", body: "The transaction was assigned to an account.", variant: "saved" }, opener);
      } catch (error) {
        if (error.status === 409 && String(error.message).includes("explicit confirmation")) {
          openMobileConfirmation({
            title: "Assign this transaction?",
            body: "Assigning it changes an ended account period and recalculates its history.",
            actionLabel: "Assign account",
            onAction: async () => {
              await api(`/api/v1/transactions/${transaction.id}/assign-account`, {
                method: "POST",
                body: JSON.stringify({ account_id: Number(value), confirm_ended_period: true }),
              });
              closeAllMobileOverlays();
              await refreshAll();
              openMobileConfirmation({ title: "Saved", body: "The transaction was assigned to an account.", variant: "saved" }, opener);
            },
          }, opener);
          return;
        }
        toast(error.message);
      }
    },
  }, opener);
}

function mobilePlannedDetailBody(detail) {
  const occurrence = detail.occurrence;
  const rule = occurrence.rule;
  const body = document.createElement("div");
  body.className = "mobile-transaction-detail";
  const accountId = rule.kind === "income" ? rule.default_to_account_id : rule.default_from_account_id;
  const account = accountById(accountId);
  const label = rule.kind === "income" ? "To account" : "From account";
  const details = document.createElement("dl");
  details.className = "mobile-readonly-list";
  details.innerHTML = `
    <div><dt>Status</dt><dd>${escapeHtml(detail.mobile_status)}</dd></div>
    <div><dt>Due</dt><dd>${escapeHtml(localDate(occurrence.due_date))}</dd></div>
    <div><dt>Amount</dt><dd>${moneyMarkup(occurrence.planned_amount, rule.asset.code)}</dd></div>
    <div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(account?.name || "Not selected")}</dd></div>
    <div><dt>Repeats</dt><dd>${escapeHtml(rule.recurrence)}</dd></div>
    <div><dt>Matched transaction</dt><dd>${occurrence.transaction_id ? `#${occurrence.transaction_id}` : "—"}</dd></div>`;
  body.append(details);
  const hint = document.createElement("p");
  hint.className = "mobile-sheet-hint";
  hint.textContent = "Plan items never change real balances until a transaction is linked.";
  body.append(hint);
  return body;
}

function openMobilePlannedDetail(detail, opener = document.activeElement) {
  openMobileSheet({
    kicker: "PLAN",
    title: detail.occurrence.rule.name,
    buildBody: () => mobilePlannedDetailBody(detail),
    primaryLabel: detail.available_actions.includes("link_transaction") ? "Link transaction" : "",
    onPrimary: () => openMobilePlanLink(null, document.activeElement, detail.occurrence),
  }, opener);
}

function eligiblePlanOccurrences(transaction) {
  return state.planOccurrences.filter((occurrence) => (
    ["planned", "overdue"].includes(occurrence.status)
    && transactionMatchesOccurrence(transaction, occurrence)
  ));
}

function eligiblePlanTransactions(occurrence) {
  return state.transactions.filter((transaction) => (
    transactionMatchesOccurrence(transaction, occurrence)
    && !transaction.plan_occurrence_id
  ));
}

function openMobilePlanLink(transaction = null, opener = document.activeElement, occurrence = null) {
  const occurrences = transaction ? eligiblePlanOccurrences(transaction) : state.planOccurrences.filter((item) => ["planned", "overdue"].includes(item.status));
  const transactions = occurrence ? eligiblePlanTransactions(occurrence) : state.transactions.filter((item) => canLinkTransactionToPlan(item));
  const draft = {
    occurrenceId: occurrence?.id || occurrences[0]?.id || null,
    transactionId: transaction?.id || transactions[0]?.id || null,
    error: "",
  };
  const bodyBuilder = () => {
    const body = document.createElement("div");
    body.className = "mobile-account-form";
    body.append(mobileChoiceField({
      label: "Plan item",
      value: occurrences.find((item) => item.id === Number(draft.occurrenceId))?.rule.name || "Choose plan item",
      id: "mobile-plan-link-occurrence",
      onOpen: () => openMobileChoose({
        title: "Plan item",
        returnFocusSelector: "#mobile-plan-link-occurrence",
        options: occurrences.map((item) => ({ value: item.id, label: `${item.rule.name} · ${localDate(item.due_date)}`, current: item.id === Number(draft.occurrenceId) })),
        onSelect: (value) => { draft.occurrenceId = Number(value); },
      }, document.activeElement),
    }));
    body.append(mobileChoiceField({
      label: "Transaction",
      value: transactions.find((item) => item.id === Number(draft.transactionId)) ? transactionTitle(transactions.find((item) => item.id === Number(draft.transactionId))) : "Choose transaction",
      id: "mobile-plan-link-transaction",
      onOpen: () => openMobileChoose({
        title: "Transaction",
        returnFocusSelector: "#mobile-plan-link-transaction",
        options: transactions.map((item) => ({ value: item.id, label: `${transactionTitle(item)} · ${localDate(item.local_date)}`, current: item.id === Number(draft.transactionId) })),
        onSelect: (value) => { draft.transactionId = Number(value); },
      }, document.activeElement),
    }));
    const hint = document.createElement("p");
    hint.className = "mobile-sheet-hint";
    hint.textContent = "Only eligible posted transactions are shown.";
    const error = document.createElement("p");
    error.className = "form-error";
    error.setAttribute("role", "alert");
    error.textContent = draft.error;
    body.append(hint, error);
    return body;
  };
  openMobileSheet({
    kicker: "PLAN VS ACTUAL",
    title: "Link transaction",
    buildBody: bodyBuilder,
    secondaryLabel: "Cancel",
    primaryLabel: "Link transaction",
    onPrimary: async () => {
      if (!draft.occurrenceId || !draft.transactionId) {
        draft.error = "Choose both a plan item and a transaction";
        renderMobileOverlay();
        return;
      }
      try {
        await api(`/api/v1/workspaces/${state.context.workspace.id}/plan-occurrences/${draft.occurrenceId}/link-transaction`, {
          method: "POST",
          body: JSON.stringify({ transaction_id: Number(draft.transactionId) }),
        });
        closeAllMobileOverlays();
        await refreshAll();
        openMobileConfirmation({ title: "Saved", body: "The transaction was linked to the Plan item.", variant: "saved" }, opener);
      } catch (error) {
        draft.error = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
}

function transactionEditAccountChoices(transaction, action = null) {
  const requiredAction = action || (transaction.type === "expense" ? "expense" : transaction.type === "income" ? "income" : transaction.type === "adjustment" ? "owner" : "edit");
  return state.accounts.filter((account) => canUseAccount(account, requiredAction));
}

function mobileEditChoice(label, value, id, options, onSelect) {
  return mobileChoiceField({
    label,
    value,
    id,
    onOpen: () => openMobileChoose({
      title: label,
      returnFocusSelector: `#${id}`,
      options,
      onSelect,
    }, document.activeElement),
  });
}

function mobileEditInput(label, id, value, draft, key, { inputmode = "text", multiline = false } = {}) {
  const field = document.createElement("label");
  field.className = "mobile-sheet-field";
  const tag = multiline ? "textarea" : "input";
  field.innerHTML = `<span class="mobile-sheet-field-label">${escapeHtml(label)}</span><${tag} id="${id}" class="mobile-field" inputmode="${inputmode}"></${tag}>`;
  const input = field.querySelector(tag);
  input.value = value || "";
  input.addEventListener("input", (event) => { draft[key] = event.target.value; });
  return field;
}

function monthStartValue(value) {
  const date = new Date(`${value || todayValue()}T00:00:00Z`);
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-01`;
}

function shiftedMonthValue(value, offset) {
  const date = new Date(`${monthStartValue(value)}T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() + offset);
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-01`;
}

function mobileCalendarDates(month) {
  const first = new Date(`${monthStartValue(month)}T00:00:00Z`);
  first.setUTCDate(first.getUTCDate() - first.getUTCDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(first);
    date.setUTCDate(first.getUTCDate() + index);
    return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}-${String(date.getUTCDate()).padStart(2, "0")}`;
  });
}

function openMobileDateChoose({ label, value, allowAny = false, onSelect, returnFocusSelector }, opener = document.activeElement) {
  const picker = { month: monthStartValue(value) };
  openMobileSheet({
    kicker: "CHOOSE",
    title: label,
    returnFocusSelector,
    buildBody: () => {
      const body = document.createElement("div");
      body.className = "mobile-date-picker";
      if (allowAny) {
        const any = document.createElement("button");
        any.type = "button";
        any.className = "mobile-option mobile-date-any";
        any.innerHTML = `<span>Any</span><span class="mobile-option-current" aria-hidden="true">${value ? "" : "✓"}</span>`;
        any.addEventListener("click", () => { onSelect(""); closeMobileOverlay(); });
        body.append(any);
      }
      const toolbar = document.createElement("div");
      toolbar.className = "mobile-date-toolbar";
      const previous = document.createElement("button");
      previous.type = "button";
      previous.className = "mobile-date-nav mobile-interactive";
      previous.setAttribute("aria-label", "Previous month");
      previous.textContent = "‹";
      const heading = document.createElement("strong");
      heading.textContent = new Intl.DateTimeFormat("en", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${picker.month}T00:00:00Z`));
      const next = document.createElement("button");
      next.type = "button";
      next.className = "mobile-date-nav mobile-interactive";
      next.setAttribute("aria-label", "Next month");
      next.textContent = "›";
      previous.addEventListener("click", () => { picker.month = shiftedMonthValue(picker.month, -1); renderMobileOverlay(); });
      next.addEventListener("click", () => { picker.month = shiftedMonthValue(picker.month, 1); renderMobileOverlay(); });
      toolbar.append(previous, heading, next);
      body.append(toolbar);
      const weekdays = document.createElement("div");
      weekdays.className = "mobile-date-weekdays";
      for (const day of ["S", "M", "T", "W", "T", "F", "S"]) {
        const cell = document.createElement("span");
        cell.textContent = day;
        weekdays.append(cell);
      }
      body.append(weekdays);
      const grid = document.createElement("div");
      grid.className = "mobile-date-grid";
      const monthPrefix = picker.month.slice(0, 7);
      for (const date of mobileCalendarDates(picker.month)) {
        const day = document.createElement("button");
        day.type = "button";
        day.className = "mobile-date-day mobile-interactive";
        day.classList.toggle("outside", !date.startsWith(monthPrefix));
        day.classList.toggle("current", date === value);
        day.textContent = String(Number(date.slice(-2)));
        day.setAttribute("aria-label", localDate(date));
        day.setAttribute("aria-pressed", String(date === value));
        day.addEventListener("click", () => { onSelect(date); closeMobileOverlay(); });
        grid.append(day);
      }
      body.append(grid);
      return body;
    },
  }, opener);
}

function mobileDateChoice(label, id, value, draft, key, { allowAny = false } = {}) {
  return mobileChoiceField({
    label,
    value: value ? localDate(value) : "Any",
    id,
    onOpen: () => openMobileDateChoose({
      label,
      value,
      allowAny,
      returnFocusSelector: `#${id}`,
      onSelect: (selected) => { draft[key] = selected; },
    }, document.activeElement),
  });
}

function mobileTransactionEditBody(transaction, draft) {
  const body = document.createElement("div");
  body.className = "mobile-account-form";
  const type = document.createElement("dl");
  type.className = "mobile-readonly-list";
  type.innerHTML = `<div><dt>Type</dt><dd>${escapeHtml(transactionDisplayType(transaction))}</dd></div>`;
  body.append(type);
  const single = ["expense", "income", "adjustment"].includes(transaction.type);
  if (single) {
    const accounts = transactionEditAccountChoices(transaction);
    const selected = accountById(draft.accountId);
    body.append(mobileEditChoice(
      "Account",
      selected ? `${selected.name} · ${selected.asset.code}` : "Unassigned",
      "mobile-transaction-account",
      [
        ...(transaction.type === "adjustment" ? [] : [{ value: "", label: "Unassigned", current: !draft.accountId }]),
        ...accounts.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}`, current: account.id === Number(draft.accountId) })),
      ],
      (value) => { draft.accountId = value ? Number(value) : null; },
    ));
    body.append(mobileEditInput(transaction.type === "adjustment" ? "Delta" : "Amount", "mobile-transaction-amount", draft.amount, draft, "amount", { inputmode: "decimal" }));
  } else {
    const accounts = transactionEditAccountChoices(transaction, "edit");
    const from = accountById(draft.fromAccountId);
    const to = accountById(draft.toAccountId);
    body.append(mobileEditChoice("From account", from ? `${from.name} · ${from.asset.code}` : "Choose account", "mobile-transaction-from", accounts.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}`, current: account.id === Number(draft.fromAccountId) })), (value) => { draft.fromAccountId = Number(value); }));
    body.append(mobileEditChoice("To account", to ? `${to.name} · ${to.asset.code}` : "Choose account", "mobile-transaction-to", accounts.map((account) => ({ value: account.id, label: `${account.name} · ${account.asset.code}`, current: account.id === Number(draft.toAccountId) })), (value) => { draft.toAccountId = Number(value); }));
    body.append(mobileEditInput(transaction.type === "transfer" ? "Amount" : "From amount", "mobile-transaction-from-amount", draft.fromAmount, draft, "fromAmount", { inputmode: "decimal" }));
    if (transaction.type === "exchange") body.append(mobileEditInput("To amount", "mobile-transaction-to-amount", draft.toAmount, draft, "toAmount", { inputmode: "decimal" }));
  }
  if (["expense", "income"].includes(transaction.type)) {
    const workspaceId = accountById(draft.accountId)?.workspace_id || state.context.workspace.id;
    const categories = (state.categories.get(workspaceId) || []).filter((category) => (
      category.id === Number(draft.categoryId)
      || (!category.archived_at && [transaction.type, "both"].includes(category.kind))
    ));
    const selectedCategory = categories.find((category) => category.id === Number(draft.categoryId));
    body.append(mobileEditChoice("Category", selectedCategory?.name || "Uncategorized", "mobile-transaction-category", [
      { value: "", label: "Uncategorized", current: !draft.categoryId },
      ...categories.map((category) => ({ value: category.id, label: category.name, current: category.id === Number(draft.categoryId), disabled: Boolean(category.archived_at) })),
    ], (value) => { draft.categoryId = value ? Number(value) : null; }));
  }
  body.append(mobileDateChoice("Financial date", "mobile-transaction-date", draft.localDate, draft, "localDate"));
  body.append(mobileEditInput("Note", "mobile-transaction-note", draft.note, draft, "note", { multiline: true }));
  const hint = document.createElement("p");
  hint.className = "mobile-sheet-hint";
  hint.textContent = "Editing rewrites the movement. Balances and the active period are recalculated on save.";
  const error = document.createElement("p");
  error.className = "form-error";
  error.setAttribute("role", "alert");
  error.textContent = draft.error;
  body.append(hint, error);
  return body;
}

function mobileTransactionPatchBody(transaction, draft, confirmed = false) {
  const body = {
    local_date: draft.localDate || null,
    note: draft.note.trim() || null,
    counterparty: transaction.counterparty,
  };
  if (["expense", "income"].includes(transaction.type)) {
    body.account_id = draft.accountId;
    if (!draft.accountId) body.asset_code = transaction.legs[0].asset.code;
    body.amount = draft.amount.trim();
    body.category_id = draft.categoryId;
  } else if (transaction.type === "adjustment") {
    body.account_id = draft.accountId;
    body.delta = draft.amount.trim();
  } else {
    body.from_account_id = draft.fromAccountId;
    body.to_account_id = draft.toAccountId;
    body.from_amount = draft.fromAmount.trim();
    body.to_amount = transaction.type === "transfer" ? draft.fromAmount.trim() : draft.toAmount.trim();
  }
  if (confirmed) body.confirm_ended_period = true;
  return body;
}

async function finishMobileTransactionCorrection(transaction, opener, body) {
  await api(`/api/v1/transactions/${transaction.id}`, { method: "PATCH", body: JSON.stringify(body) });
  closeAllMobileOverlays();
  await refreshAll();
  openMobileConfirmation({
    title: "Saved",
    body: "The transaction was updated. Balances and the active period were recalculated.",
    variant: "saved",
  }, opener);
}

function openMobileTransactionEdit(transaction, opener = document.activeElement) {
  const negative = transaction.legs.find((leg) => String(leg.amount).startsWith("-"));
  const positive = transaction.legs.find((leg) => !String(leg.amount).startsWith("-"));
  const leg = transaction.legs[0];
  const draft = {
    accountId: leg?.account_id || null,
    fromAccountId: negative?.account_id || null,
    toAccountId: positive?.account_id || null,
    amount: leg ? (transaction.type === "expense" ? String(leg.amount).replace("-", "") : String(leg.amount)) : "",
    fromAmount: negative ? String(negative.amount).replace("-", "") : "",
    toAmount: positive ? String(positive.amount) : "",
    categoryId: transaction.category_id,
    localDate: transaction.local_date,
    note: transaction.note || "",
    error: "",
  };
  openMobileSheet({
    kicker: "LEDGER ENTRY",
    title: "Edit transaction",
    buildBody: () => mobileTransactionEditBody(transaction, draft),
    secondaryLabel: "Cancel",
    primaryLabel: "Save changes",
    onPrimary: async () => {
      draft.error = "";
      const body = mobileTransactionPatchBody(transaction, draft);
      try {
        await finishMobileTransactionCorrection(transaction, opener, body);
      } catch (error) {
        if (error.status === 409 && String(error.message).includes("explicit confirmation")) {
          openMobileConfirmation({
            title: "Save this correction?",
            body: "Balances and ended period history will be recalculated from the corrected movement.",
            actionLabel: "Save changes",
            onAction: () => finishMobileTransactionCorrection(transaction, opener, mobileTransactionPatchBody(transaction, draft, true)),
          }, document.activeElement);
          return;
        }
        draft.error = error.message;
        renderMobileOverlay();
      }
    },
  }, opener);
}

function transactionAdvancedDraft() {
  return {
    accountId: $("filter-account").value,
    periodId: $("filter-period").value,
    type: $("filter-type").value,
    categoryId: $("filter-category").value,
    dateFrom: $("filter-from").value,
    dateTo: $("filter-to").value,
  };
}

function advancedFilterCount(draft) {
  return Object.values(draft).filter(Boolean).length;
}

function mobileTransactionFiltersBody(draft) {
  const body = document.createElement("div");
  body.className = "mobile-account-form";
  const account = accountById(draft.accountId);
  body.append(mobileEditChoice("Account", account?.name || "All accounts", "mobile-filter-account", [
    { value: "", label: "All accounts", current: !draft.accountId },
    ...state.accounts.map((item) => ({ value: item.id, label: `${item.name} · ${item.asset.code}`, current: item.id === Number(draft.accountId) })),
  ], (value) => {
    draft.accountId = value;
    const period = state.transactionPeriods.find((item) => item.id === Number(draft.periodId));
    if (period && value && period.account_id !== Number(value)) draft.periodId = "";
  }));
  const period = state.transactionPeriods.find((item) => item.id === Number(draft.periodId));
  const periods = state.transactionPeriods.filter((item) => !draft.accountId || item.account_id === Number(draft.accountId));
  body.append(mobileEditChoice("Period", period ? `${period.account.name} · ${localDate(period.start_date)}` : "All periods", "mobile-filter-period", [
    { value: "", label: "All periods", current: !draft.periodId },
    ...periods.map((item) => ({ value: item.id, label: `${item.account.name} · ${localDate(item.start_date)} — ${localDate(item.end_date)}`, current: item.id === Number(draft.periodId) })),
  ], (value) => {
    draft.periodId = value;
    const selected = state.transactionPeriods.find((item) => item.id === Number(value));
    if (selected) draft.accountId = String(selected.account_id);
  }));
  const typeLabels = { expense: "Expense", income: "Income", transfer: "Transfer", exchange: "Exchange", adjustment: "Adjustment" };
  body.append(mobileEditChoice("Type", typeLabels[draft.type] || "All types", "mobile-filter-type", [
    { value: "", label: "All types", current: !draft.type },
    ...Object.entries(typeLabels).map(([value, label]) => ({ value, label, current: draft.type === value })),
  ], (value) => { draft.type = value; }));
  const categories = [...state.categories.values()].flat().filter((category, index, all) => all.findIndex((item) => item.id === category.id) === index);
  const category = categories.find((item) => item.id === Number(draft.categoryId));
  body.append(mobileEditChoice("Category", category?.name || "All categories", "mobile-filter-category", [
    { value: "", label: "All categories", current: !draft.categoryId },
    ...categories.map((item) => ({ value: item.id, label: item.name, current: item.id === Number(draft.categoryId), disabled: Boolean(item.archived_at) })),
  ], (value) => { draft.categoryId = value; }));
  body.append(mobileDateChoice("From", "mobile-filter-from", draft.dateFrom, draft, "dateFrom", { allowAny: true }));
  body.append(mobileDateChoice("To", "mobile-filter-to", draft.dateTo, draft, "dateTo", { allowAny: true }));
  return body;
}

function writeAdvancedFilters(draft) {
  $("filter-account").value = draft.accountId;
  $("filter-period").value = draft.periodId;
  $("filter-type").value = draft.type;
  $("filter-category").value = draft.categoryId;
  $("filter-status").value = "";
  $("filter-from").value = draft.dateFrom;
  $("filter-to").value = draft.dateTo;
}

function openMobileTransactionFilters(opener = document.activeElement) {
  const draft = transactionAdvancedDraft();
  openMobileSheet({
    kicker: "LEDGER",
    title: "Filters",
    buildBody: () => mobileTransactionFiltersBody(draft),
    secondaryLabel: "Clear",
    onSecondary: async () => {
      $("transaction-filters").reset();
      state.transactionAdvancedActive = false;
      state.transactionAdvancedCount = 0;
      const entry = mobileOverlayState.stack.at(-1);
      if (entry) entry.actionTaken = false;
      closeMobileOverlay({ restoreFocus: false });
      await loadMobileTransactionFeed(false);
    },
    primaryLabel: "Apply",
    onPrimary: async () => {
      writeAdvancedFilters(draft);
      state.transactionAdvancedActive = true;
      state.transactionAdvancedCount = advancedFilterCount(draft);
      const loaded = await loadTransactions(false);
      if (!loaded) return;
      const entry = mobileOverlayState.stack.at(-1);
      if (entry) entry.actionTaken = false;
      closeMobileOverlay({ restoreFocus: false });
    },
  }, opener);
}

async function setMobileTransactionFeedFilter(filter) {
  if (state.transactionFeedLoading) return;
  $("transaction-filters").reset();
  state.transactionAdvancedActive = false;
  state.transactionAdvancedCount = 0;
  state.transactionFeedFilter = filter;
  state.transactionFeedCursor = null;
  state.transactionFeedItems = [];
  renderTransactions();
  await loadMobileTransactionFeed(false);
}

function openTransactionDetails(transaction) {
  if (isMobileViewport()) {
    void api(`/api/v1/transaction-feed/transaction/${transaction.id}`)
      .then((detail) => openMobileTransactionDetails(detail.transaction, document.activeElement))
      .catch((error) => toast(error.message));
    return;
  }
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
  if (isMobileViewport()) {
    renderMobileTransactions();
    return;
  }
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
    return true;
  } catch (error) {
    toast(error.message);
    return false;
  }
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
$("app-shell").append($("mobile-overlay-root"));
$("mobile-overlay-scrim").addEventListener("click", () => closeMobileOverlay());
$("mobile-sheet-close").addEventListener("click", () => closeMobileOverlay());
$("mobile-confirm-cancel").addEventListener("click", () => closeMobileOverlay());
$("mobile-overlay-root").addEventListener("keydown", trapMobileOverlayFocus);
$("mobile-overlay-root").addEventListener("focusin", (event) => {
  if (!mobileOverlayState.stack.length) return;
  const panel = $("mobile-confirm").hidden ? $("mobile-sheet") : $("mobile-confirm");
  if (event.target === panel || !panel.contains(event.target)) {
    const focusables = mobileOverlayFocusable(panel);
    (mobileOverlayState.lastTabBackward ? focusables.at(-1) : focusables[0] || panel).focus();
  }
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
  renderOperationsAccountBalance();
  void renderOperationsForms();
  void loadOperationsPeriods();
  void loadOperationsUndoCandidate();
});
$("operations-account-overlay-trigger").addEventListener("click", openOperationsAccountChoose);
for (const id of ["operations-spend-amount", "operations-add-amount", "operations-transfer-amount"]) {
  $(id).addEventListener("input", updateMobileOperationsSubmitState);
}
$("operations-spend-category-mobile").addEventListener("click", (event) => openMobileOperationsCategory("spend", event.currentTarget));
$("operations-add-category-mobile").addEventListener("click", (event) => openMobileOperationsCategory("add", event.currentTarget));
$("operations-spend-date-mobile").addEventListener("click", (event) => openMobileOperationsDate("spend", event.currentTarget));
$("operations-add-date-mobile").addEventListener("click", (event) => openMobileOperationsDate("add", event.currentTarget));
$("operations-transfer-date-mobile").addEventListener("click", (event) => openMobileOperationsDate("transfer", event.currentTarget));
$("operations-transfer-to-mobile").addEventListener("click", (event) => openMobileOperationsDestination(event.currentTarget));
$("operations-spend-form").addEventListener("submit", (event) => saveOperationsSingle(event, "spend"));
$("operations-add-form").addEventListener("submit", (event) => saveOperationsSingle(event, "add-funds"));
$("operations-transfer-form").addEventListener("submit", saveOperationsTransfer);
$("operations-transfer-to").addEventListener("change", updateOperationsTransferMode);
$("operations-has-fee").addEventListener("change", () => {
  $("operations-fee-fields").classList.toggle("hidden", !$("operations-has-fee").checked);
  updateOperationsTransferMode();
});
$("operations-add-period").addEventListener("click", () => openPeriodDialog());
$("operations-add-period-mobile").addEventListener("click", () => {
  if (!isMobileViewport()) openPeriodDialog();
});
$("operations-period-retry-mobile").addEventListener("click", loadOperationsPeriods);
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
  if (isMobileViewport()) {
    openLogoutConfirmation(document.activeElement);
    return;
  }
  await api("/api/v1/auth/logout", { method: "POST" });
  document.querySelector(".profile-menu").removeAttribute("open");
  showAuth();
});

$("manage-categories").addEventListener("click", openCategories);
$("manage-rates").addEventListener("click", (event) => openRateSettings(event.currentTarget));
$("mobile-profile-trigger").addEventListener("click", (event) => openMobileProfile(event.currentTarget));
$("category-form").addEventListener("submit", createCategory);
$("rate-asset").addEventListener("change", renderDesktopRateValue);
$("rate-form").addEventListener("submit", saveDesktopRate);
$("delete-rate").addEventListener("click", deleteDesktopRate);
$("add-plan-rule").addEventListener("click", () => openPlanRule());
$("empty-add-plan-rule").addEventListener("click", () => openPlanRule());
$("plan-rule-kind").addEventListener("change", () => updatePlanRuleFields());
$("plan-rule-asset").addEventListener("change", () => updatePlanRuleFields());
$("plan-rule-form").addEventListener("submit", savePlanRule);
$("plan-link-form").addEventListener("submit", linkPlanTransaction);
$("plan-detail-filter").addEventListener("change", renderPlanRuleDetail);

$("add-account").addEventListener("click", () => openAccountForm());
$("accounts-add-row").addEventListener("click", () => openAccountForm());
$("empty-add-account").addEventListener("click", () => openAccountForm());
$("unvalued-warning").addEventListener("click", (event) => openSetRateEntry(event.currentTarget));
$("account-form").addEventListener("submit", saveAccount);
$("reconcile-form").addEventListener("submit", saveReconcile);
$("invitation-form").addEventListener("submit", createInvitation);
$("copy-invite").addEventListener("click", copyInvitation);
$("empty-open-operations").addEventListener("click", () => switchView("operations"));
$("transaction-filter-trigger").addEventListener("click", (event) => openMobileTransactionFilters(event.currentTarget));
document.querySelectorAll("[data-feed-filter]").forEach((button) => {
  button.addEventListener("click", () => void setMobileTransactionFeedFilter(button.dataset.feedFilter));
});
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
$("load-more").addEventListener("click", () => {
  if (isMobileViewport() && !state.transactionAdvancedActive) void loadMobileTransactionFeed(true);
  else void loadTransactions(true);
});

window.addEventListener("popstate", () => switchView(new URLSearchParams(window.location.search).get("view") || "accounts", false));
api("/api/v1/auth/me").then(showApp).catch(showAuth);
