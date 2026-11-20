#!/usr/bin/env python3
"""
Propose a `kind` for every range row, for review before anything is written.

The six kinds, decided in v2.0 (see SCHEMA.md):

  ref     a reference interval — what "normal" is for a population.
          OVERRIDABLE in My Lab.
  method  a reference interval for a particular measurement method, specimen
          or assay label (venous vs arterial lactate, total vs free phenytoin,
          hs-cTnI Abbott vs hs-cTnT, US-FDA vs non-US troponin labelling).
          Selected by what the LAB measures, not by the patient.
          OVERRIDABLE in My Lab — this is the row most worth overriding,
          because it is exactly what differs between laboratories.
  dx      a diagnostic or classification threshold (HbA1c diabetes, vitamin D
          deficiency, ACR A1/A2/A3). Guideline-owned. LOCKED.
  target  a treatment target (therapeutic INR by indication, LDL by CV risk,
          drug therapeutic levels). LOCKED.
  cutoff  a decision cutoff for a specific clinical question (D-dimer
          exclusion, NT-proBNP rule-in/rule-out, amylase for pancreatitis,
          lactate sepsis threshold). LOCKED.
  note    narrative, or a different measurand reported alongside the parent
          test (SBP fluid-neutrophil threshold, blood-culture time to
          positivity). Never numeric, never unit-converted. LOCKED.

This script only PROPOSES. Anything it cannot classify confidently is marked
REVIEW and must be resolved by hand in row_kinds_overrides.json, which is
applied on top of the heuristics and serves as the audit trail for every
judgement call.

Usage:
  cd app && python3 -I classify_rows.py            # report proposals
  cd app && python3 -I classify_rows.py --write     # write `kind` into the data
"""

import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OVERRIDES = os.path.join(HERE, "row_kinds_overrides.json")


def load_corpus():
    """Read the corpus through node, so the single source of truth stays the JS."""
    data = sorted(glob.glob(os.path.join(HERE, "labref_data_v*.js")))
    if len(data) != 1:
        sys.exit("expected exactly one data module, found: %s" % data)
    js = """
      const fs=require('fs'); const g={};
      new Function('g', fs.readFileSync(%s,'utf8') + '; g.T=LABREF_TESTS;')(g);
      const out=g.T.map(t=>({
        id:t.id, cat:t.cat, name:t.name, units:t.units,
        rows:(t.ranges||[]).map(r=>({
          rid:r.rid, grp:r.grp, sex:r.sex, age:r.age, preg:r.preg,
          analyte: r.analyte ? r.analyte.key : null,
          kind: r.kind || null,
          hasNum: !!(r.conv && (r.conv.lo!=null || r.conv.hi!=null)),
          txt: (r.conv && r.conv.txt) || null
        }))
      }));
      process.stdout.write(JSON.stringify(out));
    """ % json.dumps(data[0])
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# --- label patterns, most specific first -----------------------------------
# Deliberately narrow. A pattern that is not clearly decisive is left out, so
# the row falls through to REVIEW rather than being guessed at.

METHOD = re.compile(
    r"\b(venous|arterial|capillary)\b"
    r"|\((total|free|ionis|ionized)\)"
    r"|\b(abbott|roche|siemens|beckman|ortho)\b"
    r"|\b(us\s*fda|fda|non-?us|guideline\s*/|label)\b"
    r"|\boverall\s+99th\b|\b99th\s+centile\b"
    r"|—\s*(male|female)\s*/\s*(male|female)\b"
    r"|\b(immunoassay|lc-?ms|hplc|clia|elisa)\b", re.I)

TARGET = re.compile(
    r"\b(therapeutic|treatment\s+target|target|trough|peak|prophyla"
    r"|treatment\s+line|legal\s+(driving\s+)?limit|action\s+level|chelation)\b", re.I)

DX = re.compile(
    r"\b(diabetes|prediabetes|impaired\s+(fasting|glucose)|gdm)\b"
    r"|\b(deficien\w*|insufficien\w*|sufficien\w*|toxicity|replete)\b"
    r"|\b(a1|a2|a3)\s*—|\b(g1|g2|g3a|g3b|g4|g5)\b"
    r"|\b(mildly|moderately|severely)\s+increased\b"
    r"|\b(low|moderate|high)\s+positive\b|\bnegative\b|\bborderline\b"
    r"|\b(mild|marked|moderate)\s+rise\b"
    r"|\boptimal\b|\bdesirable\b|\bhigh\s+titre\b"
    r"|\binappropriate\b|\bexcluded\b|\bsuggest\w*\b"
    r"|\bhypogonadism\b|\brecurrence\b|\bhighly\s+suggestive\b"
    r"|\b(sle|lupus)-specific\b|\bimmunosuppression\b"
    r"|\bovarian\s+reserve\b|\bhomocystinuria\b"
    r"|\b(stage|grade|class)\s*[ivx0-9]\b"
    r"|\b(anaemia|anemia)\b|\bmicroalbumin|\bmacroalbumin", re.I)

