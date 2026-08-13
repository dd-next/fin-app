from html.parser import HTMLParser
from pathlib import Path
import subprocess


STATIC = Path("app/static")


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def function_source(javascript: str, name: str, next_name: str) -> str:
    start = javascript.index(f"function {name}")
    return javascript[start : javascript.index(f"function {next_name}", start)]


def executable_function_source(javascript: str, name: str) -> str:
    async_marker = f"async function {name}"
    marker = async_marker if async_marker in javascript else f"function {name}"
    start = javascript.index(marker)
    opening = javascript.index("{", start)
    depth = 0
    for index in range(opening, len(javascript)):
        if javascript[index] == "{":
            depth += 1
        elif javascript[index] == "}":
            depth -= 1
            if depth == 0:
                return javascript[start : index + 1]
    raise AssertionError(f"unclosed JavaScript function: {name}")


class NavParentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[str] = []
        self.nav_ancestors: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id") == "primary-nav":
            self.nav_ancestors = list(self.stack)
        if tag not in {"meta", "link", "input", "br", "img"}:
            self.stack.append(values.get("id", ""))

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()


def test_primary_nav_is_reparented_only_for_the_ios_safari_scroll_container():
    html = source("index.html")
    javascript = source("app.js")
    parser = NavParentParser()
    parser.feed(html)

    assert "app-shell" in parser.nav_ancestors
    assert 'id="primary-nav" class="primary-nav" aria-label="Primary" hidden' in html
    placement = function_source(javascript, "placePrimaryNavForViewport", "categoriesFor")
    assert 'if (nav.parentElement === shell) shell.after(nav)' in placement
    assert 'if (nav.parentElement !== shell) shell.insertBefore(nav, $("page-loading"))' in placement
    assert 'placePrimaryNavForViewport()' in javascript
    assert '$("primary-nav").hidden = false' in javascript
    assert '$("primary-nav").hidden = true' in javascript
    assert '$("app-shell").scrollTop = 0' in javascript


def test_all_feed_drains_mixed_pages_without_rendering_planned_rows():
    javascript = source("app.js")
    drain = executable_function_source(javascript, "fetchMobileTransactionFeedPage")

    assert 'const remaining = visibleLimit - persisted.length' in drain
    assert 'new URLSearchParams({ filter, limit: String(remaining) })' in drain
    assert 'if (sourceCursor) query.set("cursor", sourceCursor)' in drain
    assert 'page.items.filter((item) => item.kind === "transaction")' in drain
    assert 'sourceCursor = page.next_cursor' in drain
    assert 'persisted.length < visibleLimit' in drain
    assert 'return { items: persisted, next_cursor: sourceCursor }' in drain
    assert '.filter(' not in function_source(
        javascript,
        "renderMobileTransactions",
        "openFeedItemDetail",
    )


