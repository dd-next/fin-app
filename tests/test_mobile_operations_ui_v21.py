from pathlib import Path


STATIC = Path("app/static")


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_mobile_operations_exact_modes_geometry_and_scan_copy():
    html = source("index.html")
    css = source("style.css")

    for action, label in (
        ("spend", "Spend"),
        ("add-funds", "Add funds"),
        ("transfer", "Transfer"),
        ("scan", "Scan"),
    ):
        assert f'data-operation-action="{action}"' in html
        assert f'>{label}</button>' in html
    assert "Scan is reserved for a later release. No OCR is performed." in html
    assert '#view-operations { margin: -2px -16px 0; padding: 8px 16px 0; }' in css
    assert "height: 96px" in css[css.index(".mobile-ops-card {"):css.index(".mobile-ops-card.is-active")]
    assert '#view-operations .operations-selector { margin: 12px 0 0; border: 0; }' in css
    assert ".mobile-ops-destination-label { grid-column: 1 / -1; order: 1; height: 44px; margin-top: 10px; }" in css
    assert "#operations-transfer-amount-field { order: 2; margin-top: -8px; }" in css
    account_trigger = css[css.index("#operations-account-overlay-trigger"):css.index("#operations-account-card .operations-account-balance")]
    assert "height: 44px" in account_trigger
    assert "min-height: 44px" in account_trigger
    assert "right: 48px" in account_trigger
    undo_rule = css[css.index("#operations-account-card #operations-undo"):css.index("#view-operations .operations-selector")]
    assert "right: 4px" in undo_rule
    assert "width: 44px" in undo_rule


def test_mobile_operations_preferences_and_stale_account_fallback_are_per_user():
    javascript = source("app.js")

    assert 'finapp:v2:operations:${state.context?.user.id || "guest"}:${kind}' in javascript
    navigation = javascript[javascript.index("function renderOperationsNavigation"):javascript.index("function selectedOperationsAccount")]
    assert "currentIsValid" in navigation
    assert "storedIsValid" in navigation
    assert ': state.accounts[0]?.id || null' in navigation
    assert 'setOperationsAction(action, { persist: false })' in navigation
    user_reset = javascript[javascript.index("if (state.lastUserId !== null"):javascript.index("state.lastUserId = context.user.id")]
    assert '"operations-spend-amount", "operations-spend-note"' in user_reset
    assert '"operations-add-amount", "operations-add-note"' in user_reset
    assert '"operations-transfer-amount", "operations-transfer-note"' in user_reset
    assert '$("operations-transfer-to").value = ""' in user_reset


def test_mobile_switch_account_refreshes_dependent_state_with_race_guards():
    javascript = source("app.js")

    start = javascript.index('$("operations-account").addEventListener("change"')
    account_change = javascript[start:javascript.index('$("operations-account-overlay-trigger").addEventListener', start)]
    for call in (
        "renderOperationsAccountBalance()",
        "renderOperationsForms()",
        "loadOperationsPeriods()",
        "loadOperationsUndoCandidate()",
    ):
        assert call in account_change
    assert "operationsPeriodRequestId" in javascript
    assert "operationsUndoRequestId" in javascript
    assert "selectedOperationsAccount()?.id !== requestedAccountId" in javascript
    assert "selectedOperationsAccount()?.id !== accountId" in javascript


def test_mobile_spend_add_defaults_and_saved_copy_are_exact():
    javascript = source("app.js")

    assert 'item.label.toLowerCase() === "groceries"' in javascript
    assert 'item.label.toLowerCase() === "salary"' in javascript
    assert 'placeholder: "Uncategorized"' in javascript
    assert "The expense was written to ${current.name} · ${current.asset.code}. Available today was recalculated." in javascript
    assert "The funds were added to ${current.name} · ${current.asset.code}. Balance and Available today were recalculated." in javascript
    finish = javascript[javascript.index("async function finishMobileOperation"):javascript.index("async function mobileOperationCommand")]
    assert 'title: "Saved"' in finish
    assert "body: messages[kind]" in finish
    assert 'variant: "saved"' in finish


def test_mobile_transfer_uses_one_exact_amount_and_quote_execute_only():
    javascript = source("app.js")

    transfer = javascript[javascript.index("async function saveOperationsTransfer"):javascript.index("function accountGroup")]
    assert 'requiredValue("operations-transfer-amount", "Amount")' in transfer
    assert '"/api/v1/operations/transfer/quotes"' in transfer
    assert 'rate_source: "manual"' in transfer
    assert '`/api/v1/operations/transfer/quotes/${quote.id}/execute`' in transfer
    assert "quote.to_amount" not in transfer
    assert "parseFloat" not in transfer
    assert "Number(fromAmount" not in transfer
    mobile_branch = transfer[transfer.index("if (isMobileViewport())"):transfer.index("} else if (exchange)")]
    assert "operations-exchange-to" not in mobile_branch


def test_mobile_operation_choose_controls_and_validation_are_non_native():
    html = source("index.html")
    javascript = source("app.js")

    for element_id in (
        "operations-spend-category-mobile",
        "operations-add-category-mobile",
        "operations-spend-date-mobile",
        "operations-add-date-mobile",
        "operations-transfer-date-mobile",
        "operations-transfer-to-mobile",
    ):
        assert f'id="{element_id}"' in html
    assert 'title: "Category"' in javascript
    assert 'label: "Date"' in javascript
    assert 'title: "Destination"' in javascript
    assert "function isPositiveDecimalInput" in javascript
    assert 'throw new Error("Enter an amount greater than zero.")' in javascript


