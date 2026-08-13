from html.parser import HTMLParser
from pathlib import Path
import re


STATIC = Path("app/static")


class DomSmokeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.views: set[str] = set()
        self.operation_actions: list[str] = []
        self.id_counts: dict[str, int] = {}

    def handle_starttag(self, _tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
            self.id_counts[values["id"]] = self.id_counts.get(values["id"], 0) + 1
        if values.get("data-view"):
            self.views.add(values["data-view"])
        if values.get("data-operation-action"):
            self.operation_actions.append(values["data-operation-action"])


def test_spa_has_five_sections_and_financial_dialogs():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    parser = DomSmokeParser()
    parser.feed(html)
    assert parser.views == {"accounts", "transactions", "operations", "plan", "analytics"}
    assert {
        "auth-form",
        "account-groups",
        "transaction-list",
        "account-dialog",
        "account-detail-dialog",
        "reconcile-dialog",
        "sharing-dialog",
        "transaction-dialog",
        "transaction-detail-dialog",
        "transaction-detail-body",
        "transaction-detail-hidden",
        "correct-transaction",
        "categories-dialog",
        "plan-rule-dialog",
        "plan-link-dialog",
        "plan-rule-cards",
        "plan-rule-detail-dialog",
        "plan-rule-detail-list",
        "plan-detail-filter",
        "operations-title",
        "operations-account",
        "operations-selector",
        "operations-undo",
        "operations-spend-form",
        "operations-add-form",
        "operations-transfer-form",
        "operations-transfer-to",
        "operations-has-fee",
        "operations-period",
        "operations-add-period",
        "operations-edit-period",
        "operations-close-period",
        "operations-period-history",
        "operations-period-retry",
        "operations-period-available",
        "operations-period-current-balance",
        "period-dialog",
        "period-form",
        "period-save",
        "period-history-dialog",
        "period-history-list",
        "filter-account",
        "filter-period",
        "filter-type",
        "filter-category",
        "filter-status",
    } <= parser.ids
    assert "Coming soon" in html
    assert 'aria-labelledby="operations-title"' in html
    assert 'aria-labelledby="plan-title"' in html
    assert 'aria-labelledby="analytics-title"' in html
    assert "Tracker" not in html
    assert "Commitments" not in html
    assert not re.search(r"[А-Яа-яЁё]", html)
    assert parser.operation_actions == ["spend", "add-funds", "transfer", "scan"]
    assert all(count == 1 for count in parser.id_counts.values())


def test_spa_wires_account_transaction_and_invitation_api_flows():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    for route in (
        "/api/v1/accounts/summary",
        "/api/v1/accounts/${account.id}/archive",
        "/reconcile",
        "/invitations",
        "/account-invitations/${encodeURIComponent(pendingInvite)}/accept",
        "/api/v1/transactions/${transaction.id}/delete",
        "/categories/${category.id}/archive",
        "/plan-rules/${rule.id}/archive",
        "/link-transaction",
        "/assign-account",
        "/delete",
        "/api/v1/operations/spend",
        "/api/v1/operations/add-funds",
        "/api/v1/operations/transfer",
        "/api/v1/operations/exchange",
        "/api/v1/operations/accounts/${accountId}/undo",
        "/api/v1/operations/accounts/${account.id}/undo",
        "/periods?scope=all",
        "/api/v1/account-periods/${periodId}",
        "/api/v1/account-periods/${period.id}/close",
    ):
        assert route in javascript
    assert "/budget-periods" not in javascript
    assert "/tracker/" not in javascript
    assert "/pay" not in javascript
    assert "/receive" not in javascript
    assert "/api/v1/transactions/${type}" not in javascript
    assert "has_hidden_legs" in javascript
    assert "access_role" in javascript
    assert "state.categories.clear()" in javascript
    assert "window.localStorage.getItem(operationsStorageKey(kind))" in javascript
    assert "window.localStorage.setItem(operationsStorageKey(kind)" in javascript
    assert 'const OPERATION_ACTIONS = ["spend", "add-funds", "transfer", "scan"]' in javascript
    assert "renderOperationsNavigation()" in javascript
    assert "saveOperationsSingle" in javascript
    assert "saveOperationsTransfer" in javascript
    assert "Cross-asset exchange" in javascript
    assert "This transaction needs explicit confirmation. Continue?" in javascript
    assert "This period needs explicit confirmation. Continue?" not in javascript
    assert "This changes an ended account period" not in javascript
    assert 'canUseAccount(account, "owner")' in javascript
    assert "period-funding" not in javascript
    assert "period.funding_amount" not in javascript
    assert "period.remaining" not in javascript
    assert "current.remaining" not in javascript
    assert "current.planned" not in javascript
    assert "occurrence.planned_amount" in javascript
    assert 'period.status === "current"' in javascript
    assert "operationsPeriodRequestId" in javascript
    assert "Period data could not be loaded. Try again." in javascript
    assert "operationsUndoCandidate" in javascript
    assert "loadOperationsUndoCandidate" in javascript
    assert "Operation undone" in javascript
    assert "transaction_id: transaction.id" in javascript
    assert 'details.textContent = "Details"' in javascript
    assert 'actions.append(details)' in javascript
    assert 'transaction.has_hidden_legs' in javascript
    assert 'state.transactionDeleteLoading = true' in javascript
    assert 'row.setAttribute("aria-busy", "true")' in javascript
    assert 'syncTransactionFilterPair("account")' in javascript
    assert 'syncTransactionFilterPair("period")' in javascript
    assert not re.search(r"[А-Яа-яЁё]", javascript)


def test_spa_keeps_archived_categories_for_history_but_not_new_choices():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "/categories?include_archived=true" in javascript
    assert 'category.archived_at ? " (archived)" : ""' in javascript
    assert ".filter((category) => !category.archived_at)" in javascript
    assert "disabled: Boolean(category.archived_at)" in javascript


def test_responsive_styles_keep_mobile_controls_tappable():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "min-height: 44px" in css
    assert "@media (max-width: 640px)" in css
    assert re.search(r"\.primary-nav\s*\{[^}]*position:\s*fixed", css)
    assert ".operations-selector" in css
    assert "tracker" not in css.lower()


def test_money_formatting_uses_explicit_asset_precision():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "assetByCode(code)?.decimals" in javascript
    assert 'fraction.padEnd(precision, "0")' in javascript
    assert "moneyMarkup(account.valued_balance, base)" in javascript


def test_plan_renders_one_card_per_rule_with_nearest_occurrences_only():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    # One card per rule; global occurrence groups and the long lists are gone.
    assert "plan-occurrence-groups" not in html
    assert "plan-occurrence-groups" not in javascript
    assert "plan-status-filter" not in html
    assert "plan-rules-section" not in html
    assert "Upcoming income" not in javascript
    assert "Upcoming income" not in html
    assert "planRuleCardNode" in javascript
    assert "state.planRules.map((rule) => planRuleCardNode(rule))" in javascript
    # Card shows only nearest overdue and nearest future occurrence.
    assert "nearestRuleOccurrences" in javascript
    assert 'item.status === "overdue"' in javascript
    assert 'item.status === "planned"' in javascript
    assert "overdue[0] ?? null" in javascript
    assert "future[0] ?? null" in javascript
    assert 'planOccurrenceNode(nearestOverdue, { label: "Overdue", overdueCount })' in javascript
    assert 'planOccurrenceNode(nearestFuture, { label: "Next" })' in javascript
    # Multiple overdue → badge with the total overdue count.
    assert "overdueCount > 1" in javascript
    assert "${overdueCount} overdue" in javascript
    # History is available only in rule details, with a compact Show control.
    assert 'show.textContent = "Show"' in javascript
    assert "openPlanRuleDetail(rule)" in javascript
    assert "renderPlanRuleDetail" in javascript
    assert 'id="plan-rule-detail-dialog"' in html
    assert 'id="plan-detail-filter"' in html
    for option in ("all", "open", "completed", "skipped"):
        assert f'<option value="{option}"' in html
    # Compact Open/Completed summary stays.
    assert 'id="plan-open-count"' in html
    assert 'id="plan-completed-count"' in html


def test_operations_accessibility_and_loading_contract():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    assert html.count('role="tab"') == 4
    assert html.count('role="tabpanel"') == 4
    for action in ("spend", "add-funds", "transfer", "scan"):
        assert f'aria-controls="operation-panel-{action}"' in html
        assert f'aria-labelledby="operation-tab-{action}"' in html
    assert 'aria-busy="false"' in html
    assert 'id="operations-period-status" class="muted" role="status"' in html
    for error_id in (
        "operations-spend-error",
        "operations-add-error",
        "operations-transfer-error",
        "period-error",
    ):
        assert re.search(rf'id="{error_id}" class="[^"]*form-error[^"]*" role="alert"', html)
    assert "operationsPeriodLoading" in javascript
    assert "operationsPeriodError" in javascript
    assert "operations-period-retry" in javascript
    assert "operationsUndoLoading" in javascript
    assert "operationsCommandLoading" in javascript
    assert "periodCommandLoading" in javascript
    assert "setOperationsCommandLoading(true)" in javascript
    assert "setPeriodCommandLoading(true)" in javascript
    assert javascript.count("if (state.operationsCommandLoading) return;") == 2
    assert javascript.count("setOperationsCommandLoading(false);") == 2
    assert javascript.count("state.periodCommandLoading") >= 6
    assert javascript.count("setPeriodCommandLoading(false);") == 2
    for form_id in (
        "operations-spend-form",
        "operations-add-form",
        "operations-transfer-form",
        "period-form",
    ):
        assert f'id="{form_id}"' in html
        assert re.search(rf'id="{form_id}"[^>]*aria-busy="false"', html)
    assert 'button.setAttribute(\n    "aria-label"' in javascript
