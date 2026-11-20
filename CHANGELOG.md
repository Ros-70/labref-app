# Changelog

## v2.0 — IN DEVELOPMENT (branch `v2-data-model`)

v1.10 remains the shipped, frozen release on `main`. v2.0 exists to fix a
defect found in hands-on use of the v1.10 APK, and is staged so each step is
CI-verified before the next begins.

### The defect

My Lab overrides were stored per analyte with **no demographic scope**, and
`activeRange()` consulted the override *before* the stratum matcher. So one
saved value won in every context: enter your lab's adult haemoglobin range,
switch the age chip to Newborn, and the app displayed your adult range as the
active one and the Result Interpreter graded against it. A newborn Hb of 18
would read as "high" when newborn normal runs to about 24. Silent clinical
misread — the same class of failure as the localStorage origin and dark-mode
hazards guarded in v1.10, and it reaches 169 of the 180 tests, which have at
least one stratified analyte.

### The approach

The override layer is the symptom; the cause is that `ranges[]` holds two
different kinds of row — demographic reference intervals (479 rows) and
interpretive guideline/assay bands (280 rows, e.g. HbA1c normal/prediabetes/
diabetes). Their `sex|age|preg` triples collide on 138 rows, and "your lab's
value" means something different for each: a lab publishes its own reference
interval, but does not get to redefine a diagnostic cut-off. So the data model
is being split rather than patched around.

### Stage 1 (this stage) — identity

**Every version removed from every path.** A version baked into a path goes
stale silently, and already did once here: `test_v11_features.py` and the two
JS validators pointed at v1.1 filenames and kept passing while the v1.10 data
they were meant to check went unverified. All paths are now glob-resolved with
a strict "exactly one" rule, so a leftover build is a hard error naming both
files. Verified by planting a decoy. The Android `versionName` is now read out
of the data module rather than hand-copied beside it, and both on-device
version assertions compare against `BuildConfig.VERSION_NAME`, so an APK can
always be traced to the dataset inside it.

**Stable row ids.** All 759 range rows now carry a permanent `rid`, unique
within their test. My Lab overrides will key on `(test id, rid)` — deliberately
not including the analyte key, so there is one less identifier that can shift
under a saved value. The corpus was verified byte-identical once `rid` is
stripped, proving the change was purely additive.

**The guard that makes them trustworthy.** `qa/validate_rids.js` (method 5)
enforces on every build that a published rid never changes meaning: its
`sex`/`age`/`preg`/analyte dimensions are frozen against
`qa/rid_baseline.json`, while correcting an interval's *numbers* stays freely
allowed. rids are append-only; removal requires an explicit `retired` entry and
a retired number is never reused. `qa/test_rid_guard.js` (method 5b) then
drives the guard through all 12 violations and legitimate edits it claims to
distinguish, because a guard never observed to fail is not evidence of
anything.

No clinical content changed in this stage.

### Stage 2a — row kind, and a second tie-break bug it found

Every range row now carries a `kind`: `ref` (demographic reference interval),
`method` (assay/specimen variant), `dx` (diagnostic/classification band),
`target` (treatment target), `cutoff` (decision threshold), or `note`
(narrative/different-measurand). This is what will let Stage 3 restrict My
Lab overrides to `ref`/`method` rows only — a lab can publish its own
reference interval, but should never be able to silently redefine a
diagnostic threshold.

Classification was heuristic (`app/classify_rows.py`) plus ~56 hand-reviewed
corrections (`app/row_kinds_overrides.json`), each with a clinical rationale.
The check for "do any two `ref`/`method` rows share the same (analyte, sex,
age, preg) key" — the actual invariant the original My Lab bug violated —
surfaced two distinct problems, not classification noise:

- **15 rows were bundling different measurands under one blank analyte key**
  (osmolality vs. its osmolal gap, HbA/HbA2/HbF, CSF panel components,
  urinalysis components, serum vs. red-cell folate). Given their own
  `analyte.key` — pure data correction. This changed what 27 already-identified
  rows meant, which the Stage 1 identity guard correctly flagged; those rids
  were retired and reassigned fresh numbers above each test's ceiling, exactly
  as the guard prescribes.
