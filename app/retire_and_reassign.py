#!/usr/bin/env python3
"""
One-off: the rid identity guard (qa/validate_rids.js) correctly caught that
assign_analyte_keys.py changed what 27 published rids MEAN (adding a real
analyte.key where there was none is exactly the kind of stratum change the
guard exists to catch). Since v2.0 has never shipped, there is no live My Lab
override pointing at these rids yet -- but the guard makes no pre-release
exception, on purpose, so this does the guard's own prescribed fix: retire
the old rid and give the corrected row a brand new one, continuing above the
historical ceiling for that test, exactly as assign_rids.py would for an
appended row.

For each affected test every existing row moves (old rid r1..rN -> new rid
r(N+1)..r(2N), same order) because every row in these five tests got an
analyte key. Old rids are recorded under "retired" in rid_baseline.json.

Usage:  cd app && python3 -I retire_and_reassign.py [--dry-run]
"""

import glob
import json
import re
import sys

DRY_RUN = "--dry-run" in sys.argv

# test id -> ordered list of its current rids, all being retired+reassigned
AFFECTED = {
    "osmolality": ["r1", "r2"],
    "hbelectrophoresis": ["r1", "r2", "r3", "r4", "r5", "r6"],
    "folate": ["r1", "r2", "r3", "r4"],
    "urineroutine": ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"],
    "csfanalysis": ["r1", "r2", "r3", "r4", "r5", "r6", "r7"],
    "crp": ["r1", "r2", "r3", "r4", "r5", "r6"],
    "tpoab": ["r1", "r2"],
    "csfada": ["r1", "r2", "r3", "r4"],
    "saag": ["r1", "r2", "r3"],
    "psa": ["r1", "r2", "r3", "r4", "r5", "r6"],
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


def main():
    path = sole_data_module()
    src = open(path, encoding="utf-8").read()

    mapping = {}  # testId -> { oldRid: newRid }
    for test_id, old_rids in AFFECTED.items():
        n = len(old_rids)
        mapping[test_id] = {old: "r%d" % (n + i + 1) for i, old in enumerate(old_rids)}

    changed = 0
    pieces = []
    for test_id in AFFECTED:
        id_m = re.search(r'id\s*:\s*"%s"' % re.escape(test_id), src)
        if not id_m:
            sys.exit("could not find test id %r" % test_id)
        obj_start = src.rfind("{", 0, id_m.start())
        obj_end = scan_forward(src, obj_start, "{", "}")
        pieces.append((obj_start, obj_end, test_id))
    pieces.sort()

    out = []
    cursor = 0
    for (obj_start, obj_end, test_id) in pieces:
        test_block = src[obj_start:obj_end]
        rm = re.search(r"ranges\s*:\s*\[", test_block)
        arr_open = test_block.index("[", rm.start())
        arr_end = scan_forward(test_block, arr_open, "[", "]")
        body = test_block[arr_open + 1 : arr_end - 1]

        m = mapping[test_id]

        def repl(match):
            old = match.group(1)
            if old in m:
                nonlocal_changed[0] += 1
                return 'rid:"%s"' % m[old]
            return match.group(0)

        nonlocal_changed = [0]
        new_body = re.sub(r'rid\s*:\s*"(r\d+)"', repl, body)
        changed += nonlocal_changed[0]

        abs_open = obj_start + arr_open
        abs_end = obj_start + arr_end
        out.append(src[cursor : abs_open + 1])
        out.append(new_body)
        cursor = abs_end - 1

    out.append(src[cursor:])
    result = "".join(out)

    print("rids reassigned: %d" % changed)
    for test_id, m in mapping.items():
        print("  %s: %s" % (test_id, ", ".join("%s->%s" % (k, v) for k, v in m.items())))

    if DRY_RUN:
        print("--dry-run: nothing written")
        return
    open(path, "w", encoding="utf-8").write(result)
    print("wrote %s" % path)

    # Record the old rids as retired in the baseline.
    baseline_path = "../qa/rid_baseline.json"
    baseline = json.load(open(baseline_path, encoding="utf-8"))
    retired = baseline.setdefault("retired", {})
    for test_id, old_rids in AFFECTED.items():
        existing = set(retired.get(test_id, []))
        existing.update(old_rids)
        retired[test_id] = sorted(existing, key=lambda r: int(r[1:]))
    json.dump(baseline, open(baseline_path, "w", encoding="utf-8"), indent=1)
    open(baseline_path, "a", encoding="utf-8").write("\n")
    print("retired rids recorded in %s" % baseline_path)


if __name__ == "__main__":
    main()
