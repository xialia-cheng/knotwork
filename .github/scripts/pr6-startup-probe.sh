#!/usr/bin/env bash
# Capture the real installed app's cold start on the existing PR #6 emulator legs.
# These recordings are evidence, not an assertion that the requested animation exists.
set -euo pipefail

package='me.lcfuns.zhiwen.debug'
component="$package/app.knotwork.android.presentation.ui.MainActivity"
out_dir="build/pr6-startup-evidence/api${PR6_API_LEVEL:?}"
mkdir -p "$out_dir"
apk_path=$(find app/build/outputs/apk/foss/debug -maxdepth 1 -name '*.apk' -print -quit)
if [[ -z "$apk_path" ]]; then
  echo 'FOSS debug APK was not produced by the instrumented build' >&2
  exit 1
fi

{
  printf 'commit=%s\n' "${GITHUB_SHA:-unknown}"
  printf 'pull_request_head=%s\n' "${PR6_HEAD_SHA:-unknown}"
  printf 'api_expected=%s\n' "$PR6_API_LEVEL"
  printf 'api_actual=%s\n' "$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
  printf 'component=%s\n' "$component"
  printf 'apk_sha256='
  sha256sum "$apk_path"
  printf 'recording=emulator screenrecord; elapsed times are approximate host timestamps\n'
  printf 'limitation=recordings show actual launch, not an automated animation or reduced-motion verdict\n'
} > "$out_dir/metadata.txt"

# connectedAndroidTest may uninstall its target; reinstall precisely the tested APK if needed.
if ! adb shell pm path "$package" | grep -q '^package:'; then
  adb install -r "$apk_path" > "$out_dir/install.log"
fi
# Avoid a notification permission dialog obscuring the startup frame on the disposable CI emulator.
adb shell pm grant "$package" android.permission.POST_NOTIFICATIONS >/dev/null
adb shell wm dismiss-keyguard >/dev/null
adb shell input keyevent 82 >/dev/null

keys=(window_animation_scale transition_animation_scale animator_duration_scale)
original=()
for key in "${keys[@]}"; do
  original+=("$(adb shell settings get global "$key" | tr -d '\r')")
done
restore_settings() {
  local index key value
  for index in "${!keys[@]}"; do
    key=${keys[$index]}
    value=${original[$index]}
    if [[ "$value" == null ]]; then
      adb shell settings delete global "$key" >/dev/null || true
    else
      adb shell settings put global "$key" "$value" >/dev/null || true
    fi
  done
  adb shell am force-stop "$package" >/dev/null 2>&1 || true
}
trap restore_settings EXIT

capture() {
  local label="$1" window="$2" transition="$3" animator="$4"
  local remote="/sdcard/pr6-startup-${label}.mp4" recorder
  adb shell settings put global window_animation_scale "$window"
  adb shell settings put global transition_animation_scale "$transition"
  adb shell settings put global animator_duration_scale "$animator"
  {
    printf 'window=%s\ntransition=%s\nanimator=%s\n' "$window" "$transition" "$animator"
    printf 'before_force_stop_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)"
    adb shell settings get global window_animation_scale
    adb shell settings get global transition_animation_scale
    adb shell settings get global animator_duration_scale
  } > "$out_dir/${label}.txt"
  adb shell am force-stop "$package"
  adb shell input keyevent HOME
  adb shell rm -f "$remote"
  # The first emulator launch can take over five seconds; keep recording through the app handoff.
  adb shell screenrecord --time-limit 12 --bit-rate 2000000 "$remote" > "$out_dir/${label}-record.log" 2>&1 &
  recorder=$!
  sleep 1
  printf 'launch_requested_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" >> "$out_dir/${label}.txt"
  adb shell am start -W -n "$component" >> "$out_dir/${label}.txt"
  if ! grep -q '^Status: ok' "$out_dir/${label}.txt"; then
    echo "Activity did not report a successful launch: $label" >&2
    return 1
  fi
  printf 'launch_returned_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" >> "$out_dir/${label}.txt"
  wait "$recorder"
  adb pull "$remote" "$out_dir/${label}.mp4" >/dev/null
  test -s "$out_dir/${label}.mp4"
  adb shell rm -f "$remote"
}

# Separate animator=0 and transition=0 from the all-off configuration.
capture normal 1 1 1
capture half 0.5 0.5 0.5
capture double 2 2 2
capture animator_off 1 1 0
capture transition_off 1 0 1
capture all_off 0 0 0
adb logcat -d -v threadtime > "$out_dir/logcat.txt"
