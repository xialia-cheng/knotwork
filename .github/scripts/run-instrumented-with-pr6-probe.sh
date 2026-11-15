#!/usr/bin/env bash
# The emulator action executes script input line by line; keep orchestration in one shell process.
set -euo pipefail
bash .github/scripts/run-instrumented.sh
if [[ "${PR6_STARTUP_PROBE:-false}" == true ]]; then
  mkdir -p build/pr6-startup-evidence/icon-render
  adb pull /sdcard/Android/data/me.lcfuns.zhiwen.debug/files/icon-render/. build/pr6-startup-evidence/icon-render/
  bash .github/scripts/pr6-icon-ui-probe.sh
  if ! bash .github/scripts/pr6-startup-probe.sh; then
    echo probe > "${LOG_DIR:?}/failure-class.txt"
    exit 1
  fi
fi
