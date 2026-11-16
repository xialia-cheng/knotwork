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
  printf 'variant=isolated diagnostic; system and app animation timings scaled 8x\n'
  printf 'component=%s\n' "$component"
  printf 'apk_sha256='
  sha256sum "$apk_path"
  printf 'recording=emulator screenrecord; elapsed times are approximate host timestamps\n'
  printf 'limitation=recordings show actual launch, not an automated animation or reduced-motion verdict\n'
} > "$out_dir/metadata.txt"
# Make the built APK hash visible in the CI log as well as in the evidence artifact.
cat "$out_dir/metadata.txt"

# connectedAndroidTest may uninstall its target; reinstall precisely the tested APK if needed.
if ! adb shell pm path "$package" | grep -q '^package:'; then
  adb install -r "$apk_path" > "$out_dir/install.log"
fi
# Avoid a notification permission dialog obscuring the startup frame on the disposable CI emulator.
adb shell pm grant "$package" android.permission.POST_NOTIFICATIONS >/dev/null
adb shell wm dismiss-keyguard >/dev/null
adb shell input keyevent 82 >/dev/null

original_night="$(adb shell cmd uimode night | tr -d '\r')"
original_trace_tag="$(adb shell getprop log.tag.PR6Handoff | tr -d '\r')"
adb shell setprop log.tag.PR6Handoff DEBUG
original_font_scale="$(adb shell settings get system font_scale | tr -d '\r')"
original_override_size="$(adb shell wm size | tr -d '\r' | sed -n 's/^Override size: //p')"
keys=(window_animation_scale transition_animation_scale animator_duration_scale)
original=()
for key in "${keys[@]}"; do
  original+=("$(adb shell settings get global "$key" | tr -d '\r')")
done
restore_settings() {
  local index key value
  adb shell setprop log.tag.PR6Handoff "$original_trace_tag" >/dev/null 2>&1 || true
  adb shell atrace --async_stop gfx view wm am >/dev/null 2>&1 || true
  for index in "${!keys[@]}"; do
    key=${keys[$index]}
    value=${original[$index]}
    if [[ "$value" == null ]]; then
      adb shell settings delete global "$key" >/dev/null || true
    else
      adb shell settings put global "$key" "$value" >/dev/null || true
    fi
  done
  if [[ "$original_font_scale" == null ]]; then
    adb shell settings delete system font_scale >/dev/null || true
  else
    adb shell settings put system font_scale "$original_font_scale" >/dev/null || true
  fi
  if [[ -n "$original_override_size" ]]; then
    adb shell wm size "$original_override_size" >/dev/null || true
  else
    adb shell wm size reset >/dev/null || true
  fi
  case "$original_night" in
    *yes*) adb shell cmd uimode night yes >/dev/null 2>&1 || true ;;
    *no*) adb shell cmd uimode night no >/dev/null 2>&1 || true ;;
    *auto*) adb shell cmd uimode night auto >/dev/null 2>&1 || true ;;
  esac
  adb shell am force-stop "$package" >/dev/null 2>&1 || true
}
trap restore_settings EXIT

