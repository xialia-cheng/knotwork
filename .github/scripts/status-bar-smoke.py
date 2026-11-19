#!/usr/bin/env python3
"""Measure actual status-bar contrast on a disposable GitHub Actions emulator."""

import hashlib
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from PIL import Image

PKG = "me.lcfuns.zhiwen.debug"
COMPONENT = PKG + "/app.knotwork.android.presentation.ui.MainActivity"
FIX_SHA = "16d76141f9672f480394a54dd6835cbec5f04350"


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


def luminance(rgb):
    linear = []
    for value in rgb:
        channel = value / 255
        linear.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def measure_status_bar(path):
    with Image.open(path) as image:
        scale = image.width / 1080
        # Top-left clock, away from the cutout, toolbar and navigation bar.
        clock = image.convert("RGB").crop(tuple(round(value * scale) for value in (70, 45, 245, 85)))
        colors = Counter(clock.getdata()).most_common(2)
    if len(colors) < 2:
        return {"background": colors[0][0], "ink": None, "ink_pixels": 0, "contrast": 1}
    background, _ = colors[0]
    ink, pixels = colors[1]
    high, low = sorted((luminance(background), luminance(ink)), reverse=True)
    return {"background": background, "ink": ink, "ink_pixels": pixels, "contrast": (high + 0.05) / (low + 0.05)}


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
        self.measurements = {}

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
        path = self.evidence / f"{name}.png"
        path.write_bytes(png)
        return path

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
        def visible_target(node):
            if not predicate(node):
                return False
            x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds", "")))
            return x2 - x1 >= 24 and y2 - y1 >= 24

        node, _ = self.wait_ui(name, visible_target, scroll_once=scroll_once)
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

    def set_system_theme(self, mode):
        shell("cmd", "uimode", "night", mode)
        actual = shell("cmd", "uimode", "night")
        check(actual.endswith(mode), f"Expected system night mode {mode}, got {actual}")
        (self.evidence / f"system-night-{mode}.txt").write_text(actual + "\n")

    def settings(self, name):
        self.click(name + "-more", labeled("More"))
        self.click(name + "-settings", labeled("Settings"), scroll_once=True)
        self.wait_ui(name + "-hub", labeled("Search settings"))

    def choose_app_theme(self, name, label_text):
        self.click(name + "-choose-mode", labeled(label_text), scroll_once=True)
        self.wait_ui(name + "-selected-mode", labeled("✓ " + label_text))

    def restart_to_chat(self, name):
        self.stop()
        self.launch(name)
        self.chat(name + "-chat")

    def assert_status_bar(self, name, dark_surface):
        until = time.monotonic() + 24
        measured = None
        while time.monotonic() < until:
            measured = measure_status_bar(self.screenshot(name))
            background = luminance(measured["background"])
            ink = luminance(measured["ink"]) if measured["ink"] is not None else background
            surface_ok = background < 0.2 if dark_surface else background > 0.5
            direction_ok = ink > background if dark_surface else ink < background
            if surface_ok and direction_ok and measured["ink_pixels"] >= 40 and measured["contrast"] >= 4.5:
                self.record(name, measured, "pass")
                return
            time.sleep(0.7)
        self.record(name, measured, "fail")
        raise AssertionError(f"{name} has unreadable status-bar contrast: {measured}")

    def record(self, name, measurement, status):
        self.measurements[name] = {"status": status, **(measurement or {})}
        (self.evidence / "measurements.json").write_text(json.dumps(self.measurements, indent=2))
        print(name, self.measurements[name], flush=True)

    def check_themes(self):
        self.set_system_theme("no")
        self.denied_first_launch()
        self.assert_status_bar("follow-system-light", dark_surface=False)

        self.settings("app-dark")
        self.choose_app_theme("app-dark", "深色")
        self.assert_status_bar("app-dark-system-light-live", dark_surface=True)
        self.restart_to_chat("app-dark-restart")
        self.assert_status_bar("app-dark-system-light-restart", dark_surface=True)

        self.set_system_theme("yes")
        self.restart_to_chat("system-dark")
        self.settings("app-light")
        self.choose_app_theme("app-light", "浅色")
        self.assert_status_bar("app-light-system-dark-live", dark_surface=False)
        self.restart_to_chat("app-light-restart")
        self.assert_status_bar("app-light-system-dark-restart", dark_surface=False)

        self.settings("follow-system")
        self.choose_app_theme("follow-system", "跟随系统")
        self.assert_status_bar("follow-system-dark-live", dark_surface=True)
        self.set_system_theme("no")
        self.wait_ui("follow-system-back-to-light",
                     lambda n: label(n) in ("Search settings", "Message the agent…"), deny_again=True)
        self.assert_status_bar("follow-system-light-after-system-change", dark_surface=False)


def main():
    apk = Path(sys.argv[1])
    evidence = Path(sys.argv[2])
    api = sys.argv[3]
    evidence.mkdir(parents=True, exist_ok=True)
    serial = adb("get-serialno").decode().strip()
    check(serial.startswith("emulator-") and shell("getprop", "ro.kernel.qemu") == "1",
          "Use a disposable emulator")
    check(shell("getprop", "ro.build.version.sdk") == api, "Wrong emulator API")
    expected_hash = apk.with_suffix(".apk.sha256").read_text().split()[0]
    with apk.open("rb") as data:
        check(hashlib.file_digest(data, "sha256").hexdigest() == expected_hash, "Unexpected APK contents")
    (evidence / "target.txt").write_text(f"fix={FIX_SHA}\napi={api}\napk_sha256={expected_hash}\n")
    adb("install", str(apk), timeout=150)
    check(shell("pm", "clear", PKG) == "Success", "Could not clear emulator test data")
    shell("input", "keyevent", "KEYCODE_WAKEUP")
    shell("wm", "dismiss-keyguard")
    adb("logcat", "-c")
    smoke = Smoke(evidence)
    try:
        smoke.check_themes()
    finally:
        (evidence / "logcat.txt").write_bytes(adb("logcat", "-d", "-v", "threadtime"))
        (evidence / "crash.txt").write_bytes(adb("logcat", "-b", "crash", "-d"))


if __name__ == "__main__":
    main()
