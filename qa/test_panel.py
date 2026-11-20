import sys, json, time
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

errors = []

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=_chrome_path(), headless=True)
        page = browser.new_page(viewport={"width":390,"height":844})
        page.on("console", lambda msg: errors.append(("console", msg.type, msg.text)) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(("pageerror", str(exc))))

        page.goto(URL)
        page.wait_for_timeout(300)

        def open_test(test_id, name_fragment):
            # go to the tests tab, open search, search, click the matching row --
            # drives the real UI path rather than reaching into closed-over scope
            page.click("[data-nav='tests']")
            page.wait_for_timeout(100)
            if not page.is_visible("#searchBox"):
                page.click("#searchToggle")
                page.wait_for_timeout(150)
            page.fill("#searchBox", name_fragment)
            page.wait_for_timeout(200)
            page.click(f"[data-test='{test_id}']")
            page.wait_for_timeout(250)

        # ---- 1. Lipid Profile detail page ----
        open_test("lipid", "Lipid")
        page.screenshot(path="qa/panel_01_lipid_detail.png", full_page=True)
        html = page.content()
        comp_sections = page.eval_on_selector_all(".rng-sub .comp-h", "els => els.map(e=>e.textContent)")
        print("Lipid range components:", comp_sections)
        assert len(comp_sections) == 5, f"expected 5 lipid components, got {comp_sections}"

        # Check triglycerides conversion factor shown (0.0113) not cholesterol's 0.0259
        # -- scope to the rendered .rng-sub sections, not full page.content(), since
        # the latter also contains the raw inlined JS data source (which repeats
        # "Triglycerides" as plain object-literal text long before the rendered DOM).
        rng_subs = page.eval_on_selector_all(".rng-sub", "els => els.map(e=>e.textContent)")
        tg_section = next((s for s in rng_subs if s.startswith("Triglycerides")), "")
        has_0113 = "0.0113" in tg_section
        has_wrong_0259 = "0.0259" in tg_section
        print("Triglycerides section mentions 0.0113:", has_0113, "| wrongly mentions 0.0259:", has_wrong_0259)
        assert has_0113 and not has_wrong_0259, f"triglycerides conversion factor wrong: {tg_section}"

        # ---- 2. My Lab block for Lipid shows 5 separate override sub-forms ----
        # the "Your lab's values" block is a collapsible <details>-like block; open it
        mylab_header = page.query_selector("[data-blk='loc'] .bh")
        if mylab_header:
            mylab_header.click()
            page.wait_for_timeout(150)
        mylab_comps = page.eval_on_selector_all(".mylab-comp .comp-h", "els => els.map(e=>e.textContent)")
        print("Lipid My Lab components:", mylab_comps)
        assert len(mylab_comps) == 5, f"expected 5 mylab sub-forms, got {mylab_comps}"
        page.screenshot(path="qa/panel_02_lipid_mylab.png", full_page=True)

        # ---- 3. Save an override for LDL only, verify others unaffected ----
        # find the LDL component block and fill its lo/hi
        ldl_idx = None
        blocks = page.query_selector_all(".mylab-comp")
        for i, b in enumerate(blocks):
            txt = b.query_selector(".comp-h").text_content()
            if "LDL" in txt:
                ldl_idx = i
                break
        assert ldl_idx is not None, "LDL block not found"
        ldl_block = blocks[ldl_idx]
        ldl_block.query_selector(".lc-lo").fill("50")
        ldl_block.query_selector(".lc-hi").fill("110")
        page.click("#lcSave")
        page.wait_for_timeout(200)
        page.screenshot(path="qa/panel_03_lipid_after_save.png", full_page=True)

        local_storage = page.evaluate("localStorage.getItem('labref_v1')")
        state = json.loads(local_storage)
        lipid_local = state.get("local", {}).get("lipid")
        print("lipid local state after LDL save:", lipid_local)
        assert lipid_local is not None
        assert "ldl" in lipid_local.get("comp", {})
        assert lipid_local["comp"]["ldl"]["lo"] == "50"
        other_keys = [k for k in lipid_local.get("comp", {}).keys() if k != "ldl"]
        print("other comp keys present (should be empty):", other_keys)
        assert other_keys == [], f"saving LDL leaked into other components: {other_keys}"

        # dot indicator should show on the lipid row in the list
        open_test("lipid", "Lipid")  # reopen to re-render after save, idempotent

        # ---- 4. ABG Panel ----
        open_test("abgpanel", "ABG")
        page.screenshot(path="qa/panel_04_abg_detail.png", full_page=True)
        abg_comps = page.eval_on_selector_all(".rng-sub .comp-h", "els => els.map(e=>e.textContent)")
        print("ABG components:", abg_comps)
        assert len(abg_comps) >= 6, f"expected >=6 ABG components, got {abg_comps}"

        # ---- 5. PT/INR ----
        open_test("ptinr", "Prothrombin")
        page.screenshot(path="qa/panel_05_ptinr_detail.png", full_page=True)
        ptinr_comps = page.eval_on_selector_all(".rng-sub .comp-h", "els => els.map(e=>e.textContent)")
        print("PT/INR components:", ptinr_comps)
        assert len(ptinr_comps) == 2

        # ---- 6. Troponin ----
        open_test("troponin", "Troponin")
        page.screenshot(path="qa/panel_06_troponin_detail.png", full_page=True)
        tn_comps = page.eval_on_selector_all(".rng-sub .comp-h", "els => els.map(e=>e.textContent)")
        print("Troponin components:", tn_comps)
        assert len(tn_comps) == 2

        # ---- 7. Bilirubin ----
        open_test("bilirubin", "Bilirubin")
        page.screenshot(path="qa/panel_07_bilirubin_detail.png", full_page=True)
        bili_comps = page.eval_on_selector_all(".rng-sub .comp-h", "els => els.map(e=>e.textContent)")
        print("Bilirubin components:", bili_comps)
        assert len(bili_comps) == 2

        # ---- 8. Calcium ----
        open_test("calcium", "Calcium")
        page.screenshot(path="qa/panel_08_calcium_detail.png", full_page=True)
        ca_comps = page.eval_on_selector_all(".rng-sub .comp-h", "els => els.map(e=>e.textContent)")
        print("Calcium components:", ca_comps)
        assert len(ca_comps) == 2

        # ---- 9. Result Interpreter: panel test shows component selector ----
        page.click("[data-nav='tools']")
        page.wait_for_timeout(150)
        page.click("[data-tool='interp']")
        page.wait_for_timeout(200)
        page.select_option("#ipTest", "lipid")
        page.wait_for_timeout(150)
        page.screenshot(path="qa/panel_09_interp_lipid_selector.png", full_page=True)
        comp_select = page.query_selector("#ipPart")
        assert comp_select is not None, "component selector did not appear for panel test"
        opts = page.eval_on_selector_all("#ipPart option", "els => els.map(e=>e.textContent)")
        print("Interpreter component options:", opts)
        assert len(opts) == 5

        # choose HDL, enter a low value, interpret
        page.select_option("#ipPart", label=[o for o in opts if "HDL" in o][0])
        page.fill("#ipVal", "30")
        page.click("#ipGo")
        page.wait_for_timeout(200)
        page.screenshot(path="qa/panel_10_interp_hdl_result.png", full_page=True)
        out_text = page.inner_text("#ipOut")
        print("Interpreter output (HDL):", out_text[:300])
        assert "HDL" in out_text or "Below" in out_text or "BELOW" in out_text

        # ---- 10. Result Interpreter: non-panel test still works (no selector) ----
        page.select_option("#ipTest", "")
        page.wait_for_timeout(100)
        page.select_option("#ipTest", "ptinr")  # this IS a panel -- test one that's not. use 'creatinine'
        page.wait_for_timeout(100)
        page.select_option("#ipTest", "creatinine")
        page.wait_for_timeout(150)
        comp_select2 = page.query_selector("#ipPart")
        print("Component selector for non-panel test (should be None):", comp_select2)
        assert comp_select2 is None
        page.fill("#ipVal", "1.0")
        page.click("#ipGo")
        page.wait_for_timeout(200)
        page.screenshot(path="qa/panel_11_interp_creatinine.png", full_page=True)

        # ---- 11. Troponin critical value via compOverride (nested storage) ----
        open_test("troponin", "Troponin")
        tn_mylab_header = page.query_selector("[data-blk='loc'] .bh")
        if tn_mylab_header:
            tn_mylab_header.click()
            page.wait_for_timeout(150)
        blocks2 = page.query_selector_all(".mylab-comp")
        tni_block = None
        for b in blocks2:
            txt = b.query_selector(".comp-h").text_content()
            if "cTnI" in txt or "Abbott" in txt:
                tni_block = b
                break
        assert tni_block is not None
        tni_block.query_selector(".lc-crit").fill("Call physician immediately >100")
        page.click("#lcSave")
        page.wait_for_timeout(150)

        page.click("[data-nav='tools']")
        page.wait_for_timeout(150)
        page.click("[data-tool='interp']")
        page.wait_for_timeout(150)
        page.select_option("#ipTest", "troponin")
        page.wait_for_timeout(150)
        opts_tn = page.eval_on_selector_all("#ipPart option", "els => els.map(e=>e.textContent)")
        tni_label = [o for o in opts_tn if "cTnI" in o or "Abbott" in o][0]
        page.select_option("#ipPart", label=tni_label)
        page.fill("#ipVal", "500")
        page.click("#ipGo")
        page.wait_for_timeout(200)
        out2 = page.inner_text("#ipOut")
        print("Interpreter output w/ saved critical value:", out2[:400])
        page.screenshot(path="qa/panel_12_interp_critical.png", full_page=True)
        assert "Call physician" in out2, "critical value from nested storage did not surface in Result Interpreter"

        # cleanup local storage so repeated runs are clean
        page.evaluate("localStorage.removeItem('labref_v1')")

        browser.close()

if __name__ == "__main__":
    run()
    if errors:
        print("\n=== CONSOLE/PAGE ERRORS ===")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("\nALL PANEL TESTS PASSED, NO CONSOLE ERRORS")
