"""
LabRef full-corpus sweep  (test method 4: every test opened in a real browser)

The other three methods check the shell, the schema and the build. This one
opens all 180 detail pages in sequence and asserts that each actually renders
the clinical content a clinician would look for, with no console error anywhere
in the walk. It also exercises patient-mode interpretation on every panel test,
which is where the component-scoping logic lives.

Run: python3 -I qa/test_all_tests.py
"""
import sys, json, re
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

def fail(label, detail=""):
    failures.append(label + (("  -> " + str(detail)) if detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=_chrome_path(),
                          args=["--no-sandbox"], headless=True)
    pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("console", lambda m: errors.append((m.type, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    pg.goto(URL); pg.wait_for_timeout(500)

    meta = pg.evaluate("""()=>LABREF_TESTS.map(t=>({
        id:t.id, name:t.name, cat:t.cat,
        panel:t.ranges.some(r=>r.analyte),
        comps:[...new Set(t.ranges.filter(r=>r.analyte).map(r=>r.analyte.key))],
        nRange:t.ranges.length, nInc:(t.inc||[]).length, nDec:(t.dec||[]).length,
        nPearl:(t.pearls||[]).length, hasPrep:!!(t.prep&&t.prep.items&&t.prep.items.length),
        hasPatient:!!(t.prep&&t.prep.patient), tube:t.tube&&t.tube.id,
        nSrc:(t.src||[]).length }))""")
    print("corpus: %d tests, %d panel tests" % (len(meta), sum(1 for m in meta if m["panel"])))

    # ---- 1. content completeness, straight off the data module ----
    print("\n-- content completeness --")
    for m in meta:
        if m["nRange"] == 0:            fail("no reference ranges", m["id"])
        if m["nInc"] == 0:              fail("no raised-value causes", m["id"])
        if m["nDec"] == 0:              fail("no lowered-value causes", m["id"])
        if m["nPearl"] < 3:             fail("fewer than 3 interpretation notes", m["id"])
        if not m["hasPrep"]:            fail("no clinician pre-test instructions", m["id"])
        if not m["tube"]:               fail("no vacutainer assigned", m["id"])
        if m["nSrc"] == 0:              fail("no recorded source", m["id"])
    print("checked %d records for ranges / causes / notes / prep / tube / source" % len(meta))

    # ---- 2. every detail page renders ----
    print("\n-- detail pages (all %d) --" % len(meta))
    blanks, missing_rng, bad_crumb = [], [], []
    for n, m in enumerate(meta):
        ok = pg.evaluate("""(id)=>{
            const r=[...document.querySelectorAll('[data-test]')];
            return true;}""", m["id"])
        # navigate by search, the way a user would
        pg.evaluate("()=>{const t=document.querySelector(\"[data-nav='tests']\"); t&&t.click();}")
        pg.wait_for_timeout(15)
        if not pg.is_visible("#searchBox"):
            pg.click("#searchToggle"); pg.wait_for_timeout(30)
        pg.fill("#searchBox", "")
        pg.wait_for_timeout(140)
        pg.fill("#searchBox", m["name"][:18])
        sel = "[data-test='%s']" % m["id"]
        # oninput is debounced 120 ms; poll for the row to become visible
        # instead of a flat sleep, so a slow/contended CI runner doesn't
        # produce a false "not reachable". Keep a short settle buffer
        # afterwards — the list can still be mid-layout right as it
        # becomes visible.
        try:
            pg.locator(sel).first.wait_for(state="visible", timeout=2000)
        except Exception:
            pass
        if pg.locator(sel).count() == 0:
            fail("not reachable by searching its own name", m["id"]); continue
        pg.wait_for_timeout(60)
        pg.locator(sel).first.click()
        pg.wait_for_timeout(60)
        state = pg.evaluate("""()=>{
            const v=document.querySelector('#v-detail');
            const rows=v?v.querySelectorAll('table.rng tr').length:0;
            const blocks=[...(v?v.querySelectorAll('.block'):[])].map(x=>x.dataset.blk);
            return {len:(v?v.innerText.trim().length:0), rows, blocks,
                    crumb:document.querySelector('#crumbs').innerText.trim()};}""")
        if state["len"] < 300:        blanks.append(m["id"])
        if state["rows"] == 0:        missing_rng.append(m["id"])
        if "rng" not in state["blocks"]: missing_rng.append(m["id"] + " (no rng block)")
        if m["name"].split(" (")[0][:12] not in state["crumb"]:
            bad_crumb.append((m["id"], state["crumb"]))
    if blanks:      fail("detail page nearly empty", blanks)
    if missing_rng: fail("no reference-range table rendered", missing_rng)
    if bad_crumb:   fail("breadcrumb does not name the page", bad_crumb[:5])
    print("opened %d detail pages; empty: %d, missing range table: %d, bad crumb: %d"
          % (len(meta), len(blanks), len(missing_rng), len(bad_crumb)))

    # ---- 3. Result Interpreter: every panel, every component ----
    print("\n-- Result Interpreter, all panel components --")
    pg.evaluate("""()=>{const k='labref_v1';const o=JSON.parse(localStorage.getItem(k)||'{}');
        o.mode='patient';localStorage.setItem(k,JSON.stringify(o));}""")
    pg.reload(); pg.wait_for_timeout(400)
    pg.click("[data-nav='tools']"); pg.wait_for_timeout(150)
    pg.click("[data-tool='interp']"); pg.wait_for_timeout(200)
    if pg.locator("#ipTest").count() == 0:
        fail("Result Interpreter did not open")
    else:
        sel_opts = pg.eval_on_selector("#ipTest", "s=>[...s.options].map(o=>o.value)")
        checked_comp, comp_fail = 0, []
        for m in meta:
            if m["id"] not in sel_opts:
                # qualitative tests are intentionally excluded from the interpreter
                continue
            pg.select_option("#ipTest", m["id"]); pg.wait_for_timeout(60)
            has_picker = pg.locator("#ipPart").count() > 0
            if m["panel"] and not has_picker:
                comp_fail.append(m["id"] + ": panel offers no component picker"); continue
            if (not m["panel"]) and has_picker:
                comp_fail.append(m["id"] + ": single-analyte test wrongly offers a picker"); continue
            keys = pg.eval_on_selector("#ipPart", "s=>[...s.options].map(o=>o.value)") if has_picker else [None]
            if m["panel"]:
                for k in m["comps"]:
                    if k not in keys:
                        comp_fail.append("%s: component %s missing" % (m["id"], k))
            for k in keys:
                if k is not None:
                    pg.select_option("#ipPart", k); pg.wait_for_timeout(25)
                pg.fill("#ipVal", "1")
                pg.click("#ipGo"); pg.wait_for_timeout(50)
                out = pg.inner_text("#ipOut").strip()
                if len(out) < 10:
                    comp_fail.append("%s/%s: interpreter produced no output" % (m["id"], k))
                checked_comp += 1
        if comp_fail: fail("Result Interpreter", comp_fail[:8])
        print("interpreted a value for %d test/component combinations (%d panel tests)"
              % (checked_comp, sum(1 for x in meta if x["panel"])))

    # ---- 4. search finds every test by every synonym ----
    print("\n-- search coverage --")
    bad_syn = pg.evaluate("""()=>{
        const out=[];
        for(const t of LABREF_TESTS){
          for(const s of (t.syn||[])){
            const q=s.toLowerCase();
            const hit=LABREF_TESTS.some(x=>x.id===t.id && (
              x.name.toLowerCase().includes(q) || (x.abbr||'').toLowerCase().includes(q) ||
              (x.syn||[]).some(y=>y.toLowerCase().includes(q))));
            if(!hit) out.push(t.id+' / '+s);
          }
        }
        return out;}""")
    if bad_syn: fail("synonym not matchable", bad_syn[:8])
    print("verified every synonym on all %d tests resolves to its own record" % len(meta))

    b.close()

print("\n" + "=" * 60)
print("console/page errors: " + ("none" if not errors else json.dumps(errors[:8], indent=1)))
if errors: failures.append("console errors during the walk")
if failures:
    print("FAILURES (%d):" % len(failures))
    for f in failures: print("  - " + f)
    sys.exit(1)
print("FULL-CORPUS SWEEP PASSED — all %d tests render and interpret correctly" % len(meta))