def test_mobile_undo_is_compact_branded_and_refreshes_server_candidate():
    javascript = source("app.js")
    css = source("style.css")

    undo = javascript[javascript.index("async function performOperationsUndo"):javascript.index("async function updateOperationsCategories")]
    assert 'title: "Undo this operation?"' in undo
    assert 'actionLabel: "Undo"' in undo
    assert 'variant: "destructive"' in undo
    assert "/api/v1/operations/accounts/${account.id}/undo" in undo
    assert "state.operationsUndoCandidate = null" in undo
    assert "await refreshAll()" in undo
    mobile_undo = javascript[javascript.index("function renderOperationsUndo"):javascript.index("async function loadOperationsUndoCandidate")]
    assert '? "↶"' in mobile_undo
    assert '#operations-account-card #operations-undo { position: absolute; top: 4px; right: 4px; width: 44px' in css


def test_mobile_role_boundaries_keep_quote_owner_private():
    javascript = source("app.js")

    targets = javascript[javascript.index("function operationsTransferTargets"):javascript.index("function isPositiveDecimalInput")]
    assert 'const requiredAction = isMobileViewport() ? "owner" : "edit"' in targets
    transfer = javascript[javascript.index("async function saveOperationsTransfer"):javascript.index("function accountGroup")]
    assert '!canUseAccount(source, "owner") || !canUseAccount(target, "owner")' in transfer
    assert "Mobile Transfer is available only to the account owner." in transfer
    assert 'canUseAccount(account, "expense")' in javascript
    assert 'canUseAccount(account, "income")' in javascript


def test_mobile_no_period_host_and_success_reset_are_stable():
    html = source("index.html")
    javascript = source("app.js")
    css = source("style.css")

    period = javascript[javascript.index("function renderOperationsPeriod"):javascript.index("async function loadOperationsPeriods")]
    assert '"Loading period…"' in period
    assert '"Period unavailable"' in period
    assert '"Could not load period."' in period
    assert '$("operations-period-retry-mobile").classList.toggle("hidden", !state.operationsPeriodError)' in period
    assert 'id="operations-period-mobile-state"' in html
    assert 'id="operations-period-retry-mobile"' in html
    assert '.mobile-ops-period-state { display: flex; height: 44px; min-height: 44px;' in css
    assert '"N/A"' in javascript[javascript.index("function renderOperationsPeriod"):javascript.index("async function loadOperationsPeriods")]
    assert "height: 96px" in css[css.index(".mobile-ops-card.is-absent"):css.index(".mobile-ops-topline")]
    reset = javascript[javascript.index("function clearMobileOperationsDraft"):javascript.index("async function mobileOperationCommand")]
    assert '$("operations-transfer-to").value = ""' in reset
    assert "state.operationsAction" not in reset
    assert "state.operationsAccountId" not in reset
    finish = javascript[javascript.index("async function finishMobileOperation"):javascript.index("async function mobileOperationCommand")]
    before_saved = finish[:finish.index("openMobileConfirmation")]
    assert "await refreshAll()" not in before_saved
    assert 'variant: "saved"' in finish
    done_action = finish[finish.index("onAction: async () => {"):]
    assert done_action.index("clearMobileOperationsDraft(kind)") < done_action.index("await refreshAll()")
    start = javascript.index('$("operations-add-period-mobile").addEventListener')
    mobile_period_listener = javascript[start:javascript.index('$("operations-edit-period").addEventListener', start)]
    assert "else openPeriodDialog()" in mobile_period_listener
    assert '$("operations-period-retry-mobile").addEventListener("click", loadOperationsPeriods)' in mobile_period_listener


def test_mobile_period_day_count_uses_dst_safe_calendar_arithmetic():
    javascript = source("app.js")

    helper = javascript[javascript.index("function calendarDayNumber"):javascript.index("function renderOperationsPeriodHistory")]
    assert "Date.UTC(year, month - 1, day) / 86400000" in helper
    period = javascript[javascript.index("function renderOperationsPeriod"):javascript.index("async function loadOperationsPeriods")]
    assert "calendarDayNumber(current.end_date) - calendarDayNumber(workspaceTodayValue()) + 1" in period
    assert "T00:00:00" not in period


def test_desktop_exchange_fee_undo_and_richer_forms_remain():
    html = source("index.html")
    javascript = source("app.js")
    css = source("style.css")

    for element_id in (
        "operations-exchange-from",
        "operations-exchange-to",
        "operations-has-fee",
        "operations-fee-account",
        "operations-fee-amount",
        "operations-undo",
    ):
        assert f'id="{element_id}"' in html
    assert 'route = "/api/v1/operations/exchange"' in javascript
    assert "body.to_amount" in javascript
    assert "body.fee" in javascript
    assert 'title: "Undo this operation?"' in javascript
    assert "window.confirm" not in javascript
    assert '? "Mobile Transfer is available only to the account owner."' in javascript
    assert ': "You cannot transfer from this account."' in javascript
    assert ".mobile-ops-choice, .mobile-ops-amount-control > .mobile-amount-suffix, .mobile-period-card-trigger { display: none; }" in css
