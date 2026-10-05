#!/usr/bin/env bash
# Run every step in video order and print what each one finds.
# Takes about two minutes; step 7 plays 2,200 chaos runs.
# The clock is simulated, so the output is the same on every machine.
# The bonus (python3 live.py) uses real sockets and the real clock, so
# its timings change on every run; one run is saved in live-output.txt.
set -e
cd "$(dirname "$0")"
for step in step1_log step2_majority step3_election step4_split_vote \
            step5_replication step6_safety step7_chaos; do
  echo "## $step"; python3 $step.py
done
echo "## solutions/sizes"; python3 solutions/sizes.py
echo "## tests"; python3 tests.py
