# LabRef Data Schema — v1.1

The data file (`app/labref_data_v1.10.js`) is the single source of truth for
all app content. The UI (`app/shell.html`) only ever reads it. **Do not
rename fields** — the shell's JS reads them by exact name throughout, and
renaming without updating every call site will silently break rendering.

The authoritative copy of this schema also lives as a comment block at the
top of `labref_data_v1.10.js` itself — keep the two in sync if either
changes. This document expands on it with worked examples.

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
| `ranges[]`  | array               | see below. Every row carries a permanent `rid` — see below |
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
    comp: {
      "<component-key-or-_>": {
        lo: "string", hi: "string", unit: "string",
        crit: "string", method: "string"
      }
    }
  }
}
```

For an ordinary (non-panel) test, the single override box is stored under
the synthetic key `"_"`. For a panel test, each component gets its own
entry keyed by its `analyte.key`. **Never assume a flat
`S.local[id].lo`/`.hi`/`.crit` shape** — that was the v1.0-prototype bug;
everything now goes through `S.local[id].comp[key]`. The helper functions
`localBlob()`, `compOverride()`, `saveComponent()`, `saveNote()`, and
`hasLocal()` in `shell.html` are the only sanctioned way to read or write
this — don't access `S.local` directly from new code.

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
