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
    pg.on("pageerror",lambda e: errors.append("PAGEERROR: "+str(e)))
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)
    pg.goto(PATH); pg.wait_for_timeout(500)
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(250)
    for t in ["lipid","tsh","glucosef","ptinr","hb","potassium"]:
        pg.locator(f"[data-pk='{t}']").click(); pg.wait_for_timeout(90)
    pg.wait_for_timeout(300)
    pg.locator("#toHandout").click(); pg.wait_for_timeout(400)
    ho=pg.locator("#hoText").inner_text()
    leak=[s for s in ["dead-space","DOAC","amiodarone","Record the exact time of the last warfarin",
                      "dilutional false low","tourniquet","No special preparation"] if s in ho]
    print("clinician lines leaked into handout:", leak if leak else "NONE")
    print("---- handout ----"); print(ho)
    pg.screenshot(path="Q1_handout.png")
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-cat='horm']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='tsh']").click(); pg.wait_for_timeout(350)
    pg.evaluate("window.scrollTo(0,450)"); pg.wait_for_timeout(200)
    pg.screenshot(path="Q2_prep_split.png")
    b.close()
print("ERRORS:", errors if errors else "none")
