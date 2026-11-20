"""
LabRef Stage 3/4 override-isolation sweep (test method 1 family)

Stage 3 re-keyed My Lab overrides from "one value per component" to "one
value per (test id, rid)" specifically to stop a saved value from bleeding
across demographic strata (CHANGELOG's "The defect": a saved adult male
haemoglobin range silently became the newborn range too). test_panel.py
proved that fix on ONE hand-picked case (HDL's two rows). This file sweeps
the property across every overridable row in the entire corpus, and also
reproduces the ORIGINAL defect scenario end-to-end on a live patient-mode
switch, not just in storage.

Part A — full-corpus isolation & coverage sweep. Every overridable row on
every test gets its own distinct sentinel value, written once via
localStorage before a single page load (so no per-test reload is needed).
For every test, the My Lab block is opened and every rendered row's value
is checked against its own sentinel -- confirming (a) nothing is missing
(every overridable row got an input) and (b) nothing bled (no row shows a
sentinel that belongs to a different row).

Part B — the original defect, reproduced and refuted on a live profile
switch. Save Haemoglobin's "Adult male" row, switch the active patient
profile to Newborn, and confirm the detail page shows the textbook newborn
range, not the saved adult value -- then switch back and confirm the
override IS shown for Adult male. This is the exact before/after the
CHANGELOG describes, run against the shipped build rather than asserted
only against stored JSON.

Run: python3 -I qa/test_override_sweep.py
"""
import sys, json
from playwright.sync_api import sync_playwright

import os as _os

def _chrome_path():
    import os, shutil
    p = os.environ.get("CHROME_PATH")
    if p and os.path.exists(p):
        return p
    for c in ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"):
        if os.path.exists(c):
            return c
    found = shutil.which("google-chrome") or shutil.which("chromium")
    return found

def _labref_html():
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

URL = _labref_html()
errors, failures = [], []

