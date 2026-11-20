# Unit Conversions — reference & verification method

## 1. How the conversion system works

Every test (and every component of a panel test) carries:

```js
units:{ conv:"mg/dL", si:"mmol/L", factor:0.0259 }
```

`si_value = conv_value × factor`. The UI computes nothing dynamically from
molecular formulas — both the conventional and SI numbers in every
`ranges[]` row are **pre-computed and stored directly**, and `factor` is
shown to the clinician as a footnote, not used to derive the displayed
range. This means **`factor` must be independently verified against the
stored `conv`/`si` pair on every row**, not just copied from a reference
table and trusted — a wrong `factor` doesn't break the app, it just quietly
shows a wrong "how to convert" line while the actual range stays correct
(or, worse, if someone later computes a new row from the factor instead of
from a primary source, the error propagates into the range itself).

For a panel test, `units.factor` is a **default only**. Any component whose
true conversion differs gets its own `analyte.factor` — see SCHEMA.md §2b.
Do not assume a panel's components share one factor; verify each one.

## 2. Verification method (use this before adding or trusting any factor)

Given a row's stored `conv.hi`/`conv.lo` and `si.hi`/`si.lo`, the implied
factor is simply `si / conv`. A one-off Node check across the whole data
file catches any row whose stored SI value doesn't match its declared
factor:

```js
const {LABREF_TESTS} = require('./labref_data_v1.10.js'); // after stripping <cite> tags, see build.py
LABREF_TESTS.forEach(t=>{
  t.ranges.forEach(r=>{
    const factor = (r.analyte && r.analyte.factor!=null) ? r.analyte.factor : t.units.factor;
    ["lo","hi"].forEach(k=>{
      if(r.conv[k]!=null && r.si[k]!=null && factor){
        const implied = r.conv[k]*factor;
        const stored  = r.si[k];
        if(Math.abs(implied-stored) > Math.max(0.02, stored*0.02)){
          console.log(t.id, r.grp, k, "implied", implied.toFixed(4), "stored", stored, "factor used", factor);
        }
      }
    });
  });
});
```

This is exactly the method that caught the original Lipid Profile bug
(triglycerides' stored SI values implied 0.0113, not the panel default
0.0259). **Run this check after every content-population batch**, not just
once at the end — it's cheap and catches copy-paste factor errors
immediately rather than after 150 more rows have been added the same way.

## 3. Factors currently in use (v1.10, 180 tests)

| factor    | conv → SI                          | used by |
|-----------|-------------------------------------|---------|
| 0.001     | cells/µL → ×10⁹/L                   | tlc, platelet |
| 0.001     | ng/mL FEU → mg/L FEU                 | ddimer |
| 0.0113    | mg/dL → mmol/L (triglycerides only) | lipid (`analyte.factor`, component `trig`) |
| 0.0259    | mg/dL → mmol/L (cholesterol species) | lipid (panel default: total chol, LDL, HDL, non-HDL) |
| 0.0555    | mg/dL → mmol/L (glucose)             | glucosef |
| 0.111     | mg/dL → mmol/L (lactate)             | lactate |
| 0.113     | mg/g creatinine → mg/mmol creatinine | urineacr |
| 0.1333    | mmHg → kPa                           | abgpanel (PaCO₂, PaO₂ components) |
| 0.25      | mg/dL → mmol/L (calcium, total & ionised alike) | calcium |
| 0.738     | pg/mL → pmol/L (vitamin B12)         | b12 |
| 1         | fL → fL                              | mcv |
| 1         | mEq/L → mmol/L                       | sodium, potassium |
| 1         | U/L → U/L                            | alt, alp |
| 1         | ng/L → ng/L                          | troponin |
| 1         | pg/mL → ng/L                         | ntprobnp |
| 1         | ng/mL → µg/L                         | pct, ferritin |
| 1         | mg/L → mg/L                          | crp |
| 1         | µIU/mL → mIU/L                       | tsh |
| 1         | seconds → seconds / ratio unchanged  | ptinr, aptt |
| 2.496     | ng/mL → nmol/L (25-OH vitamin D)     | vitd |
| 3.96      | µg/mL → µmol/L (phenytoin)           | phenytoin |
| 10        | g/dL → g/L                           | hb, albumin, saag |
| 12.87     | ng/dL → pmol/L (free T4)             | ft4 |
| 17.1      | mg/dL → µmol/L (bilirubin)           | bilirubin |
| 88.4      | mg/dL → µmol/L (creatinine)          | creatinine |
| — (`noConvert`/`null`) | % → mmol/mol IFCC, Qualitative, Titre + pattern | hba1c, bloodculture, ana |

Reuse a factor from this table whenever a new test measures the **same
analyte** as an existing one — e.g. any future test reporting glucose in
mg/dL stays at 0.0555, any future bilirubin fraction stays at 17.1. Do
**not** reuse a factor just because two analytes happen to share a unit
pair (mg/dL → mmol/L appears for five different substances above with five
different factors, because the conversion depends on molar mass, which is
substance-specific).

## 4. Where a `noConvert` or qualitative result applies

Three patterns exist in the current data and should be followed for new
content needing them:

- **No second unit exists**: `analyte:{..., noConvert:true}` — used for pH
  and SaO₂ in the ABG panel. Suppresses the conversion footnote instead of
  showing a wrong one.
- **Qualitative/titre result**: `units:{conv:"Qualitative", si:"Qualitative", factor:null}`
  (blood culture) or `units:{conv:"Titre + pattern", si:"Titre + pattern", factor:null}`
  (ANA) — the UI detects these via `qualitativeTest()` in `shell.html` and
  suppresses both the unit suffix and the conversion footnote app-wide for
  that test.
- **Already-harmonised unit systems**: IFCC HbA1c (`%` → `mmol/mol`) uses
  `factor:null` because the relationship is an affine formula (`IFCC =
  (DCCT − 2.15) × 10.929`), not a simple multiplicative factor — both
  values are pre-computed and stored directly per row instead.
