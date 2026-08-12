from html.parser import HTMLParser
from pathlib import Path
import json
import re
import subprocess


STATIC = Path("app/static")
MOBILE_MARKER = "@media (max-width: 640px)"
PRIMITIVE_SELECTORS = {
    ".mobile-screen-header",
    ".mobile-screen-title",
    ".mobile-list-row",
    ".mobile-row-title",
    ".mobile-leading-icon",
    ".mobile-ghost-row",
    ".mobile-ghost-row .mobile-leading-icon",
    ".mobile-ghost-label",
    ".mobile-group-header",
    ".mobile-group-count",
    ".mobile-metric-strip",
    ".accounts-metrics",
    ".plan-summary.mobile-metric-strip",
    ".mobile-metric",
    ".mobile-metric + .mobile-metric",
    ".accounts-metrics .mobile-metric",
    ".plan-summary.mobile-metric-strip .mobile-metric",
    ".mobile-metric-label",
    ".mobile-metric-value",
    ".mobile-metric.is-accent .mobile-metric-value",
    ".operations-card-row",
    ".mobile-ops-card",
    ".mobile-ops-card.is-active",
    ".mobile-ops-card.is-absent",
    ".mobile-ops-topline",
    ".mobile-ops-title",
    ".mobile-ops-period-text",
    ".mobile-ops-dot",
    ".mobile-ops-card.is-active .mobile-ops-dot",
    ".mobile-ops-card.is-absent .mobile-ops-dot",
    ".mobile-ops-label",
    ".mobile-ops-value",
    ".mobile-ops-suffix",
    ".mobile-start-period",
    ".mobile-start-period-visual",
    ".mobile-segmented",
    ".mobile-segmented > button",
    ".mobile-segmented > button.active",
    ".mobile-chip-lane",
    ".mobile-chip",
    ".mobile-chip.active",
    ".mobile-field",
    ".mobile-field-sheet",
    ".mobile-field-sheet-label",
    ".mobile-field-sheet-value",
    ".mobile-amount-field",
    ".mobile-amount-suffix",
    ".mobile-field-error",
    ".mobile-field:focus",
    ".mobile-amount-field.is-error",
    ".mobile-submit-disabled",
    ".mobile-button-primary",
    ".mobile-button-sheet-primary",
    ".mobile-button-secondary",
    ".mobile-button-inline",
    ".mobile-button-destructive-inline",
    ".mobile-button-destructive-confirm",
    ".mobile-money",
    ".mobile-money .mobile-money-value",
    ".mobile-money .mobile-money-code",
    ".mobile-metric-value .mobile-money-value",
    ".rule-card .mobile-money",
    ".mobile-truncate",
    ".mobile-interactive",
    ".mobile-surface",
}


def balanced_span(source: str, marker: str) -> tuple[str, int, int]:
    marker_start = source.index(marker)
    opening = source.index("{", marker_start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index], marker_start, index + 1
    raise AssertionError(f"unclosed block: {marker}")


def balanced_block(source: str, marker: str) -> str:
    return balanced_span(source, marker)[0]


def declarations(scope: str, selector: str) -> dict[str, str]:
    effective: dict[str, str] = {}
    without_comments = re.sub(r"/\*.*?\*/", "", scope, flags=re.DOTALL)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", without_comments):
        selectors = [item.strip() for item in match.group(1).split(",")]
        if selector not in selectors:
            continue
        for declaration in match.group(2).split(";"):
            if ":" not in declaration:
                continue
            key, value = declaration.split(":", 1)
            effective[key.strip()] = re.sub(r"\s+", " ", value.strip())
    assert effective, f"missing CSS rule: {selector}"
    return effective


def function_definition(javascript: str, name: str) -> str:
    marker = f"function {name}("
    body, start, end = balanced_span(javascript, marker)
    opening = javascript.index("{", start)
    return javascript[start:opening] + "{" + body + "}"


