from playwright.sync_api import sync_playwright
import sys

import os as _os

def _chrome_path():
    """Chrome location differs between this workspace and CI; honour CHROME_PATH."""
    import os, shutil
    p = os.environ.get("CHROME_PATH")
    if p and os.path.exists(p):
        return p
    for c in ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if os.path.exists(c):
            return c
    found = shutil.which("google-chrome") or shutil.which("chromium")
    return found  # None -> Playwright falls back to its own bundled browser

def _labref_html():
    """Resolve the built app by glob, in either layout: repo root or app/.

    The version is NOT hardcoded here on purpose. It used to be, and that let
    this suite pass against a stale build from an earlier version while the
    current data sat unverified. Globbing with a strict "exactly one" rule
    turns a leftover build into a hard error instead of a silent fallback."""
    import glob as _glob
    here = _os.path.dirname(_os.path.abspath(__file__))
    hits = []
    for rel in ("../LabRef_v*.html", "../app/LabRef_v*.html"):
        hits += _glob.glob(_os.path.normpath(_os.path.join(here, rel)))
    hits = sorted(set(hits))
    if not hits:
        raise SystemExit("No LabRef_v*.html found — run build.py first")
    if len(hits) > 1:
        raise SystemExit(
            "%d builds found (%s) — remove stale versions so the suite cannot "
            "verify the wrong one" % (len(hits), ", ".join(_os.path.basename(h) for h in hits)))
    return "file://" + hits[0]

URL = _labref_html()
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=_chrome_path(), headless=True)
    page = browser.new_page(viewport={"width":390,"height":844})
    page.on("console", lambda m: errors.append(("console", m.type, m.text)) if m.type=="error" else None)
    page.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    page.goto(URL)
    page.wait_for_timeout(300)

    # open More -> Appearance
    page.click("[data-nav='more']")
    page.wait_for_timeout(200)

    chips = page.eval_on_selector_all("[data-th]", "els => els.map(e=>({t:e.dataset.th, label:e.textContent}))")
    print("Theme chips:", chips)
    assert len(chips) == 6, f"expected 6 theme chips, got {chips}"
    expected = {"light","dark","sepia","pista","beige","steel"}
    assert {c["t"] for c in chips} == expected

    for t in ["light","dark","sepia","pista","beige","steel"]:
        page.click(f"[data-th='{t}']")
        page.wait_for_timeout(150)
        applied = page.evaluate("document.body.dataset.theme")
        assert applied == t, f"theme {t} did not apply, body has {applied}"
        meta = page.evaluate("document.querySelector('meta[name=theme-color]').content")
        print(f"{t}: body theme={applied}  meta theme-color={meta}")
        # go look at a detail page + my lab block to make sure nothing is unreadable/broken
        page.click("[data-nav='tests']")
        page.wait_for_timeout(100)
        page.click("[data-cat='lipid']")
        page.wait_for_timeout(150)
        page.click("[data-test='lipid']")
        page.wait_for_timeout(200)
        page.screenshot(path=f"qa/theme_{t}.png", full_page=True)
        page.click("[data-nav='more']")
        page.wait_for_timeout(150)

    page.evaluate("localStorage.removeItem('labref_v1')")
    browser.close()

if errors:
    print("\n=== ERRORS ===")
    for e in errors: print(e)
    sys.exit(1)
print("\nALL THEME TESTS PASSED, NO CONSOLE ERRORS")
