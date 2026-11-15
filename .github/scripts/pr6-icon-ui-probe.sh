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
# Only mutate the disposable emulator home. Coordinates come from the captured UI tree.
if [[ -s "$out_dir/home-ui.xml" ]]; then
  coordinates="$(python3 - "$out_dir/home-ui.xml" <<'PYCODE'
import re
import sys
import xml.etree.ElementTree as ET
text = open(sys.argv[1], encoding="utf-8").read()
root = ET.fromstring(text[:text.rfind(">") + 1])
def center(label):
    for node in root.iter("node"):
        if node.get("text") == label and node.get("clickable") == "true":
            values = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
            if len(values) == 4:
                return (values[0] + values[2]) // 2, (values[1] + values[3]) // 2
    return None
source, target = center("织问 Debug"), center("Gmail")
if source and target:
    print(*source, *target)
PYCODE
)"
  if [[ -n "$coordinates" ]]; then
    read -r source_x source_y target_x target_y <<< "$coordinates"
    if adb shell input draganddrop "$source_x" "$source_y" "$target_x" "$target_y" 1000; then
      capture folder-after-drag
      folder_coordinates="$(python3 - "$out_dir/folder-after-drag-ui.xml" <<'PYCODE'
import re
import sys
import xml.etree.ElementTree as ET
text = open(sys.argv[1], encoding="utf-8").read()
root = ET.fromstring(text[:text.rfind(">") + 1])
for node in root.iter("node"):
    desc = node.get("content-desc", "")
    if "folder" in desc.lower() and node.get("clickable") == "true":
        values = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
        if len(values) == 4:
            print((values[0] + values[2]) // 2, (values[1] + values[3]) // 2)
            break
PYCODE
)"
      if [[ -n "$folder_coordinates" ]]; then
        read -r folder_x folder_y <<< "$folder_coordinates"
        adb shell input tap "$folder_x" "$folder_y"
        capture folder-open
      else
        printf '%s\n' 'No folder node found after dragging; folder view was not verified.' > "$out_dir/folder-unavailable.txt"
      fi
    else
      printf '%s\n' 'Could not drag icon to create a folder.' > "$out_dir/folder-unavailable.txt"
    fi
  else
    printf '%s\n' 'App or target icon not found in home hierarchy.' > "$out_dir/folder-unavailable.txt"
  fi
fi
if adb shell am start -a android.intent.action.ALL_APPS > "$out_dir/all-apps-launch.txt" 2>&1 &&
  ! grep -q "Error:" "$out_dir/all-apps-launch.txt"; then
  capture all-apps
else
  printf '%s\n' 'Launcher does not expose the all-apps intent.' > "$out_dir/all-apps-unavailable.txt"
fi
