from html.parser import HTMLParser
from pathlib import Path
import re


STATIC = Path("app/static")


class OverlayDomParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.elements.append((tag, values, tuple(self.stack)))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, values))

    def handle_endtag(self, _tag):
        if self.stack:
            self.stack.pop()


def balanced_mobile(css: str) -> tuple[str, str]:
    marker = "@media (max-width: 640px)"
    start = css.index(marker)
    brace = css.index("{", start)
    depth = 0
    for index in range(brace, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[brace + 1:index], css[:start] + css[index + 1:]
    raise AssertionError("mobile media block")


def css_rule(css: str, selector: str) -> dict[str, str]:
    matches = re.findall(rf"(?:^|\}})\s*{re.escape(selector)}\s*\{{([^}}]+)\}}", css, re.M)
    assert matches, selector
    result = {}
    for body in matches:
        for item in body.split(";"):
            if ":" in item:
                key, value = item.split(":", 1)
                result[key.strip()] = " ".join(value.split())
    return result


def function_source(js: str, name: str) -> str:
    start = js.index(f"function {name}(")
    brace = js.index(") {", start) + 2
    depth = 0
    quote = None
    escaped = False
    for index in range(brace, len(js)):
        char = js[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return js[start:index + 1]
    raise AssertionError(name)


def test_overlay_root_is_one_accessible_production_structure():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    parser = OverlayDomParser()
    parser.feed(html)
    ids = [attrs.get("id") for _, attrs, _ in parser.elements if attrs.get("id")]
    assert ids.count("mobile-overlay-root") == 1
    required = {
        "mobile-overlay-scrim", "mobile-sheet", "mobile-sheet-title",
        "mobile-sheet-kicker", "mobile-sheet-close", "mobile-sheet-body",
        "mobile-sheet-footer", "mobile-confirm", "mobile-confirm-title",
        "mobile-confirm-body", "mobile-confirm-cancel", "mobile-confirm-action",
        "operations-account-overlay-trigger",
    }
    assert required <= set(ids)
    sheet = next(item for item in parser.elements if item[1].get("id") == "mobile-sheet")
    confirm = next(item for item in parser.elements if item[1].get("id") == "mobile-confirm")
    for _, attrs, ancestors in parser.elements:
        if attrs.get("id") in required - {"operations-account-overlay-trigger"}:
            assert any(parent.get("id") == "mobile-overlay-root" for _, parent in ancestors)
            assert not any(parent.get("id") == "app-shell" for _, parent in ancestors)
    assert not any(parent.get("id") == "app-shell" for _, parent in next(item for item in parser.elements if item[1].get("id") == "mobile-overlay-root")[2])
    sheet = sheet[1]
    confirm = confirm[1]
    assert sheet["role"] == "dialog" and sheet["aria-modal"] == "true"
    assert sheet["aria-labelledby"] == "mobile-sheet-title"
    assert confirm["role"] == "alertdialog" and confirm["aria-modal"] == "true"
    assert confirm["aria-labelledby"] == "mobile-confirm-title"
    assert "component-gallery" not in html and "overlay-demo" not in html


def test_overlay_css_matches_frozen_geometry_and_reduced_motion():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    mobile, outside = balanced_mobile(css)
    base_mobile = mobile.split("@media (prefers-reduced-motion: reduce)", 1)[0]
    assert "@media (min-width: 641px)" in outside
    root = css_rule(base_mobile, ".mobile-overlay-root")
    assert root["position"] == "fixed" and root["inset"] == "0"
    assert root["z-index"] == "100"
    active_nav = css_rule(base_mobile, "body.overlay-active .primary-nav")
    assert int(active_nav["z-index"]) > int(root["z-index"])
    scrim = css_rule(base_mobile, ".mobile-overlay-scrim")
    assert scrim["background"] == "rgba(0,0,0,.62)"
    sheet = css_rule(base_mobile, ".mobile-sheet")
    assert sheet["position"] == "absolute" and sheet["bottom"] == "0"
    assert sheet["max-height"] == "88%"
    assert sheet["border-radius"] == "20px 20px 0 0"
    assert sheet["background"] == "var(--mobile-surface)"
    assert sheet["transition"] == "transform 180ms ease-out"
    hidden_panels = css_rule(base_mobile, ".mobile-sheet[hidden], .mobile-confirm[hidden]")
    assert hidden_panels["display"] == "none"
    header = css_rule(base_mobile, ".mobile-sheet-header")
    assert header["height"] == "44px" and header["padding"] == "0 16px"
    safe = css_rule(base_mobile, ".mobile-sheet-safe-band")
    assert safe["height"] == "var(--mobile-safe-bottom)"
    active_safe = css_rule(base_mobile, "body.overlay-active .mobile-sheet-safe-band")
    assert active_safe["height"] == "calc(var(--mobile-safe-bottom) + var(--mobile-tabbar-height))"
    assert active_safe["min-height"] == "calc(var(--mobile-safe-bottom) + var(--mobile-tabbar-height))"
    dialog = css_rule(base_mobile, ".mobile-confirm")
    assert dialog["left"] == dialog["right"] == "16px"
    assert dialog["border-radius"] == "18px"
    assert dialog["background"] == "#1B2028"
    active_dialog = css_rule(base_mobile, "body.overlay-active .mobile-confirm")
    assert active_dialog["bottom"] == "calc(var(--mobile-safe-bottom) + var(--mobile-tabbar-height))"
    reduced = mobile.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert css_rule(reduced, ".mobile-sheet")["transition"] == "none"
    assert css_rule(reduced, ".mobile-sheet")["transform"] == "none"
    desktop_trigger = css_rule(outside, ".operations-account-overlay-trigger")
    assert desktop_trigger["display"] == "none"


def test_controller_owns_stack_focus_dismiss_and_single_action_contract():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "const mobileOverlayState =" in js
    for name in (
        "openMobileSheet", "openMobileChoose", "openMobileConfirmation",
        "closeMobileOverlay", "closeAllMobileOverlays", "renderMobileOverlay",
        "trapMobileOverlayFocus",
    ):
        function_source(js, name)
    render = function_source(js, "renderMobileOverlay")
    assert "setMobileOverlayBackground(active)" in render
    assert 'document.body.classList.toggle("overlay-active", active)' in render
    background = function_source(js, "setMobileOverlayBackground")
    assert '"#app-shell > .topbar, .app-view"' in background
    assert "element.inert = active" in background
    assert 'element.setAttribute("aria-hidden", "true")' in background
    assert "requestAnimationFrame" in render and ".focus()" in render
    close = function_source(js, "closeMobileOverlay")
    assert "restoreFocus" in close and ".focus()" in close and "setMobileOverlayBackground(false)" in close
    assert "mobileOverlayState.stack.at(-1)?.actionTaken" in close
    assert "closed?.opener" in close
    assert "closed?.openerId" in close and "document.getElementById(closed.openerId)" in close
    trap = function_source(js, "trapMobileOverlayFocus")
    assert 'event.key === "Escape"' in trap
    assert 'event.key !== "Tab"' in trap
    assert "focusables" in trap
    assert "mobileOverlayState.lastTabBackward = event.shiftKey" in trap
    confirm = function_source(js, "openMobileConfirmation")
    assert re.search(r"if\s*\([^)]*actionTaken[^)]*\)\s*return", confirm)
    assert confirm.index("actionTaken = true") < confirm.index("await onAction")
    assert "destructive" in confirm and "saved" in confirm
    assert "opener, openerId: opener?.id" in confirm
    assert 'switchView' in js and "closeAllMobileOverlays();" in function_source(js, "switchView")
    assert '$("app-shell").append($("mobile-overlay-root"))' in js


def test_choose_sheet_returns_to_parent_and_rejects_disabled_options():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    choose = function_source(js, "openMobileChoose")
    assert "option.disabled" in choose
    assert 'setAttribute("aria-disabled", "true")' in choose
    assert "closeMobileOverlay()" in choose
    assert "onSelect(button.dataset.value)" in choose
    assert choose.index("if (option.disabled)") < choose.index("onSelect(button.dataset.value)")
    assert "mobile-option-current" in choose


def test_switch_account_is_the_bounded_production_integration():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    integration = function_source(js, "openOperationsAccountChoose")
    assert "state.accounts.map" in integration
    assert "openMobileChoose" in integration
    assert "account.id === state.operationsAccountId" in integration
    assert '$(' + '"operations-account"' + ').dispatchEvent(new Event("change"' in integration
    assert "/api/" not in integration
    assert "period" not in integration.lower()
    assert '$("operations-account-overlay-trigger").addEventListener("click", openOperationsAccountChoose)' in js
    controller = js[js.index("const mobileOverlayState ="):js.index("const OPERATION_ACTIONS")]
    assert not re.search(r"\b(?:alert|prompt|confirm)\s*\(", controller)
    assert "window.confirm" not in controller


def test_confirmation_variants_have_exact_action_semantics():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    confirm = function_source(js, "openMobileConfirmation")
    for variant in ("accent", "destructive", "saved"):
        assert f'"{variant}"' in confirm
    assert "mobile-button-destructive-confirm" in confirm
    assert "mobile-button-sheet-primary" in confirm
    assert "mobile-confirm-cancel" in confirm
    assert 'cancel.hidden = variant === "saved"' in confirm


def test_no_financial_or_backend_scope_widening():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    controller = js[js.index("const mobileOverlayState ="):js.index("const OPERATION_ACTIONS")]
    assert not re.search(r"\b(?:Number|parseFloat|toFixed)\s*\(", controller)
    assert "/api/" not in controller
    assert "fetch(" not in controller


def test_browser_verification_hook_is_attribute_gated_and_non_financial():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    scenario = function_source(js, "runMobileOverlayVerificationScenario")
    assert 'has("verify-overlay")' in scenario
    assert '"nested"' in scenario and '"confirmation"' in scenario and '"saved"' in scenario and '"accent"' in scenario
    assert "Disabled option" in scenario and "data-overlay-action-count" in scenario
    assert "/api/" not in scenario and "fetch(" not in scenario
    assert 'document.addEventListener("finapp:verify-overlay"' in js
    assert 'get("verify-overlay")' in js
    assert '$("mobile-overlay-verify-trigger").addEventListener("click"' in js
    assert "window.setTimeout(() =>" in js
