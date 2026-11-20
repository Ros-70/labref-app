from playwright.sync_api import sync_playwright
import json, sys
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


PATH = _labref_html()
errors, logs = [], []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=_chrome_path(), args=["--no-sandbox"])
    pg = b.new_page(viewport={"width":390,"height":844})
    pg.on("console", lambda m: (errors.append(m.text) if m.type=="error" else logs.append(m.text)))
    pg.on("pageerror", lambda e: errors.append("PAGEERROR: "+str(e)))
    pg.goto(PATH); pg.wait_for_timeout(800)
    _shotdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_shots")
    _os.makedirs(_shotdir, exist_ok=True)

    def shot(n): pg.screenshot(path=_os.path.join(_shotdir, f"{n}.png"), full_page=False)

    # 1. home
    shot("01_home")
    print("categories rendered:", pg.locator("[data-cat]").count())

    # 2. open a category then a test
    pg.locator("[data-cat='sepsis']").click(); pg.wait_for_timeout(300)
    print("sepsis tests:", pg.locator("[data-test]").count())
    shot("02_category")

    pg.locator("[data-test='pct']").click(); pg.wait_for_timeout(400)
    print("detail title:", pg.locator("#v-detail h1").inner_text())
    print("badges:", pg.locator("#v-detail .badges .badge").all_inner_texts())
    shot("03_detail")

    # 3. expand all blocks
    for i in range(pg.locator("#v-detail .block .bh").count()):
        pg.locator("#v-detail .block .bh").nth(i).click()
    pg.wait_for_timeout(300)
    shot("04_detail_expanded")

    # 4. unit toggle
    pg.locator("#backBtn").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='creatinine']").click() if pg.locator("[data-test='creatinine']").count() else None
    pg.goto(PATH); pg.wait_for_timeout(500)
    pg.locator("#searchToggle").click(); pg.wait_for_timeout(200)
    pg.locator("#searchBox").fill("KFT"); pg.wait_for_timeout(400)
    print("search 'KFT' results:", pg.locator("[data-test]").count())
    shot("05_search")
    pg.locator("[data-test]").first.click(); pg.wait_for_timeout(400)
    conv = pg.locator("#v-detail table.rng tr.match .val").first.inner_text()
    pg.locator("#modebar .chip").first.click(); pg.wait_for_timeout(400)
    si = pg.locator("#v-detail table.rng tr.match .val").first.inner_text()
    print("unit toggle:", conv, "->", si)
    shot("06_si_units")

    # 5. patient mode: female + pregnancy
    pg.goto(PATH); pg.wait_for_timeout(500)
    pg.locator("[data-cat='rbc']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='hb']").click(); pg.wait_for_timeout(300)
    m0 = pg.locator("#v-detail tr.match .grp").first.inner_text()
    pg.locator("#modebar .chip").nth(1).click(); pg.wait_for_timeout(300)   # -> Female
    pg.locator("#modebar .chip").nth(3).click(); pg.wait_for_timeout(300)   # -> T1
    pg.locator("#modebar .chip").nth(3).click(); pg.wait_for_timeout(300)   # -> T2
    m1 = pg.locator("#v-detail tr.match .grp").first.inner_text()
    print("patient mode:", m0, "->", m1)
    shot("07_pregnancy_mode")

    # 6. paediatric
    pg.locator("#modebar .chip").nth(3).click(); pg.wait_for_timeout(200)  # T3
    pg.locator("#modebar .chip").nth(3).click(); pg.wait_for_timeout(200)  # none
    pg.locator("#modebar .chip").nth(2).click(); pg.wait_for_timeout(300)  # neonate
    print("neonate match:", pg.locator("#v-detail tr.match .grp").first.inner_text())

    # 7. local lab override
    pg.goto(PATH); pg.wait_for_timeout(500)
    pg.locator("[data-cat='cardiac']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-test='troponin']").click(); pg.wait_for_timeout(300)
    blocks = pg.locator("#v-detail .block .bh")
    for i in range(blocks.count()):
        if "Your lab" in blocks.nth(i).inner_text(): blocks.nth(i).click(); break
    pg.wait_for_timeout(300)
    pg.locator("#lcLo").fill("0"); pg.locator("#lcHi").fill("19")
    pg.locator("#lcMethod").fill("Roche cobas e411, hs-cTnT")
    pg.locator("#lcCrit").fill(">52 ng/L")
    pg.locator("#lcSave").click(); pg.wait_for_timeout(500)
    print("local row present:", pg.locator("#v-detail tr.localrow").count())
    print("local badge:", "Local value set" in pg.locator("#v-detail .badges").inner_text())
    shot("08_local_override")

    # 8. interpreter uses local value
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(300)
    pg.locator("[data-tool='interp']").click(); pg.wait_for_timeout(300)
    pg.select_option("#ipTest","troponin"); pg.locator("#ipVal").fill("31")
    pg.locator("#ipGo").click(); pg.wait_for_timeout(400)
    print("interpreter:", pg.locator(".result-flag").inner_text())
    print("used local:", "Your lab" in pg.locator("#ipOut").inner_text())
    shot("09_interpreter")

    # 9. tube picker
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(300)
    for tid in ["hb","ptinr","glucosef","potassium","bloodculture"]:
        pg.locator(f"[data-pk='{tid}']").click(); pg.wait_for_timeout(120)
    pg.wait_for_timeout(300)
    print("picker order rows:", pg.locator("#v-tools .card-pad .kv").count())
    shot("10_tube_picker")

    # 10. handout
    pg.locator("#toHandout").click(); pg.wait_for_timeout(400)
    ho = pg.locator("#hoText").inner_text()
    print("handout chars:", len(ho), "| fasting line:", "FASTING REQUIRED" in ho)
    shot("11_handout")

    # 11. tubes tab
    pg.locator("[data-nav='tubes']").click(); pg.wait_for_timeout(300)
    print("tube blocks:", pg.locator("#v-tubes .block").count())
    shot("12_tubes")

    # 12. my lab + export
    pg.locator("[data-nav='mylab']").click(); pg.wait_for_timeout(300)
    print("overridden listed:", pg.locator("#v-mylab [data-test]").count())
    shot("13_mylab")

    # 13. reverse lookup
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(200)
    pg.locator("[data-tool='reverse']").click(); pg.wait_for_timeout(300)
    pg.select_option("#rvSel","2"); pg.wait_for_timeout(400)
    print("reverse causes:", pg.locator("#rvOut ul.lst li").count())
    shot("14_reverse")

    # 14. dark theme
    pg.locator("[data-nav='more']").click(); pg.wait_for_timeout(300)
    pg.locator("[data-th='dark']").click(); pg.wait_for_timeout(400)
    shot("15_dark")
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(300)
    shot("16_dark_home")

    # 15. persistence across reload
    pg.reload(); pg.wait_for_timeout(700)
    print("theme persisted:", pg.evaluate("document.body.dataset.theme"))
    print("local persisted:", pg.evaluate("JSON.parse(localStorage.getItem('labref_v1')).local.troponin.hi"))

    b.close()

print("\n--- CONSOLE ERRORS ---")
print("\n".join(errors) if errors else "none")
