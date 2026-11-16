#!/usr/bin/env bash
# Isolated experiment: build and capture real startup, without running the suite.
# A green result here is NOT an instrumented test or production validation.
set -euo pipefail
./gradlew :app:assembleFossDebug --no-daemon --max-workers=2
bash .github/scripts/pr6-startup-probe.sh
