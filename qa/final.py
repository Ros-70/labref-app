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
    pg.goto(PATH); pg.wait_for_timeout(600)
    # visit every test detail and expand every block — catches data/render faults
    ids=pg.evaluate("MEDREF_TESTS.map(t=>t.id)")
    bad=[]
    for tid in ids:
        pg.evaluate("""(id)=>{const b=document.createElement('button');b.id='__jump';
          b.onclick=()=>{};document.body.appendChild(b);}""",tid)
        pg.goto(PATH); pg.wait_for_timeout(120)
        cat=pg.evaluate("(id)=>MEDREF_TESTS.find(t=>t.id===id).cat",tid)
        pg.locator(f"[data-cat='{cat}']").click(); pg.wait_for_timeout(100)
        pg.locator(f"[data-test='{tid}']").click(); pg.wait_for_timeout(160)
        n=pg.locator("#v-detail .block").count()
        for i in range(n): pg.locator("#v-detail .block .bh").nth(i).click()
        pg.wait_for_timeout(120)
        h1=pg.locator("#v-detail h1").inner_text()
        if n<8 or not h1: bad.append((tid,n,h1))
    print("tests opened:",len(ids),"| blocks<8 or no title:",bad if bad else "none")
    # every tube block
    pg.locator("[data-nav='tubes']").click(); pg.wait_for_timeout(250)
    tb=pg.locator("#v-tubes .block .bh")
    for i in range(tb.count()): tb.nth(i).click()
    pg.wait_for_timeout(200); print("tube blocks opened:",tb.count())
    # every reverse-lookup finding
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='reverse']").click(); pg.wait_for_timeout(200)
    opts=pg.locator("#rvSel option").count()
    for i in range(1,opts,7):
        pg.select_option("#rvSel",str(i-1)); pg.wait_for_timeout(90)
    print("reverse findings available:",opts-1)
    b.close()
print("ERRORS:", errors if errors else "none")
