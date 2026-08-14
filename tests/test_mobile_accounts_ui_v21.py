from pathlib import Path
import re


STATIC = Path("app/static")


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_mobile_accounts_have_the_frozen_screen_geometry_and_empty_state():
    html = source("index.html")
    css = source("style.css")

    assert 'id="view-accounts"' in html
    assert 'id="unvalued-warning"' in html
    assert 'id="accounts-add-row"' in html
    assert 'id="accounts-empty"' in html
    assert "▤" in html
    assert "Add your first account" in html
    assert "Cash, cards, wallets, reserves, and crypto all live here." in html
    assert re.search(r"\.mobile-screen-header\s*\{[^}]*height:\s*44px", css)
    assert re.search(r"\.accounts-metrics\s*\{[^}]*height:\s*72px", css)
    assert re.search(r"#view-accounts \.mobile-rate-warning\s*\{[^}]*height:\s*44px", css)
    assert re.search(r"\.mobile-group-header\s*\{[^}]*height:\s*24px", css)
    assert re.search(r"\.account-card\s*\{[^}]*height:\s*64px", css)
    assert re.search(r"\.mobile-ghost-row\s*\{[^}]*height:\s*56px", css)
    assert "overflow-y: auto" in css


def test_mobile_accounts_use_summary_only_and_exact_storage_groups():
    javascript = source("app.js")

    assert 'api("/api/v1/accounts/summary")' in javascript
    assert "state.accounts = summary.accounts" in javascript
    assert 'if (account.storage_type === "cash") return "Cash";' in javascript
    assert '["crypto_wallet", "exchange"].includes(account.storage_type)' in javascript
    assert 'return "Bank";' in javascript
    assert 'const order = ["Cash", "Bank", "Crypto"]' in javascript
    assert "state.summary.net_worth" in javascript
    assert "state.summary.available" in javascript
    assert "account.valued_balance" in javascript
    assert "account.include_in_available" in javascript
    assert 'account.valued_balance === null' in javascript
    assert '"Not valued"' in javascript
    assert "protected" in javascript
    assert "moneyMarkup(account.balance, account.asset.code)" in javascript
    assert "moneyMarkup(account.valued_balance, base)" in javascript


def test_mobile_account_warning_and_lifecycle_are_overlay_and_api_backed():
    javascript = source("app.js")

    assert 'new CustomEvent("finapp:open-set-rate"' in javascript
    assert 'title: "Set a rate"' in javascript
    assert '"asset has" : "assets have"' in javascript
    assert 'title: account ? "Edit account" : "Add account"' in javascript
    assert 'title: "Reconcile account"' in javascript
    assert 'title: "Archive this account?"' in javascript
    assert (
        'body: "It disappears from Accounts and stops counting toward Total capital. '
        'History is kept."'
    ) in javascript
    assert "it can be restored" not in javascript.lower()
    assert "restoration" not in javascript.lower()
    for route in (
        'account ? `/api/v1/accounts/${account.id}` : "/api/v1/accounts"',
        '`/api/v1/accounts/${account.id}/reconcile`',
        '`/api/v1/accounts/${account.id}/archive`',
        '`/api/v1/transactions?account_id=${account.id}&limit=10`',
    ):
        assert route in javascript
    assert "openAccountHistory(account)" in javascript
    assert 'syncTransactionFilterPair("account")' in javascript
    assert 'title: "Saved"' in javascript
    assert 'variant: "saved"' in javascript
    assert javascript.count('title: "Saved"') >= 2
    assert "A correction entry is written to history. Existing transactions are untouched." in javascript
    assert '$("mobile-confirm-error").classList.remove("hidden")' in javascript
    assert "const loaded = await loadTransactions(false)" in javascript
    assert "if (!loaded)" in javascript


def test_account_detail_valued_money_uses_separate_value_and_currency_markup():
    javascript = source("app.js")

    detail_start = javascript.index("function mobileAccountDetailBody")
    detail_end = javascript.index("function openMobileAccountDetail", detail_start)
    detail = javascript[detail_start:detail_end]
    assert "moneyMarkup(account.valued_balance, base)" in detail
    assert '<div><dt>Valued amount</dt><dd>${valued}</dd></div>' in detail
    assert "formatMoney(account.valued_balance, base)" not in detail


def test_mobile_account_actions_follow_permissions_and_desktop_dialogs_remain():
    html = source("index.html")
    javascript = source("app.js")

    for dialog_id in ("account-dialog", "account-detail-dialog", "reconcile-dialog"):
        assert f'id="{dialog_id}"' in html
    assert 'canUseAccount(account, "edit") ? "Edit details" : ""' in javascript
    assert javascript.count('canUseAccount(account, "owner")') >= 2
    assert 'if (isMobileViewport()) {' in javascript
    assert '$("account-detail-dialog").showModal()' in javascript
    assert '$("account-dialog").showModal()' in javascript
    assert '$("reconcile-dialog").showModal()' in javascript