- **34 rows (22 groups) are genuine clinical sub-populations the sex/age/preg
  chips can't distinguish** — ESR/PSA/testosterone/IGF-1 by age band,
  LH/FSH/estradiol/progesterone/17-OHP by menstrual-cycle phase, cortisol/ACTH
  by time of day, lactate/vWF/CEA/Bence Jones by a one-off covariate (specimen
  type, blood group, smoking status, renal function). `bestRange()` was
  breaking these ties silently, by array order — the same class of
  silent-wrong-value risk as the original bug, just in the interpreter's
  row-picker instead of the override store, and never caught by 759 rows of
  prior QA because nothing had tested what happens when more than one row
  legitimately ties.

**Fix:** `bestRange()`/`activeRange()` now detect a genuine tie instead of
guessing. The Result Interpreter requires the user to pick which group
applies, by its own label, before grading a value; the test detail page
highlights every tied row instead of just the first. `qa/known_tie_groups.json`
records every expected tie as a reviewed baseline, so a future content change
that introduces an unreviewed new one fails the build rather than guessing
silently — the same append-only-review discipline as the rid guard. The fix
caught a 23rd tie outside the original ref/method scan (D-dimer's two cutoff
rows, by age), confirming it isn't scoped to one `kind`.

A wider, unscoped scan found roughly 130 further same-key groups, almost all
genuine value-ordered severity ladders (vitamin D deficient → insufficient →
sufficient → toxic, D-dimer's age-adjusted cutoff, CRP's inflammation ladder,
etc.) rather than picker ties. Those need the interpreter to walk a ladder by
the *entered value*, not ask the user to pre-pick a row by label — a different
fix, left for Stage 2b below.

### Stage 2b — value-ordered ladder classification

`bestRange()`'s ref/method tie-chooser (Stage 2a) was built for *demographic*
ties, and wrongly fired for tests like vitamin D, whose four `dx` rows
(deficient/insufficient/sufficient/toxic) all apply to the same "any adult" —
the real distinguishing factor is the entered *value*, not the patient. Fix:
`scoredCandidates()` is now scoped to `ref`/`method` rows only, so a
dx/cutoff/target row never enters the demographic tie check; a separate
`classifyAgainstLadder()` walks `dx`/`cutoff`/`target` rows by the number the
user actually enters, picking the one band whose interval contains it (or the
nearest band, labelled "above"/"below", when the value falls outside every
defined band).

Not every same-key `dx`/`cutoff`/`target` group is a clean ladder. A group
counts as one only if every row carries numeric bounds and every pair of
intervals is either disjoint or one fully nests inside the other (a severity
refinement, e.g. "severely deficient <10" nesting inside "deficient <20") —
`isValueLadder()`. A handful of groups fail that test on purpose: ptinr and
anti-Xa's targets depend on the indication/drug, not the number; digoxin's two
targets overlap; D-dimer's age-adjusted cutoff has no fixed bound at all, only
a formula; a few more (HbA1c's individualised treatment target, NT-proBNP's
mixed age-bands-plus-rule-out set, ANA's and the Down-syndrome screen's
titre/risk-ratio results, which were never numeric to begin with) likewise
can't be placed on one axis. For these the interpreter shows the entered value
plus an informational note naming the candidates, rather than blocking —
unlike a ref/method tie, there is no single verdict being silently guessed at
here, so a hard block would be over-caution, not safety.

The wider scan (qa/validate_ties.js, method 6, below) also caught three
genuine bundled-measurand bugs this pass of classification surfaced: SAAG's
"SBP threshold" row is a different measurement entirely (ascitic fluid
neutrophil count, not SAAG) and PSA's free:total ratio and post-prostatectomy
rows are a different assay and a different clinical context respectively —
all three were sharing a blank analyte key with rows they don't belong with,
the same bundled-measurand pattern as Stage 2a's 15 rows. Given their own
`analyte.key`, same fix, same rid-retirement mechanics. Hb electrophoresis's
"HbA2 — β-thalassaemia trait" row was also reclassified from `ref` to `dx`: a
carrier-status finding is a diagnostic band, not a population reference
range, and the misclassification was creating a false ref/method tie against
the genuine HbA2 reference interval.

