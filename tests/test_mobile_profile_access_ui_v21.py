from pathlib import Path
import re


STATIC = Path("app/static")


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_mobile_profile_has_supported_settings_only():
    html = source("index.html")
    javascript = source("app.js")

    assert 'id="mobile-profile-trigger"' in html
    assert 'aria-label="Open profile"' in html
    for copy in (
        "Manage categories",
        "Exchange rates",
        "Workspace",
        "Log out",
    ):
        assert copy in javascript
    profile_start = javascript.index("function mobileProfileBody")
    profile_end = javascript.index("function openMobileProfile", profile_start)
    profile = javascript[profile_start:profile_end]
    assert "password" not in profile.lower()
    assert "Edit profile" not in profile
    assert "Change password" not in profile


def test_mobile_categories_use_sheets_and_supported_archive_contract():
    javascript = source("app.js")

    assert 'title: "Categories"' in javascript
    assert 'title: category ? "Edit category" : "Add category"' in javascript
    assert 'title: "Kind"' in javascript
    assert "ALL CATEGORIES · TAP TO EDIT" in javascript
    assert "A category only groups transactions. Renaming it later keeps every past entry attached." in javascript
    assert 'method: category ? "PATCH" : "POST"' in javascript
    assert "Archive category" in javascript
    assert "/categories/${category.id}/archive" in javascript
    mobile_start = javascript.index("function mobileCategoriesBody")
    mobile_end = javascript.index("async function openSharing", mobile_start)
    mobile_categories = javascript[mobile_start:mobile_end]
    assert "window.prompt" not in mobile_categories
    assert "window.confirm" not in mobile_categories
    assert "Merge into another" not in mobile_categories
    assert "Delete category" not in mobile_categories


def test_manual_rate_is_exact_asset_to_main_and_auto_is_disabled():
    javascript = source("app.js")

    assert 'return `${code} → ${state.context.workspace.base_asset.code}`' in javascript
    assert 'value: "manual", label: "Manual value", current: true' in javascript
    assert 'value: "auto", label: "Auto · Coming soon", disabled: true' in javascript
    assert 'inputmode="decimal"' in javascript
    assert "JSON.stringify({ rate: draft.rate.trim() })" in javascript
    assert "/valuation-rates/${draft.assetCode}" in javascript
    assert 'method: "PUT"' in javascript
    assert 'method: "DELETE"' in javascript
    assert "await refreshAll()" in javascript
    assert "parseFloat" not in javascript
    assert "Number(draft.rate" not in javascript


def test_rate_delete_can_replace_confirmation_without_leaving_app_inert():
    javascript = source("app.js")

    assert "if (mobileOverlayState.stack.at(-1) !== entry) return;" in javascript
    assert "if (mobileOverlayState.stack.at(-1) === entry)" in javascript
    delete_start = javascript.index('title: `Delete ${ratePairLabel(draft.assetCode)} rate?`')
    delete_end = javascript.index("body.append(remove);", delete_start)
    delete_flow = javascript[delete_start:delete_end]
    assert "closeAllMobileOverlays()" in delete_flow
    assert 'title: "Saved"' in delete_flow


def test_mobile_sharing_uses_authorized_rows_roles_and_invitation_api():
    javascript = source("app.js")

    assert 'const rows = await api(`/api/v1/accounts/${accountId}/access`)' in javascript
    assert 'title: `Share ${account.name}`' in javascript
    assert "PEOPLE" in javascript
    assert "Owner · Coming soon" in javascript
    for role in ("viewer", "contributor", "editor"):
        assert f'"{role}"' in javascript
    assert "/access/${row.user.id}" in javascript
    assert "/accounts/${account.id}/invitations" in javascript
    assert "Create invite link" in javascript
    assert "Invitation link" in javascript
    assert 'canUseAccount(account, "owner")' in javascript
    account_detail_start = javascript.index("function openMobileAccountDetail")
    account_detail_end = javascript.index("function buildMobileAccountFormBody", account_detail_start)
    account_detail = javascript[account_detail_start:account_detail_end]
    assert 'secondaryLabel: canUseAccount(account, "owner") ? "Share" : ""' in account_detail
    assert "onSecondary: () => openSharing" in account_detail


def test_mobile_access_list_discards_stale_account_responses():
    javascript = source("app.js")

    assert "context: config.context || parentContext" in javascript
    assert "context: mobileOverlayState.stack.at(-1)?.context || null" in javascript
    assert "function isActiveSharingContext(context)" in javascript
    assert "mobileOverlayState.stack.at(-1)?.context === context" in javascript
    access_start = javascript.index("async function loadMobileAccess")
    access_end = javascript.index("function openMobileSharing", access_start)
    access_loader = javascript[access_start:access_end]
    assert "const accountId = context.account.id" in access_loader
    assert "const rows = await api" in access_loader
    assert access_loader.count("!isActiveSharingContext(context)") == 2
    assert "state.sharingRows = rows" in access_loader
    assert "const context = { kind: \"sharing\", account }" in javascript
    assert "void loadMobileAccess(context)" in javascript
    sharing_start = javascript.index("function mobileSharingBody")
    sharing_end = javascript.index("async function loadMobileAccess", sharing_start)
    sharing_body = javascript[sharing_start:sharing_end]
    assert "const sharingAccount = context.account" in sharing_body
    assert "!isActiveSharingContext(context)" in sharing_body


def test_mobile_logout_is_branded_and_cancel_is_non_mutating():
    javascript = source("app.js")

    assert 'title: `Log out of ${state.context.user.username}?`' in javascript
    assert "You will be signed out on this device. Your data stays safely in your workspace." in javascript
    assert 'actionLabel: "Log out"' in javascript
    assert 'variant: "destructive"' in javascript
    logout_start = javascript.index("function openLogoutConfirmation")
    logout_end = javascript.index("function categoryKindLabel", logout_start)
    logout = javascript[logout_start:logout_end]
    assert '/api/v1/auth/logout' in logout
    assert logout.count('/api/v1/auth/logout') == 1
    assert "window.confirm" not in logout


def test_desktop_profile_rate_category_share_and_logout_surfaces_remain():
    html = source("index.html")
    javascript = source("app.js")

    for element_id in (
        "profile-summary",
        "manage-categories",
        "manage-rates",
        "logout",
        "categories-dialog",
        "rate-dialog",
        "sharing-dialog",
    ):
        assert f'id="{element_id}"' in html
    assert 'if (isMobileViewport()) return openMobileCategories(opener);' in javascript
    assert 'if (isMobileViewport()) return openMobileRateSettings(opener, preferredAsset);' in javascript
    assert re.search(r"async function openSharing\([^)]*\)\s*\{[^}]*if \(isMobileViewport\(\)\)", javascript)
