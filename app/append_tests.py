#!/usr/bin/env python3
"""
Splice a chunk of new test records into LABREF_TESTS in the data file.

    python3 -I append_tests.py chunks/<file>.js

The chunk file holds bare record literals separated by commas, e.g.
    { id:"urea", ... },
    { id:"chloride", ... }
They are inserted immediately before the closing `];` of LABREF_TESTS.
Refuses to insert a record whose id already exists, so re-running a chunk
cannot silently duplicate content.
"""
import sys, re, io, os

import glob as _glob
_hits = sorted(_glob.glob("labref_data_v*.js"))
assert len(_hits) == 1, "expected exactly one data module, found: %s" % _hits
DATA = _hits[0]

def main(chunk_path):
    data = io.open(DATA, encoding="utf-8").read()
    chunk = io.open(chunk_path, encoding="utf-8").read().strip()
    if not chunk:
        sys.exit("chunk is empty")

    # locate the LABREF_TESTS array and its closing bracket
    start = data.index("const LABREF_TESTS = [")
    end = data.index("\n];", start)

    existing = set(re.findall(r"^\s+id:\"([a-z0-9]+)\"", data, re.M))
    incoming = re.findall(r'^\s*\{\s*\n?\s*id:"([a-z0-9]+)"', chunk, re.M)
    if not incoming:
        incoming = re.findall(r'id:"([a-z0-9]+)"', chunk)[:1]
    dupes = [i for i in incoming if i in existing]
    if dupes:
        sys.exit("refusing to insert — these ids already exist: " + ", ".join(sorted(set(dupes))))

    body = data[:end].rstrip()
    if not body.endswith(","):
        body += ","
    merged = body + "\n\n" + chunk.rstrip().rstrip(",") + "\n" + data[end+1:]
    io.open(DATA, "w", encoding="utf-8").write(merged)

    total = len(re.findall(r"^\s+id:\"[a-z0-9]+\"", merged, re.M))
    print(f"inserted {len(incoming)} record(s) from {os.path.basename(chunk_path)} -> {total} tests total")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