CUTOFF = re.compile(
    r"\b(threshold|cut-?off|exclusion|rule[-\s]?(in|out)|diagnostic)\b"
    r"|\b(likely|unlikely)\b|\bgrey\s*zone\b"
    r"|\b(age-?adjusted)\b|\brisk\b|\bsepsis\b|\bsuspicion\b"
    r"|\bdiscriminatory\s+zone\b|\bbiochemical\s+recurrence\b"
    r"|\brefer\b|\bindicated\b|\bconsider\b|\bremove\s+from\s+exposure\b"
    r"|\bhaemodialysis|\bdialysis\b", re.I)

# A row label that plainly names a population and nothing else.
POP_ONLY = re.compile(
    r"^(adult|adults?\s*\(|newborn|neonate|infant|child|children|adolescent|elderly"
    r"|adult\s+(male|female)|male|female|pregnan\w*|pregnancy\s*t[123]"
    r"|expected\s+result|normal|reference)\b", re.I)


def propose(test, row, triple_counts):
    """Return (kind, confidence) for a row. confidence in {'auto','review'}."""
    grp = (row["grp"] or "").strip()
    triple = (row["sex"] or "any", row["age"] or "any", row["preg"] or "none")
    key = (row["analyte"], triple)
    shares_triple = triple_counts.get(key, 0) > 1

    # A row carrying only narrative text, no numbers at all, is a note UNLESS
    # its label marks it as a threshold/target expressed in prose.
    if not row["hasNum"]:
        if TARGET.search(grp):
            return "target", "auto"
        if CUTOFF.search(grp) or DX.search(grp):
            return "cutoff" if CUTOFF.search(grp) else "dx", "review"
        return "note", "auto" if row["txt"] else "review"

    # Numeric rows.
    if TARGET.search(grp):
        return "target", "auto"
    if METHOD.search(grp):
        return "method", "auto"
    if DX.search(grp):
        return "dx", "auto"
    if CUTOFF.search(grp):
        return "cutoff", "auto"

    # Nothing matched. A unique population with a population-only label is a
    # plain reference interval; anything else needs a human.
    if not shares_triple and POP_ONLY.match(grp):
        return "ref", "auto"
    if not shares_triple:
        return "ref", "review"
    return "ref", "review"


def main():
    corpus = load_corpus()
    overrides = {}
    if os.path.exists(OVERRIDES):
        raw = json.load(open(OVERRIDES))
        overrides = raw.get("rows", raw)

    proposals = {}
    stats = {"auto": 0, "review": 0, "overridden": 0}
    counts = {}

    for t in corpus:
        triple_counts = {}
        for r in t["rows"]:
            k = (r["analyte"], (r["sex"] or "any", r["age"] or "any", r["preg"] or "none"))
            triple_counts[k] = triple_counts.get(k, 0) + 1

        proposals[t["id"]] = {}
        for r in t["rows"]:
            kind, conf = propose(t, r, triple_counts)
            ov = overrides.get(t["id"], {}).get(r["rid"])
            if ov:
                kind, conf = (ov["kind"] if isinstance(ov, dict) else ov), "override"
                stats["overridden"] += 1
            else:
                stats[conf] += 1
            proposals[t["id"]][r["rid"]] = kind
            counts[kind] = counts.get(kind, 0) + 1

    total = sum(counts.values())
    print("rows: %d   (auto %d, overridden %d, NEEDS REVIEW %d)"
          % (total, stats["auto"], stats["overridden"], stats["review"]))
    print("kinds: " + "  ".join("%s=%d" % (k, counts[k]) for k in sorted(counts)))

    if "--json" in sys.argv:
        json.dump(proposals, open("/tmp/row_kind_proposals.json", "w"), indent=1)
        print("\nwrote /tmp/row_kind_proposals.json")

    if "--review" in sys.argv:
        print("\n--- rows still needing a human decision ---")
        for t in corpus:
            tc = {}
            for r in t["rows"]:
                k = (r["analyte"], (r["sex"] or "any", r["age"] or "any", r["preg"] or "none"))
                tc[k] = tc.get(k, 0) + 1
            flagged = []
            for r in t["rows"]:
                if overrides.get(t["id"], {}).get(r["rid"]):
                    continue
                kind, conf = propose(t, r, tc)
                if conf == "review":
                    flagged.append((r, kind))
            if flagged:
                print("\n### %s (%s)  units=%s" % (t["id"], t["cat"], (t["units"] or {}).get("conv")))
                for r, kind in flagged:
                    print("   %-4s %-7s [%s|%s|%s]%s %s%s" % (
                        r["rid"], "->" + kind,
                        r["sex"] or "any", r["age"] or "any", r["preg"] or "none",
                        ("/" + r["analyte"]) if r["analyte"] else "",
                        r["grp"],
                        ("   txt=" + r["txt"][:60]) if r["txt"] else ""))

    return proposals


if __name__ == "__main__":
    main()
