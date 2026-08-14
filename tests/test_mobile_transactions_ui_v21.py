from pathlib import Path


STATIC = Path("app/static")


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_mobile_transactions_header_chips_and_empty_copy_are_frozen():
    html = source("index.html")

    assert 'id="transaction-filter-trigger"' in html
    assert 'id="transaction-filter-count"' in html
    for value, label in (
        ("all", "All"),
        ("income", "Income"),
        ("expense", "Expense"),
        ("transfer", "Transfer"),
        ("planned", "Planned"),
    ):
        assert f'data-feed-filter="{value}"' in html
        assert f'>{label}</button>' in html
    assert "Create financial events from Operations — they appear here." in html
    assert ">Open Operations</button>" in html
    transaction_start = html.index('id="view-transactions"')
    transaction_end = html.index('id="view-operations"', transaction_start)
    assert "Add transaction" not in html[transaction_start:transaction_end]


def test_mobile_top_chips_use_real_feed_and_opaque_cursor():
    javascript = source("app.js")

    assert 'new URLSearchParams({ filter: state.transactionFeedFilter, limit: "50" })' in javascript
    assert 'query.set("cursor", state.transactionFeedCursor)' in javascript
    assert 'api(`/api/v1/transaction-feed?${query}`)' in javascript
    assert "state.transactionFeedCursor = page.next_cursor" in javascript
    filter_start = javascript.index("async function setMobileTransactionFeedFilter")
    filter_end = javascript.index("function openTransactionDetails", filter_start)
    filter_flow = javascript[filter_start:filter_end]
    assert 'state.transactionFeedCursor = null' in filter_flow
    assert 'state.transactionAdvancedActive = false' in filter_flow
    assert "loadMobileTransactionFeed(false)" in filter_flow


def test_mobile_feed_groups_rows_and_maps_status_without_fake_filtering():
    javascript = source("app.js")

    assert "function feedGroupLabel" in javascript
    assert 'heading.className = "mobile-transaction-date"' in javascript
    assert "item.financial_date !== currentDate" in javascript
    assert 'transaction.type === "exchange" ? "transfer"' in javascript
    assert 'transaction.status === "deleted" ? "Deleted"' in javascript
    assert 'if (item.kind === "planned") return "Planned"' in javascript
    render_start = javascript.index("function renderMobileTransactions")
    render_end = javascript.index("async function openFeedItemDetail", render_start)
    assert ".filter(" not in javascript[render_start:render_end]


def test_discriminated_feed_details_preserve_redaction_and_plan_sheet_flow():
    javascript = source("app.js")

    assert "/transaction-feed/planned/${id}" in javascript
    assert "/transaction-feed/transaction/${item.transaction.id}" in javascript
    assert "openMobilePlannedDetail(detail, opener)" in javascript
    assert "openMobileTransactionDetails(detail.transaction, opener)" in javascript
    assert "Some movements are hidden because you only have access to part of this transaction." in javascript
    planned_start = javascript.index("function openMobilePlannedDetail")
    planned_end = javascript.index("function eligiblePlanOccurrences", planned_start)
    planned_flow = javascript[planned_start:planned_end]
    assert 'kicker: "PLAN"' in planned_flow
    assert 'primaryLabel: detail.available_actions.includes("link_transaction") ? "Link transaction"' in planned_flow
    assert "switchView(" not in planned_flow


def test_swipe_actions_are_keyboard_buttons_and_match_geometry():
    javascript = source("app.js")
    css = source("style.css")

    assert 'plan.type = "button"' in javascript
    assert 'remove.type = "button"' in javascript
    assert 'plan.textContent = "Plan"' in javascript
    assert 'remove.textContent = "Delete"' in javascript
    assert 'event.target.closest(".mobile-swipe-actions")' in javascript
    assert ".mobile-swipe-actions button { width: 64px; min-width: 64px; height: 64px; min-height: 64px" in css
    assert "transform: translateX(-112px)" in css


def test_mobile_delete_is_branded_soft_void_without_native_confirmation():
    javascript = source("app.js")

    delete_start = javascript.index("function openMobileDeleteTransaction")
    delete_end = javascript.index("function openMobileAssignTransaction", delete_start)
    delete_flow = javascript[delete_start:delete_end]
    assert 'body: "It stays in history as Deleted but no longer affects balances or periods."' in delete_flow
    assert 'actionLabel: "Delete"' in delete_flow
    assert 'variant: "destructive"' in delete_flow
    assert "/transactions/${transaction.id}/delete" in delete_flow
    assert "confirm_ended_period: true" in delete_flow
    assert "window.confirm" not in delete_flow
    assert 'method: "DELETE"' not in delete_flow


