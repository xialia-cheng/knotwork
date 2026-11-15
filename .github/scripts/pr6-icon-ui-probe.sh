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
  printf '%s\n' 'Launcher does not expose the all-apps intent; attempting a home swipe.' > "$out_dir/all-apps-intent-unavailable.txt"
  swipe_coordinates="$(python3 - "$out_dir/home-ui.xml" <<'PYCODE'
import re
import sys
import xml.etree.ElementTree as ET
text = open(sys.argv[1], encoding="utf-8").read()
root = ET.fromstring(text[:text.rfind(">") + 1])
for node in root.iter("node"):
    values = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
    if len(values) == 4 and values[0] == 0 and values[1] == 0:
        print(values[2] // 2, values[3] * 4 // 5, values[3] * 7 // 20)
        break
PYCODE
)"
  if [[ -n "$swipe_coordinates" ]]; then
    read -r swipe_x swipe_start swipe_end <<< "$swipe_coordinates"
    adb shell input swipe "$swipe_x" "$swipe_start" "$swipe_x" "$swipe_end" 450
    capture all-apps
  else
    printf '%s\n' 'Could not derive a launcher swipe from the UI tree.' > "$out_dir/all-apps-unavailable.txt"
  fi
fi
# A predicted home icon may not be draggable. If the launcher exposed the app
# drawer, use the actual app entry and the previously observed home target.
if [[ -f "$out_dir/folder-unavailable.txt" && -s "$out_dir/all-apps-ui.xml" ]]; then
  coordinates="$(python3 - "$out_dir/all-apps-ui.xml" "$out_dir/home-ui.xml" <<'PYCODE'
import re
import sys
import xml.etree.ElementTree as ET

def center(path, label):
    text = open(path, encoding="utf-8").read()
    root = ET.fromstring(text[:text.rfind(">") + 1])
    for node in root.iter("node"):
        if node.get("text") == label and node.get("clickable") == "true":
            values = list(map(int, re.findall(r"\d+", node.get("bounds", ""))))
            if len(values) == 4:
                return (values[0] + values[2]) // 2, (values[1] + values[3]) // 2
    return None

source, target = center(sys.argv[1], "织问 Debug"), center(sys.argv[2], "Gmail")
if source and target:
    print(*source, *target)
PYCODE
)"
  if [[ -n "$coordinates" ]]; then
    read -r source_x source_y target_x target_y <<< "$coordinates"
    adb shell input draganddrop "$source_x" "$source_y" "$target_x" "$target_y" 1000
    capture folder-from-drawer
    folder_coordinates="$(python3 - "$out_dir/folder-from-drawer-ui.xml" <<'PYCODE'
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
      capture folder-from-drawer-open
    else
      printf '%s\n' 'No folder node found after dragging from the app drawer.' > "$out_dir/folder-from-drawer-unavailable.txt"
    fi
  else
    printf '%s\n' 'App drawer entry or home target missing.' > "$out_dir/folder-from-drawer-unavailable.txt"
  fi
fi
