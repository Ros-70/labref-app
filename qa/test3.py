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
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.on("pageerror",lambda e: errors.append("PAGEERROR: "+str(e)))
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)
    pg.goto(PATH); pg.wait_for_timeout(700)
    _shotdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_shots")
    _os.makedirs(_shotdir, exist_ok=True)
    def shot(n): pg.screenshot(path=_os.path.join(_shotdir, f"{n}.png"))
    shot("A_home")
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(300)
    shot("B_picker")
    pg.locator("[data-cat='sepsis']") if False else None
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-cat='coag']").click(); pg.wait_for_timeout(250)
    shot("C_category")
    pg.locator("[data-test='ddimer']").click(); pg.wait_for_timeout(350)
    shot("D_detail")
    # pregnancy T3 on d-dimer
    pg.locator("#modebar .chip").nth(1).click(); pg.wait_for_timeout(200)
    for _ in range(3): pg.locator("#modebar .chip").nth(3).click(); pg.wait_for_timeout(180)
    print("ddimer preg match:", pg.locator("#v-detail tr.match .grp").first.inner_text(),
          "|", pg.locator("#v-detail tr.match .val").first.inner_text())
    shot("E_ddimer_preg")
    b.close()
print("ERRORS:", errors if errors else "none")