def test_all_feed_executes_plan_heavy_cursor_drain_and_append_continuity():
    javascript = source("app.js")
    drain = executable_function_source(javascript, "fetchMobileTransactionFeedPage")
    script = f"""
const assert = require("node:assert/strict");
let responses = [];
let calls = [];
async function api(path) {{
  const url = new URL(path, "http://finapp.test");
  calls.push({{ filter: url.searchParams.get("filter"), limit: Number(url.searchParams.get("limit")), cursor: url.searchParams.get("cursor") }});
  return responses.shift();
}}
{drain}
const planned = (count) => Array.from({{ length: count }}, (_, index) => ({{ kind: "planned", key: `p${{index}}` }}));
const transaction = (key, financial_date) => ({{ kind: "transaction", key, financial_date }});
(async () => {{
  responses = [
    {{ items: [...planned(48), transaction("corrected-new", "2026-08-13"), transaction("second", "2026-08-12")], next_cursor: "c1" }},
    {{ items: [planned(1)[0], ...Array.from({{ length: 47 }}, (_, index) => transaction(`t${{index}}`, `2026-07-${{String(31 - index).padStart(2, "0")}}`))], next_cursor: "c2" }},
    {{ items: [transaction("last", "2026-06-01")], next_cursor: "c3" }},
  ];
  const first = await fetchMobileTransactionFeedPage("all");
  assert.deepEqual(calls.map((call) => call.limit), [50, 48, 1]);
  assert.deepEqual(calls.map((call) => call.cursor), [null, "c1", "c2"]);
  assert.equal(first.items.length, 50);
  assert.equal(first.items.some((item) => item.kind === "planned"), false);
  assert.deepEqual(first.items.slice(0, 2).map((item) => item.key), ["corrected-new", "second"]);
  assert.equal(first.items.at(-1).key, "last");
  assert.equal(first.next_cursor, "c3");

  calls = [];
  responses = [{{ items: [transaction("append", "2026-05-01")], next_cursor: null }}];
  const appended = await fetchMobileTransactionFeedPage("all", first.next_cursor);
  assert.deepEqual(calls, [{{ filter: "all", limit: 50, cursor: "c3" }}]);
  assert.deepEqual([...first.items, ...appended.items].slice(-2).map((item) => item.key), ["last", "append"]);

  calls = [];
  responses = [{{ items: [{{ kind: "planned", key: "explicit-planned" }}], next_cursor: "p1" }}];
  const explicit = await fetchMobileTransactionFeedPage("planned");
  assert.equal(explicit.items[0].kind, "planned");
  assert.equal(explicit.next_cursor, "p1");
  assert.deepEqual(calls, [{{ filter: "planned", limit: 50, cursor: null }}]);

  calls = [];
  responses = [
    {{ items: planned(50), next_cursor: "e1" }},
    {{ items: [transaction("only-1", "2026-04-02"), transaction("only-2", "2026-04-01")], next_cursor: null }},
  ];
  const exhausted = await fetchMobileTransactionFeedPage("all");
  assert.deepEqual(calls.map((call) => call.limit), [50, 50]);
  assert.deepEqual(exhausted.items.map((item) => item.key), ["only-1", "only-2"]);
  assert.equal(exhausted.next_cursor, null);
}})().catch((error) => {{ console.error(error); process.exitCode = 1; }});
"""
    subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)


def test_core_overlays_cover_tabs_but_profile_and_plan_keep_prior_geometry():
    javascript = source("app.js")
    css = source("style.css")

    render = function_source(javascript, "renderMobileOverlay", "openMobileSheet")
    assert 'root.classList.toggle("core-overlay", Boolean(active && entry.coverTabBar))' in render
    assert '.mobile-overlay-root.core-overlay { bottom: 0; }' in css
    assert '.mobile-option-list, .mobile-option { width: 100%; }' in css
    profile = function_source(javascript, "openMobileProfile", "openLogoutConfirmation")
    categories = function_source(javascript, "openMobileCategories", "buildMobileCategoryForm")
    rates = javascript[javascript.index("async function openMobileRateSettings"):javascript.index("async function openRateSettings")]
    plan = function_source(javascript, "openMobilePlanItem", "archivePlanRule")
    assert 'coverTabBar: false' in profile
    assert 'coverTabBar: false' in categories
    assert rates.count('coverTabBar: false') >= 2
    assert 'coverTabBar: false' in plan
    link_start = javascript.index("async function openMobilePlanLink")
    link_end = javascript.index("function mobileTransactionEditBody", link_start)
    assert 'coverTabBar: false' in javascript[link_start:link_end]


def test_core_editable_controls_prevent_safari_auto_zoom_without_disabling_zoom():
    html = source("index.html")
    css = source("style.css")

    viewport = 'content="width=device-width, initial-scale=1, viewport-fit=cover"'
    assert viewport in html
    assert "maximum-scale" not in html
    assert "user-scalable=no" not in html
    assert '.mobile-overlay-root.core-overlay textarea { font-size: 16px; }' in css
    for view in ("accounts", "transactions", "operations"):
        assert f'#view-{view} input:not([type="checkbox"])' in css


def test_mobile_assets_are_cache_busted_for_real_device_recheck():
    html = source("index.html")

    assert '/style.css?v=phase15-t030a-1' in html
    assert '/app.js?v=phase15-t030a-1' in html
