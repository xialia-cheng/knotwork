#!/usr/bin/env python3
"""Verify the no-model startup path on a disposable GitHub Actions emulator."""

import hashlib
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PKG = "me.lcfuns.zhiwen.debug"
COMPONENT = PKG + "/app.knotwork.android.presentation.ui.MainActivity"
DRAFT = "Stage10 local smoke"
FIX_SHA = "2960fd4d0bcf02d212d8a0124db5a872947d663d"


def adb(*args, timeout=35):
    result = subprocess.run(
        ["adb", *args], capture_output=True, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace") or result.stdout.decode(errors="replace"))
    return result.stdout


def shell(*args, timeout=35):
    return adb("shell", *args, timeout=timeout).decode(errors="replace").strip()


def check(condition, details):
    if not condition:
        raise AssertionError(details)


def label(node):
    return node.get("text", "") or node.get("content-desc", "")


def labeled(text):
    return lambda node: label(node) == text


def composer(node):
    return node.get("package") == PKG and node.get("class") == "android.widget.EditText"


def permission_deny(node):
    return node.get("resource-id", "").endswith((
        "/permission_deny_button", "/permission_deny_and_dont_ask_again_button",
    ))


def enabled_action(node):
    return node.get("action-enabled") == "true"


def ui_nodes(xml):
    root = ET.fromstring(xml)
    parents = {child: node for node in root.iter() for child in node}
    nodes = list(root.iter("node"))
    for node in nodes:
        control = node
        while control is not None and control.get("clickable") != "true":
            control = parents.get(control)
        if control is not None:
            node.set("action-enabled", control.get("enabled", "false"))
            node.set("action-bounds", control.get("bounds", ""))
    return nodes


class Smoke:
    def __init__(self, evidence):
        self.evidence = evidence
        self.results = []

    def snapshot_tree(self):
        raw = adb("exec-out", "uiautomator", "dump", "/dev/tty", timeout=18)
        start = raw.find(b"<?xml")
        end = raw.find(b"</hierarchy>")
        if start == -1 or end == -1:
            raise ValueError(raw.decode(errors="replace")[:250])
        xml = raw[start:end + len(b"</hierarchy>")]
        return xml, ui_nodes(xml)

    def screenshot(self, name):
        png = adb("exec-out", "screencap", "-p")
        check(png.startswith(b"\x89PNG"), "Invalid screenshot")
        (self.evidence / f"{name}.png").write_bytes(png)

    def wait_ui(self, name, predicate, deny_again=False, scroll_once=False, timeout=60):
        until = time.monotonic() + timeout
        last_xml = b""
        last_error = ""
        while time.monotonic() < until:
            try:
                last_xml, nodes = self.snapshot_tree()
                if any(label(node) == "Pixel Launcher isn't responding" for node in nodes):
                    close = next((node for node in nodes if node.get("resource-id") == "android:id/aerr_close"), None)
                    if close is not None:
                        (self.evidence / f"{name}-launcher-anr.xml").write_bytes(last_xml)
                        self.tap(close)
                        continue
                if deny_again:
                    dialog = next((node for node in nodes if permission_deny(node)), None)
                    if dialog is not None:
                        (self.evidence / f"{name}-repeated-permission.xml").write_bytes(last_xml)
                        self.tap(dialog)
                        continue
                match = next((node for node in nodes if predicate(node)), None)
                if match is not None:
                    (self.evidence / f"{name}.xml").write_bytes(last_xml)
                    return match, nodes
                if scroll_once:
                    area = next((node for node in nodes if node.get("scrollable") == "true"), None)
                    if area is not None:
                        x1, y1, x2, y2 = map(int, re.findall(r"\d+", area.get("bounds", "")))
                        x = str((x1 + x2) // 2)
                        step = (y2 - y1) // 4
                        shell("input", "swipe", x, str(y2 - step), x, str(y1 + step), "350")
                        scroll_once = False
            except (RuntimeError, ValueError, ET.ParseError, subprocess.TimeoutExpired) as error:
                last_error = str(error)
            time.sleep(0.5)
        (self.evidence / f"{name}-last.xml").write_bytes(last_xml)
        self.screenshot(f"{name}-timeout")
        raise AssertionError(f"Timed out waiting for {name}. {last_error}")

    def tap(self, node):
        check(node.get("action-enabled", node.get("enabled")) == "true", f"Disabled target: {label(node)}")
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("action-bounds", node.get("bounds", ""))))
        check(x2 > x1 and y2 > y1, "Empty touch bounds")
        shell("input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))

    def click(self, name, predicate, scroll_once=False):
        node, _ = self.wait_ui(name, predicate, scroll_once=scroll_once)
        self.tap(node)

    def launch(self, name, warm=False):
        options = ["-f", "0x10008000"] if warm else []
        result = shell("am", "start", "-W", *options, "-n", COMPONENT, timeout=75)
        (self.evidence / f"{name}-activity.txt").write_text(result + "\n")
        check("Status: ok" in result, result)
        return result

    def stop(self):
        shell("am", "force-stop", PKG)

    def chat(self, name):
        self.wait_ui(name, composer, deny_again=True)
        self.screenshot(name)

    def permission_denied(self):
        info = shell("dumpsys", "package", PKG)
        match = re.search(r"android\.permission\.POST_NOTIFICATIONS: granted=false[^\r\n]*", info)
        check(match is not None, "Notifications should remain denied")
        return match.group(0)

    def denied_first_launch(self):
        self.launch("first-launch")
        deny, _ = self.wait_ui("notification-dialog", permission_deny)
        self.screenshot("notification-dialog")
        self.tap(deny)
        skip, _ = self.wait_ui("onboarding-without-model", labeled("Skip"))
        self.screenshot("onboarding-without-model")
        self.tap(skip)
        self.chat("chat-after-skip")
        return self.permission_denied()

    def no_model_caption(self):
        _, nodes = self.wait_ui(
            "empty-chat-caption",
            lambda node: label(node) == "Pipeline · Local-only Q&A · No active local model",
        )
        check(not any("Local model (active)" in label(node) for node in nodes),
              "An empty installation still claims an active local model")
        self.screenshot("empty-chat-caption")
        return "The seeded local pipeline shows No active local model"

    def no_local_model(self):
        editor, _ = self.wait_ui("chat-composer", composer)
        self.tap(editor)
        shell("input", "text", DRAFT.replace(" ", "%s"))
        self.click("send-first-message", labeled("Send message"))
        _, nodes = self.wait_ui("first-task-no-local-model", lambda n: "No active model." in label(n))
        self.screenshot("first-task-no-local-model")
        check(any(n.get("class") == "android.widget.EditText" and DRAFT in label(n) for n in nodes),
              "The blocked send cleared the draft")
        check(any("Settings" in label(n) and "Models" in label(n) and "No active model." in label(n)
                  for n in nodes), "No-model error does not explain where to install a model")
        return "Send gives the Settings → Models route and preserves the draft"

    def models_entry(self):
        self.click("more-tab", labeled("More"))
        self.click("settings-from-more", labeled("Settings"), scroll_once=True)
        self.click("models-setting", labeled("Models"), scroll_once=True)
        self.wait_ui("no-model-setting", labeled("No model installed"))
        self.screenshot("no-model-setting")
        self.click("manage-models", labeled("Manage"), scroll_once=True)
        _, nodes = self.wait_ui("empty-models-list", lambda n: label(n).startswith("0 active · 0 on disk ·"))
        check(any(label(node) == "Discover models" for node in nodes), "Model discovery action is missing")
        self.screenshot("empty-models-list")
        self.click("back-to-chat-tab", labeled("Chat"))
        self.chat("chat-after-models")
        return "Settings → Models → Manage shows zero active and zero on disk with a model discovery action"

    def warm_start(self):
        original = shell("pidof", PKG)
        shell("input", "keyevent", "KEYCODE_HOME")
        result = self.launch("warm-start", warm=True)
        self.chat("warm-start-chat")
        check("LaunchState: WARM" in result, "Activity result does not classify the launch as warm")
        check(original == shell("pidof", PKG), "App PID changed during warm launch")
        return f"Warm launch, same PID {original}, chat composer visible"

    def run(self, name, action):
        try:
            note = action()
            self.results.append({"case": name, "status": "pass", "note": note})
        except (AssertionError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            self.results.append({"case": name, "status": "fail", "note": str(error)})
            try:
                self.screenshot(f"{name}-failed")
            except (AssertionError, RuntimeError, subprocess.TimeoutExpired):
                pass
        print(self.results[-1], flush=True)
        (self.evidence / "results.json").write_text(json.dumps(self.results, indent=2, ensure_ascii=False))


def main():
    apk = Path(sys.argv[1])
    evidence = Path(sys.argv[2])
    api = sys.argv[3]
    expected_hash = apk.with_suffix(".apk.sha256").read_text().split()[0]
    evidence.mkdir(parents=True, exist_ok=True)
    serial = adb("get-serialno").decode().strip()
    check(serial.startswith("emulator-") and shell("getprop", "ro.kernel.qemu") == "1",
          "Refusing to mutate app data outside a disposable emulator")
    check(shell("getprop", "ro.build.version.sdk") == api, "Wrong emulator API")
    with apk.open("rb") as data:
        check(hashlib.file_digest(data, "sha256").hexdigest() == expected_hash, "Unexpected APK contents")
    (evidence / "target.txt").write_text(f"fix={FIX_SHA}\n"
                                         f"api={api}\nserial={serial}\napk_sha256={expected_hash}\n")
    adb("install", str(apk), timeout=130)
    check(shell("pm", "clear", PKG) == "Success", "Expected a clean app installation")
    shell("input", "keyevent", "KEYCODE_WAKEUP")
    shell("wm", "dismiss-keyguard")
    adb("logcat", "-c")
    smoke = Smoke(evidence)
    try:
        smoke.run("denied_notifications_and_no_model_onboarding", smoke.denied_first_launch)
        smoke.run("empty_chat_without_an_active_model", smoke.no_model_caption)
        smoke.run("first_task_without_a_model", smoke.no_local_model)
        smoke.run("reach_model_install_screen", smoke.models_entry)
        smoke.run("warm_start", smoke.warm_start)
    finally:
        (evidence / "logcat.txt").write_bytes(adb("logcat", "-d", "-v", "threadtime"))
        (evidence / "crash.txt").write_bytes(adb("logcat", "-b", "crash", "-d"))
    return int(any(result["status"] != "pass" for result in smoke.results))


if __name__ == "__main__":
    sys.exit(main())
