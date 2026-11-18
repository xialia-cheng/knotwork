#!/usr/bin/env python3
"""Exercise the installed debug APK on a disposable GitHub Actions emulator."""

import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PKG = "me.lcfuns.zhiwen.debug"
COMPONENT = PKG + "/app.knotwork.android.presentation.ui.MainActivity"
DATABASE = "databases/agent_database.db"
KEY_PREFS = "shared_prefs/secure_db_passphrase_v2.xml"
HELD_KEY = "files/stage10-held-key.xml"
FIXTURE = "files/agent_workspace/stage10-recovery-fixture.txt"
LOCKED_TEXT = "Your data can’t be unlocked"
DRAFT = "Stage10 local smoke"
APK_HASH = "e5bdaf371215b6e4fea6516da6544acc079f6a9c2de3f57ae2f2aef221dbe918"


def adb(*args, timeout=35):
    result = subprocess.run(
        ["adb", *args], capture_output=True, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace") or result.stdout.decode(errors="replace"))
    return result.stdout


def shell(*args, timeout=35):
    return adb("shell", *args, timeout=timeout).decode(errors="replace").strip()


def app_shell(command):
    return shell(f"run-as {PKG} sh -c {shlex.quote(command)}")


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
        self.click("models-entry", labeled("Models"), scroll_once=True)
        self.wait_ui("empty-models-list", lambda n: label(n) in ("No model installed", "No models installed"),
                     scroll_once=True)
        self.screenshot("empty-models-list")
        shell("input", "keyevent", "KEYCODE_BACK")
        self.click("back-to-chat-tab", labeled("Chat"))
        self.chat("chat-after-models")
        return "Opened the Models screen with an actual empty model list and returned to chat"

    def warm_start(self):
        original = shell("pidof", PKG)
        shell("input", "keyevent", "KEYCODE_HOME")
        result = self.launch("warm-start", warm=True)
        self.chat("warm-start-chat")
        check("LaunchState: WARM" in result, "Activity result does not classify the launch as warm")
        check(original == shell("pidof", PKG), "App PID changed during warm launch")
        return f"Warm launch, same PID {original}, chat composer visible"

    def generic_retry(self):
        self.stop()
        old_db = self.digest(DATABASE)
        app_shell("test -d databases && test ! -e databases.stage10-held && "
                  "mv databases databases.stage10-held && touch databases")
        try:
            self.launch("initialization-fault")
            retry, nodes = self.wait_ui("generic-initialization-error", labeled("Retry"), deny_again=True)
            self.screenshot("generic-initialization-error")
            check(not any(label(node) == LOCKED_TEXT for node in nodes), "Unexpected key recovery UI")
            check(self.digest("databases.stage10-held/agent_database.db") == old_db, "Parked database changed")
        finally:
            app_shell("test -f databases && rm databases && mv databases.stage10-held databases")
        self.tap(retry)
        self.chat("chat-after-initialization-retry")
        return "Real database open failure with ordinary Retry; restored path and recovered in the same launch"

    def digest(self, path):
        return app_shell(f"sha256sum {shlex.quote(path)}").split()[0]

    def locked_ui(self, name):
        self.wait_ui(name, labeled(LOCKED_TEXT), deny_again=True)
        self.screenshot(name)

    def unavailable_key_failures(self):
        log = adb("logcat", "-d", "-s", "EncryptedDbPassphraseProvider:E").decode(errors="replace")
        return log.count("DB passphrase unavailable (PASSPHRASE_MISSING)")

    def locked_recovery(self):
        self.stop()
        app_shell(f"mkdir -p files/agent_workspace && printf stage10-fixture > {FIXTURE}")
        fixture_hash = self.digest(FIXTURE)
        database_hash = self.digest(DATABASE)
        original_key = self.digest(KEY_PREFS)
        app_shell(f"test -s {DATABASE} && test -s {KEY_PREFS} && mv {KEY_PREFS} {HELD_KEY}")
        self.launch("database-key-missing")
        self.locked_ui("real-key-recovery")
        count_before_retry = self.unavailable_key_failures()
        self.click("locked-retry", labeled("Retry"))
        self.locked_ui("locked-after-retry")
        check(self.unavailable_key_failures() > count_before_retry, "Retry did not cause another missing-key read")
        self.click("open-reset-dialog", labeled("Erase data"))
        self.wait_ui("reset-dialog", labeled("Erase your data?"))
        entry, nodes = self.wait_ui("reset-dialog-input", composer)
        buttons = [node for node in nodes if label(node) == "Erase data" and node.get("action-enabled") is not None]
        check(buttons and all(not enabled_action(node) for node in buttons),
              "Erase was enabled without confirmation")
        self.tap(entry)
        shell("input", "text", "incorrect")
        _, nodes = self.wait_ui("wrong-confirmation", lambda n: composer(n) and "incorrect" in label(n))
        buttons = [node for node in nodes if label(node) == "Erase data" and node.get("action-enabled") is not None]
        check(buttons and all(not enabled_action(node) for node in buttons),
              "Erase was enabled with the wrong confirmation")
        self.screenshot("wrong-confirmation")
        self.click("cancel-reset", labeled("Cancel"))
        self.locked_ui("locked-after-cancel")
        check(self.digest(DATABASE) == database_hash, "Retry or Cancel modified the inaccessible database")
        check(self.digest(FIXTURE) == fixture_hash, "Retry or Cancel modified the test workspace")
        app_shell(f"test ! -e {KEY_PREFS}")

        self.stop()
        app_shell(f"mv {HELD_KEY} {KEY_PREFS}")
        self.launch("original-key-restored")
        self.chat("chat-after-key-restoration")
        check(self.digest(KEY_PREFS) == original_key, "Restored key was replaced")
        check(self.digest(FIXTURE) == fixture_hash, "Restoring the key lost the test workspace")
        self.results.append({"case": "unreadable_db_retry_cancel_and_key_restoration", "status": "pass"})

        self.stop()
        app_shell(f"mv {KEY_PREFS} {HELD_KEY}")
        self.launch("confirmed-reset-fixture")
        self.locked_ui("locked-before-confirmed-reset")
        self.click("open-confirmed-reset-dialog", labeled("Erase data"))
        entry, _ = self.wait_ui("confirmed-reset-input", composer)
        self.tap(entry)
        shell("input", "text", "yes")
        self.click("confirm-erase", lambda n: label(n) == "Erase data" and enabled_action(n))
        self.chat("chat-after-confirmed-reset")
        app_shell(f"test ! -e {FIXTURE} && test -s {DATABASE} && test -s {KEY_PREFS}")
        check(self.digest(KEY_PREFS) != original_key, "Database passphrase was not regenerated")
        self.permission_denied()
        return "Confirmed reset regenerated database and passphrase, erased the test workspace and reopened chat"

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
    evidence.mkdir(parents=True, exist_ok=True)
    serial = adb("get-serialno").decode().strip()
    check(serial.startswith("emulator-") and shell("getprop", "ro.kernel.qemu") == "1",
          "Refusing to mutate app data outside a disposable emulator")
    check(shell("getprop", "ro.build.version.sdk") == api, "Wrong emulator API")
    with apk.open("rb") as data:
        check(hashlib.file_digest(data, "sha256").hexdigest() == APK_HASH, "Unexpected APK contents")
    (evidence / "target.txt").write_text(f"main=c3f65a226ae4e351c1660d58713508c9c3440757\n"
                                         f"api={api}\nserial={serial}\napk_sha256={APK_HASH}\n")
    adb("install", str(apk), timeout=130)
    check(shell("pm", "clear", PKG) == "Success", "Expected a clean app installation")
    shell("input", "keyevent", "KEYCODE_WAKEUP")
    shell("wm", "dismiss-keyguard")
    adb("logcat", "-c")
    smoke = Smoke(evidence)
    try:
        smoke.run("denied_notifications_and_no_model_onboarding", smoke.denied_first_launch)
        smoke.run("first_task_without_a_model", smoke.no_local_model)
        smoke.run("reach_model_install_screen", smoke.models_entry)
        smoke.run("warm_start", smoke.warm_start)
        smoke.run("generic_initialization_retry", smoke.generic_retry)
        smoke.run("confirmed_database_reset", smoke.locked_recovery)
    finally:
        (evidence / "logcat.txt").write_bytes(adb("logcat", "-d", "-v", "threadtime"))
        (evidence / "crash.txt").write_bytes(adb("logcat", "-b", "crash", "-d"))
    return int(any(result["status"] != "pass" for result in smoke.results))


if __name__ == "__main__":
    sys.exit(main())
