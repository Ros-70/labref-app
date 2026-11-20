# LabRef Data Schema

The data file (`app/labref_data_v*.js` — one per repository, the version in
its name must match the `LABREF_VERSION` it declares, and `build.py` fails
if they disagree) is the single source of truth for all app content. The UI
(`app/shell.html`) only ever reads it. **Do not rename fields** — the
shell's JS reads them by exact name throughout, and renaming without
updating every call site will silently break rendering.

The authoritative copy of this schema also lives as a comment block at the
top of the data module itself — keep the two in sync if either changes.
This document expands on it with worked examples. Neither this heading nor
the text below names a version on purpose: both went stale through the v2.0
rename while still claiming to describe the current file.

---

## 1. Top-level arrays

```js
const LABREF_VERSION   = "1.0";
const LABREF_CATEGORIES = [ {id, name, icon, color}, ... ];
const LABREF_TUBES      = [ {id, order, name, colors, shortColor?, additive, inv, uses, notes}, ... ];
const LABREF_TESTS      = [ {...test record...}, ... ];
```

### LABREF_CATEGORIES

One entry per test category shown as a home-screen tile.

| field   | type   | notes |
|---------|--------|-------|
| `id`    | string | slug, referenced by `test.cat` |
| `name`  | string | display name |
| `icon`  | string | a single Unicode glyph used as the category tile icon (no image assets) |
| `color` | string | hex colour for the tile accent |

26 categories are already defined (see the array in the data file). **Add
new tests to an existing category where the content genuinely fits** before
inventing a new one — the category list was deliberately scoped generously
up front so that build-out is almost always pure content population, not
schema change.

### LABREF_TUBES

One entry per physical collection-tube type.

| field        | type           | notes |
|--------------|----------------|-------|
| `id`         | string         | slug, referenced by `test.tube.id` |
| `order`      | number         | CLSI GP41 (7th ed.) order-of-draw position; `0` if not applicable (e.g. ABG syringe) |
| `name`       | string         | display name |
| `colors`     | string         | full cap-colour description — may be prose, not just a colour word (blood-culture bottles are brand-specific, not CLSI-coded, and say so here) |
| `shortColor` | string, optional | compact label for list rows; falls back to `colors` when absent |
| `additive`   | string         | anticoagulant/preservative, or "None" |
| `inv`        | string         | inversions required |
| `uses`       | string         | what the tube is used for |
| `notes`      | string         | handling notes shown in the Tube Picker |

Two notes on the tube list:

- **Shared draw-order numbers are correct.** `sst` and `plain` both sit at
  position 3, and `esr` and `trace` both at 7, because CLSI GP41 places them
  at the same step. The validator reports this as a warning so the choice
  stays visible rather than looking like a typo.
- **`sterile` (position 8) is not a vacutainer.** It is the sterile
  universal container used for urine, stool, CSF and body-fluid specimens,
  and its own `notes` say explicitly that it is outside the draw sequence.
  It exists because 13 tests collect a non-blood specimen, and showing them
  as "Plain Serum — red" was actively misleading.

11 tube/container types are defined and cover every test in the
~180-test target list. Only add a new tube type for a genuinely distinct
physical tube — do not add one per test.

---

## 2. Test records (`LABREF_TESTS[]`)

### 2a. Ordinary (single-analyte) test — full example

