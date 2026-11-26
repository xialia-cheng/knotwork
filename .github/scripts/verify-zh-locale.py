#!/usr/bin/env python3
"""Exercise Simplified Chinese locale selection, startup, and dark theme on a disposable GitHub Actions emulator."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

CURRENT = "me.lcfuns.zhiwen.debug"


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


def edit_field(node):
    return node.get("class") == "android.widget.EditText"


def is_mainland_region(node):
    return (node.get("package", "").endswith(".settings")
            and node.get("resource-id") == "android:id/locale"
            and label(node) in {"中国", "China", "中国大陆", "China mainland"})


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

    def wait_ui(self, name, predicate, deny_again=False, scroll_steps=0, timeout=60):
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
                if scroll_steps:
                    area = next((node for node in nodes if node.get("scrollable") == "true"), None)
                    if area is not None:
                        x1, y1, x2, y2 = map(int, re.findall(r"\d+", area.get("bounds", "")))
                        x = str((x1 + x2) // 2)
                        step = (y2 - y1) // 4
                        start, end = (y2 - step, y1 + step) if scroll_steps > 0 else (y1 + step, y2 - step)
                        shell("input", "swipe", x, str(start), x, str(end), "350")
                        scroll_steps += -1 if scroll_steps > 0 else 1
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

    def click(self, name, predicate, scroll_steps=0):
        node, _ = self.wait_ui(name, predicate, scroll_steps=scroll_steps)
        self.tap(node)

    def launch(self, name):
        result = shell("am", "start", "-W", "-n",
                       CURRENT + "/app.knotwork.android.presentation.ui.MainActivity", timeout=80)
        (self.evidence / f"{name}-activity.txt").write_text(result + "\n")
        check("Status: ok" in result, result)

    def stop(self):
        shell("am", "force-stop", CURRENT)

    def chat(self, name):
        return self.wait_ui(name, lambda n: n.get("package") == CURRENT and edit_field(n), deny_again=True)[0]

    def skip(self, text, name):
        button, _ = self.wait_ui(name, labeled(text), deny_again=True)
        self.screenshot(name)
        self.tap(button)
        self.chat(name + "-chat")

    def settings(self, name, more, settings, search):
        self.click(name + "-more", labeled(more))
        self.click(name + "-settings", labeled(settings), scroll_steps=4)
        self.wait_ui(name + "-hub", labeled(search))

    def app_languages(self):
        self.launch("english-first-start")
        self.skip("Skip", "onboarding-en")
        self.settings("english", "More", "Settings", "Search settings")
        self.click("app-open-about", labeled("About"), scroll_steps=7)
        self.click("app-open-language", labeled("Language"))
        self.click("app-choose-zh", lambda n: label(n) in {"中文", "简体中文", "中文（简体）"})
        _, nodes = self.wait_ui("app-language-changed", lambda n: label(n) in {"语言", "更多"}, deny_again=True)
        if not any(label(node) == "语言" for node in nodes):
            self.settings("zh-after-picker", "更多", "设置", "搜索设置")
            self.click("zh-after-picker-about", labeled("关于"), scroll_steps=7)
            self.wait_ui("zh-after-picker-language", labeled("语言"))
        self.screenshot("zh-about-light")
        actual = shell("cmd", "locale", "get-app-locales", CURRENT, "--user", "0")
        (self.evidence / "selected-app-locales.txt").write_text(actual + "\n")
        check(re.search(r"\[zh(?:[-,\]])", actual), "App picker did not set Chinese: " + actual)
        self.stop()
        self.launch("app-zh-restart")
        self.wait_ui("zh-after-restart", labeled("更多"), deny_again=True)
        return "App Settings selected Chinese, screen recreated in Chinese, and selection survived force-stop"

    def system_chinese(self, name):
        result = shell("am", "start", "-W", "-a", "android.settings.APP_LOCALE_SETTINGS", "-d",
                       "package:" + CURRENT, timeout=60)
        (self.evidence / f"{name}-action.txt").write_text(result + "\n")
        check("Status: ok" in result, result)
        def option(n):
            t = label(n).casefold()
            return n.get("package", "").endswith(".settings") and (
                "中文" in t or "chinese" in t
            )
        self.click(name + "-choose-language", option, scroll_steps=4)
        until = time.monotonic() + 18
        while time.monotonic() < until:
            actual = shell("cmd", "locale", "get-app-locales", CURRENT, "--user", "0")
            if re.search(r"\[zh(?:[-,\]])", actual):
                (self.evidence / f"{name}-app-locales.txt").write_text(actual + "\n")
                return
            time.sleep(0.5)
        # Some platform builds show the regional choice on a second screen.
        self.click(name + "-choose-region", is_mainland_region)
        until = time.monotonic() + 12
        while time.monotonic() < until:
            actual = shell("cmd", "locale", "get-app-locales", CURRENT, "--user", "0")
            (self.evidence / f"{name}-app-locales.txt").write_text(actual + "\n")
            if re.search(r"\[zh(?:[-,\]])", actual):
                return
            time.sleep(0.5)
        raise AssertionError("Android App Language did not set Chinese: " + actual)

    def chinese_first_start(self):
        self.stop()
        check(shell("pm", "clear", CURRENT) == "Success", "Could not reset disposable fixture")
        # pm clear can retain locale metadata on some releases. Restore the default
        # via the platform API to test the system Settings picker from a fresh selection.
        shell("cmd", "locale", "set-app-locales", CURRENT, "--user", "0")
        self.system_chinese("system-zh")
        self.launch("chinese-first-start")
        self.wait_ui("chinese-onboarding-brand", labeled("织问"), deny_again=True)
        self.skip("跳过", "onboarding-zh")
        return "Selected Chinese using Android App Language before first launch; onboarding and Chat remained usable"

    def no_local_model(self):
        example = "讲讲日食是怎么发生的"
        self.click("zh-sample-prompt", labeled(example))
        _, before = self.wait_ui("zh-send", labeled("发送消息"))
        draft = next((n.get("text", "").strip() for n in before if edit_field(n)), "")
        check(draft == example, f"The sample did not populate the composer: {draft!r}")
        self.tap(next(n for n in before if label(n) == "发送消息"))
        _, nodes = self.wait_ui("zh-no-model-error", lambda n: "没有已启用的模型" in label(n), timeout=35)
        self.screenshot("zh-no-model-error")
        check(any("设置 → 模型" in label(n) for n in nodes), "The error omitted the model settings path")
        check(any(edit_field(n) and n.get("text", "").strip() == draft for n in nodes),
              f"The failed send changed the draft {draft!r}")
        self.settings("zh", "更多", "设置", "搜索设置")
        self.click("zh-models-setting", labeled("模型"), scroll_steps=4)
        self.click("zh-manage-models", labeled("管理"), scroll_steps=3)
        self.wait_ui("zh-model-discovery", labeled("探索模型"))
        self.screenshot("zh-models-light")
        return "No-model reply explained where to install a model, kept the draft, and the model discovery entry opened"

    def dark_theme(self):
        shell("cmd", "uimode", "night", "yes")
        self.stop()
        self.launch("zh-dark")
        self.chat("zh-dark-chat")
        self.screenshot("zh-chat-dark")
        self.settings("zh-dark", "更多", "设置", "搜索设置")
        self.screenshot("zh-settings-dark")
        self.click("zh-dark-about", labeled("关于"), scroll_steps=7)
        self.wait_ui("zh-dark-language", labeled("语言"))
        self.screenshot("zh-about-dark")
        (self.evidence / "ui-night-mode.txt").write_text(shell("cmd", "uimode", "night") + "\n")
        return "Chinese chat, settings, and About rendered in system dark mode"

    def run(self, name, scenario):
        try:
            record = {"case": name, "status": "pass", "detail": scenario()}
        except (AssertionError, OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            record = {"case": name, "status": "fail", "detail": str(error)}
            self.screenshot(name + "-failure")
        self.results.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        (self.evidence / "results.json").write_text(json.dumps(self.results, indent=2, ensure_ascii=False))
        return record["status"] == "pass"


def main():
    apk, output, api = sys.argv[1:]
    evidence = Path(output)
    evidence.mkdir(parents=True, exist_ok=True)
    check(adb("get-serialno").decode().strip().startswith("emulator-") and
          shell("getprop", "ro.kernel.qemu") == "1", "Requires a disposable emulator")
    check(shell("getprop", "ro.build.version.sdk") == api, "Wrong API level")
    adb("logcat", "-c")
    shell("input", "keyevent", "KEYCODE_WAKEUP")
    shell("wm", "dismiss-keyguard")
    shell("cmd", "uimode", "night", "no")
    adb("install", apk, timeout=180)
    with Path(apk).open("rb") as stream:
        apk_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    (evidence / "target.json").write_text(json.dumps(
        {"head": os.environ["TARGET_HEAD"], "api": api, "apk_sha256": apk_hash}, indent=2))
    smoke = Smoke(evidence)
    try:
        smoke.run("in_app_language_and_restart", smoke.app_languages)
        chinese = smoke.run("system_language_and_first_start", smoke.chinese_first_start)
        if chinese:
            smoke.run("first_send_without_model", smoke.no_local_model)
            smoke.run("chinese_dark_theme", smoke.dark_theme)
    finally:
        (evidence / "crash.txt").write_bytes(adb("logcat", "-b", "crash", "-d"))
    return int(len(smoke.results) != 4 or any(case["status"] != "pass" for case in smoke.results))


if __name__ == "__main__":
    sys.exit(main())
