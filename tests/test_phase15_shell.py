from html.parser import HTMLParser
from pathlib import Path


STATIC = Path("app/static")


class PrimaryNavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_primary_nav = False
        self.buttons: list[dict[str, str]] = []
        self.icons: list[str] = []
        self.labels: list[str] = []
        self._button: dict[str, str] | None = None
        self._span_class = ""

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "nav" and values.get("class") == "primary-nav":
            self.in_primary_nav = True
        elif self.in_primary_nav and tag == "button":
            self._button = values
            self.buttons.append(values)
        elif self._button is not None and tag == "span":
            self._span_class = values.get("class", "")

    def handle_endtag(self, tag):
        if tag == "nav" and self.in_primary_nav:
            self.in_primary_nav = False
        elif tag == "button":
            self._button = None
        elif tag == "span":
            self._span_class = ""

    def handle_data(self, data):
        text = data.strip()
        if not text or self._button is None:
            return
        if self._span_class == "nav-icon":
            self.icons.append(text)
        elif self._span_class == "nav-label":
            self.labels.append(text)


def test_mobile_shell_uses_frozen_runtime_tokens_and_safe_area_geometry():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert 'content="width=device-width, initial-scale=1, viewport-fit=cover"' in html
    for token in (
        "--mobile-bg: #0B0D10",
        "--mobile-text: #E7EAEE",
        "--mobile-tab-idle: #6B7482",
        "--mobile-accent: #FFA24B",
        "--mobile-hairline: rgba(255,255,255,.07)",
        "--mobile-tabbar-height: 56px",
    ):
        assert token in css
    assert "--mobile-safe-top: var(--test-safe-top, env(safe-area-inset-top, 0px))" in css
    assert "--mobile-safe-bottom: var(--test-safe-bottom, env(safe-area-inset-bottom, 0px))" in css
    assert "min-height: 100vh" in css
    assert "min-height: 100dvh" in css
    assert "height: calc(100vh - var(--mobile-safe-top) - var(--mobile-tabbar-height) - var(--mobile-safe-bottom))" in css
    assert "height: calc(100dvh - var(--mobile-safe-top) - var(--mobile-tabbar-height) - var(--mobile-safe-bottom))" in css
    assert "overflow-x: hidden" in css
    assert "@import" not in css
    assert "url(" not in css


def test_primary_navigation_matches_approved_order_icons_and_state_contract():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    parser = PrimaryNavParser()
    parser.feed(html)

    assert [button["data-view"] for button in parser.buttons] == [
        "accounts",
        "transactions",
        "operations",
        "plan",
        "analytics",
    ]
    assert parser.labels == ["Accounts", "Transactions", "Operations", "Plan", "Analytics"]
    assert parser.icons == ["▤", "⇄", "◎", "◇", "ϟ"]
    assert parser.buttons[0]["aria-current"] == "page"
    assert all(button["type"] == "button" for button in parser.buttons)
    assert all(
        button["aria-controls"] == f'view-{button["data-view"]}'
        for button in parser.buttons
    )
    assert 'button.setAttribute("aria-current", "page")' in javascript
    assert 'button.removeAttribute("aria-current")' in javascript
    switch_view = javascript.split("function switchView", 1)[1].split(
        "const OPERATION_ACTIONS", 1
    )[0]
    assert "renderOperationsNavigation" not in switch_view
    assert '$("app-shell").scrollTop = 0' in switch_view


def test_mobile_tab_bar_has_fixed_geometry_and_accessible_targets():
    css = (STATIC / "style.css").read_text(encoding="utf-8")

    assert "bottom: var(--mobile-safe-bottom)" in css
    assert "height: var(--mobile-tabbar-height)" in css
    assert "border-top: 1px solid var(--mobile-hairline)" in css
    assert "flex: 1 1 20%" in css
    assert "min-height: 44px" in css
    assert "font-size: 10px" in css
    assert "font-size: 17px" in css
    assert "color: var(--mobile-tab-idle)" in css
    assert "color: var(--mobile-accent)" in css
    assert 'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif' in css
    assert ".primary-nav button:focus-visible" in css
    assert "box-shadow: inset 0 0 0 3px rgba(255, 162, 75, .55)" in css
