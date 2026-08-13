from pathlib import Path


STATIC = Path("app/static")


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def period_source() -> str:
    javascript = source("app.js")
    return javascript[
        javascript.index("function currentOperationsPeriod"):
        javascript.index("function clearMobileOperationsDraft")
    ]


def test_mobile_period_card_has_fixed_private_state_surface():
    html = source("index.html")
    javascript = period_source()
    css = source("style.css")

    assert 'id="operations-period-active-mobile"' in html
    assert 'height: 96px' in css[css.index(".mobile-period-card-trigger"):css.index(".mobile-period-card-trigger.hidden")]
    assert 'const owner = canUseAccount(account, "owner")' in javascript
    assert 'state.operationsPeriodLoading = Boolean(account && canUseAccount(account, "owner"))' in javascript
    assert '"Loading period…"' in javascript
    assert '"Period unavailable"' in javascript
    assert '$("operations-add-period-mobile").disabled = !ready || Boolean(current)' in javascript


def test_mobile_period_uses_only_api_decimal_values_and_dst_safe_days():
    javascript = period_source()

    assert "calendarDayNumber(current.end_date) - calendarDayNumber(workspaceTodayValue()) + 1" in javascript
    assert "moneyMarkup(current.available_today, current.asset.code)" in javascript
    active = javascript[javascript.index("function buildMobileActivePeriodBody"):javascript.index("function openMobileClosePeriod")]
    for field in ("opening_balance", "current_balance", "available_today"):
        assert f"period.{field}" in active
    assert "computeAllowance" not in javascript
    assert "parseFloat" not in javascript


def test_mobile_start_and_edit_map_redistribute_checkbox_exactly():
    javascript = period_source()

    form = javascript[javascript.index("function buildMobilePeriodFormBody"):javascript.index("function buildMobileActivePeriodBody")]
    assert 'title: period ? "Edit period" : "Start spending period"' in form
    assert 'primaryLabel: period ? "Save period" : "Start period"' in form
    assert 'Redistribute remaining days' in form
    assert 'draft.redistribute ? "redistribute_remaining_days" : "carry_next_day"' in form
    assert 'method: "PATCH"' in form
    assert 'method: "POST"' in form
    assert 'start_date: draft.start_date' in form
    assert 'end_date: draft.end_date' in form
    for forbidden in ("funding", "remaining", "planned"):
        assert f"{forbidden}:" not in form.lower()


def test_mobile_period_dates_use_choose_sheet_and_return_to_form():
    javascript = period_source()

    form_body = javascript[javascript.index("function buildMobilePeriodFormBody"):javascript.index("function openMobilePeriodForm")]
    assert 'id: `mobile-period-${kind}-date`' in form_body
    assert "openMobileDateChoose({" in form_body
    assert 'returnFocusSelector: `#mobile-period-${kind}-date`' in form_body
    assert 'onSelect: (value) => { draft[`${kind}_date`] = value; }' in form_body


def test_mobile_active_detail_and_history_expose_only_canonical_fields():
    javascript = period_source()

    active = javascript[javascript.index("function buildMobileActivePeriodBody"):javascript.index("function openMobileClosePeriod")]
    for label in ("Status", "Start date", "End date", "Opening balance", "Current balance", "Available today"):
        assert label in active
    assert "<dd>Active</dd>" in active
    history = javascript[javascript.index("function buildMobilePeriodHistoryBody"):javascript.index("function openMobilePeriodHistory")]
    assert 'period.status === "current" ? "button" : "article"' in history
    assert 'period.status === "closed"' in history
    assert 'period.closing_balance' in history
    assert 'period.opening_balance' not in history
    assert 'balance === null ? ""' in history
    for forbidden in ("Funding", "Remaining", "Planned", "valued"):
        assert forbidden not in history