Fixing the false positive exposed one more real bug while fixing it, same
shape as Stage 2a's: `bestRange()`'s last-resort fallback (`rows[0]`) used to
assume `rows` always held at least one row generically applicable to any
patient — true when `rows` was every range on the test, false now that it's
kind-restricted to ref/method only. D-dimer's general-population content is
entirely `kind:"cutoff"` with no separate `ref` row, so for a non-pregnant
patient `rows` held only its three pregnancy-only ref rows — none of which
match — and the old fallback silently returned "Pregnancy T1" as if it were
the active range for a male patient. Fixed to never return a row that fails
`rangeMatches()`; the test detail page falls back separately to highlighting
whichever dx/cutoff/target rows do match demographically (restoring the
"pick by eye" display for cases like D-dimer without reopening the ref/method
false-positive this stage exists to close).

**Method 6 — `qa/validate_ties.js`.** Recomputes both tie categories (every
ref/method collision, and every dx/cutoff/target group that is *not* a clean
ladder) from the live data on every build and fails if a new or changed one
isn't in `qa/known_tie_groups.json`'s reviewed baseline — the same
append-only-review discipline as the rid guard, now covering both the Stage 2a
picker-tie class and this stage's ladder-fallback class in one pass.

### Still to come

- Stage 3 — scoped override store and My Lab UI: per-stratum entry restricted
  to `ref`/`method` rows, assay-level unit/method, locked guideline bands,
  orphaned overrides surfaced.
- Stage 4 — combinatorial QA over every (test, analyte, sex, age, pregnancy)
  combination; provenance display checks; updated on-device smoke test.

Because the v1.10 store held only test data, v2.0 resets it on upgrade rather
than carrying migration code that would run once and never be exercised again.

---

## v1.10 — FINAL FREEZE

The prototype is frozen here. This entry covers both the content completion
and the packaging decision; the earlier v1.10 notes below it describe the data
work in detail.

### Packaging decision reversed: native Android, not Capacitor

The v1.1 recommendation was Capacitor. It is now **native Android with a
WebView host**, because a constraint changed: the app will be built by Claude
Code autonomously through a connected GitHub repo, with no human watching the
build.

Capacitor's characteristic failure is a version mismatch across Capacitor ↔
AGP ↔ Gradle ↔ Kotlin ↔ JDK, where the root cause is not in the repository,
not in the error message, and lands inside generated code. Native's
characteristic failure is a compile error in a hand-written file with a line
number. Full reasoning in ANDROID_PACKAGING.md §1.

What this cost: about 200 lines of Kotlin for the file picker, print and share
capabilities Capacitor would have supplied as plugins. What it bought: one
dependency ecosystem instead of two, fully pinned versions, reviewable diffs,
and — the substantive win — **no `INTERNET` permission at all**, which turns
the offline guarantee into something Android enforces rather than something a
README claims.

### New: `android/` — the native host

Nineteen hand-written files, nothing generated:

- `MainActivity.kt` — WebView configuration, `WebViewAssetLoader`, back-button
  handling, and the injected script that adds native capability without
  touching the frozen web app.
- `NativeBridge.kt` — the only JS-facing surface: `saveFile`, `printPage`,
  the file chooser, and an unused-but-ready `shareText`.
- Pinned Gradle setup with a version catalog; no version ranges anywhere.
- `stageClinicalAsset`, wired into `preBuild`, which copies the built HTML into
  assets and **fails the build** if it is missing, so an APK can never ship
  without clinical content.
- An instrumented `SmokeTest` covering the four things that would otherwise
  fail silently on a device.

**The frozen web app is not modified at all.** Every integration point was read
out of `shell.html` rather than assumed:

- Back: the app keeps its own `navStack` and pushes no history entries, so
  `canGoBack()` is always false. The host asks the page whether `#backBtn` is
  visible, clicks it if so, and exits only if not.
