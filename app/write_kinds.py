#!/usr/bin/env python3
"""
Stage 2b: write the classified `kind` (ref/method/dx/target/cutoff/note) into
every range row of the data module, from /tmp/row_kind_proposals.json
(classify_rows.py's heuristic + app/row_kinds_overrides.json's hand-reviewed
corrections, already merged there — regenerate it first: see classify_rows.py
--json). This is additive content metadata, NOT an identity dimension: adding
`kind` does not change what population/value a row's rid refers to, so it
does not require retiring or reassigning any rid (unlike adding `analyte`,
which does — see retire_and_reassign.py).

Idempotent: a row that already has `kind` is left untouched, so re-running
after a manual correction never clobbers it.

Usage:  cd app && python3 -I write_kinds.py [--dry-run]
    (classify_rows.py --json must have been run first, against the CURRENT
    data module, so /tmp/row_kind_proposals.json's rids match.)
"""

import glob
import json
import re
import sys

DRY_RUN = "--dry-run" in sys.argv

PROPOSALS_PATH = "/tmp/row_kind_proposals.json"


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
    proposals = json.load(open(PROPOSALS_PATH, encoding="utf-8"))

    changed = 0
    missing_test = []

    # Locate each test by its own unique id string directly (robust against
    # nested "id:" fields inside tube/panel sub-objects, unlike a backward
    # text search), exactly as assign_analyte_keys.py / retire_and_reassign.py
    # do — then operate only within that test's own { ... } span. Search only
    # from LABREF_TESTS onward: a test id can collide with an EARLIER, wholly
    # unrelated id — e.g. "esr" is also a LABREF_TUBES id, "lipid" also a
    # LABREF_CATEGORIES id — and the first match in the whole file would
    # silently resolve to the wrong object otherwise.
    tests_marker = re.search(r"const\s+LABREF_TESTS\s*=\s*\[", src)
    if not tests_marker:
        sys.exit("could not find LABREF_TESTS array start")
    search_from = tests_marker.end()

    pieces = []
    for test_id in proposals:
        id_m = re.search(r'id\s*:\s*"%s"' % re.escape(test_id), src[search_from:])
        if not id_m:
            missing_test.append(test_id)
            continue
        abs_pos = search_from + id_m.start()
        obj_start = src.rfind("{", 0, abs_pos)
        obj_end = scan_forward(src, obj_start, "{", "}")
        pieces.append((obj_start, obj_end, test_id))
    pieces.sort()

    out = []
    cursor = 0
    for (obj_start, obj_end, test_id) in pieces:
        test_block = src[obj_start:obj_end]
        rm = re.search(r"ranges\s*:\s*\[", test_block)
        if not rm:
            continue
        arr_open = test_block.index("[", rm.start())
        arr_end = scan_forward(test_block, arr_open, "[", "]")
        body = test_block[arr_open + 1 : arr_end - 1]

        kinds = proposals[test_id]
        spans = top_level_objects(body)
        rebuilt = []
        prev = 0
        for (s, e) in spans:
            obj = body[s:e]
            rebuilt.append(body[prev:s])
            rid_m = re.match(r'^\{\s*rid\s*:\s*"([^"]+)"', obj)
            rid = rid_m.group(1) if rid_m else None
            if rid and rid in kinds and not re.search(r"\bkind\s*:", obj):
                insert_at = rid_m.end()
                obj = obj[:insert_at] + ', kind:"%s"' % kinds[rid] + obj[insert_at:]
                changed += 1
            rebuilt.append(obj)
            prev = e
        rebuilt.append(body[prev:])

        abs_open = obj_start + arr_open
        abs_end = obj_start + arr_end
        out.append(src[cursor : abs_open + 1])
        out.append("".join(rebuilt))
        cursor = abs_end - 1

    out.append(src[cursor:])
    result = "".join(out)

    print("kind fields written: %d" % changed)
    if missing_test:
        print("WARNING: ranges[] with no resolvable/known test id: %s" % missing_test)
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
