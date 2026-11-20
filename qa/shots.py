from playwright.sync_api import sync_playwright
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
    """Resolve the built app in either layout: repo root (dev) or app/ (handover)."""
    here = _os.path.dirname(_os.path.abspath(__file__))
    for rel in ("../LabRef_v1.10.html", "../app/LabRef_v1.10.html"):
        p = _os.path.normpath(_os.path.join(here, rel))
        if _os.path.exists(p):
            return "file://" + p
    raise SystemExit("LabRef_v1.10.html not found — run build.py first")

PATH=_labref_html()
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=_chrome_path(),args=["--no-sandbox"])
    pg=b.new_page(viewport={"width":390,"height":900})
    pg.goto(PATH); pg.wait_for_timeout(500)
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(250)
    for t in ["hb","ptinr","glucosef","potassium","bloodculture","lactate","ferritin"]:
        pg.locator(f"[data-pk='{t}']").click(); pg.wait_for_timeout(90)
    pg.wait_for_timeout(350); pg.screenshot(path="P1_picker_full.png")
    pg.locator("#toHandout").click(); pg.wait_for_timeout(400); pg.screenshot(path="P2_handout.png")
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-cat='sepsis']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='pct']").click(); pg.wait_for_timeout(350)
    pg.screenshot(path="P3_pct_top.png")
    bl=pg.locator("#v-detail .block .bh")
    for i in range(bl.count()):
        if "Causes of raised" in bl.nth(i).inner_text(): bl.nth(i).click(); break
    pg.wait_for_timeout(300)
    pg.evaluate("window.scrollTo(0,700)"); pg.wait_for_timeout(200)
    pg.screenshot(path="P4_pct_mid.png")
    b.close()
print("ok")