- Export/backup: the app builds a `Blob`, attaches it to `<a download>`, clicks
  it, and revokes the object URL after 500 ms. WebView cannot fetch a `blob:`
  URL, so a **capture-phase** click listener reads it synchronously and hands it
  to the bridge. Capture phase is load-bearing — deferring past the revoke
  would lose the data.
- Print: `window.print()` is ignored by WebView, so it is replaced by injection
  and routed to `PrintManager`.

### Four hazards identified and guarded

1. **localStorage origin.** My Lab values are keyed to origin. The asset is
   served over a fixed `https://appassets.androidplatform.net/assets/index.html`
   and renamed to a version-free `index.html` precisely so the origin can never
   drift; `file://` was rejected because its origin is opaque. An instrumented
   test exists solely to fail if this changes.
2. **Algorithmic darkening.** Android 13+ auto-inverts WebView content in dark
   mode, which would destroy the sepia, pista and beige themes. Explicitly
   disabled. A light-mode debug build would never reveal it.
3. **R8 stripping the bridge.** Nothing in Kotlin calls `NativeBridge`, so R8
   would remove it; the release build would install fine and break the first
   time a clinician tapped Export or Print. Kept by a ProGuard rule, with a
   test to catch its removal.
4. **`allowBackup`.** Set to `false` deliberately rather than inherited — the
   default would copy local reference ranges to the user's Google account.
   Backup rules are written and scoped if a hospital chooses to enable it.

### New: CI

`.github/workflows/build.yml`. The ordering is the point: **the four-method
clinical QA suite runs first and gates everything else**, so a data error
cannot reach an installable artifact. Then the debug APK with lint and unit
tests; then an emulator smoke test on pull requests; then a manual release
bundle whose signing material comes from repository secrets and never from the
repo.

The QA suite was made portable to support this — Chrome resolves from
`CHROME_PATH` with a fallback to Playwright's bundled Chromium, and both the
Node validators and the Python suites now find the built HTML in either the
development or the handover layout.

### Still to do before the first release

Launcher icons need copying into the Android project (the build will not
succeed until they are), a Gradle wrapper needs generating, a signing keystore
needs creating, `applicationId` and `targetSdk` need confirming, and the
release build should be checked once on a physical device. The full list is
KNOWN_GAPS.md and ANDROID_PACKAGING.md §9.

---

## v1.10 — content completion (detail)

### Scope

The clinical corpus went from **34 tests to 180** — the full planned set.
Every one of the 26 categories now holds content. No design decisions were
reopened; the schema settled at v1.1 absorbed all 146 new records without
change, which was the point of freezing it first.

Corpus at this freeze:

| | |
|---|---|
| Tests | 180 |
| Categories | 26 (none empty) |
| Reference-range rows | 759 |
| Multi-analyte panel tests | 32 |
| Collection tubes | 11 |
| Tests with critical-value thresholds | 96 |
| Interpretation notes | 840 |
| Tests with patient-facing instructions | 132 |
| Records with recorded provenance | 180 / 180 |

### New in the UI

- **Version number in the app bar**, as `v 1.10` in a smaller, lighter font
  beside the app name. It is written at runtime from `LABREF_VERSION` in the
  data module, so the displayed number has exactly one source of truth and
  cannot drift from the file it was built from.
- **Long descriptive range text wraps** instead of being clipped. Range
  values over 24 characters get a `.wrap` class that drops
  `white-space:nowrap`, which matters now that many records express a range
  as a sentence ("Non-reactive; if reactive, report a quantitative titre")
  rather than two numbers.

### Data-model additions (backward compatible)

- **`src[]` on every record** — an array naming the guideline or standard
  each record's reference limits and decision thresholds rest on. This
  replaces the v1.1 inline citation markers, whose source URLs had not been
  captured into a bibliography. `qa/validate_data.js` warns on any record
  without it, so the gap cannot silently reopen. All 180 records carry one,
  including the original 34, which were backfilled.
- **An eleventh tube: `sterile`** — a sterile universal container for
  non-blood specimens, with notes on boric acid urine transport, 24-hour
  collection preservatives, and splitting a fluid tap across EDTA, plain and
  sterile containers. The 13 urine, stool, CSF and body-fluid tests
  previously (and misleadingly) shown as "Plain Serum — red" now point here.
  It carries `order:8` and its notes state explicitly that it is not part of
  the CLSI GP41 draw sequence.

