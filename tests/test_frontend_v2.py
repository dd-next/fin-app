from html.parser import HTMLParser
from pathlib import Path
import re


STATIC = Path("app/static")


class DomSmokeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.views: set[str] = set()

    def handle_starttag(self, _tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("data-view"):
            self.views.add(values["data-view"])


def test_spa_has_five_sections_and_financial_dialogs():
    html = (STATIC / "index.html").read_text()
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
        "categories-dialog",
        "plan-rule-dialog",
        "plan-link-dialog",
        "plan-occurrence-groups",
        "operations-title",
        "filter-account",
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


def test_spa_wires_account_transaction_and_invitation_api_flows():
    javascript = (STATIC / "app.js").read_text()
    for route in (
        "/api/v1/accounts/summary",
        "/api/v1/accounts/${account.id}/archive",
        "/reconcile",
        "/invitations",
        "/account-invitations/${encodeURIComponent(pendingInvite)}/accept",
        "/api/v1/transactions/${type}",
        "/categories/${category.id}/archive",
        "/plan-rules/${rule.id}/archive",
        "/link-transaction",
        "/assign-account",
        "/void",
    ):
        assert route in javascript
    assert "/budget-periods" not in javascript
    assert "/tracker/" not in javascript
    assert "/pay" not in javascript
    assert "/receive" not in javascript
    assert "has_hidden_legs" in javascript
    assert "access_role" in javascript
    assert "state.categories.clear()" in javascript
    assert not re.search(r"[А-Яа-яЁё]", javascript)


def test_spa_keeps_archived_categories_for_history_but_not_new_choices():
    javascript = (STATIC / "app.js").read_text()
    assert "/categories?include_archived=true" in javascript
    assert 'category.archived_at ? " (archived)" : ""' in javascript
    assert ".filter((category) => !category.archived_at)" in javascript
    assert "disabled: Boolean(category.archived_at)" in javascript


def test_responsive_styles_keep_mobile_controls_tappable():
    css = (STATIC / "style.css").read_text()
    assert "min-height: 44px" in css
    assert "@media (max-width: 640px)" in css
    assert ".primary-nav { position: fixed" in css
