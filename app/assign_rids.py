#!/usr/bin/env python3
"""
Assign a stable `rid` to every range row in the clinical data module.

WHY THIS EXISTS
---------------
A user's own lab values (My Lab) are stored against individual reference rows.
Those overrides live in localStorage on the user's device and must survive
every future content update. If rows were identified by their position in the
`ranges` array, then inserting one row in a later version would silently slide
every saved override in that test onto the WRONG stratum — a clinician's
adult-female range quietly becoming the newborn range, with nothing on screen
to show it had happened. That is the single worst failure this app could have,
so rows carry an explicit identity instead.

THE RULES (enforced by qa/validate_rids.js on every build)
----------------------------------------------------------
  * `rid` is unique within its test. Overrides key on (testId, rid), so the
    analyte key is deliberately NOT part of a row's identity — one less thing
    that can change under a saved override.
  * A rid, once published, never changes meaning. Its stratum dimensions
    (sex / age / preg / analyte) are frozen. Correcting an interval's numbers
    is fine and expected; re-pointing a rid at a different population is not.
  * rids are append-only. Removing one requires an explicit `retired` entry in
    qa/rid_baseline.json, and a retired rid is never reused.

This script is IDEMPOTENT: a row that already has a rid is left exactly as it
is, so re-running can never renumber published ids. New rows get the next
number above the highest already used in that test.

Usage:  cd app && python3 -I assign_rids.py [--dry-run]
"""

import glob
import re
import sys

DRY_RUN = "--dry-run" in sys.argv


def sole_data_module():
    hits = sorted(glob.glob("labref_data_v*.js"))
    if len(hits) != 1:
        sys.exit("expected exactly one data module, found: %s" % hits)
    return hits[0]


def scan_forward(text, start, open_ch, close_ch):
    """Return the index just past the bracket pair opening at `start`.

    String- and escape-aware, so a brace or bracket inside a clinical label
    (or an apostrophe in prose) cannot throw the depth count off.
    """
    assert text[start] == open_ch, "scan_forward must begin on %r" % open_ch
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
    """Yield (start, end) spans of the top-level {...} entries inside an array
    body, skipping objects nested within them."""
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


RID_AT_TOP = re.compile(r'^\{\s*rid\s*:')


def main():
    path = sole_data_module()
    src = open(path, encoding="utf-8").read()

    out = []
    cursor = 0
    stats = {"tests": 0, "rows": 0, "assigned": 0, "kept": 0}

    for m in re.finditer(r"ranges\s*:\s*\[", src):
        arr_open = src.index("[", m.start())
        if arr_open < cursor:
            continue  # inside a block already processed
        arr_end = scan_forward(src, arr_open, "[", "]")
        body = src[arr_open + 1:arr_end - 1]

        spans = top_level_objects(body)
        if not spans:
            continue
        stats["tests"] += 1

        # Highest rid already present in this test — new rows continue above it,
        # so a gap left by a retired row is never backfilled and reused.
        used = [int(x) for x in re.findall(r'rid\s*:\s*"r(\d+)"', body)]
        next_n = (max(used) + 1) if used else 1

        rebuilt = []
        prev = 0
        for (s, e) in spans:
            rebuilt.append(body[prev:s])
            obj = body[s:e]
            stats["rows"] += 1
            if RID_AT_TOP.match(obj) or re.match(r'^\{[^{]*?\brid\s*:', obj):
                rebuilt.append(obj)          # already identified — never touch
                stats["kept"] += 1
            else:
                rebuilt.append('{ rid:"r%d", ' % next_n + obj[1:].lstrip())
                next_n += 1
                stats["assigned"] += 1
            prev = e
        rebuilt.append(body[prev:])

        out.append(src[cursor:arr_open + 1])
        out.append("".join(rebuilt))
        cursor = arr_end - 1

    out.append(src[cursor:])
    result = "".join(out)

    print("tests with ranges : %d" % stats["tests"])
    print("rows seen         : %d" % stats["rows"])
    print("rids assigned     : %d" % stats["assigned"])
    print("rids already set  : %d (left untouched)" % stats["kept"])

    if DRY_RUN:
        print("\n--dry-run: nothing written")
        return
    if stats["assigned"] == 0:
        print("\nnothing to do")
        return

    open(path, "w", encoding="utf-8").write(result)
    print("\nwrote %s" % path)


if __name__ == "__main__":
    main()