### Clinical data corrections found during this pass

- **Cortisol unit mismatch** — the 9 am adrenal-insufficiency-unlikely
  threshold read 15 µg/dL against 400 nmol/L; 400 nmol/L is 14.5 µg/dL.
  Corrected to 14.5. Caught by the conversion check in
  `qa/validate_data.js`, not by eye.
- **Wrong tube id** on one record (`fluor` instead of `fluoride`), which
  would have rendered no tube at all. Caught by the referential check.
- **Lipid panel critical value was unscoped** — the triglyceride
  pancreatitis threshold (>1000 mg/dL) appeared when interpreting HDL or
  LDL. Now scoped with `critical.analyte:["trig"]`.
- **LDL-C high-risk target added** (<70 mg/dL / 1.8 mmol/L), which the v1.1
  record omitted despite being the number most often needed at the bedside.
- **Calcium renamed** to "Calcium (Total & Ionised)" to make the panel's
  contents visible in search results and lists.
- **Two `rel[]` typos** (`hcg` → `bhcg`) that pointed at no record.

### Verification

Now **four** independent methods, all passing with zero errors — see QA.md.
New in v1.10:

- **Method 4, `qa/test_all_tests.py`** — a full-corpus sweep. It opens all
  180 detail pages in a real browser by searching for each test by its own
  name, and asserts each renders a reference-range table, a breadcrumb
  naming the page, and enough content to be useful; then drives the Result
  Interpreter through **all 243 test/component combinations**, checking that
  panels offer a component picker, that single-analyte tests do not, that
  every declared component appears in the picker, and that each produces
  output; then verifies every synonym on every test resolves to its own
  record. Console and page errors are collected across the entire walk.
- The data validator gained the **provenance check** and a
  **precision-aware conversion tolerance** (half of the last decimal place,
  or 3%, whichever is larger), which removed false positives on correctly
  rounded conversions such as bilirubin 1.2 mg/dL → 21 µmol/L.

A harness bug was also found and fixed: `test_v11_features.py` was still
pointing at `LabRef_v1.10.html`, so it had been passing against the previous
build. All QA scripts now target `LabRef_v1.10.html`. Method 4 initially
reported 46 tests as unreachable by search; this was its own 60 ms wait
against the search box's 120 ms input debounce, not an app defect — it was
confirmed by direct measurement before the harness was corrected.

### Icons

Unchanged. The artwork carries no version or product name.

---

## v1.1 — second freeze

### Clinical data corrections

These came out of a full re-verification pass over all 34 records: a
programmatic sweep (`qa/validate_data.js`) plus a value-by-value domain
review, with authoritative-source checks on the highest-consequence and
most-likely-to-have-moved figures.

- **TSH pregnancy ranges corrected — this one mattered.** The trimester
  ranges were the superseded 2011 ATA / 2014 ETA values (T1 upper limit
  2.5, T2–T3 3.0 mIU/L). ATA 2017 replaced these after studies in Asia,
  India and the Netherlands found only a modest fall in the upper limit,
  and sets ~4.0 mIU/L where a local trimester-specific interval is not
  available. Corrected to T1 0.1–4.0, T2 0.2–4.0, T3 0.3–4.0, with two new
  interpretation notes: one explaining the change explicitly (so a
  clinician taught 2.5 understands why this reads 4.0), one noting the
  shift applies from weeks 7–12 and returns gradually toward the
  non-pregnant range. **Using the old 2.5 cutoff over-diagnoses subclinical
  hypothyroidism in pregnancy and leads to unnecessary levothyroxine** —
  the reason this was worth catching.
- **LDL-C high-risk target added.** The panel carried the optimal (<100)
  and very-high-risk (<55 mg/dL) targets but omitted the widely-used
  high-risk target of <70 mg/dL / <1.8 mmol/L (ESC/EAS). Added.
