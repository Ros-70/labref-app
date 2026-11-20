#!/usr/bin/env bash
# LabRef full verification — six independent methods.
# Usage:  bash qa/run_all.sh        (run from the repo root, after build.py)
set -u
cd "$(dirname "$0")/.."
fail=0
hr(){ printf '\n\033[1m%s\033[0m\n' "── $* ─────────────────────────────────────────"; }

hr "METHOD 2 — data integrity (node, no browser)"
node qa/validate_data.js            || fail=1

# Row identity is checked before anything else looks at behaviour: if a rid has
# changed meaning, every saved My Lab value in that test is already suspect, and
# no amount of UI testing would reveal it.
hr "METHOD 5 — stable row identity (My Lab overrides depend on this)"
node qa/validate_rids.js            || fail=1

hr "METHOD 5b — self-test: the identity guard rejects what it claims to"
node qa/test_rid_guard.js           || fail=1

hr "METHOD 6 — row-selection tie-break guard (ref/method + ladder-fallback)"
node qa/validate_ties.js            || fail=1

hr "METHOD 3 — built-artifact structural audit (static analysis)"
node qa/audit_build.js              || fail=1

hr "METHOD 1 & 4 — behaviour in a real browser + full 180-test corpus sweep"
for t in test_v11_features test_all_tests test_panel test_override_sweep test_reset test5 test3 test6 checkbc fstest test_themes; do
  printf '  %-20s ' "$t"
  if out=$(timeout 300 python3 -I "qa/$t.py" 2>&1); then
    # Some of the older suites report failures in their output but still exit
    # 0, so output is scanned as well as the exit status. The patterns are
    # anchored to the start of a line: unanchored "ERRORS: \[" matched a
    # PASSING line in test_reset.py that happened to read "... new console
    # errors: []", marking a green suite red. A failure detector that fires
    # on the word "errors" appearing anywhere is one that gets ignored.
    # ("FAILURES ABOVE" is test5.py's summary and prints mid-line, so it is
    # matched unanchored -- the phrase cannot occur in a passing run.)
    if echo "$out" | grep -qE "^FAIL|^FAILURES|FAILURES ABOVE|^ERRORS: \[|^Traceback"; then
      echo "FAIL"; echo "$out" | tail -20; fail=1
    else
      echo "pass"
    fi
  else
    echo "FAIL"; echo "$out" | tail -20; fail=1
  fi
done

hr "RESULT"
if [ "$fail" -eq 0 ]; then echo "All six methods passed."; else echo "FAILURES ABOVE"; fi
exit $fail
