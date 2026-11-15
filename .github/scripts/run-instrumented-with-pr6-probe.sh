#!/usr/bin/env bash
# The emulator action executes script input line by line; keep orchestration in one shell process.
set -euo pipefail
bash .github/scripts/run-instrumented.sh
if [[ "${PR6_STARTUP_PROBE:-false}" == true ]]; then
  if ! bash .github/scripts/pr6-startup-probe.sh; then
    echo probe > "${LOG_DIR:?}/failure-class.txt"
    exit 1
  fi
fi
