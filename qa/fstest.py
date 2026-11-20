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
    pg.on("pageerror",lambda e: errors.append(str(e)))
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)
    pg.goto(PATH); pg.wait_for_timeout(500)

    def px(sel): return pg.eval_on_selector(sel,"e=>getComputedStyle(e).fontSize")

    base_h1 = px("h2.sec") if False else None
    pg.locator("[data-cat='rbc']").click(); pg.wait_for_timeout(200)
    print("row name @100%:", px(".row .nm"))
    print("sec header @100%:", px("h2.sec"))
    print("badge @100%:", px(".badge")) if pg.locator(".badge").count() else None

    pg.locator("[data-nav='more']").click(); pg.wait_for_timeout(250)
    pg.eval_on_selector("#fsRange","e=>{e.value=145;e.dispatchEvent(new Event('input'))}")
    pg.wait_for_timeout(300)
    print("root fontSize style:", pg.evaluate("document.documentElement.style.fontSize"))

    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-cat='rbc']").click(); pg.wait_for_timeout(200)
    print("row name @145%:", px(".row .nm"))
    print("row desc @145%:", px(".row .ds"))
    print("sec header @145%:", px("h2.sec"))
    pg.screenshot(path="FS1_145_list.png")

    pg.locator("[data-test='hb']").click(); pg.wait_for_timeout(350)
    print("h1 title @145%:", px("#v-detail h1"))
    for i in range(pg.locator("#v-detail .block .bh").count()):
        pg.locator("#v-detail .block .bh").nth(i).click()
    pg.wait_for_timeout(250)
    print("list item @145%:", px("#v-detail ul.lst li"))
    pg.screenshot(path="FS2_145_detail.png")

    # check input still matches too (regression)
    bl=pg.locator("#v-detail .block .bh")
    for i in range(bl.count()):
        if "Your lab" in bl.nth(i).inner_text():
            print("input @145%:", px(".lc-lo")); break

    pg.locator("[data-nav='more']").click(); pg.wait_for_timeout(250)
    pg.eval_on_selector("#fsRange","e=>{e.value=85;e.dispatchEvent(new Event('input'))}")
    pg.wait_for_timeout(300)
    pg.locator("[data-nav='tests']").click(); pg.wait_for_timeout(250)
    print("row name @85%:", px(".row .nm"))
    pg.screenshot(path="FS3_85_list.png")

    # persistence
    pg.reload(); pg.wait_for_timeout(600)
    print("fs persisted:", pg.evaluate("document.documentElement.style.fontSize"))
    b.close()
print("ERRORS:", errors if errors else "none")
