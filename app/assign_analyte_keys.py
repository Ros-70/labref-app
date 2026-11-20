#!/usr/bin/env python3
"""
One-off: give distinct `analyte.key` to range rows that were bundling two or
more genuinely different measurands under one blank analyte slot on a single
test (e.g. osmolality's "Osmolal gap" sharing no analyte key with osmolality
itself). This was surfaced by the Stage 2a ref/method collision check: rows
that are NOT demographic variants of each other at all, just mislabelled as
sharing an analyte.

Idempotent and scoped: only touches the exact (testId, rid) pairs listed in
TARGETS below, and only rows that don't already carry an analyte key. Reuses
the same string/escape-aware object-walking as assign_rids.py so a brace or
apostrophe inside a clinical label can't throw off the edit.

Usage:  cd app && python3 -I assign_analyte_keys.py [--dry-run]
"""

import glob
import re
import sys

DRY_RUN = "--dry-run" in sys.argv

TARGETS = {
    "osmolality": {
        "r1": ("osm", "Osmolality"),
        "r2": ("gap", "Osmolal Gap"),
    },
    "hbelectrophoresis": {
        "r1": ("hba", "HbA"),
        "r2": ("hba2", "HbA2"),
        "r3": ("hba2", "HbA2"),
        "r4": ("hba2", "HbA2"),
        "r5": ("hbf", "HbF"),
        "r6": ("hbf", "HbF"),
    },
    "csfanalysis": {
        "r1": ("pressure", "Opening Pressure"),
        "r2": ("appearance", "Appearance"),
        "r3": ("wbc", "White Cells"),
        "r4": ("wbc", "White Cells"),
        "r5": ("protein", "Protein"),
        "r6": ("protein", "Protein"),
        "r7": ("glucratio", "CSF:Plasma Glucose Ratio"),
    },
    "urineroutine": {
        "r1": ("appearance", "Appearance"),
        "r2": ("ph", "pH"),
        "r3": ("sg", "Specific Gravity"),
        "r4": ("protein", "Protein"),
        "r5": ("dipstick", "Glucose / Ketones / Nitrite / Bilirubin"),
        "r6": ("rbc", "Red Cells"),
        "r7": ("wbc", "White Cells / Pus Cells"),
        "r8": ("casts", "Casts"),
    },
    "folate": {
        "r1": ("serum", "Serum Folate"),
        "r2": ("serum", "Serum Folate"),
        "r3": ("serum", "Serum Folate"),
        "r4": ("rbc", "Red Cell Folate"),
    },
    # Found by the Stage 2b severity-ladder scan: these aren't value ladders
    # at all, they're two or more genuinely different assays/specimens
    # bundled under one blank analyte key, same as the Stage 2a batch above.
    "crp": {
        "r1": ("crp", "CRP"),
        "r2": ("crp", "CRP"),
        "r3": ("crp", "CRP"),
        "r4": ("hscrp", "hs-CRP"),
        "r5": ("hscrp", "hs-CRP"),
        "r6": ("hscrp", "hs-CRP"),
    },
    "tpoab": {
        "r1": ("tpo", "TPO Antibody"),
        "r2": ("tgab", "Thyroglobulin Antibody"),
    },
    "csfada": {
        "r1": ("csf", "CSF ADA"),
        "r2": ("pleural", "Pleural Fluid ADA"),
        "r3": ("ascitic", "Ascitic Fluid ADA"),
        "r4": ("pericardial", "Pericardial Fluid ADA"),
    },
    # Found by qa/validate_ties.js: SAAG's r3 is a completely different
    # measurement (ascitic fluid absolute neutrophil count, used to
    # diagnose spontaneous bacterial peritonitis) bundled under the same
    # blank analyte slot as the SAAG value itself (r1/r2). Splitting it
    # off also lets r1/r2 stand alone as the clean 2-band SAAG ladder
    # they already are.
    "saag": {
        "r1": ("saag", "SAAG"),
        "r2": ("saag", "SAAG"),
        "r3": ("sbpneut", "Ascitic Fluid Neutrophil Count"),
    },
    # Found by qa/validate_ties.js: PSA's r5 (free:total PSA ratio — a
    # different assay entirely) and r6 (post-prostatectomy biochemical
    # recurrence threshold — a different clinical context, not an
    # age-banded reference range) were bundled under the same blank
    # analyte slot as the age-banded total-PSA ref rows (r1-r4).
    "psa": {
        "r1": ("total", "Total PSA"),
        "r2": ("total", "Total PSA"),
        "r3": ("total", "Total PSA"),
        "r4": ("total", "Total PSA"),
        "r5": ("ratio", "Free:Total PSA Ratio"),
        "r6": ("total", "Total PSA"),
    },
}


