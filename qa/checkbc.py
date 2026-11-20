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
errors=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=_chrome_path(),args=["--no-sandbox"])
    pg=b.new_page(viewport={"width":390,"height":900})
    pg.on("pageerror",lambda e: errors.append(str(e)))
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)
    pg.goto(PATH); pg.wait_for_timeout(500)
    pg.locator("[data-nav='tubes']").click(); pg.wait_for_timeout(250)
    pg.locator("#v-tubes .block .bh").first.click(); pg.wait_for_timeout(250)
    print("first tube block text:", pg.locator("#v-tubes .block").first.inner_text()[:400])
    pg.screenshot(path="BC1_tubes.png")
    # also check tube picker dot for blood culture
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-pk='bloodculture']").click(); pg.wait_for_timeout(300)
    print("picker shows:", pg.locator("#v-tools .card-pad .kv .v").first.inner_text())
    pg.screenshot(path="BC2_picker.png")
    b.close()
print("ERRORS:", errors if errors else "none")