def fail(label, detail=""):
    failures.append(label + (("  -> " + str(detail)) if detail else ""))

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=_chrome_path(), args=["--no-sandbox"], headless=True)
    pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("console", lambda m: errors.append((m.type, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    pg.goto(URL); pg.wait_for_timeout(400)

    # ============================================================
    # Part A — full-corpus isolation & coverage sweep
    # ============================================================
    print("-- Part A: My Lab isolation sweep, every overridable row in the corpus --")

    expected = pg.evaluate("""()=>{
        /* Mirrors overridableKind() in shell.html -- the gate deciding which
           rows may ever carry a saved override. Reimplemented here only to
           pick WHICH rids to plant sentinels on; the thing actually being
           tested is whether the REAL app (via the My Lab block it renders)
           shows each sentinel on the right row and nowhere else. */
        function overridableKind(r, t){
            return r.kind==="ref" || r.kind==="method" || r.kind==null
                 || (r.kind==="cutoff" && !!t.assayDep);
        }
        const local = {}, expected = {};
        let n = 1;
        LABREF_TESTS.forEach(t=>{
            const rows = t.ranges.filter(r=>overridableKind(r,t));
            if(!rows.length) return;
            const byRid = {}, exp = [];
            rows.forEach(r=>{
                const lo = String(100000+n), hi = String(100000+n+1); n += 2;
                byRid[r.rid] = { lo, hi };
                exp.push({ rid:r.rid, lo, hi });
            });
            local[t.id] = { note:"", assay:{}, byRid };
            expected[t.id] = { name:t.name, rows:exp };
        });
        const key = "labref_v1";
        const o = JSON.parse(localStorage.getItem(key) || "{}");
        o.local = local;
        localStorage.setItem(key, JSON.stringify(o));
        return expected;
    }""")
    pg.reload(); pg.wait_for_timeout(500)

    total_rows_checked = 0
    missing_rows, leaked_rows, wrong_value = [], [], []

    for tid, entry in expected.items():
        rows = entry["rows"]
        pg.evaluate("()=>{const t=document.querySelector(\"[data-nav='tests']\"); t&&t.click();}")
        pg.wait_for_timeout(15)
        if not pg.is_visible("#searchBox"):
            pg.click("#searchToggle"); pg.wait_for_timeout(30)
        pg.fill("#searchBox", "")
        pg.wait_for_timeout(140)
        pg.fill("#searchBox", entry["name"][:18])
        sel = "[data-test='%s']" % tid
        try:
            pg.locator(sel).first.wait_for(state="visible", timeout=2000)
        except Exception:
            pass
        if pg.locator(sel).count() == 0:
            fail("test not reachable during override sweep", tid); continue
        pg.locator(sel).first.click()
        pg.wait_for_timeout(60)
        header = pg.query_selector("[data-blk='loc'] .bh")
        if header and "open" not in (pg.get_attribute("[data-blk='loc']", "class") or ""):
            header.click(); pg.wait_for_timeout(60)

        rendered = pg.eval_on_selector_all(
            ".mylab-rid",
            "els => els.map(e => ({rid: e.dataset.rid, "
            "lo: e.querySelector('.lc-lo').value, hi: e.querySelector('.lc-hi').value}))"
        )
        by_rid = {r["rid"]: r for r in rendered}
        for exp in rows:
            got = by_rid.get(exp["rid"])
            total_rows_checked += 1
            if got is None:
                missing_rows.append("%s/%s" % (tid, exp["rid"])); continue
            if got["lo"] != exp["lo"] or got["hi"] != exp["hi"]:
                wrong_value.append("%s/%s: expected %s-%s, got %s-%s" %
                    (tid, exp["rid"], exp["lo"], exp["hi"], got["lo"], got["hi"]))
        # leakage: any rendered row whose rid isn't in THIS test's expected set
        # can't happen by construction (rendered rows come from this test's own
        # ranges), but a row showing a VALUE that belongs to a different rid
        # on the SAME test is exactly the Stage-3 bug class -- already covered
        # by wrong_value above since each rid's sentinel is globally unique.
        if len(rendered) != len(rows):
            leaked_rows.append("%s: expected %d editable rows, rendered %d" % (tid, len(rows), len(rendered)))

    if missing_rows: fail("override not rendered for an overridable row", missing_rows[:10])
    if wrong_value:  fail("override value cross-contaminated between rows", wrong_value[:10])
    if leaked_rows:  fail("editable-row count mismatch", leaked_rows[:10])
    print("checked %d overridable rows across %d tests; missing: %d, cross-contaminated: %d, count mismatches: %d"
          % (total_rows_checked, len(expected), len(missing_rows), len(wrong_value), len(leaked_rows)))

    # clear every test's local overrides before Part B, so they don't interfere
    pg.evaluate("""()=>{const k='labref_v1';const o=JSON.parse(localStorage.getItem(k)||'{}');
        o.local = {}; localStorage.setItem(k, JSON.stringify(o));}""")

    # ============================================================
    # Part B — the original defect, reproduced and refuted live
    # ============================================================
    print("\n-- Part B: the original defect, end to end (hb, Adult male vs Newborn) --")

    def set_profile(sex, age, preg):
        pg.evaluate("""([s,a,p])=>{const k='labref_v1';const o=JSON.parse(localStorage.getItem(k)||'{}');
            o.sex=s; o.age=a; o.preg=p; o.units='conv'; localStorage.setItem(k, JSON.stringify(o));}""",
            [sex, age, preg])
        pg.goto(URL); pg.wait_for_timeout(350)
        pg.click("[data-cat='rbc']"); pg.wait_for_timeout(150)
        pg.click("[data-test='hb']"); pg.wait_for_timeout(200)

    # 1. As an adult male, save an override on the "Adult male" row.
    set_profile("M", "adult", "none")
    header = pg.query_selector("[data-blk='loc'] .bh")
    if header: header.click(); pg.wait_for_timeout(100)
    male_block = None
    for div in pg.query_selector_all(".mylab-rid"):
        label = div.inner_text()
        if "Adult male" in label:
            male_block = div; break
    if male_block is None:
        fail("hb Adult male override row not found")
    else:
        male_block.query_selector(".lc-lo").fill("20.0")
        male_block.query_selector(".lc-hi").fill("22.0")
        pg.click("#lcSave"); pg.wait_for_timeout(150)
        active_now = pg.locator("#v-detail tr.match .grp").first.inner_text() if pg.locator("#v-detail tr.match").count() else "NONE"
        shown_lo = pg.locator("#v-detail tr.match td").nth(1).inner_text() if pg.locator("#v-detail tr.match").count() else ""
        has_badge = pg.locator("#v-detail tr.match .b-local").count() > 0
        if active_now != "Adult male":
            fail("active range after save is not Adult male", active_now)
        if not has_badge or "20.0" not in shown_lo:
            fail("saved override not reflected in the Adult male active range", shown_lo)
        print("Adult male, after save -> active row: %r, shown: %r" % (active_now, shown_lo))

    # 2. Switch to Newborn. The ORIGINAL bug: this used to silently display
    # the adult override as if it were the newborn range. Confirm it shows
    # the textbook newborn range instead.
    set_profile("M", "neonate", "none")
    active_newborn = pg.locator("#v-detail tr.match .grp").first.inner_text() if pg.locator("#v-detail tr.match").count() else "NONE"
    shown_newborn = pg.locator("#v-detail tr.match td").nth(1).inner_text() if pg.locator("#v-detail tr.match").count() else ""
    is_override_badge = pg.locator("#v-detail tr.match .b-local").count() > 0
    if active_newborn != "Newborn (0–3 d)":
        fail("active range for a newborn is not the newborn row", active_newborn)
    if "20.0" in shown_newborn or "22.0" in shown_newborn:
        fail("THE ORIGINAL DEFECT REPRODUCED: newborn patient shown the adult male override",
             shown_newborn)
    if is_override_badge:
        fail("newborn row wrongly shows a 'your lab' badge — no override exists for this row")
    print("Newborn, same test, no save here -> active row: %r, shown: %r (textbook, as expected)"
          % (active_newborn, shown_newborn))

    # 3. Back to adult male — the override should still be exactly there.
    set_profile("M", "adult", "none")
    active_back = pg.locator("#v-detail tr.match .grp").first.inner_text() if pg.locator("#v-detail tr.match").count() else "NONE"
    shown_back = pg.locator("#v-detail tr.match td").nth(1).inner_text() if pg.locator("#v-detail tr.match").count() else ""
    has_badge_back = pg.locator("#v-detail tr.match .b-local").count() > 0
    if active_back != "Adult male" or not has_badge_back or "20.0" not in shown_back:
        fail("override did not persist on returning to Adult male", (active_back, shown_back))
    print("Back to Adult male -> active row: %r, shown: %r" % (active_back, shown_back))

    # cleanup
    pg.evaluate("""()=>{const k='labref_v1';const o=JSON.parse(localStorage.getItem(k)||'{}');
        o.local = {}; localStorage.setItem(k, JSON.stringify(o));}""")

    b.close()

print("\n" + "=" * 60)
print("console/page errors: " + ("none" if not errors else json.dumps(errors[:8], indent=1)))
if errors: failures.append("console errors during the sweep")
if failures:
    print("FAILURES (%d):" % len(failures))
    for f in failures: print("  - " + f)
    sys.exit(1)
print("OVERRIDE SWEEP PASSED — isolation holds across the full corpus, "
      "and the original defect does not reproduce")
