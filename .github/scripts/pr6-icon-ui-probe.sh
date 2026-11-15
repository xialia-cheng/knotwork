#!/usr/bin/env bash
# Capture actual emulator UI separately from the Drawable renderings.
set -u
out_dir="build/pr6-startup-evidence/icon-ui"
mkdir -p "$out_dir"
package=me.lcfuns.zhiwen.debug
capture() {
  local name="$1"
  if adb exec-out uiautomator dump /dev/tty > "$out_dir/$name-ui.xml" 2> "$out_dir/$name-ui.err"; then
    adb exec-out screencap -p > "$out_dir/$name.png" 2> "$out_dir/$name-screenshot.err" || true
  else
    printf '%s\n' 'UI hierarchy unavailable; no screenshot captured.' > "$out_dir/$name-unavailable.txt"
  fi
}
if adb shell am start -a android.settings.APPLICATION_DETAILS_SETTINGS -d "package:$package" \
  > "$out_dir/settings-launch.txt" 2>&1; then
  capture settings
else
  printf '%s\n' 'Could not open application details.' > "$out_dir/settings-unavailable.txt"
fi
if adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME \
  > "$out_dir/home-launch.txt" 2>&1; then
  capture home
else
  printf '%s\n' 'Could not open the launcher home.' > "$out_dir/home-unavailable.txt"
fi
if adb shell am start -a android.intent.action.ALL_APPS > "$out_dir/all-apps-launch.txt" 2>&1; then
  capture all-apps
else
  printf '%s\n' 'Launcher does not expose the all-apps intent.' > "$out_dir/all-apps-unavailable.txt"
fi
