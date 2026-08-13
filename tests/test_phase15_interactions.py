from html.parser import HTMLParser
from pathlib import Path
import re


STATIC = Path("app/static")


class InteractionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.select_count = 0
        self.pickers: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "select":
            self.select_count += 1
        if "picker-control" in values.get("class", "").split():
            self.pickers[values.get("id", "")] = values


def sources():
    return (
        (STATIC / "index.html").read_text(encoding="utf-8"),
        (STATIC / "app.js").read_text(encoding="utf-8"),
        (STATIC / "style.css").read_text(encoding="utf-8"),
    )


def test_runtime_uses_shared_picker_and_confirmation_primitives_only():
    html, javascript, _css = sources()
    parser = InteractionParser()
    parser.feed(html)
    assert parser.select_count == 0
    assert len(parser.pickers) >= 25
    assert all(attributes.get("type") == "button" for attributes in parser.pickers.values())
    assert all(attributes.get("aria-haspopup") == "dialog" for attributes in parser.pickers.values())
    assert not re.search(r"window\.(?:alert|confirm|prompt)\s*\(", javascript)
    assert 'createElement("select")' not in javascript
    assert "initializeStaticPickers()" in javascript
    assert "openPickerControl(control)" in javascript
    assert 'control.dispatchEvent(new Event("change", { bubbles: true }))' in javascript
    assert "requestSharedConfirmation" in javascript
    assert '$("logout").addEventListener("click", () => openLogoutConfirmation(document.activeElement));' in javascript
    logout_start = javascript.index("function openLogoutConfirmation")
    logout_end = javascript.index("function categoryKindLabel", logout_start)
    assert 'api("/api/v1/auth/logout", { method: "POST" })' in javascript[logout_start:logout_end]


def test_overlay_graph_closes_restores_and_contains_focus():
    html, javascript, _css = sources()
    assert 'id="mobile-overlay-root"' in html
    assert 'popover="manual"' in html
    assert 'role="dialog" aria-modal="true" aria-labelledby="mobile-sheet-title"' in html
    assert 'role="alertdialog" aria-modal="true" aria-labelledby="mobile-confirm-title"' in html
    assert "closeAllMobileOverlays();" in javascript[javascript.index("function switchView"):]
    assert 'if (event.key === "Escape")' in javascript
    assert 'if (event.key !== "Tab") return;' in javascript
    assert "mobileOverlayFocusable(panel)" in javascript
    assert "mobileOverlayState.rootOpener" in javascript
    assert "returnFocusSelector" in javascript
    assert "setMobileOverlayBackground(active)" in javascript
    assert "dialog.inert = active" in javascript
    assert "root.showPopover()" in javascript
    assert "root.hidePopover()" in javascript


def test_keyboard_motion_and_target_contracts_are_frozen():
    html, javascript, css = sources()
    assert html.count('inputmode="decimal"') >= 10
    assert 'id="operations-spend-note"' in html
    assert 'id="operations-add-note"' in html
    assert 'id="operations-transfer-note"' in html
    action_start = javascript.index("function setOperationsAction")
    action_end = javascript.index("function renderOperationsNavigation", action_start)
    assert "document.activeElement.blur()" in javascript[action_start:action_end]
    assert "transition: transform 180ms ease-out" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert re.search(r"\.mobile-sheet\s*\{[^}]*transform:\s*none", css)
    assert "min-height: 44px" in css
    assert ".mobile-chip-lane" in css
    assert "height: 44px" in css


def test_deferred_controls_stay_disabled_or_placeholder_only():
    html, javascript, _css = sources()
    assert "Owner · Coming soon" in javascript
    assert "Auto · Coming soon" in javascript
    assert "Scan is reserved for a later release. No OCR is performed." in html
    assert "Income, spending, and trends arrive once the core ledger is stable." in html
    assert 'data-account-action="restore"' not in javascript
    assert "merge categor" not in javascript.lower()