def sole_data_module():
    hits = sorted(glob.glob("labref_data_v*.js"))
    if len(hits) != 1:
        sys.exit("expected exactly one data module, found: %s" % hits)
    return hits[0]


def scan_forward(text, start, open_ch, close_ch):
    assert text[start] == open_ch
    depth = 0
    i = start
    quote = None
    n = len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    sys.exit("unbalanced %r starting at offset %d" % (open_ch, start))


def top_level_objects(block):
    spans = []
    i = 0
    quote = None
    n = len(block)
    while i < n:
        c = block[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'`":
            quote = c
            i += 1
            continue
        if c == "{":
            end = scan_forward(block, i, "{", "}")
            spans.append((i, end))
            i = end
            continue
        i += 1
    return spans


def main():
    path = sole_data_module()
    src = open(path, encoding="utf-8").read()

    # Each test is its own top-level { id:"<testId>", ... } object in
    # LABREF_TESTS. Locate the test by its id string directly (unique,
    # unlike "id:" which also appears inside nested tube/panel objects),
    # walk out to that object's own { ... } span, then operate on the
    # ranges[] found ONLY within that span.
    changed = 0
    out = []
    cursor = 0
    pieces = []
    for test_id, targets in TARGETS.items():
        id_m = re.search(r'id\s*:\s*"%s"' % re.escape(test_id), src)
        if not id_m:
            sys.exit("could not find test id %r" % test_id)
        # Walk backward to the '{' that opens this test's own object.
        obj_start = src.rfind("{", 0, id_m.start())
        obj_end = scan_forward(src, obj_start, "{", "}")
        pieces.append((obj_start, obj_end, test_id, targets))
    pieces.sort()

    for (obj_start, obj_end, test_id, targets) in pieces:
        test_block = src[obj_start:obj_end]
        rm = re.search(r"ranges\s*:\s*\[", test_block)
        if not rm:
            sys.exit("no ranges[] found in test object for %r" % test_id)
        arr_open = test_block.index("[", rm.start())
        arr_end = scan_forward(test_block, arr_open, "[", "]")
        body = test_block[arr_open + 1 : arr_end - 1]

        spans = top_level_objects(body)
        rebuilt = []
        prev = 0
        for (s, e) in spans:
            obj = body[s:e]
            rid_m = re.match(r'^\{\s*rid\s*:\s*"([^"]+)"', obj)
            rid = rid_m.group(1) if rid_m else None
            rebuilt.append(body[prev:s])
            if rid in targets and not re.search(r"\banalyte\s*:", obj):
                key, label = targets[rid]
                insert_at = rid_m.end()
                obj = (
                    obj[:insert_at]
                    + ', analyte:{key:"%s",label:"%s"}' % (key, label)
                    + obj[insert_at:]
                )
                changed += 1
            rebuilt.append(obj)
            prev = e
        rebuilt.append(body[prev:])

        # arr_open/arr_end are offsets within test_block; convert to
        # absolute offsets in src before splicing.
        abs_open = obj_start + arr_open
        abs_end = obj_start + arr_end
        out.append(src[cursor : abs_open + 1])
        out.append("".join(rebuilt))
        cursor = abs_end - 1

    out.append(src[cursor:])
    result = "".join(out)

    print("analyte keys assigned: %d" % changed)
    if DRY_RUN:
        print("--dry-run: nothing written")
        return
    if changed == 0:
        print("nothing to do")
        return
    open(path, "w", encoding="utf-8").write(result)
    print("wrote %s" % path)


if __name__ == "__main__":
    main()
