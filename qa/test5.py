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
    pg.on("pageerror",lambda e: errors.append("PAGEERROR: "+str(e)))
    pg.on("console",lambda m: errors.append(m.text) if m.type=="error" else None)
    pg.goto(PATH)

    cases=[("ddimer","coag","M","none","adult","Adult (<50 y) exclusion cutoff"),
           ("ddimer","coag","F","T3","adult","Pregnancy T3"),
           ("ddimer","coag","F","T1","adult","Pregnancy T1"),
           ("hb","rbc","F","T2","adult","Pregnancy T2"),
           ("hb","rbc","F","none","adult","Adult female"),
           ("hb","rbc","M","none","neonate","Newborn (0–3 d)"),
           ("hb","rbc","M","none","child","Child (2–12 y)"),
           ("hb","rbc","F","none","adolescent","Adolescent (12–18)"),
           ("alp","enz","M","none","child","Child (2–9 y)"),
           ("alp","enz","F","none","adolescent","Adolescent female (10–15 y)"),
           ("alp","enz","F","T3","adult","Pregnancy T3"),
           ("tsh","horm","F","T1","adult","Pregnancy T1"),
           ("tsh","horm","M","none","neonate","Newborn (0–4 d)"),
           ("creatinine","elec","F","none","adult","Adult female"),
           ("creatinine","elec","M","none","adult","Adult male"),
           ("creatinine","elec","F","T2","adult","Pregnancy"),
           ("ferritin","ions","F","none","adult","Adult female"),
           ("ferritin","ions","M","none","adult","Adult male"),
           ("bilirubin","liver","M","none","neonate","Newborn 24 h (total)"),
           ("platelet","coag","F","T3","adult","Pregnancy"),
           ("tlc","wbc","F","T2","adult","Pregnancy"),
           ("alt","enz","F","none","adult","Adult female"),
           ("potassium","elec","M","none","child","Child"),
           ("abgpanel","abg","F","T3","adult","Pregnancy (compensated resp alkalosis)")]
    # Panel tests (lipid, abgpanel, ptinr, troponin, bilirubin, calcium) now render
    # one reference-range sub-table PER bundled component, each with its own
    # independently-highlighted "match" row -- so a page-wide tr.match count is no
    # longer 1 for these. For a panel test, scope the lookup to the specific
    # component sub-table (".rng-sub") that contains the expected group label.
    panel_tests = {"lipid","abgpanel","ptinr","troponin","bilirubin","calcium"}
    # Rows the interpreter now correctly refuses to silently pick between
    # (see qa/known_tie_groups.json) highlight as MULTIPLE "match" rows on
    # the detail page on purpose — ddimer's <50y exclusion cutoff and the
    # age-adjusted (>50y) cutoff both match "adult, any sex" alone, and only
    # the clinician knows which one actually fits. Exempt these from the
    # n==1 assumption the same way panel tests already are.
    tie_tests = {"ddimer"}
    ok=True
    for tid,cat,sex,preg,age,expect in cases:
        pg.evaluate("""([s,p,a])=>{const k='labref_v1';const o=JSON.parse(localStorage.getItem(k)||'{}');
            o.sex=s;o.preg=p;o.age=a;o.units='conv';localStorage.setItem(k,JSON.stringify(o));}""",[sex,preg,age])
        pg.goto(PATH); pg.wait_for_timeout(350)
        pg.locator(f"[data-cat='{cat}']").click(); pg.wait_for_timeout(180)
        pg.locator(f"[data-test='{tid}']").click(); pg.wait_for_timeout(280)
        if tid in panel_tests:
            # find the .rng-sub section whose table contains a row with the
            # expected grp text, then check match status within that section only
            subs = pg.locator("#v-detail .rng-sub")
            n = 0; got = "NONE"
            for i in range(subs.count()):
                sub = subs.nth(i)
                row = sub.locator("tr", has=pg.locator(".grp", has_text=expect))
                if row.count():
                    n = sub.locator("tr.match").count()
                    matched_row = sub.locator("tr.match .grp")
                    got = matched_row.first.inner_text() if matched_row.count() else "NO MATCH IN SECTION"
                    break
        else:
            n=pg.locator("#v-detail tr.match").count()
            got=pg.locator("#v-detail tr.match .grp").first.inner_text() if n else "NONE"
        good=(got==expect and (n==1 if tid not in panel_tests and tid not in tie_tests else got==expect)); ok=ok and good
        print(("PASS " if good else "FAIL "),f"{tid:11s} {sex} {preg:4s} {age:11s} -> {got!r} rows={n}")
        if not good: print("        expected:",repr(expect))
    print("\nRANGE SELECTION:", "ALL PASS" if ok else "FAILURES ABOVE")
    b.close()
print("ERRORS:", errors if errors else "none")