class PrimitiveDomParser(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.elements: list[tuple[str, dict[str, str], tuple[tuple[str, dict[str, str]], ...]]] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.elements.append((tag, values, tuple(self.stack)))
        if tag not in self.VOID:
            self.stack.append((tag, values))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                return

    def by_id(self, element_id: str):
        matches = [item for item in self.elements if item[1].get("id") == element_id]
        assert len(matches) == 1
        return matches[0]


def classes(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def ancestor_ids(element) -> set[str]:
    return {attrs.get("id", "") for _, attrs in element[2]}


def test_mobile_tokens_and_every_primitive_rule_are_scoped_to_mobile():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    root = declarations(css, ":root")
    mobile, media_start, media_end = balanced_span(css, MOBILE_MARKER)
    outside_mobile = css[:media_start] + css[media_end:]

    expected_tokens = {
        "--mobile-surface": "#151A21",
        "--mobile-surface-border": "rgba(255,255,255,.08)",
        "--mobile-field": "#101419",
        "--mobile-field-border": "rgba(255,255,255,.12)",
        "--mobile-neutral": "#232A33",
        "--mobile-secondary": "#C9D0D9",
        "--mobile-muted": "#8A93A0",
        "--mobile-hint": "#5F6875",
        "--mobile-chevron": "#4A525E",
        "--mobile-positive": "#6EE7A8",
        "--mobile-negative": "#FF7B7B",
        "--mobile-accent-tint": "rgba(255,162,75,.14)",
        "--mobile-accent-focus": "rgba(255,162,75,.55)",
        "--mobile-danger-bg": "rgba(255,123,123,.1)",
        "--mobile-danger-border": "rgba(255,123,123,.3)",
        "--mobile-destructive": "#7A2F35",
        "--mobile-on-destructive": "#FFD9D9",
    }
    assert {name: root[name] for name in expected_tokens} == expected_tokens
    for selector in PRIMITIVE_SELECTORS:
        assert declarations(mobile, selector)
    mobile_classes = set(re.findall(r"\.mobile-[a-z0-9-]+", css))
    assert mobile_classes
    for class_name in mobile_classes:
        assert class_name not in outside_mobile


def test_exact_header_row_metric_and_operations_geometry():
    mobile = balanced_block((STATIC / "style.css").read_text(encoding="utf-8"), MOBILE_MARKER)

    header = declarations(mobile, ".mobile-screen-header")
    assert header["display"] == "flex"
    assert header["height"] == header["min-height"] == header["max-height"] == "44px"
    assert header["padding"] == "0 16px"
    assert header["align-items"] == "center"
    assert header["justify-content"] == "space-between"
    assert header["border-bottom"] == "1px solid var(--mobile-hairline)"
    title = declarations(mobile, ".mobile-screen-title")
    assert (title["font-size"], title["font-weight"], title["letter-spacing"]) == ("17px", "600", "normal")
    row = declarations(mobile, ".mobile-list-row")
    assert row["display"] == "flex" and row["align-items"] == "center"
    assert row["height"] == row["min-height"] == row["max-height"] == "64px"
    assert row["gap"] == "12px"
    assert row["border-radius"] == "0"
    assert row["border-bottom"] == "1px solid var(--mobile-hairline)"
    row_title = declarations(mobile, ".mobile-row-title")
    assert (row_title["font-size"], row_title["font-weight"]) == ("15px", "600")
    icon = declarations(mobile, ".mobile-leading-icon")
    assert (icon["width"], icon["height"], icon["border-radius"], icon["flex"]) == ("28px", "28px", "8px", "0 0 28px")
    ghost = declarations(mobile, ".mobile-ghost-row")
    assert ghost["height"] == ghost["min-height"] == ghost["max-height"] == "56px"
    assert ghost["border-bottom"] == "0"
    ghost_tile = declarations(mobile, ".mobile-ghost-row .mobile-leading-icon")
    assert ghost_tile["border"] == "1px dashed rgba(255,255,255,.16)"
    assert declarations(mobile, ".mobile-ghost-label")["color"] == "var(--mobile-muted)"
    group = declarations(mobile, ".mobile-group-header")
    assert group["height"] == "24px"
    assert group["font-size"] == "11px"
    assert group["font-weight"] == "600"
    assert group["letter-spacing"] == ".1em"
    assert group["color"] == "var(--mobile-muted)"
    assert group["text-transform"] == "uppercase"
    count = declarations(mobile, ".mobile-group-count")
    assert (count["font-size"], count["font-weight"], count["color"]) == ("11px", "400", "var(--mobile-muted)")

    strip = declarations(mobile, ".mobile-metric-strip")
    assert strip["display"] == "grid"
    assert strip["grid-template-columns"] == "repeat(2, minmax(0, 1fr))"
    assert strip["background"] == "var(--mobile-surface)"
    assert strip["border"] == "1px solid var(--mobile-surface-border)"
    assert strip["border-radius"] == "16px" and strip["overflow"] == "hidden"
    accounts_strip = declarations(mobile, ".accounts-metrics")
    assert accounts_strip["height"] == accounts_strip["min-height"] == accounts_strip["max-height"] == "72px"
    plan_strip = declarations(mobile, ".plan-summary.mobile-metric-strip")
    assert plan_strip["height"] == plan_strip["min-height"] == plan_strip["max-height"] == "64px"
    metric = declarations(mobile, ".mobile-metric")
    assert metric["height"] == "100%"
    assert metric["min-height"] == "0"
    assert metric["border"] == "0"
    assert metric["background"] == "transparent"
    assert metric["box-shadow"] == "none"
    assert declarations(mobile, ".mobile-metric + .mobile-metric")["border-left"] == "1px solid var(--mobile-hairline)"
    assert declarations(mobile, ".accounts-metrics .mobile-metric")["padding"] == "14px 16px"
    assert declarations(mobile, ".plan-summary.mobile-metric-strip .mobile-metric")["padding"] == "12px 14px"
    metric_label = declarations(mobile, ".mobile-metric-label")
    assert (metric_label["font-size"], metric_label["font-weight"], metric_label["color"]) == ("11px", "500", "var(--mobile-muted)")
    metric_value = declarations(mobile, ".mobile-metric-value")
    assert (metric_value["font-size"], metric_value["font-weight"], metric_value["white-space"]) == ("20px", "600", "nowrap")
    assert declarations(mobile, ".mobile-metric.is-accent .mobile-metric-value")["color"] == "var(--mobile-accent)"

    row_cards = declarations(mobile, ".operations-card-row")
    assert row_cards["display"] == "grid"
    assert row_cards["grid-template-columns"] == "repeat(2, minmax(0, 1fr))"
    assert row_cards["gap"] == "10px"
    for selector in (".mobile-ops-card", ".mobile-ops-card.is-active", ".mobile-ops-card.is-absent"):
        card = declarations(mobile, selector)
        assert card["height"] == card["min-height"] == card["max-height"] == "96px"
        assert card["box-sizing"] == "border-box"
    card = declarations(mobile, ".mobile-ops-card")
    assert card["display"] == "flex" and card["flex-direction"] == "column"
    assert card["padding"] == "10px 14px 12px"
    assert card["border-radius"] == "16px"
    assert card["justify-content"] == "space-between"
    assert card["background"] == "var(--mobile-surface)"
    assert card["border"] == "1px solid var(--mobile-surface-border)"
    absent = declarations(mobile, ".mobile-ops-card.is-absent")
    assert absent["border"] == "1px dashed rgba(255,255,255,.16)"
    assert absent["background"] == "transparent"
    assert declarations(mobile, ".mobile-ops-topline")["height"] == "26px"
    ops_title = declarations(mobile, ".mobile-ops-title")
    assert (ops_title["font-size"], ops_title["font-weight"]) == ("15px", "600")
    period_text = declarations(mobile, ".mobile-ops-period-text")
    assert (period_text["font-size"], period_text["font-weight"], period_text["color"]) == ("13px", "500", "var(--mobile-secondary)")
    dot = declarations(mobile, ".mobile-ops-dot")
    assert dot["width"] == dot["height"] == "6px" and dot["border-radius"] == "50%"
    assert declarations(mobile, ".mobile-ops-card.is-active .mobile-ops-dot")["background"] == "var(--mobile-positive)"
    assert declarations(mobile, ".mobile-ops-card.is-absent .mobile-ops-dot")["background"] == "var(--mobile-muted)"
    ops_label = declarations(mobile, ".mobile-ops-label")
    assert (ops_label["font-size"], ops_label["font-weight"], ops_label["color"]) == ("11px", "500", "var(--mobile-muted)")
    ops_value = declarations(mobile, ".mobile-ops-value")
    assert (ops_value["font-size"], ops_value["font-weight"], ops_value["white-space"]) == ("22px", "600", "nowrap")
    suffix = declarations(mobile, ".mobile-ops-suffix")
    assert (suffix["font-size"], suffix["font-weight"], suffix["color"]) == ("11px", "500", "var(--mobile-muted)")
    start = declarations(mobile, ".mobile-start-period")
    assert start["height"] == start["min-height"] == start["max-height"] == "44px"
    assert start["background"] == "transparent"
    start_visual = declarations(mobile, ".mobile-start-period-visual")
    assert start_visual["height"] == "36px" and start_visual["background"] == "var(--mobile-accent-tint)"


def test_exact_controls_fields_buttons_money_and_truncation_contract():
    mobile = balanced_block((STATIC / "style.css").read_text(encoding="utf-8"), MOBILE_MARKER)
    expected = {
        ".mobile-segmented": ("44px", "12px"),
        ".mobile-chip-lane": ("44px", "0"),
        ".mobile-chip": ("36px", "6px"),
        ".mobile-field": ("44px", "12px"),
        ".mobile-field-sheet": ("44px", "10px"),
        ".mobile-amount-field": ("60px", "12px"),
        ".mobile-field-error": ("20px", "0"),
        ".mobile-button-primary": ("50px", "12px"),
        ".mobile-button-sheet-primary": ("48px", "10px"),
        ".mobile-button-secondary": ("48px", "10px"),
        ".mobile-button-inline": ("44px", "10px"),
        ".mobile-button-destructive-inline": ("44px", "10px"),
        ".mobile-button-destructive-confirm": ("48px", "10px"),
    }
    for selector, (height, radius) in expected.items():
        rule = declarations(mobile, selector)
        assert rule["height"] == rule["min-height"] == rule["max-height"] == height
        assert rule["border-radius"] == radius
    segmented = declarations(mobile, ".mobile-segmented")
    assert (segmented["padding"], segmented["gap"]) == ("3px", "2px")
    assert (segmented["display"], segmented["background"]) == ("flex", "var(--mobile-surface)")
    segment = declarations(mobile, ".mobile-segmented > button")
    assert (segment["flex"], segment["font-size"], segment["font-weight"], segment["border-radius"], segment["background"], segment["color"]) == ("1", "13px", "600", "9px", "transparent", "var(--mobile-muted)")
    active_segment = declarations(mobile, ".mobile-segmented > button.active")
    assert (active_segment["background"], active_segment["color"]) == ("var(--mobile-neutral)", "var(--mobile-text)")
    lane = declarations(mobile, ".mobile-chip-lane")
    assert lane["overflow-x"] == "auto" and lane["flex-wrap"] == "nowrap"
    assert (lane["display"], lane["gap"], lane["padding"]) == ("flex", "8px", "0 16px")
    chip = declarations(mobile, ".mobile-chip")
    assert (chip["padding"], chip["font-size"], chip["font-weight"], chip["background"], chip["border"], chip["color"]) == ("0 14px", "13px", "600", "transparent", "1px solid var(--mobile-field-border)", "#9AA3B0")
    active_chip = declarations(mobile, ".mobile-chip.active")
    assert (active_chip["background"], active_chip["color"]) == ("var(--mobile-accent)", "var(--mobile-bg)")
    field = declarations(mobile, ".mobile-field")
    assert (field["background"], field["border"], field["padding"]) == ("var(--mobile-field)", "1px solid var(--mobile-field-border)", "0 14px")
    assert declarations(mobile, ".mobile-field:focus")["border-color"] == "var(--mobile-accent-focus)"
    sheet_label = declarations(mobile, ".mobile-field-sheet-label")
    assert (sheet_label["font-size"], sheet_label["font-weight"], sheet_label["color"]) == ("13px", "500", "var(--mobile-muted)")
    sheet_value = declarations(mobile, ".mobile-field-sheet-value")
    assert (sheet_value["font-size"], sheet_value["font-weight"]) == ("15px", "500")
    sheet_field = declarations(mobile, ".mobile-field-sheet")
    assert (sheet_field["display"], sheet_field["align-items"], sheet_field["background"], sheet_field["border"]) == ("flex", "center", "var(--mobile-field)", "1px solid var(--mobile-field-border)")
    amount = declarations(mobile, ".mobile-amount-field")
    assert (amount["font-size"], amount["font-weight"]) == ("28px", "600")
    assert (amount["display"], amount["align-items"], amount["background"], amount["border"]) == ("flex", "center", "var(--mobile-field)", "1px solid var(--mobile-field-border)")
    amount_suffix = declarations(mobile, ".mobile-amount-suffix")
    assert (amount_suffix["font-size"], amount_suffix["font-weight"], amount_suffix["color"]) == ("15px", "500", "var(--mobile-muted)")
    error_line = declarations(mobile, ".mobile-field-error")
    assert (error_line["font-size"], error_line["font-weight"], error_line["color"]) == ("12px", "500", "var(--mobile-negative)")
    primary = declarations(mobile, ".mobile-button-primary")
    assert (primary["width"], primary["font-size"], primary["font-weight"], primary["background"], primary["color"]) == ("100%", "16px", "700", "var(--mobile-accent)", "var(--mobile-bg)")
    sheet_primary = declarations(mobile, ".mobile-button-sheet-primary")
    assert (sheet_primary["font-size"], sheet_primary["font-weight"], sheet_primary["background"], sheet_primary["color"]) == ("16px", "700", "var(--mobile-accent)", "var(--mobile-bg)")
    secondary = declarations(mobile, ".mobile-button-secondary")
    assert (secondary["padding"], secondary["border"], secondary["font-size"], secondary["font-weight"], secondary["color"]) == ("0 18px", "1px solid var(--mobile-field-border)", "15px", "600", "var(--mobile-secondary)")
    inline = declarations(mobile, ".mobile-button-inline")
    assert (inline["padding"], inline["background"], inline["font-size"], inline["font-weight"], inline["color"]) == ("0 16px", "var(--mobile-neutral)", "15px", "600", "var(--mobile-secondary)")
    destructive = declarations(mobile, ".mobile-button-destructive-inline")
    assert (destructive["background"], destructive["border"], destructive["color"]) == ("var(--mobile-danger-bg)", "1px solid var(--mobile-danger-border)", "var(--mobile-negative)")
    confirm = declarations(mobile, ".mobile-button-destructive-confirm")
    assert (confirm["background"], confirm["color"]) == ("var(--mobile-destructive)", "var(--mobile-on-destructive)")
    error_amount = declarations(mobile, ".mobile-amount-field.is-error")
    assert (error_amount["border-color"], error_amount["color"]) == ("rgba(255,123,123,.6)", "var(--mobile-negative)")
    disabled = declarations(mobile, ".mobile-submit-disabled")
    assert (disabled["background"], disabled["color"], disabled["pointer-events"]) == ("#3A2A2C", "#8A6B6E", "none")
    money = declarations(mobile, ".mobile-money")
    assert money["font-variant-numeric"] == "tabular-nums" and money["white-space"] == "nowrap"
    suffix = declarations(mobile, ".mobile-money .mobile-money-code")
    assert (suffix["font-size"], suffix["font-weight"], suffix["color"]) == ("11px", "500", "var(--mobile-muted)")
    effective_metric = declarations(mobile, ".mobile-metric-value .mobile-money-value")
    assert (effective_metric["font-size"], effective_metric["font-weight"]) == ("20px", "600")
    assert declarations(mobile, ".rule-card .mobile-money")["display"] == "inline-flex"
    assert declarations(mobile, ".mobile-truncate") == {
        "min-width": "0",
        "overflow": "hidden",
        "text-overflow": "ellipsis",
        "white-space": "nowrap",
    }
    target = declarations(mobile, ".mobile-interactive")
    assert target["min-height"] == "44px" and target["min-width"] == "44px"


def test_live_static_dom_binds_primitives_to_accounts_operations_and_plan():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    parser = PrimitiveDomParser()
    parser.feed(html)

    for title_id, view_id in (("accounts-title", "view-accounts"), ("plan-title", "view-plan")):
        title = parser.by_id(title_id)
        assert title[0] == "h2" and "mobile-screen-title" in classes(title[1])
        assert view_id in ancestor_ids(title)
        header = next(item for item in title[2] if "mobile-screen-header" in classes(item[1]))
        assert header[0] == "div"

    for value_id, view_id, strip_class in (
        ("net-worth", "view-accounts", "accounts-metrics"),
        ("available-total", "view-accounts", "accounts-metrics"),
        ("plan-open-count", "view-plan", "plan-summary"),
        ("plan-completed-count", "view-plan", "plan-summary"),
    ):
        value = parser.by_id(value_id)
        assert view_id in ancestor_ids(value)
        assert any({"mobile-metric-strip", strip_class} <= classes(attrs) for _, attrs in value[2])
        assert any("mobile-metric" in classes(attrs) for _, attrs in value[2])

    selector = parser.by_id("operations-selector")
    assert selector[0] == "div" and selector[1]["role"] == "tablist"
    assert "mobile-segmented" in classes(selector[1])
    assert "view-operations" in ancestor_ids(selector)
    for action in ("spend", "add-funds", "transfer", "scan"):
        tab = parser.by_id(f"operation-tab-{action}")
        assert tab[0] == "button" and tab[1]["role"] == "tab"
        assert "mobile-interactive" in classes(tab[1])

    account_card = parser.by_id("operations-account-card")
    period_card = parser.by_id("operations-period")
    assert "mobile-ops-card" in classes(account_card[1])
    assert "mobile-ops-card" in classes(period_card[1])
    assert "is-active" in classes(account_card[1])
    assert "is-absent" in classes(period_card[1])
    assert any("operations-card-row" in classes(attrs) for _, attrs in account_card[2])
    assert any("operations-card-row" in classes(attrs) for _, attrs in period_card[2])
    assert account_card[1]["role"] == period_card[1]["role"] == "group"
    all_ids = {attrs.get("id") for _, attrs, _ in parser.elements if attrs.get("id")}
    for card in (account_card, period_card):
        label_id = card[1].get("aria-labelledby")
        assert label_id in all_ids
        label = parser.by_id(label_id)
        assert card[1]["id"] in ancestor_ids(label)
    account_select = parser.by_id("operations-account")
    assert account_select[0] == "select" and "mobile-field" in classes(account_select[1])
    assert "operations-account-card" in ancestor_ids(account_select)
    period_buttons = [item for item in parser.elements if "operations-period" in ancestor_ids(item) and item[0] == "button"]
    assert period_buttons and all("mobile-interactive" in classes(item[1]) for item in period_buttons)
    headers = [item for item in parser.elements if "mobile-screen-header" in classes(item[1])]
    for header in headers:
        header_view = next(attrs["id"] for _, attrs in header[2] if attrs.get("id", "").startswith("view-"))
        buttons = [
            item for item in parser.elements
            if item[0] == "button"
            and any("mobile-screen-header" in classes(attrs) for _, attrs in item[2])
            and header_view in ancestor_ids(item)
        ]
        assert len(buttons) == 1
        assert "mobile-interactive" in classes(buttons[0][1])
        assert buttons[0][1].get("aria-label")
        if header_view == "view-plan":
            assert buttons[0][1]["id"] == "add-plan-rule"
    for value_id in ("net-worth", "available-total", "plan-open-count", "plan-completed-count"):
        value = parser.by_id(value_id)
        surfaces = [attrs for _, attrs in value[2] if "mobile-metric-strip" in classes(attrs)]
        assert len(surfaces) == 1
        visual_surfaces = [attrs for _, attrs in value[2] if "mobile-surface" in classes(attrs)]
        assert len(visual_surfaces) == 1
        metric_ancestors = [attrs for _, attrs in value[2] if "mobile-metric" in classes(attrs)]
        assert len(metric_ancestors) == 1
    assert "primitive-demo" not in html and "demo-gallery" not in html


def test_live_renderers_bind_rows_money_and_both_operations_states():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    accounts = function_definition(javascript, "renderAccounts")
    operations = function_definition(javascript, "renderOperationsPeriod")
    plan = function_definition(javascript, "planRuleCardNode")
    money_parts = function_definition(javascript, "moneyParts")
    money_markup = function_definition(javascript, "moneyMarkup")

    for fragment in (
        'class="group-heading mobile-group-header"',
        'button.className = "account-card mobile-list-row mobile-interactive"',
        'class="account-icon mobile-leading-icon"',
        'class="account-name mobile-row-title mobile-truncate"',
        "moneyMarkup(account.balance, account.asset.code)",
    ):
        assert fragment in accounts
    assert 'card.className = "rule-card plan-rule-card mobile-surface"' in plan
    assert 'class="plan-rule-meta"' in plan
    assert "moneyMarkup(rule.amount, rule.asset.code)" in plan
    assert '$(' + '"operations-period"' + ').classList.toggle("is-active", Boolean(current))' in operations
    assert '$(' + '"operations-period"' + ').classList.toggle("is-absent", !current)' in operations
    assert "formatNumber(value, assetByCode(code)?.decimals ?? null)" in money_parts
    assert "return { value:" in money_parts and "code: String(code)" in money_parts
    assert not re.search(r"\b(?:Number|parseFloat|toFixed)\s*\(", money_parts)
    for fragment in ('class="mobile-money"', 'class="mobile-money-value"', 'class="mobile-money-code"', "escapeHtml(parts.value)", "escapeHtml(parts.code)"):
        assert fragment in money_markup
    account_change = javascript.split('$("operations-account").addEventListener("change", () => {', 1)[1].split("});", 1)[0]
    assert "renderOperationsAccountBalance();" in account_change


def test_format_number_executes_exact_fiat_and_crypto_string_cases_without_float_conversion():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    formatter = function_definition(javascript, "formatNumber")
    assert 'fraction.padEnd(precision, "0")' in formatter
    assert not re.search(r"\b(?:Number|parseFloat|toFixed)\s*\(", formatter)
    cases = [
        ["0", 2],
        ["1234.5", 2],
        ["-00012.34000000", 8],
        ["0.12345678", 8],
        ["12345678901234567890.12345678", 8],
    ]
    script = f"{formatter}; process.stdout.write(JSON.stringify({json.dumps(cases)}.map(([v,p]) => formatNumber(v,p))));"
    result = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [
        "0.00",
        "1,234.50",
        "−12.34000000",
        "0.12345678",
        "12,345,678,901,234,567,890.12345678",
    ]


def test_desktop_contract_declarations_remain_and_mobile_overrides_reset_inherited_sizes():
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    mobile = balanced_block(css, MOBILE_MARKER)
    desktop = css.split("@media (max-width: 900px)", 1)[0]
    assert declarations(desktop, ".account-card")["min-height"] == "170px"
    assert declarations(desktop, ".account-card")["border-radius"] == "18px"
    assert declarations(desktop, ".metric-card")["min-height"] == "152px"
    assert declarations(desktop, ".operations-selector")["grid-template-columns"] == "repeat(4, minmax(0, 1fr))"
    assert ".metric-card span" not in desktop
    assert ".metric-card > span" in desktop
    assert ".rule-card span" not in desktop
    rule_meta = declarations(desktop, ".rule-card .plan-rule-meta")
    assert (rule_meta["display"], rule_meta["margin-top"], rule_meta["color"], rule_meta["font-size"]) == ("block", "4px", "var(--muted)", ".76rem")
    assert declarations(mobile, ".account-card")["height"] == "64px"
    assert declarations(mobile, ".account-card")["min-height"] == "64px"
    assert declarations(mobile, ".mobile-metric")["min-height"] == "0"
    assert declarations(mobile, ".operations-selector")["grid-template-columns"] == "repeat(4, minmax(0, 1fr))"
