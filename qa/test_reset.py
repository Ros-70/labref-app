"""
LabRef reset / stored-state robustness suite (test method 1 family)

Added after two bugs were reported from the installed APK:

  1. "Reset all settings and local values" raised the WebView's own
     confirm() chrome — 'The page at "https://appassets.androidplatform.net"
     says:' above the message. Correct for a web page, wrong for something
     presented as an offline app, and alarming on a destructive action.
  2. Accepting that dialog did nothing: every saved My Lab value was still
     there afterwards.

(2) was a shallow-copy defect. `Object.assign({}, defaults)` copied the
reference to defaults.local / defaults.panels / defaults.picker rather than
the objects, and those are mutated in place (S.local[id]=…), so defaults
itself accumulated the user's data — and reset rebuilt S from defaults,
handing the same polluted objects straight back.

Chasing that exposed three more failures of the same class, all reachable
through the app's own Restore button: a backup holding {"local":null} or
{"favs":null} threw on the first lookup and left the Tests tab permanently
blank, and a patient mode outside the known values matched NO range row at
all — the test page opened with an empty reference table and no error.

Run: python3 -I qa/test_reset.py
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
    return shutil.which("google-chrome") or shutil.which("chromium")

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
errors, failures, native_dialogs = [], [], []

def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + (("  -> " + str(detail)) if detail else ""))
    if not cond:
        failures.append(label + (("  -> " + str(detail)) if detail else ""))

def stored(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem('labref_v1')||'{}')")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=_chrome_path(), args=["--no-sandbox"], headless=True)
    pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("console", lambda m: errors.append((m.type, m.text)) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(("pageerror", str(e))))
    # A native dialog anywhere in this suite is itself the reported bug.
    pg.on("dialog", lambda d: (native_dialogs.append((d.type, d.message)), d.accept()))

    def goto_test(tid, cat):
        pg.click("[data-nav='tests']"); pg.wait_for_timeout(120)
        pg.click("[data-cat='%s']" % cat); pg.wait_for_timeout(150)
        pg.click("[data-test='%s']" % tid); pg.wait_for_timeout(200)

    def dirty_everything():
        """Put something in every container the reset is supposed to clear,
        through the real UI, from a FRESH page load -- the state in which the
        original defect reproduced (nothing in storage at load time, so S's
        containers were the very objects inside `defaults`)."""
        goto_test("hb", "rbc")
        pg.click("[data-blk='loc'] .bh"); pg.wait_for_timeout(120)
        blk = pg.query_selector_all(".mylab-rid")[0]
        blk.query_selector(".lc-lo").fill("11.1")
        blk.query_selector(".lc-hi").fill("22.2")
        pg.query_selector("#lcNote").fill("send-out after 6pm")
        pg.click("#lcSave"); pg.wait_for_timeout(200)
        pg.click("#favBtn"); pg.wait_for_timeout(150)      # a favourite
        pg.click("#addPick"); pg.wait_for_timeout(150)     # a picker entry
        pg.click("[data-nav='more']"); pg.wait_for_timeout(180)
        pg.click("[data-th='dark']"); pg.wait_for_timeout(180)   # a theme
        pg.click("[data-un='si']"); pg.wait_for_timeout(180)     # a unit choice

    # =========================================================
    print("\n-- 1. the reported bug: reset must actually erase --")
    pg.goto(URL); pg.wait_for_timeout(400)
    pg.evaluate("()=>localStorage.clear()")
    pg.reload(); pg.wait_for_timeout(400)

    dirty_everything()
    before = stored(pg)
    check("setup: a lab value was saved", bool(before.get("local", {}).get("hb")), before.get("local"))
    check("setup: a favourite was saved", before.get("favs") == ["hb"], before.get("favs"))
    check("setup: a picker entry was saved", before.get("picker") == ["hb"], before.get("picker"))
    check("setup: theme and units changed",
          before.get("theme") == "dark" and before.get("units") == "si",
          (before.get("theme"), before.get("units")))

    pg.click("#bkReset"); pg.wait_for_timeout(250)
    check("reset raises the in-app dialog, not the WebView's", pg.is_visible("#dlgWrap"))
    check("no native dialog was used", native_dialogs == [], native_dialogs)
    dlg_text = pg.inner_text("#dlg")
    check("the dialog does not leak the asset origin at the user",
          "appassets" not in dlg_text and "The page at" not in dlg_text, dlg_text[:80])
    check("the dialog names the destructive action on its own button",
          "Erase" in pg.inner_text("#dlgOk"), pg.inner_text("#dlgOk"))

    pg.click("#dlgOk"); pg.wait_for_timeout(300)
    after = stored(pg)
    check("local lab values are gone", after.get("local") == {}, after.get("local"))
    check("favourites are gone", after.get("favs") == [], after.get("favs"))
    check("picker is gone", after.get("picker") == [], after.get("picker"))
    check("theme is back to default", after.get("theme") == "light", after.get("theme"))
    check("units are back to default", after.get("units") == "conv", after.get("units"))
    check("the user is told the reset happened",
          "Reset complete" in pg.inner_text("#dlgTitle"), pg.inner_text("#dlgTitle"))
    pg.click("#dlgOk"); pg.wait_for_timeout(150)

    # The in-memory object and the stored blob must agree -- the original bug
    # would also have been missed by checking only one of them.
    pg.reload(); pg.wait_for_timeout(400)
    after_reload = stored(pg)
    check("the erase survives a reload", after_reload.get("local") == {}, after_reload.get("local"))
    pg.click("[data-nav='mylab']"); pg.wait_for_timeout(250)
    check("My Lab shows nothing saved",
          "No local values saved yet" in pg.inner_text("#v-mylab"),
          pg.inner_text("#v-mylab")[:90])

    # =========================================================
    print("\n-- 2. cancelling must change nothing --")
    pg.evaluate("()=>localStorage.clear()")
    pg.reload(); pg.wait_for_timeout(400)
    dirty_everything()
    pg.click("#bkReset"); pg.wait_for_timeout(250)
    pg.click("#dlgCancel"); pg.wait_for_timeout(250)
    kept = stored(pg)
    check("cancel keeps the saved lab value", bool(kept.get("local", {}).get("hb")), kept.get("local"))
    check("cancel keeps the favourite", kept.get("favs") == ["hb"], kept.get("favs"))
    check("cancel closes the dialog", not pg.is_visible("#dlgWrap"))

    # Escape key and a backdrop tap are cancels too, not silent confirms --
    # on a destructive action the default must never be "yes".
    pg.click("#bkReset"); pg.wait_for_timeout(200)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
    check("Escape cancels rather than erasing",
          bool(stored(pg).get("local", {}).get("hb")) and not pg.is_visible("#dlgWrap"))

    # =========================================================
    print("\n-- 3. an explicit erase clears the pre-rename copy too --")
    pg.evaluate("""()=>{
        localStorage.setItem('medref_v1', JSON.stringify({local:{hb:{note:'',assay:{},byRid:{r1:{lo:'9',hi:'9'}}}}}));
    }""")
    pg.click("[data-nav='more']"); pg.wait_for_timeout(200)
    pg.click("#bkReset"); pg.wait_for_timeout(200)
    pg.click("#dlgOk"); pg.wait_for_timeout(250)
    pg.click("#dlgOk"); pg.wait_for_timeout(150)
    check("the legacy medref_v1 copy is erased as well",
          pg.evaluate("()=>localStorage.getItem('medref_v1')") is None)

    # =========================================================
    print("\n-- 4. malformed stored state must not brick or blank the app --")
    # Each of these is reachable through the app's own Restore button, since a
    # backup file is just user-supplied JSON.
    for blob, label in [
        ('{"local":null}',  "a null local store"),
        ('{"favs":null}',   "a null favourites list"),
        ('{"panels":null}', "a null panels map"),
        ('{"picker":null}', "a null picker list"),
        ('{"preg":"BOGUS","age":"zzz","sex":"?"}', "an unknown patient mode"),
        ('{"theme":"nope","fs":"big","units":"furlongs"}', "unknown appearance values"),
        ('{"local":{"hb":null}}', "a null entry inside the local store"),
    ]:
        before_errs = len(errors)
        pg.evaluate("b=>localStorage.setItem('labref_v1',b)", blob)
        pg.reload(); pg.wait_for_timeout(350)
        try:
            goto_test("hb", "rbc")
            n = pg.locator("#v-detail tr.match .grp").count()
            match = pg.locator("#v-detail tr.match .grp").first.inner_text() if n else "NO ROW MATCHED"
        except Exception as ex:
            match = "UNUSABLE: " + str(ex)[:50]
        check("%s recovers and still matches a range" % label,
              match == "Adult male" and len(errors) == before_errs,
              "%s | new console output: %s" % (match, errors[before_errs:][:1]))

    # =========================================================
    print("\n-- 4b. a test's own 'Clear all' asks before discarding values --")
    pg.evaluate("()=>localStorage.clear()")
    pg.reload(); pg.wait_for_timeout(400)
    def open_mylab():
        """The detail page's blocks reset to their defaults on every render,
        and 'Your lab's values' defaults to collapsed -- so it has to be
        reopened after each save/clear, which themselves re-render."""
        if "open" not in (pg.get_attribute("[data-blk='loc']", "class") or ""):
            pg.click("[data-blk='loc'] .bh"); pg.wait_for_timeout(150)

    goto_test("hb", "rbc")
    open_mylab()
    blk = pg.query_selector_all(".mylab-rid")[0]
    blk.query_selector(".lc-lo").fill("12.3")
    pg.click("#lcSave"); pg.wait_for_timeout(200)
    check("setup: a value is saved for hb", bool(stored(pg).get("local", {}).get("hb")))
    open_mylab()
    pg.click("#lcClear"); pg.wait_for_timeout(200)
    check("Clear all asks first instead of wiping on the tap", pg.is_visible("#dlgWrap"))
    check("the question names the test being cleared",
          "Haemoglobin" in pg.inner_text("#dlgTitle"), pg.inner_text("#dlgTitle"))
    pg.click("#dlgCancel"); pg.wait_for_timeout(200)
    check("cancelling Clear all keeps the value",
          bool(stored(pg).get("local", {}).get("hb")), stored(pg).get("local"))
    open_mylab()
    pg.click("#lcClear"); pg.wait_for_timeout(200)
    pg.click("#dlgOk"); pg.wait_for_timeout(250)
    check("confirming Clear all removes just that test",
          stored(pg).get("local", {}).get("hb") is None, stored(pg).get("local"))
    # with nothing saved there is nothing to lose, so it must not nag
    open_mylab()
    pg.click("#lcClear"); pg.wait_for_timeout(200)
    check("Clear all does not ask when the test has nothing saved",
          not pg.is_visible("#dlgWrap"))

    # =========================================================
    print("\n-- 5. backup round-trip still works --")
    pg.evaluate("()=>localStorage.clear()")
    pg.reload(); pg.wait_for_timeout(400)
    dirty_everything()
    backup = pg.evaluate("()=>JSON.stringify(Object.assign({type:'labref-backup'},JSON.parse(localStorage.getItem('labref_v1'))))")
    pg.click("#bkReset"); pg.wait_for_timeout(200)
    pg.click("#dlgOk"); pg.wait_for_timeout(250)
    pg.click("#dlgOk"); pg.wait_for_timeout(150)
    check("erased before restoring", stored(pg).get("local") == {})
    # restore through the real file input
    pg.set_input_files("#bkFile", {"name": "labref-backup.json", "mimeType": "application/json",
                                   "buffer": backup.encode()})
    pg.wait_for_timeout(400)
    restored = stored(pg)
    check("restore brings the lab value back", bool(restored.get("local", {}).get("hb")), restored.get("local"))
    check("restore reports success in-app, not natively",
          "Backup restored" in pg.inner_text("#dlgTitle") and native_dialogs == [],
          (pg.inner_text("#dlgTitle"), native_dialogs))
    pg.click("#dlgOk"); pg.wait_for_timeout(150)

    # a backup that would previously have bricked the app
    pg.set_input_files("#bkFile", {"name": "bad.json", "mimeType": "application/json",
                                   "buffer": b'{"type":"labref-backup","local":null,"favs":null,"preg":"X"}'})
    pg.wait_for_timeout(400)
    pg.click("#dlgOk"); pg.wait_for_timeout(200)
    before_errs = len(errors)
    goto_test("hb", "rbc")
    n = pg.locator("#v-detail tr.match .grp").count()
    check("restoring a malformed backup leaves a usable app",
          n and pg.locator("#v-detail tr.match .grp").first.inner_text() == "Adult male"
          and len(errors) == before_errs,
          errors[before_errs:][:1])

    # a file that is not a backup at all
    pg.set_input_files("#bkFile", {"name": "notes.json", "mimeType": "application/json",
                                   "buffer": b'{"hello":"world"}'})
    pg.wait_for_timeout(350)
    check("a non-backup file is refused in-app",
          "Restore failed" in pg.inner_text("#dlgTitle") and native_dialogs == [],
          pg.inner_text("#dlgTitle"))
    pg.click("#dlgOk"); pg.wait_for_timeout(150)

    b.close()

print("\n" + "=" * 60)
print("native dialogs raised anywhere in this suite: "
      + ("none" if not native_dialogs else json.dumps(native_dialogs)))
if native_dialogs:
    failures.append("the app raised a native WebView dialog")
print("console/page errors: " + ("none" if not errors else json.dumps(errors[:6], indent=1)))
if errors:
    failures.append("console errors during the run")
if failures:
    print("FAILURES (%d):" % len(failures))
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("RESET AND STORED-STATE SUITE PASSED")
