# Known Gaps — read this as a checklist, not a surprise

Everything below is a deliberate, scoped item rather than an oversight
discovered late. This list is substantially shorter than at the v1.1 freeze
because v1.10 closed the content gap that dominated it.

## Closed since v1.1

- ~~34 of ~180 tests populated~~ → **all 180 populated.** Every one of the
  26 categories now has content; none is empty.
- ~~9 dangling `rel[]` forward references~~ → **zero.** Every `rel[]` entry
  resolves to a real record; `qa/validate_data.js` enforces this.
- ~~Citation gap: 12 claims with uncaptured sources~~ → **closed.** The
  inline citation markers were removed from the data (the build script
  strips any that reappear), and replaced with a structured `src[]`
  provenance array on **every one of the 180 records**, naming the guideline
  or standard its reference limits and decision thresholds come from. The
  validator now *warns on any record without `src[]`*, so this cannot
  silently regress. See SOURCES.md.
- ~~Non-blood specimens shown as "Plain Serum (red)"~~ → a dedicated
  `sterile` container record was added (tube #11) and the 13 urine, stool,
  CSF and fluid tests retargeted to it.

## Content — still open

- **Panel `inc[]`/`dec[]` causes are test-level, not per-component.** For the
  32 panel tests the Result Interpreter shows the same "causes of
  raised/lowered value" list regardless of which component was interpreted,
  because `inc[]`/`dec[]` live on the test record rather than per `analyte`.
  This is usually a fair fit — most panels' causes genuinely overlap across
  components, and the lists are written to read sensibly for the panel as a
  whole — but it is imprecise for a few (e.g. "causes of raised HDL" is not
  really the clinical category that "causes of raised LDL" is). Splitting
  causes per component was judged a deliberate design decision rather than a
  defect; make the call (split vs. accept) before adding further panels.
- **Test-level critical values on panels.** `critical.analyte` scopes a
  critical value to named components, which covers every current need. Eleven
  panels carry an unscoped critical value *by intent* — these are narrative
  test-wide warnings (e.g. "tamponade is a clinical diagnosis — drain first")
  that apply however the test is used. The validator flags them as warnings
  so the choice stays visible. A panel whose components each need a
  *different* numeric critical value still cannot be expressed; no current
  test needs that.
- **Reference ranges are textbook/guideline values, not local analyser
  values.** This is inherent to the product, not a defect — the My Lab
  feature exists precisely so a department overrides them. Worth stating
  plainly in any user-facing release notes.
- **My Lab overrides have no demographic scope — a real defect, found in
  hands-on use of the v1.10 APK, not by this suite.** An override is stored
  per analyte only, and `activeRange()` consults it *before* the stratum
  matcher, so one saved value wins in every context: a lab's adult
  haemoglobin range also replaces the newborn and pregnancy rows, and the
  Result Interpreter grades against it. A newborn Hb of 18 reads as "high"
  when newborn normal runs to about 24. This affects 169 of the 180 tests.
  **Being fixed in v2.0** (branch `v2-data-model`) by splitting demographic
  reference intervals from interpretive bands and keying overrides to
  individual rows; see CHANGELOG.md. It is recorded here because v1.10 is
  what ships today, and anyone using its My Lab feature should enter values
  only for the adult rows until v2.0 lands.
  It is also a lesson about this suite's blind spot: five methods and 759
  verified rows did not catch it, because every check asked whether the
  *textbook* data was right, and none asked what happens once a user's own
  value sits on top of it. Stage 4 of v2.0 adds that dimension.
- **Assay-dependent tests.** 60-odd records are flagged `assayDep:true`,
  meaning the quoted interval is platform-specific (most immunoassays,
  tumour markers, free hormones, drug levels by immunoassay). The app shows
  this caveat; it is not something data entry can resolve.

## Items worth re-checking at each release

Guideline thresholds move. These are the specific numbers most likely to be
revised, with what they currently rest on recorded in each record's `src[]`:

- Pregnancy TSH ranges (revised once already — see CHANGELOG.md)
- LDL-C goals by cardiovascular risk category (ESC/EAS)
- High-sensitivity troponin 99th-percentile URLs and 0/1-h algorithm cut-offs
- NT-proBNP rule-out/rule-in thresholds
- HbA1c and glucose diagnostic thresholds (ADA/WHO)
- Vitamin D sufficiency thresholds (contested between bodies)
- Ferritin thresholds for iron deficiency, including the inflammation-adjusted value
- eGFR equation (CKD-EPI 2021 is current; a further revision is plausible)
- Aldosterone:renin ratio screening cut-off
- Sweat chloride diagnostic bands
- Myeloma free-light-chain ratio myeloma-defining threshold

## Engineering — still open

- **The Android app has not been built or shipped.** The packaging decision is
  made (native, not Capacitor) and the scaffold is written, builds are wired
  and CI is configured — but no APK or AAB has been produced, because the
  pre-release items below have to come first.
- **Launcher icons are not yet copied into the Android project.**
  `icons/android/` holds the rendered `mipmap-*` assets and the adaptive
  layers; they need copying into `android/app/src/main/res/`. The scaffold
  references `@mipmap/ic_launcher` and **will not build until they are there**.
  This is the first thing to do and takes one `cp -r`.
- **No Gradle wrapper JAR is committed.** Run
  `gradle wrapper --gradle-version 8.9` once in `android/`, or let the CI
  action supply Gradle.
- **No signing keystore exists.** Generate it, store it somewhere durable —
  losing it means never being able to update the app on Play — and add the four
  `ANDROID_*` repository secrets. Until then, release builds are unsigned by
  design rather than failing.
- **`targetSdk`/`compileSdk` are pinned at 35.** Play raises its minimum
  target API roughly once a year. Verify the current requirement before the
  first upload and bump both together.
- **`applicationId` is the placeholder `com.labref.app`.** Change it before the
  first Play upload if the organisation has its own namespace — it cannot be
  changed afterwards.
- **The release build has never run on a physical device.** Debug builds skip
  R8, so they cannot catch the one failure R8 can cause here (stripping
  `NativeBridge`, which breaks Export and Print at runtime while the app
  otherwise looks fine). `SmokeTest` covers it on an emulator; do one manual
  release-build check on a real phone before the first upload.
- **Play Data Safety declaration and medical disclaimer are not written.** The
  honest Data Safety answer is that nothing is collected or transmitted; see
  ANDROID_PACKAGING.md §9.
- **The app icon is not wired into the single-file HTML.** `icons/` contains
  source SVGs and rendered PNGs sized for the Android launcher, Play Store
  listing and PWA manifest, but `shell.html`'s `<head>` has no
  `<link rel="icon">`, `manifest.json` or `apple-touch-icon`. That is
  deliberate: referencing external PNGs would break the single-file offline
  guarantee, and inlining a base64 data URI was left as an optional
  follow-up for the HTML-only distribution. For the native build the assets
  drop straight into the generated project's resource folders.
- **File size.** The built single file is now ~703 KB (from ~190 KB at
  v1.1), all of it text. It loads instantly from local storage and the
  offline guarantee is unaffected, but if the corpus grows much beyond this
  it is worth considering lazy-loading categories in the native build.

## What is NOT a gap — explicitly validated and considered closed

- The multi-analyte/panel data model across all **32** panel tests — schema,
  range matching, My Lab overrides, unit conversion and Result Interpreter
  verified end-to-end (`qa/test_panel.py`, plus method 4 which interprets a
  value for all 243 test/component combinations).
- All 180 detail pages render with ranges, causes, notes, prep and a tube,
  with no console error anywhere in the walk (`qa/test_all_tests.py`).
- Every synonym on every test resolves to its own record (same script).
- Patient-mode range matching specificity scoring — 24-case regression
  matrix passing (`qa/test5.py`).
- Text resizing, theming (6 themes), tube picker, blood-culture tube
  handling, patient-prep handout clinician/patient content separation.
- The build process (`build.py`) — stable and content-agnostic.
- The offline guarantee — `qa/audit_build.js` fails on any external resource
  reference, so it cannot regress silently.
- The MedRef→LabRef rename, including one-way localStorage migration and
  backward-compatible import of files exported by the old build.
- v1.1 UI behaviour: detail-page collapse defaults, the breadcrumb and its
  navigation, the persisted Tests-tab panels.
- v1.10 UI behaviour: the version label in the app bar, rendered from
  `LABREF_VERSION` so the number has one source of truth.
- **The packaging decision**, with the reversal from Capacitor reasoned out in
  ANDROID_PACKAGING.md §1 rather than left implicit.
- **The native host's integration points**, each read out of the frozen shell
  rather than assumed: back-button behaviour against the app's own `navStack`,
  blob-based export intercepted in the click capture phase before the 500 ms
  object-URL revoke, and `window.print` redirected to `PrintManager`. The
  frozen web app needs no modification for any of them.
- **The localStorage origin hazard**, identified before any code was written
  and guarded by both a fixed `index.html` asset name and an instrumented test.
- **The CI ordering** — clinical QA is a hard gate before anything is packaged,
  so a data error cannot reach an installable artifact.