def test_mobile_correction_keeps_type_read_only_and_uses_exact_strings():
    javascript = source("app.js")

    body_start = javascript.index("function mobileTransactionEditBody")
    body_end = javascript.index("function mobileTransactionPatchBody", body_start)
    edit_body = javascript[body_start:body_end]
    assert '<dt>Type</dt><dd>' in edit_body
    assert 'title: "Type"' not in edit_body
    assert "transaction-type" not in edit_body
    patch_start = javascript.index("function mobileTransactionPatchBody")
    patch_end = javascript.index("async function finishMobileTransactionCorrection", patch_start)
    patch_body = javascript[patch_start:patch_end]
    assert "draft.amount.trim()" in patch_body
    assert "draft.fromAmount.trim()" in patch_body
    assert "parseFloat" not in patch_body
    assert "Number(draft.amount" not in patch_body
    correction_start = javascript.index("function openMobileTransactionEdit")
    correction_end = javascript.index("function transactionAdvancedDraft", correction_start)
    correction = javascript[correction_start:correction_end]
    assert 'title: "Save this correction?"' in correction
    assert "window.confirm" not in correction
    assert 'mobileDateChoice("Financial date"' in edit_body


def test_mobile_assignment_requires_branded_ended_period_confirmation():
    javascript = source("app.js")

    assign_start = javascript.index("function openMobileAssignTransaction")
    assign_end = javascript.index("function mobilePlannedDetailBody", assign_start)
    assignment = javascript[assign_start:assign_end]
    initial_request = assignment[:assignment.index('title: "Assign this transaction?"')]
    assert 'body: JSON.stringify({ account_id: Number(value) })' in initial_request
    assert "confirm_ended_period" not in initial_request
    assert 'title: "Assign this transaction?"' in assignment
    assert 'actionLabel: "Assign account"' in assignment
    assert "confirm_ended_period: true" in assignment
    assert 'title: "Saved"' in assignment


def test_mobile_advanced_filters_keep_persisted_api_and_clear_back_to_feed():
    javascript = source("app.js")

    filters_start = javascript.index("function openMobileTransactionFilters")
    filters_end = javascript.index("async function setMobileTransactionFeedFilter", filters_start)
    filters = javascript[filters_start:filters_end]
    for label in ("Account", "Period", "Type", "Category", "From", "To"):
        assert f'"{label}"' in javascript[javascript.index("function mobileTransactionFiltersBody"):filters_start]
    assert 'kicker: "LEDGER"' in filters
    assert 'title: "Filters"' in filters
    assert 'secondaryLabel: "Clear"' in filters
    assert 'primaryLabel: "Apply"' in filters
    assert "loadTransactions(false)" in filters
    assert "loadMobileTransactionFeed(false)" in filters
    assert "state.transactionAdvancedActive = false" in filters
    assert 'api(`/api/v1/transactions?${transactionQuery' in javascript
    assert "isMobileViewport() && state.transactionAdvancedActive" in javascript
    assert "api(transactionUrl)" in javascript
    date_choices = javascript[javascript.index("function monthStartValue"):filters_start]
    assert 'mobileDateChoice("From"' in date_choices
    assert 'mobileDateChoice("To"' in date_choices
    assert "mobileEditInput(\"From\"" not in date_choices
    assert "mobileEditInput(\"To\"" not in date_choices
    assert 'aria-label", "Previous month"' in date_choices
    assert 'aria-label", "Next month"' in date_choices
    assert "mobileCalendarDates(picker.month)" in date_choices
    assert 'onSelect(date); closeMobileOverlay()' in date_choices
    assert "const candidates" not in date_choices


def test_desktop_transaction_filters_assignment_and_details_remain():
    html = source("index.html")
    javascript = source("app.js")

    for element_id in (
        "transaction-filters",
        "filter-account",
        "filter-period",
        "filter-type",
        "filter-category",
        "filter-status",
        "filter-from",
        "filter-to",
        "transaction-detail-dialog",
        "transaction-dialog",
    ):
        assert f'id="{element_id}"' in html
    assert "async function assignTransaction" in javascript
    assert "if (isMobileViewport())" in javascript[javascript.index("function openTransactionDetails"):javascript.index("function renderTransactions")]
    assert 'if (isMobileViewport()) {\n    renderMobileTransactions();' in javascript
