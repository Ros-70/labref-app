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
def setmode(pg,sex=None,preg=0,age=0):
    if sex=="F": pg.locator("#modebar .chip").nth(1).click(); pg.wait_for_timeout(150)
    for _ in range(preg): pg.locator("#modebar .chip").nth(3).click(); pg.wait_for_timeout(150)
    for _ in range(age):  pg.locator("#modebar .chip").nth(2).click(); pg.wait_for_timeout(150)

with sync_playwright() as p:
    b=p.chromium.launch(executable_path=_chrome_path(),args=["--no-sandbox"])
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.on("pageerror",lambda e: errors.append("PAGEERROR: "+str(e)))
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)

    cases=[("ddimer","coag","F",3,0,"Pregnancy T3"),
           ("ddimer","coag",None,0,0,"Adult (<50 y) exclusion cutoff"),
           ("hb","rbc","F",2,0,"Pregnancy T2"),
           ("hb","rbc",None,0,1,"Newborn (0–3 d)"),
           ("hb","rbc",None,0,3,"Child (2–12 y)"),
           ("alp","enz",None,0,3,"Child (2–9 y)"),
           ("alp","enz","F",3,0,"Pregnancy T3"),
           ("tsh","horm","F",1,0,"Pregnancy T1"),
           ("creatinine","elec","F",0,0,"Adult female"),
           ("creatinine","elec",None,0,0,"Adult male"),
           ("ferritin","ions","F",0,0,"Adult female"),
           ("bilirubin","liver",None,0,1,"Newborn 24 h")]
    ok=True
    for tid,cat,sex,preg,age,expect in cases:
        pg.goto(PATH); pg.wait_for_timeout(450)
        setmode(pg,sex,preg,age)
        pg.locator(f"[data-cat='{cat}']").click(); pg.wait_for_timeout(200)
        pg.locator(f"[data-test='{tid}']").click(); pg.wait_for_timeout(300)
        n=pg.locator("#v-detail tr.match").count()
        got=pg.locator("#v-detail tr.match .grp").first.inner_text() if n else "NONE"
        good = (got==expect and n==1)
        ok = ok and good
        print(("PASS " if good else "FAIL "),f"{tid:12s} sex={sex or 'M'} preg={preg} age={age} -> {got!r} (rows={n}) expect {expect!r}")
    print("\nALL RANGE SELECTION:", "PASS" if ok else "FAIL")

    # visual re-check of fixed rows
    pg.goto(PATH); pg.wait_for_timeout(450)
    _shotdir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_shots")
    _os.makedirs(_shotdir, exist_ok=True)
    pg.screenshot(path=_os.path.join(_shotdir, "A_home.png"))
    pg.locator("[data-nav='tools']").click(); pg.wait_for_timeout(250)
    pg.locator("[data-tool='picker']").click(); pg.wait_for_timeout(300)
    pg.screenshot(path=_os.path.join(_shotdir, "B_picker.png"))
    b.close()
print("ERRORS:", errors if errors else "none")
