# Extension Guide — adding or amending a test

*All 180 planned tests are populated as of v1.10. This guide is now a
maintenance document: use it when adding a test beyond the planned corpus,
correcting a record, or revising a range after a guideline change.*

The schema is frozen and validated (SCHEMA.md). This document is the
practical workflow for turning research into correctly-shaped records at
volume, without re-deriving design decisions that are already settled.

## 1. Before adding any test

1. Check `LABREF_CATEGORIES` in `app/labref_data_v1.10.js` — the category
   almost certainly already exists. 9 of the 26 defined categories
   currently have zero populated tests and are first in line: Cancer
   Markers, Cerebrospinal Fluid, Toxicology, Bone & Mineral, Stool,
   Antenatal & Fertility, Allergy, Blood Bank (see KNOWN_GAPS.md for the
   full priority list).
2. Check `LABREF_TUBES` — the physical tube almost certainly already
   exists. Only add a new tube entry for a genuinely distinct collection
   method (a new tube colour/additive combination), never one per test.
3. Decide: **is this a panel?** A test is a panel only if it bundles more
   than one real, separately-reported analyte under one clinical order
   (see SCHEMA.md §2b for the exact rule and the decision each of the six
   existing panels made). Most new tests are not panels — when in doubt,
   it almost certainly isn't one; a panel adds real UI and storage
   complexity and should only be used when the lab genuinely reports
   multiple independent numbers under one order.

## 2. Research standard

Carry forward the standard used for all 180 existing records:
CLSI/WHO/ADA/NKF-KDIGO/ACC-AHA/ATS-ERS-class guideline bodies, major
reference laboratories' published intervals (Mayo, ARUP), peer-reviewed
primary literature for anything with a specific numeric claim (a formula,
a cutoff, an interference mechanism), and FDA safety communications for
interference warnings. See SOURCES.md for how to cite a specific claim and
the known gap in the current citation trail that needs resolving first.

Every numeric claim that isn't common knowledge in laboratory medicine
(a specific cutoff, a named formula, an interference mechanism, a
guideline recommendation) should be traceable to a specific source at the
time it's written — don't write it now and plan to find the citation
later; that's how the current 12-marker gap happened.

## 3. Field-by-field checklist for a new test

Work through this top to bottom; it mirrors the order fields appear in
every existing record so a reviewer can scan new entries consistently.

- [ ] `id` — lowercase, no spaces or punctuation, short enough to type in
      search (`creatinine`, not `serum_creatinine_level`)
- [ ] `name`, `abbr` — abbr is what's shown in list rows; keep it to what a
      clinician would actually write on a form
- [ ] `syn[]` — include every Indian clinical shorthand a clinician might
      search (KFT/LFT/TLC-style abbreviations, common misspellings, the
      colloquial name)
- [ ] `cat` — existing category id (see §1)
- [ ] `specimen`, `tube` — tube.id from `LABREF_TUBES`; vol and handling
      specific to this test, not copy-pasted generically
- [ ] `prep.items[]` — clinician/collection-staff instructions
- [ ] `prep.patient[]` — **only** if the patient must actually do
      something (fast, hold a drug, time the sample); plain language; omit
      the field entirely otherwise. Never let a clinician-only instruction
      (drug-interaction notes, "discard dead-space volume") leak in here —
      it feeds the printable patient handout directly.
- [ ] `assayDep` — `true` if different analysers/methods give materially
      different cutoffs for this test (most immunoassays: troponin, NT-
      proBNP, thyroid tests, tumour markers; most chemistry-analyser tests:
      `false`)
- [ ] `units` — conv/si pair + factor; verify the factor per UNIT_CONVERSIONS.md
      §2 before moving on, not after
- [ ] `ranges[]` — one row per sex/age/pregnancy variant that actually
      differs; if adult male and adult female share one range, use a
      single `sex:"any"` row rather than two identical rows
- [ ] `critical` — `null` if the test has no recognised critical/panic
      value; otherwise `{txt, lo, hi}`
- [ ] `inc[]`, `dec[]` — causes, ordered roughly by clinical frequency/
      relevance, not alphabetically
- [ ] `interf[]` — analytical interferences (pre-analytical and assay-
      specific)
- [ ] `pearls[]` — the two or three things a resident actually needs to
      know to not misinterpret this result
- [ ] `rel[]` — test ids a clinician would reasonably want to see data for
      alongside this one

## 4. Adding a panel test — worked walkthrough

Say you're adding a Thyroid Panel that reports TSH, Free T4, and Free T3
as one order (a hypothetical — TSH, FT4, FT3 are separate test records in
the current data, but this illustrates the pattern on a familiar example).

1. Confirm it's genuinely a panel: yes — three separately-reported,
   independently-interpreted numbers under one clinical order.
2. Pick stable `analyte.key` values: `"tsh"`, `"ft4"`, `"ft3"`.
3. Write each component's range rows with its own `analyte:{key,label}`,
   and its own `factor`/`convUnit`/`siUnit` wherever it differs from
   whatever you set as the panel-level `units` default.
4. If any row is a patient-mode note rather than another component (e.g.
   "in pregnancy, interpret FT4 against trimester-specific intervals — see
   note"), leave it **without** an `analyte` tag so it renders in the
   panel's "Also note" section instead of being offered as a selectable
   component.
5. If there's a panel-wide critical value that only applies to one
   component (not all three), add `critical.analyte:["key"]` restricting
   it — see SCHEMA.md §2b and the Lipid Profile triglycerides example.
6. Run the UNIT_CONVERSIONS.md §2 verification script before building.
7. Build (`python3 -I build.py`) and open the test's detail page — you
   should see one sub-table per component, one My Lab override box per
   component, and the Result Interpreter should offer a component picker
   when you select this test.
8. Add a case to `qa/test5.py`'s matrix if the new panel has a tricky
   patient-mode-matching scenario worth locking in permanently (see
   QA.md).

## 5. The build-and-verify loop

Don't batch 50 tests and then build once — the cost of catching a schema
mistake in record #3 is much lower than catching the same mistake repeated
across 50 records.

```
1. Write/edit records in app/labref_data_v1.10.js
2. Run the UNIT_CONVERSIONS.md §2 factor-verification script
3. cd app && python3 -I build.py
4. Open app/LabRef_v1.10.html, spot-check the new test(s) in the browser
5. Run the QA suite (see QA.md) — at minimum test_panel.py if you touched
   a panel test, test5.py always (range matching)
6. Commit
```

## 6. What NOT to do

- Don't invent a new top-level field on a test record. If the schema
  genuinely can't represent something a real test needs, that's a design
  decision — flag it rather than improvising a field name, since the UI
  code won't read a field it doesn't know about and the content will
  silently not render.
- Don't collapse two real, differently-reported analytes into one range
  table "because they're usually similar" — that's exactly the Lipid
  Profile bug this prototype phase fixed.
- Don't write a `factor` from a general conversion table without checking
  it against this specific analyte's molar mass / assay convention — see
  UNIT_CONVERSIONS.md §1 for why a wrong factor is a silent failure mode.
- Don't add a `patient[]` instruction that wasn't in `items[]` first in
  substance — the two arrays describe the same preparation to two
  different audiences, they shouldn't diverge in content, only in
  language and level of detail.
