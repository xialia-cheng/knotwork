#!/usr/bin/env bash
# The emulator action executes script input line by line; keep orchestration in one shell process.
set -euo pipefail
bash .github/scripts/run-instrumented.sh
catalog_result=0
if [[ "${PR6_STARTUP_PROBE:-false}" == true ]]; then
  # Exercise the original-pixel time textures on the emulator before recording playback.
  ./gradlew :catalog:connectedDebugAndroidTest --no-daemon --max-workers=2 || catalog_result=$?
  # AGP can report success even if the runner failed to start. Reinstall and
  # require the explicit one-test JUnit result before accepting pixel evidence.
  mkdir -p build/pr6-startup-evidence/pixel-render
  catalog_apk=catalog/build/outputs/apk/androidTest/debug/catalog-debug-androidTest.apk
  if adb install -r -t "$catalog_apk" > build/pr6-startup-evidence/pixel-render/install.txt 2>&1; then
    adb shell am instrument -w -e class \
      app.knotwork.design.screens.splash.PixelStrokePainterTest \
      app.knotwork.design.test/androidx.test.runner.AndroidJUnitRunner \
      | tee build/pr6-startup-evidence/pixel-render/instrumentation.txt || catalog_result=1
    grep -q 'OK (1 test)' build/pr6-startup-evidence/pixel-render/instrumentation.txt || catalog_result=1
    adb pull /sdcard/Android/data/app.knotwork.design.test/files/handoff-pixels/. \
      build/pr6-startup-evidence/pixel-render/ || catalog_result=1
  else
    catalog_result=1
  fi
  # Gradle uninstalls the app after connected tests, including its external files.
  # Reinstall the same APKs and rerun only the renderer before pulling its evidence.
  adb install -r app/build/outputs/apk/foss/debug/app-foss-debug.apk
  adb install -r -t app/build/outputs/apk/androidTest/foss/debug/app-foss-debug-androidTest.apk
  mkdir -p build/pr6-startup-evidence/recovery
  adb shell am instrument -w -e class \
    app.knotwork.android.presentation.ui.splash.SplashRecoveryDeviceTest \
    me.lcfuns.zhiwen.debug.test/androidx.test.runner.AndroidJUnitRunner \
    | tee build/pr6-startup-evidence/recovery/instrumentation.txt || catalog_result=1
  grep -q 'OK (1 test)' build/pr6-startup-evidence/recovery/instrumentation.txt || catalog_result=1
  mkdir -p build/pr6-startup-evidence/first-frame
  adb shell am instrument -w -e class \
    app.knotwork.android.presentation.ui.splash.SplashFrameDeviceTest \
    me.lcfuns.zhiwen.debug.test/androidx.test.runner.AndroidJUnitRunner \
    | tee build/pr6-startup-evidence/first-frame/instrumentation.txt || catalog_result=1
  grep -q 'OK (1 test)' build/pr6-startup-evidence/first-frame/instrumentation.txt || catalog_result=1
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

if [[ "$catalog_result" -ne 0 ]]; then
  echo test > "${LOG_DIR:?}/failure-class.txt"
  exit "$catalog_result"
fi