capture() {
  local label="$1" window="$2" transition="$3" animator="$4"
  local remote="/sdcard/pr6-startup-${label}.mp4" recorder trace_started=false
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
  if [[ "$label" == normal || "$label" == double || "$label" == dark_normal ]]; then
    adb shell 'date +%s%3N; cat /proc/uptime' > "$out_dir/${label}-clock-before.txt"
    if adb shell atrace --async_start -c -b 16384 gfx view wm am > "$out_dir/${label}-trace-start.txt" 2>&1; then
      trace_started=true
    fi
  fi
  sleep 1
  printf 'launch_requested_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" >> "$out_dir/${label}.txt"
  adb shell am start -W -n "$component" >> "$out_dir/${label}.txt"
  if ! grep -q '^Status: ok' "$out_dir/${label}.txt"; then
    echo "Activity did not report a successful launch: $label" >&2
    return 1
  fi
  printf 'launch_returned_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)" >> "$out_dir/${label}.txt"
  wait "$recorder"
  if [[ "$trace_started" == true ]]; then
    adb shell atrace --async_stop gfx view wm am > "$out_dir/${label}-system-trace.txt" 2>&1 || true
    adb shell 'date +%s%3N; cat /proc/uptime' > "$out_dir/${label}-clock-after.txt"
    adb shell dumpsys SurfaceFlinger --list > "$out_dir/${label}-surface-layers.txt" 2>&1 || true
  fi
  adb shell dumpsys meminfo "$package" > "$out_dir/${label}-meminfo.txt" 2>&1 || true
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
# Recreate the activity with a live process to look for handoff before the
# system animation completes. Preserve the observed PIDs rather than assuming
# that Android kept the process alive.
adb shell settings put global window_animation_scale 1
adb shell settings put global transition_animation_scale 1
adb shell settings put global animator_duration_scale 1
adb shell input keyevent HOME
adb shell rm -f /sdcard/pr6-startup-warm.mp4
adb shell pidof "$package" > "$out_dir/warm-pid-before.txt" || true
adb shell screenrecord --time-limit 12 --bit-rate 2000000 /sdcard/pr6-startup-warm.mp4 \
  > "$out_dir/warm-record.log" 2>&1 &
warm_recorder=$!
sleep 1
adb shell am start -W -f 0x10008000 -n "$component" > "$out_dir/warm.txt"
adb shell pidof "$package" > "$out_dir/warm-pid-after.txt" || true
wait "$warm_recorder"
adb pull /sdcard/pr6-startup-warm.mp4 "$out_dir/warm.mp4" >/dev/null
adb shell rm -f /sdcard/pr6-startup-warm.mp4
# Capture a short display with a large system font; restore both afterwards.
adb shell wm size 720x1280
adb shell settings put system font_scale 1.5
capture short_large_font 1 1 1
if [[ -n "$original_override_size" ]]; then
  adb shell wm size "$original_override_size"
else
  adb shell wm size reset
fi
if [[ "$original_font_scale" == null ]]; then
  adb shell settings delete system font_scale
else
  adb shell settings put system font_scale "$original_font_scale"
fi
# Explicitly exercise the matching drawable-night and the app's light tint.
adb shell cmd uimode night yes > "$out_dir/dark-mode-command.txt"
capture dark_normal 1 1 1
capture dark_animator_off 1 1 0
# A debug-only activity uses the same platform splash and pixel player but keeps
# its loading screen visible, making an in-flight handoff more likely. These
# recordings are controlled APK evidence, not the production MainActivity.
adb shell cmd uimode night no >/dev/null
controlled_component="$package/app.knotwork.android.debug.SplashHandoffProbeActivity"
# Start the warm process under a nonzero animation setting. The preceding
# production probe intentionally disabled animators, and an existing Compose
# recomposer can otherwise initially retain its previous duration scale.
adb shell settings put global window_animation_scale 1
adb shell settings put global transition_animation_scale 1
adb shell settings put global animator_duration_scale 1
# The preceding disabled-animation case left its process alive. Start a fresh
# process after setting the scale, then retain it for controlled warm launches.
adb shell am force-stop "$package"
adb shell am start -W -f 0x10008000 -n "$controlled_component" > "$out_dir/controlled-prewarm.txt"
adb shell input keyevent BACK
controlled_failed=false
capture_controlled() {
  local label="$1" scale="$2" fast="$3" remote recorder before after
  remote="/sdcard/pr6-controlled-${label}.mp4"
  adb shell settings put global window_animation_scale "$scale"
  adb shell settings put global transition_animation_scale "$scale"
  adb shell settings put global animator_duration_scale "$scale"
  adb shell pidof "$package" > "$out_dir/controlled-${label}-pid-before.txt" || true
  before=$(adb logcat -d -s 'PR6Handoff:D' '*:S' | grep -c 'controlled_exit' || true)
  adb shell rm -f "$remote"
  adb shell screenrecord --time-limit 20 --bit-rate 2000000 "$remote" > "$out_dir/controlled-${label}-record.log" 2>&1 &
  recorder=$!
  adb shell 'date +%s%3N; cat /proc/uptime' > "$out_dir/controlled-${label}-clock-before.txt"
  sleep 1
  adb shell am start -W -f 0x10008000 -n "$controlled_component" --ez fast_ready "$fast" > "$out_dir/controlled-${label}.txt"
  adb shell pidof "$package" > "$out_dir/controlled-${label}-pid-after.txt" || true
  wait "$recorder"
  after=$(adb logcat -d -s 'PR6Handoff:D' '*:S' | grep -c 'controlled_exit' || true)
  printf 'platform_exit_count_before=%s\nplatform_exit_count_after=%s\n' "$before" "$after" \
    > "$out_dir/controlled-${label}-listener-status.txt"
  if (( after <= before )); then
    echo "Controlled $label did not observe a platform exit listener; handoff is unproven" >&2
    controlled_failed=true
  fi
  adb pull "$remote" "$out_dir/controlled-${label}.mp4" >/dev/null
  adb shell rm -f "$remote"
  adb shell input keyevent BACK
}
capture_controlled half 0.5 false
capture_controlled normal 1 false
capture_controlled double 2 false
capture_controlled fast_ready 1 true
capture_controlled off 0 false
adb logcat -d -v threadtime > "$out_dir/logcat.txt"
if [[ "$controlled_failed" == true ]]; then exit 1; fi
