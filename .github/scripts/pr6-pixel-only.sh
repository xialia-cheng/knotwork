#!/usr/bin/env bash
set -euo pipefail
mkdir -p build/pr6-pixel-probe
adb install -r -t catalog/build/outputs/apk/androidTest/debug/catalog-debug-androidTest.apk \
  > build/pr6-pixel-probe/install.txt 2>&1
result=0
adb shell am instrument -w -e class app.knotwork.design.screens.splash.PixelStrokePainterTest \
  app.knotwork.design.test/androidx.test.runner.AndroidJUnitRunner \
  | tee build/pr6-pixel-probe/instrumentation.txt || result=1
adb logcat -d -v threadtime > build/pr6-pixel-probe/logcat.txt
grep -q 'OK (1 test)' build/pr6-pixel-probe/instrumentation.txt || result=1
exit "$result"