```js
{
  id:"creatinine", name:"Creatinine (Serum)", abbr:"S.Cr", cat:"elec",
  syn:["creatinine","cr","kft","rft","renal function","kidney function","egfr"],
  specimen:"Serum or lithium heparin plasma",
  tube:{ id:"sst", vol:"3 mL", handling:"Separate within 2 h." },
  prep:{
    fasting:"Not required",
    items:["Avoid a heavy cooked-meat meal in the preceding 12 h...", "..."],
    patient:["Avoid a heavy meat meal the night before the test.", "..."]
  },
  assayDep:true,
  units:{ conv:"mg/dL", si:"µmol/L", factor:88.4 },
  ranges:[
    { rid:"r1", grp:"Adult male",   sex:"M", age:"adult",   preg:null,  conv:{lo:0.70,hi:1.30}, si:{lo:62,hi:115} },
    { rid:"r2", grp:"Adult female", sex:"F", age:"adult",   preg:null,  conv:{lo:0.55,hi:1.10}, si:{lo:49,hi:97} },
    { rid:"r3", grp:"Pregnancy",    sex:"F", age:"adult",   preg:"any", conv:{lo:0.40,hi:0.80}, si:{lo:35,hi:71} },
    { rid:"r4", grp:"Newborn",      sex:"any",age:"neonate",preg:null,  conv:{lo:0.30,hi:1.00}, si:{lo:27,hi:88} },
    { rid:"r5", grp:"Child (1–12 y)",sex:"any",age:"child", preg:null,  conv:{lo:0.30,hi:0.70}, si:{lo:27,hi:62} }
  ],
  critical:{ txt:">4.0 mg/dL, or a rise >0.3 mg/dL in 48 h (AKI)", lo:null, hi:4.0 },
  inc:["Acute kidney injury...", "..."],
  dec:["Low muscle mass...", "..."],
  interf:["Jaffe method: bilirubin falsely lowers...", "..."],
  pearls:["Report eGFR with every creatinine...", "..."],
  rel:["urea","potassium","urineacr","cystatin"]
}
```

### Field reference

| field       | type                | notes |
|-------------|---------------------|-------|
| `id`        | string              | unique, lowercase, hyphen-free slug (used as a DOM id and localStorage key) |
| `name`      | string              | full display name |
| `abbr`      | string              | short form shown in list rows and the category-icon initials |
| `syn[]`     | string[]            | search synonyms — include Indian clinical shorthand (KFT, LFT, TLC, etc.) |
| `cat`       | string              | category id from `LABREF_CATEGORIES` |
| `specimen`  | string              | specimen type, free text |
| `tube`      | `{id, vol, handling}` | `id` refers to `LABREF_TUBES` |
| `prep`      | `{fasting, items[], patient[]}` | see below |
| `assayDep`  | boolean             | `true` when the cutoff is analyser/method-specific — shows a warning badge pointing to My Lab |
| `units`     | `{conv, si, factor}` | `si_value = conv_value * factor`. For a panel test this is a **default only** — see §2b |
| `ranges[]`  | array               | see below. Every row carries a permanent `rid` and a `kind` — see below |
| `critical`  | `{txt, lo, hi, analyte?}` or `null` | see below |
| `inc[]`     | string[]            | causes of a raised value |
| `dec[]`     | string[]            | causes of a low value |
| `interf[]`  | string[]            | analytical interferences |
| `pearls[]`  | string[]            | interpretation notes, clinical pearls |
| `rel[]`     | string[]            | related test ids, shown as "Related tests" links. Every entry must resolve to a real record — `qa/validate_data.js` errors otherwise |
| `src[]`     | string[]            | **provenance.** Names the guideline(s) or standard(s) the record's reference limits and decision thresholds come from. Not rendered in the UI; it is maintenance metadata so a guideline revision can be traced to the records it affects. Required in practice — the validator warns on any record without it. See SOURCES.md |

