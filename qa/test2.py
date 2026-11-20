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

PATH=_labref_html()
errors=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=_chrome_path(),args=["--no-sandbox"])
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)
    pg.on("pageerror",lambda e: errors.append("PAGEERROR: "+str(e)))
    pg.goto(PATH); pg.wait_for_timeout(700)
    _shotdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_shots")
    _os.makedirs(_shotdir, exist_ok=True)
    def shot(n): pg.screenshot(path=_os.path.join(_shotdir, f"{n}.png"))

    # local override on troponin first
    pg.locator("[data-cat='cardiac']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='troponin']").click(); pg.wait_for_timeout(300)
    bl=pg.locator("#v-detail .block .bh")
    for i in range(bl.count()):
        if "Your lab" in bl.nth(i).inner_text(): bl.nth(i).click(); break
    pg.wait_for_timeout(250)
    pg.locator("#lcLo").fill("0"); pg.locator("#lcHi").fill("19")
    pg.locator("#lcMethod").fill("Roche cobas e411, hs-cTnT")
    pg.locator("#lcCrit").fill(">52 ng/L")
    pg.locator("#lcSave").click(); pg.wait_for_timeout(450)
    print("badges now:", pg.locator("#v-detail .badges .badge").all_inner_texts())
    shot("08_local_override")

    # nav bug fix: tools -> interp -> tools nav -> should show tool list
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-tool='interp']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(250)
    print("nav fix — tool list shown:", pg.locator("[data-tool='picker']").count()==1)

    # tube picker
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(300)
    for t in ["hb","ptinr","glucosef","potassium","bloodculture","lactate"]:
        pg.locator(f"[data-pk='{t}']").click(); pg.wait_for_timeout(100)
    pg.wait_for_timeout(300)
    order=[x.strip().split("\n")[0] for x in pg.locator("#v-tools .card-pad .kv .v").all_inner_texts()]
    print("draw order:", order[:8])
    shot("10_tube_picker")

    pg.locator("#toHandout").click(); pg.wait_for_timeout(400)
    ho=pg.locator("#hoText").inner_text()
    print("handout chars:",len(ho),"| fasting:", "FASTING REQUIRED" in ho)
    shot("11_handout")

    pg.locator("[data-nav='tubes']").click(); pg.wait_for_timeout(300)
    print("tube blocks:",pg.locator("#v-tubes .block").count())
    pg.locator("#v-tubes .block .bh").nth(1).click(); pg.wait_for_timeout(250)
    shot("12_tubes")

    pg.locator("[data-nav='mylab']").click(); pg.wait_for_timeout(300)
    print("overridden listed:",pg.locator("#v-mylab [data-test]").count())
    shot("13_mylab")

    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='reverse']").click(); pg.wait_for_timeout(250)
    pg.select_option("#rvSel","2"); pg.wait_for_timeout(400)
    print("reverse causes:",pg.locator("#rvOut ul.lst li").count())
    shot("14_reverse")

    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='interp']").click(); pg.wait_for_timeout(250)
    pg.select_option("#ipTest","troponin"); pg.locator("#ipVal").fill("31")
    pg.locator("#ipGo").click(); pg.wait_for_timeout(400)
    print("interp:",pg.locator(".result-flag").inner_text(),"| local used:","Your lab" in pg.locator("#ipOut").inner_text())
    shot("09_interpreter")

    pg.locator("[data-nav='more']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-th='dark']").click(); pg.wait_for_timeout(350)
    shot("15_dark_more")
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(300)
    shot("16_dark_home")
    pg.locator("[data-cat='elec']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='potassium']").click(); pg.wait_for_timeout(350)
    for i in range(pg.locator("#v-detail .block .bh").count()):
        pg.locator("#v-detail .block .bh").nth(i).click()
    pg.wait_for_timeout(300)
    shot("17_dark_detail")

    # font scale max
    pg.locator("[data-nav='more']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-th='sepia']").click(); pg.wait_for_timeout(200)
    pg.eval_on_selector("#fsRange","e=>{e.value=145;e.dispatchEvent(new Event('input'))}")
    pg.wait_for_timeout(300)
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(300)
    shot("18_sepia_large")

    pg.reload(); pg.wait_for_timeout(700)
    print("persisted theme/fs/local:",pg.evaluate("[document.body.dataset.theme,JSON.parse(localStorage.getItem('labref_v1')).fs,JSON.parse(localStorage.getItem('labref_v1')).local.troponin.hi]"))
    b.close()
print("\nERRORS:", errors if errors else "none")
