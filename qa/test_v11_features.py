"""
LabRef v1.1 feature regression  (test method 1: real browser, real user actions)

Covers everything added or changed in v1.1:
  * detail-page blocks collapsed by default except Reference ranges + Interpretation notes
  * breadcrumb "page address" — content, navigation, no truncation
  * Tests-tab panels collapsible, open by default, collapse state persisted
  * MedRef -> LabRef rename, including legacy localStorage migration
Run: python3 -I qa/test_v11_features.py
"""
import sys, json
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

URL = _labref_html()
errors, failures = [], []

def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + (("  -> " + str(detail)) if detail else ""))
    if not cond:
        failures.append(label)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=_chrome_path(), args=["--no-sandbox"], headless=True)
    pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("console", lambda m: errors.append((m.type, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    pg.goto(URL); pg.wait_for_timeout(400)

    # ---------- 1. rename ----------
    print("\n-- rename --")
    bar = pg.inner_text("#appbar .title").strip()
    check("app bar shows LabRef", bar.startswith("LabRef"), bar)
    check("app bar shows the version next to the name",
          pg.inner_text("#appbar .ver").strip() == "v 1.10",
          pg.inner_text("#appbar .ver").strip())
    check("version label is smaller than the app name",
          pg.evaluate("""()=>{const t=getComputedStyle(document.querySelector('#appbar .title')).fontSize,
              v=getComputedStyle(document.querySelector('#appbar .ver')).fontSize;
              return parseFloat(v) < parseFloat(t);}"""))
    check("document title renamed", "LabRef" in pg.title(), pg.title())
    check("no MedRef string anywhere in rendered body",
          "MedRef" not in pg.inner_text("body"))
    pg.click("[data-nav='more']"); pg.wait_for_timeout(200)
    check("About shows LabRef version", "LabRef v1.10" in pg.inner_text("#v-more"))

    # ---------- 2. detail-page block defaults ----------
    print("\n-- detail block defaults --")
    pg.click("[data-nav='tests']"); pg.wait_for_timeout(150)
    pg.click("[data-cat='elec']"); pg.wait_for_timeout(150)
    pg.click("[data-test='creatinine']"); pg.wait_for_timeout(300)
    blocks = pg.evaluate("""()=>[...document.querySelectorAll('#v-detail .block')]
        .map(b=>({id:b.dataset.blk, open:b.classList.contains('open'),
                  title:b.querySelector('.bh').textContent.replace('›','').trim()}))""")
    opened = sorted(b["id"] for b in blocks if b["open"])
    check("only rng + prl open by default", opened == ["prl", "rng"], opened)
    check("all other blocks collapsed",
          all(not b["open"] for b in blocks if b["id"] not in ("rng", "prl")),
          [b["id"] for b in blocks if b["open"]])
    # a saved local value must NOT auto-open the My Lab editor
    pg.evaluate("""()=>{const k='labref_v1';const o=JSON.parse(localStorage.getItem(k)||'{}');
        o.local={creatinine:{note:'',comp:{_:{lo:'0.6',hi:'1.2',crit:'>3.5',method:'x'}}}};
        localStorage.setItem(k,JSON.stringify(o));}""")
    pg.reload(); pg.wait_for_timeout(400)
    pg.click("[data-cat='elec']"); pg.wait_for_timeout(150)
    pg.click("[data-test='creatinine']"); pg.wait_for_timeout(300)
    loc_open = pg.evaluate("()=>document.querySelector(\"[data-blk='loc']\").classList.contains('open')")
    check("My Lab block stays collapsed even with a saved value", loc_open is False)
    check("but the saved value still shows as the active range",
          "Your lab" in pg.inner_text("[data-blk='rng']"))
    pg.evaluate("()=>localStorage.clear()"); pg.reload(); pg.wait_for_timeout(400)

    # ---------- 3. breadcrumb ----------
    print("\n-- breadcrumb --")
    def crumbs():
        return pg.inner_text("#crumbs").replace("\n", " ").strip()
    check("root crumb on Tests", crumbs() == "Tests", crumbs())
    pg.click("[data-cat='lipid']"); pg.wait_for_timeout(200)
    check("category crumb", crumbs() == "Tests › Lipids", crumbs())
    pg.click("[data-test='lipid']"); pg.wait_for_timeout(300)
    check("detail crumb", crumbs() == "Tests › Lipids › Lipid Profile", crumbs())
    clipped = pg.evaluate("""()=>[...document.querySelectorAll('#crumbs .crumb')]
        .filter(s=>s.scrollWidth>s.clientWidth+1).map(s=>s.textContent)""")
    check("no crumb truncated at 390px", clipped == [], clipped)
    check("current crumb is styled distinctly",
          pg.evaluate("""()=>{const n=document.querySelector('#crumbs .crumb.now');
              const a=document.querySelector('#crumbs .crumb.link');
              return getComputedStyle(n).color !== getComputedStyle(a).color;}"""))
    # ancestors navigate, current is not a link
    pg.click("[data-crumb='cat:lipid']"); pg.wait_for_timeout(300)
    check("category crumb navigates to that category",
          pg.eval_on_selector(".view.active", "e=>e.id") == "v-tests" and crumbs() == "Tests › Lipids",
          crumbs())
    pg.click("[data-crumb='root:tests']"); pg.wait_for_timeout(300)
    check("root crumb returns to Tests top level", crumbs() == "Tests", crumbs())
    check("current crumb is not clickable",
          pg.evaluate("()=>!document.querySelector('#crumbs .crumb.now').hasAttribute('data-crumb')"))
    pg.click("[data-nav='tools']"); pg.wait_for_timeout(150)
    pg.click("[data-tool='interp']"); pg.wait_for_timeout(250)
    check("tool crumb", crumbs() == "Tools › Result Interpreter", crumbs())
    pg.click("[data-nav='tubes']"); pg.wait_for_timeout(200)
    check("tubes crumb", crumbs() == "Tubes", crumbs())

    # ---------- 4. collapsible Tests-tab panels ----------
    print("\n-- Tests tab panels --")
    pg.click("[data-nav='tests']"); pg.wait_for_timeout(250)
    panels = pg.evaluate("""()=>[...document.querySelectorAll('#v-tests .block')]
        .map(b=>({id:b.dataset.blk, open:b.classList.contains('open'), persist:!!b.dataset.persist}))""")
    check("Categories panel present and open", any(p["id"] == "p-cats" and p["open"] for p in panels), panels)
    check("Tests-tab panels marked persistent", all(p["persist"] for p in panels), panels)
    # collapse it, navigate away and back -- must stay collapsed
    pg.click("[data-blk='p-cats'] .bh"); pg.wait_for_timeout(200)
    check("collapses on tap",
          pg.evaluate("()=>!document.querySelector(\"[data-blk='p-cats']\").classList.contains('open')"))
    pg.click("[data-nav='more']"); pg.wait_for_timeout(150)
    pg.click("[data-nav='tests']"); pg.wait_for_timeout(250)
    check("collapse survives navigation",
          pg.evaluate("()=>!document.querySelector(\"[data-blk='p-cats']\").classList.contains('open')"))
    pg.reload(); pg.wait_for_timeout(400)
    check("collapse survives reload",
          pg.evaluate("()=>!document.querySelector(\"[data-blk='p-cats']\").classList.contains('open')"))
    pg.click("[data-blk='p-cats'] .bh"); pg.wait_for_timeout(200)
    check("re-opens on tap",
          pg.evaluate("()=>document.querySelector(\"[data-blk='p-cats']\").classList.contains('open')"))
    # favourites + recently viewed appear as panels once populated
    pg.click("[data-cat='elec']"); pg.wait_for_timeout(150)
    pg.click("[data-test='sodium']"); pg.wait_for_timeout(250)
    pg.click("#favBtn"); pg.wait_for_timeout(200)
    pg.click("[data-nav='tests']"); pg.wait_for_timeout(250)
    ids = pg.eval_on_selector_all("#v-tests .block", "els=>els.map(e=>e.dataset.blk)")
    check("Favourites + Recently viewed render as panels",
          "p-favs" in ids and "p-recent" in ids, ids)
    check("new panels default to open",
          pg.evaluate("""()=>['p-favs','p-recent'].every(i=>
              document.querySelector(`[data-blk='${i}']`).classList.contains('open'))"""))
    check("rows inside a panel are flush (no double padding)",
          pg.evaluate("""()=>getComputedStyle(
              document.querySelector("[data-blk='p-cats'] .bc")).paddingLeft === '0px'"""))

    # ---------- 5. legacy storage migration ----------
    print("\n-- legacy MedRef migration --")
    pg.evaluate("""()=>{ localStorage.clear();
      localStorage.setItem('medref_v1', JSON.stringify({
        theme:'sepia', fs:120, units:'si', favs:['creatinine'],
        local:{creatinine:{note:'Send-out after 6pm',comp:{_:{lo:'0.6',hi:'1.2'}}}}})); }""")
    pg.reload(); pg.wait_for_timeout(400)
    mig = pg.evaluate("""()=>{const n=JSON.parse(localStorage.getItem('labref_v1')||'null');
        return {theme:document.body.dataset.theme, favs:n&&n.favs, units:n&&n.units, fs:n&&n.fs,
                note:n&&n.local&&n.local.creatinine&&n.local.creatinine.note};}""")
    check("theme migrated", mig["theme"] == "sepia", mig["theme"])
    check("favourites migrated", mig["favs"] == ["creatinine"], mig["favs"])
    check("units migrated", mig["units"] == "si", mig["units"])
    check("text size migrated", mig["fs"] == 120, mig["fs"])
    check("My Lab notes migrated", mig["note"] == "Send-out after 6pm", mig["note"])
    check("migration written to new key immediately (no save needed)",
          pg.evaluate("()=>!!localStorage.getItem('labref_v1')"))
    pg.evaluate("()=>localStorage.clear()"); pg.reload(); pg.wait_for_timeout(300)
    check("fresh install unaffected", pg.evaluate("()=>document.body.dataset.theme") == "light")

    b.close()

print("\n" + "="*60)
print(f"console/page errors: {errors if errors else 'none'}")
if failures:
    print(f"FAILURES ({len(failures)}): " + "; ".join(failures))
    sys.exit(1)
print("ALL v1.1 FEATURE TESTS PASSED")
sys.exit(1 if errors else 0)