**`prep.items[]` vs `prep.patient[]`** — this split is load-bearing and easy
to get wrong. `items[]` is for the person drawing the sample (may include
clinician-only detail: drug-interaction notes, "discard dead-space
volume", etc.). `patient[]` feeds the **printable patient handout** and
must contain only plain language the patient should actually be told —
never mention it unless the test genuinely needs patient action (fasting,
a drug hold, timing). Omit `patient[]` entirely when there's nothing to
tell the patient.

**`ranges[].rid`** is the row's **permanent identity**, unique within its test
(`"r1"`, `"r2"`, …). Added in v2.0. A user's own lab values are stored against
`(test id, rid)`, in localStorage on their own device, so a rid is a contract
with every installed copy of the app:

- **It never changes meaning.** Its stratum dimensions (`sex`, `age`, `preg`,
  and the analyte for a panel row) are frozen once published. Correcting an
  interval's numbers is fine and expected — that is ordinary content
  maintenance and does not disturb anyone's override. Re-pointing a rid at a
  different population is forbidden: give the new stratum a new rid and retire
  the old one.
- **rids are append-only.** Removing a row requires an explicit entry under
  `retired` in `qa/rid_baseline.json`, and a retired number is never reused —
  not even by backfilling the gap it left.
- **Never renumber.** Do not tidy, re-sort, or compact rids. Row order in the
  array carries no meaning; the rid does.

Assign them with `cd app && python3 -I assign_rids.py`, which is idempotent and
only ever adds. All of the above is enforced on every build by
`qa/validate_rids.js` (method 5), which is itself tested by
`qa/test_rid_guard.js` (method 5b). Those two exist because the failure they
prevent is silent: a clinician's adult-female range quietly becoming the
newborn range, with nothing on screen to show it.

**`ranges[].grp`** is the human-readable row label shown in the UI and used
as the row-match fallback ordering tiebreaker; keep it short and specific
("Pregnancy T3", not "Third trimester of pregnancy"). **`sex`** is `"M"`,
`"F"`, or `"any"`. **`age`** is one of `"neonate"`, `"infant"`, `"child"`,
`"adolescent"`, `"adult"`. **`preg`** is `null` (not pregnancy-specific),
`"any"` (applies across all trimesters), or `"T1"`/`"T2"`/`"T3"`.

**`ranges[].kind`** classifies what a row actually *is*, added in Stage 2 of
v2.0. One of:

| kind       | meaning |
|------------|---------|
| `ref`      | a population reference interval — what a healthy member of this demographic group looks like |
| `method`   | an assay/specimen variant of a reference interval (not a different population) |
| `dx`       | a diagnostic/classification band (e.g. Vitamin D deficient/insufficient/sufficient/toxic) |
| `target`   | a treatment target for someone already diagnosed (e.g. HbA1c's "<7.0, individualise") |
| `cutoff`   | a decision threshold not tied to one diagnosis (e.g. D-dimer's exclusion cutoff) |
| `note`     | narrative/different-measurand row — info-only, never matched or ranked |

This exists because `ranges[]` mixes two fundamentally different things a lab
value can be compared against, and conflating them was the root cause of two
separate bugs (see CHANGELOG's Stage 2a/2b). **It is why My Lab overrides are
restricted to `ref`/`method` rows (plus `cutoff` rows on assayDep tests —
see §3), as of Stage 3** — a lab can publish its own reference interval, but
should never be able to silently redefine a diagnostic threshold or
treatment target.

`kind` is deliberately **not** part of a rid's frozen identity fingerprint
(unlike `sex`/`age`/`preg`/analyte) — it is pure, correctable content
metadata, so reclassifying a row (e.g. hb electrophoresis's "HbA2 —
β-thalassaemia trait" from `ref` to `dx`, Stage 2b) never triggers the rid
guard or disturbs a saved override.

Classify with `cd app && python3 -I classify_rows.py` (heuristic first pass)
plus hand-reviewed corrections in `app/row_kinds_overrides.json`, each with a
`_why`; write the result into the data module with
`cd app && python3 -I write_kinds.py`.

**How `kind` drives row selection** — two independent mechanisms, both in
`shell.html`:

- **Demographic matching** (`scoredCandidates()`/`bestRange()`/
  `tiedCandidates()`) is scoped to `kind:"ref"`/`"method"` rows only (plus
  rows with no `kind` at all, from before this field existed). When two or
  more score identically for the current patient mode, that is a genuine
  *demographic* tie (ESR by age band, LH by cycle phase) and the Result
  Interpreter requires the user to pick which group applies, rather than
  guessing. `qa/known_tie_groups.json`'s `groups` array is the reviewed
  baseline of every expected tie; `qa/validate_ties.js` (method 6) fails the
  build on an unreviewed new one.
- **Value-ladder classification** (`classifyAgainstLadder()`/
  `isValueLadder()`) walks `kind:"dx"`/`"cutoff"`/`"target"` rows that share a
  key by the number the user actually *enters*, not by demographic matching —
  picking the one band whose interval contains the value (or flagging
  "above"/"below" the nearest band when the value falls outside every defined
  one). A group only counts as a clean ladder if every row has numeric bounds
  and every pair of intervals is disjoint or nested (a severity refinement).
  The handful that aren't (ptinr, anti-Xa, digoxin, D-dimer's age-adjusted
  cutoff, HbA1c's treatment target, NT-proBNP, ANA, the Down-syndrome screen —
  see CHANGELOG's Stage 2b for why each one fails) show the entered value plus
  an informational note naming the candidates, never a hard block —
  `qa/known_tie_groups.json`'s `ladder_fallback_groups` is their reviewed
  baseline, also enforced by `qa/validate_ties.js`.

Both mechanisms key on `(analyte.key or "_") + sex + age + preg` — a test
with no `analyte` on any row effectively has one component, keyed `"_"`.

**`critical`** is `null` for a test with no recognised critical/panic value.
When present, `txt` is the display string, `lo`/`hi` are optional numeric
bounds (shown in the interpreter alongside the text). `analyte` (panel
tests only) restricts the critical value to specific component keys — see
§2b.

### 2b. Panel (multi-analyte) tests

Six current tests bundle more than one genuinely separate, independently-
reported measurement under a single test `id`:

| test id     | components |
|-------------|------------|
| `lipid`     | total cholesterol, LDL-C, HDL-C, triglycerides, non-HDL-C |
| `abgpanel`  | pH, PaCO₂, PaO₂, HCO₃⁻, base excess, SaO₂, anion gap |
| `ptinr`     | PT (seconds), INR (unitless ratio) |
| `troponin`  | hs-cTnI (Abbott assay), hs-cTnT (Roche assay) — a lab reports one, never both |
| `bilirubin` | total, direct (conjugated) |
| `calcium`   | total, ionised |

**Why this exists**: before this was modeled explicitly, the UI picked a
single "best matching" range row per test — which for Lipid Profile under
a male/adult patient mode silently resolved to the HDL row and displayed
it as if it were the whole panel's range. The single test-level
`units.factor` was also wrong for triglycerides (a different molar mass
than cholesterol). Every panel test must have each of its components
tagged so the UI can treat them independently end-to-end: its own range
table, its own unit-conversion factor, its own "My Lab" override box, and
its own selection in the Result Interpreter.

**How to tag a component** — add `analyte:{key, label, factor?, convUnit?,
siUnit?, noConvert?}` to every range row belonging to that component:

```js
ranges:[
  { grp:"Total cholesterol — desirable", analyte:{key:"totalchol",label:"Total Cholesterol"},
    sex:"any",age:"adult",preg:null, conv:{lo:null,hi:200}, si:{lo:null,hi:5.18} },
  { grp:"LDL-C — optimal",        analyte:{key:"ldl",label:"LDL-C"}, ... },
  { grp:"LDL-C — very high CV risk target", analyte:{key:"ldl",label:"LDL-C"}, ... },
  { grp:"Triglycerides — normal", analyte:{key:"trig",label:"Triglycerides",factor:0.0113}, ... }
]
```

- `key` — short, stable id for the component. **Rows that share the same
  key are the same component shown under a different patient-mode
  condition** (both LDL rows above are `key:"ldl"`). Rows with different
  keys are different measurements and must never be cross-matched,
  cross-converted, or merged into one "best range" or one override box.
- `label` — display name for that component's own sub-section heading and
  My Lab override block.
- `factor` (optional) — overrides `units.factor` when this component's own
  SI conversion differs from the test's panel-level default. **This is the
  single most error-prone part of modeling a panel** — always verify a
  candidate factor against the stored SI value for that row (see
  UNIT_CONVERSIONS.md §3 for the verification method used on triglycerides).
- `convUnit` / `siUnit` (optional) — overrides the displayed unit label
  when a component's unit differs from the panel default (used for PT's
  "seconds" and INR's "ratio", which have nothing to do with the panel's
  nominal `units.conv`/`units.si`).
- `noConvert: true` — the component has no meaningful second unit (pH,
  SaO₂, a qualitative result). Suppresses the conversion footnote rather
  than showing an incorrect one.

**Omit `analyte` entirely** for an ordinary single-analyte test — the UI
falls back to one range table and one override box automatically. Don't
add `analyte` "just in case"; it only belongs on a test that genuinely
bundles distinct, separately-reported measurements.

**Info-only rows without an `analyte` tag** — a panel can also carry rows
that are patient-mode-specific notes rather than another component, e.g.
ABG Panel's "Pregnancy (compensated resp alkalosis)" row. Leave these
without an `analyte` tag; they render in an "Also note" section and are
still highlighted when they match the current patient mode (via
`rangeMatches()`), but they are never offered as a selectable component in
the Result Interpreter.

**Scoping a critical value to one component** — `critical.analyte` (an
array of component keys) restricts a test-wide critical value so it is
only shown while interpreting the named component(s):

```js
critical:{ txt:"Triglycerides >1000 mg/dL (pancreatitis risk)", lo:null, hi:1000, analyte:["trig"] }
```

Omit `critical.analyte` when the value is genuinely test-wide (Troponin —
the same 99th-percentile logic applies whichever assay is in use) or
already names its own components inline in the text (ABG Panel, PT/INR).

---

## 3. Client-side state & "My Lab" storage shape

The app stores everything in a single `localStorage` key (`labref_v1`, migrating once from the pre-rename `medref_v1`) as
one JSON blob, `S`. The fields that matter for content work:

```js
S.local = {
  "<test-id>": {
    note: "free-text notes (TAT, send-out lab, sample quirks)",
    assay: {
      "<component-key-or-_>": { unit: "string", method: "string", crit: "string" }
    },
    byRid: {
      "<rid>": { lo: "string", hi: "string" }
    }
  }
}
```

**Added in v2.0 Stage 3**, replacing a flat per-component shape
(`comp:{key:{lo,hi,unit,crit,method}}`) that was itself a replacement for the
original v1.0-prototype shape (`S.local[id].lo`/`.hi`/`.crit` directly) — see
CHANGELOG's Stage 3 for why: a per-component override carries no demographic
scope, so one saved value silently applied to every stratum of that
component, including ones it was never measured against (a saved adult-male
haemoglobin range displayed, and graded against, as the newborn range too).

The split is deliberate and the two halves are **not** interchangeable:

- **`assay`** holds what genuinely is component-level, not row-level — the
  unit your lab reports in, the analyser/method name, and your lab's
  critical/panic value. These don't vary by patient, so they're keyed by
  `analyte.key` (or `"_"` for a non-panel test), the same key used throughout
  §2b. An entry only persists once `method` or `crit` is actually filled in —
  the unit field is always pre-filled with a textbook default and therefore
  never meaningfully blank, so `unit` alone is deliberately excluded from
  the "is this worth saving" check; saving one without touching it would
  otherwise write a phantom entry for every component on every save.
- **`byRid`** holds the actual lo/hi numbers, one entry per **row**, keyed by
  that row's permanent `rid` (§2a) — never by component, sex, age, or preg
  individually; the rid already encodes the full stratum. Only rows where
  `overridableKind(r, t)` is true may ever get an entry here:

  ```js
  function overridableKind(r, t){
    return r.kind==="ref" || r.kind==="method" || r.kind==null
         || (r.kind==="cutoff" && !!t.assayDep);
  }
  ```

  `ref`/`method` rows (and legacy rows with no `kind` at all) are always
  overridable — a lab publishing its own reference interval is exactly what
  My Lab exists for. `cutoff` rows are overridable **only** when the test
  carries `assayDep:true` (D-dimer, NT-proBNP, drug levels, serology index
  cutoffs — the threshold shifts with the assay, so "your lab's cutoff" is a
  real thing). SAAG's cutoff stays locked: its test is `assayDep:false`, so
  the threshold is a published constant, not something the local analyser
  changes. `dx`, `target`, and `note` rows are **never** overridable, on any
  test — a lab doesn't get to redefine a diagnostic band or a treatment
  target, only report its own measurement against one.

**A saved value whose rid no longer maps onto an overridable row** — the row
was retired, reclassified to a locked `kind`, or the value predates Stage 3
and is still in the old `comp` shape — is never silently applied and never
silently dropped. `orphanedOverrides(t)` lists each one in plain language so
the My Lab screen can surface it for the user to re-enter or clear; see
`myLabBlockHtml()` in `shell.html`.

**`effectiveBounds(t, r)`** is the single function that decides a row's
active numbers — a saved `byRid` override if one exists and the row is
overridable, otherwise the textbook `conv`/`si` bounds. Both the ref/method
comparison (`activeRange()`) and the value-ladder classifier
(`classifyAgainstLadder()` → `bandBounds()`) read through this one function,
so an override on an assayDep cutoff row feeds both without a second,
independently-maintained copy of the same lookup.

The helper functions `localBlob()`, `overridableKind()`, `assayOverride()`,
`ridOverride()`, `saveAssay()`, `saveRid()`, `saveNote()`, `hasLocal()`,
`orphanedOverrides()`, and `effectiveBounds()` in `shell.html` are the only
sanctioned way to read or write this — don't access `S.local` directly from
new code.

### Collapse state (`S.panels`)

```js
S.panels = { "p-favs": true, "p-recent": true, "p-cats": false }
```

Open/closed state for the Tests tab's landing panels only. Absent key means
open — only an explicit `false` closes one, so a panel added later defaults
to open without a migration. Written by `block(..., {persist:true})` via
`bindBlocks()`, read by `panelOpen(id)`.

**Detail-page blocks deliberately do not persist.** They reset on every
render to fixed defaults: *Reference ranges* and *Interpretation notes*
open, everything else — including *Your lab's values*, even when a local
override exists — collapsed. If you add a block to the detail page, it
should be collapsed by default unless there is a specific reason
otherwise; the open set is deliberately small so the page opens readable
on a phone.

### Storage key migration

`LS = "labref_v1"`, with `LS_LEGACY = "medref_v1"` read once as a fallback
and immediately rewritten under the new key. If you ever rename the key
again, follow the same shape (read new → fall back to old → write new at
once) rather than dropping the old key, or users lose their saved lab
values silently.

---

## 4. Patient-mode matching

`S.sex`, `S.age`, `S.preg` drive which range row is shown as the active
match. The scoring function `rangeScore()` in `shell.html` picks the most
*specific* applicable row rather than the first one found — a sex-neutral
"Adult" row must never outrank a correctly-matching trimester-specific
row. If you add a new age bracket, sex-specific split, or pregnancy
distinction to a test, there is nothing to change in the matching logic
itself — just add the row with the correct `sex`/`age`/`preg` combination
and `rangeScore()` will rank it correctly. The 24-case regression matrix in
`qa/test5.py` is the place to add a case when you want to lock in a new
tricky matching scenario.
