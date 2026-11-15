#!/usr/bin/env bash
# The emulator action executes script input line by line; keep orchestration in one shell process.
set -euo pipefail
bash .github/scripts/run-instrumented.sh
if [[ "${PR6_STARTUP_PROBE:-false}" == true ]]; then
  # Gradle uninstalls the app after connected tests, including its external files.
  # Reinstall the same APKs and rerun only the renderer before pulling its evidence.
  adb install -r app/build/outputs/apk/foss/debug/app-foss-debug.apk
  adb install -r -t app/build/outputs/apk/androidTest/foss/debug/app-foss-debug-androidTest.apk
  mkdir -p build/pr6-startup-evidence/icon-render
  adb shell am instrument -w -e class \
    app.knotwork.android.presentation.icon.LauncherIconRenderingTest \
    me.lcfuns.zhiwen.debug.test/androidx.test.runner.AndroidJUnitRunner \
    | tee build/pr6-startup-evidence/icon-render/instrumentation.txt
  grep -q "OK (1 test)" build/pr6-startup-evidence/icon-render/instrumentation.txt
  adb pull /sdcard/Android/data/me.lcfuns.zhiwen.debug/files/icon-render/. build/pr6-startup-evidence/icon-render/
  bash .github/scripts/pr6-icon-ui-probe.sh
  if ! bash .github/scripts/pr6-startup-probe.sh; then
    echo probe > "${LOG_DIR:?}/failure-class.txt"
    exit 1
  fi
fi