def test_mobile_period_sheet_graph_has_edit_history_and_read_only_rows():
    javascript = period_source()

    active = javascript[javascript.index("function openMobileActivePeriod"):javascript.index("function buildMobilePeriodHistoryBody")]
    assert 'secondaryLabel: "View history"' in active
    assert 'primaryLabel: "Close period"' in active
    history = javascript[javascript.index("function openMobilePeriodHistory"):javascript.index("function openPeriodDialog")]
    assert 'secondaryLabel: current ? "Edit" : ""' in history
    assert 'primaryLabel: current ? "Close current" : ""' in history
    assert "openMobilePeriodForm(current" in history


def test_mobile_close_uses_exact_branded_confirmation_and_refreshes_card():
    javascript = period_source()

    close = javascript[javascript.index("function openMobileClosePeriod"):javascript.index("function openMobileActivePeriod")]
    assert 'title: "Close this period?"' in close
    assert "The current balance is saved in period history and the period becomes read-only. You can start a new period right away." in close
    assert 'actionLabel: "Close period"' in close
    assert '`/api/v1/account-periods/${period.id}/close`' in close
    assert "state.operationsPeriods = [closed" in close
    assert "renderOperationsPeriod()" in close
    assert "closeAllMobileOverlays()" in close
    assert 'switchView("operations")' in close


def test_mobile_period_commands_discard_changed_account_results():
    javascript = period_source()

    assert "const accountId = account.id" in javascript
    assert 'selectedOperationsAccount()?.id !== accountId' in javascript
    load = javascript[javascript.index("async function loadOperationsPeriods"):javascript.index("function buildMobilePeriodFormBody")]
    assert "requestId !== state.operationsPeriodRequestId" in load
    assert 'selectedOperationsAccount()?.id !== requestedAccountId' in load


def test_mobile_shared_accounts_do_not_fetch_or_expose_period_actions():
    javascript = period_source()

    load = javascript[javascript.index("async function loadOperationsPeriods"):javascript.index("function buildMobilePeriodFormBody")]
    assert 'state.operationsPeriodLoading = Boolean(account && canUseAccount(account, "owner"))' in load
    assert "if (!state.operationsPeriodLoading) return" in load
    render = javascript[javascript.index("function renderOperationsPeriod"):javascript.index("async function loadOperationsPeriods")]
    assert 'const current = owner ? currentOperationsPeriod() : null' in render
    assert '$("operations-period-active-mobile").classList.toggle("hidden", !current || !owner)' in render
    assert '$("operations-add-period-mobile").classList.toggle("hidden", !ready || Boolean(current))' in render


def test_desktop_period_dialogs_and_commands_remain_available():
    html = source("index.html")
    javascript = source("app.js")

    for element_id in ("period-dialog", "period-history-dialog", "operations-add-period", "operations-edit-period", "operations-close-period"):
        assert f'id="{element_id}"' in html
    assert "function openPeriodDialog" in javascript
    assert "async function saveOperationsPeriod" in javascript
    assert "async function closeOperationsPeriod" in javascript
    assert "function openPeriodHistory" in javascript
    desktop_history = javascript[javascript.index("function renderOperationsPeriodHistory"):javascript.index("function renderOperationsPeriod()")]
    assert 'if (period.status === "current")' in desktop_history
    assert 'period.status !== "closed"' not in desktop_history
    css = source("style.css")
    assert ".mobile-ops-choice, .mobile-ops-amount-control > .mobile-amount-suffix, .mobile-period-card-trigger { display: none; }" in css
    assert ".mobile-period-history-row { display: flex; height: 48px; min-height: 48px; max-height: 48px;" in css


def test_mobile_period_defaults_use_workspace_timezone_calendar():
    javascript = source("app.js")

    helper = javascript[javascript.index("function workspaceTodayValue"):javascript.index("function dateValueAfter")]
    assert "state.context?.workspace?.timezone" in helper
    assert 'timeZone: timezone' in helper
    assert 'return `${parts.year}-${parts.month}-${parts.day}`' in helper
    period = period_source()
    assert "calendarDayNumber(workspaceTodayValue())" in period
    assert 'start_date: period?.start_date || workspaceTodayValue()' in period
    assert 'end_date: period?.end_date || dateValueAfter(workspaceTodayValue(), 29)' in period