- **D-dimer pregnancy safety note added.** The stored trimester ranges
  match a published study exactly, but published intervals vary several-
  fold between assays and populations, and the ranges describe what is
  physiologically expected rather than an exclusion threshold. A reader
  could otherwise take a value inside the third-trimester range as ruling
  out PE at term. Now stated explicitly.
- **GDM criteria expanded.** DIPSI (non-fasting 75 g, 2 h ≥140 mg/dL) is
  correct and MoHFW-endorsed, but validation studies in Indian women show
  low sensitivity against WHO 1999 and IADPSG. Added that caveat plus the
  IADPSG/WHO 2013 fasting alternative (fasting ≥92, 1 h ≥180, 2 h ≥153).
- **Troponin assay nuance added.** hs-cTnT carries two different "overall"
  cutoffs — 19 ng/L on the US FDA label versus 14 ng/L in most published
  studies and European practice. The overall row is now labelled as the
  guideline/non-US figure and a note explains the discrepancy.
- **Calcium renamed** from "Calcium, Total & Corrected" to "Calcium (Total
  & Ionised)" — the record's two components are total and ionised; the
  corrected-calcium formula lives in the interpretation notes, and both
  remain findable through the existing synonyms.

Verified-correct and left unchanged (worth recording so the next pass does
not redo them): total and direct bilirubin SI ranges, vitamin D
deficiency/insufficiency/sufficiency thresholds, hs-cTnI Abbott 99th
percentiles (26 / 34 male / 16 female ng/L), hs-cTnT Roche sex-specific
(22 male / 14 female ng/L), ESC/EAS LDL-C very-high-risk target, HbA1c
DCCT↔IFCC conversions (checked arithmetically against the affine formula),
and the neonatal bilirubin thresholds with their hour-specific-nomogram
caveat.

### Renamed MedRef → LabRef

Throughout: UI, document title, data module constants (`LABREF_*`), file
names (`labref_data_v1.10.js`, `LabRef_v1.10.html`), export file types, and
documentation.

Two compatibility paths were kept deliberately, and are the only places the
old name survives:

- **localStorage** reads `labref_v1`, falling back once to `medref_v1` and
  immediately rewriting under the new key, so an existing user's themes,
  favourites, text size and My Lab values carry over instead of silently
  vanishing. The old key is left in place rather than deleted.
- **Import** accepts both `labref-*` and `medref-*` lab-profile and backup
  files, so anything already exported still restores.

### UI changes

- **Detail pages open collapsed** except *Reference ranges* and
  *Interpretation notes*. "Your lab's values" no longer auto-opens when a
  local value exists — the override already shows in the open Reference
  ranges block with a "Your lab" badge, so nothing is hidden.
- **Breadcrumb page address** in the app bar (`Tests › Lipids › Lipid
  Profile`): small type on its own full-width row, ancestors tappable and
  underlined, current page in a distinct colour. The highlight colour is
  per-theme because a single colour cannot clear 4.5:1 contrast on all six
  app-bar backgrounds — sepia's mid-brown tops out at 4.85:1 even against
  pure white. Each value is the most saturated warm tone that still clears
  4.5:1 on that theme.
- **Tests-tab panels are collapsible** (Favourites, Recently viewed,
  Categories), open by default, with collapse state persisted in
  `S.panels` so it survives navigation and reload. Detail-page blocks
  deliberately do *not* persist — they reset to the defaults above every
  time.
- Detail header de-duplicates abbreviation and category when they are the
  same string (Lipid Profile is abbr "Lipids" in category "Lipids", which
  rendered as "Lipids · Lipids").

### Verification

Three independent methods, all passing — see QA.md. Two are new in v1.1:
`validate_data.js` (data integrity without a browser) and `audit_build.js`
(static audit of the shipped artifact, including the offline guarantee).
`test_v11_features.py` adds 30 browser assertions for the changes above.

### Icons

Unchanged from v1.0 — the artwork carries no product name, so the rename
required no re-export.

---

## v1.0 — first freeze

Initial prototype: 34 tests across 26 categories, 10 tube types, six
multi-analyte panels, My Lab local overrides with export/import, six
themes, tube picker, result interpreter, reverse lookup, printable prep
handout, patient-mode range matching.
