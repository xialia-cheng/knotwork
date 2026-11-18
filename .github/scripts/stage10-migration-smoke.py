#!/usr/bin/env python3
"""Exercise upgrade and backup/restore on a disposable GitHub Actions emulator."""

import hashlib
import json
import re
import shlex
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

CURRENT = "me.lcfuns.zhiwen.debug"
LEGACY = "app.knotwork.android.debug"
BASELINE = "5ce69cc0246c4d4fe5927be3a888a633ebb06c6a"
SAMPLE = "Local-only Q&A"
DB = "databases/agent_database.db"
BACKUP_PASSPHRASE = "FixtureTransfer8701"


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
                if scroll_steps > 0:
                    area = next((node for node in nodes if node.get("scrollable") == "true"), None)
                    if area is not None:
                        x1, y1, x2, y2 = map(int, re.findall(r"\d+", area.get("bounds", "")))
                        x = str((x1 + x2) // 2)
                        step = (y2 - y1) // 4
                        shell("input", "swipe", x, str(y2 - step), x, str(y1 + step), "350")
                        scroll_steps -= 1
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

    def app_shell(self, command):
        return shell(f"run-as {self.pkg} sh -c {shlex.quote(command)}")

    def launch(self, name, shortcut=False):
        args = ["-a", "android.intent.action.VIEW", "-d", "knotwork://pipelines"] if shortcut else []
        component = self.pkg + "/app.knotwork.android.presentation.ui.MainActivity"
        result = shell("am", "start", "-W", *args, "-n", component, timeout=80)
        (self.evidence / f"{name}-activity.txt").write_text(result + "\n")
        check("Status: ok" in result, result)

    def stop(self):
        shell("am", "force-stop", self.pkg)

    def chat(self, name):
        self.wait_ui(name, lambda n: n.get("package") == self.pkg and edit_field(n), deny_again=True)

    def initial_install(self, pkg, apk, name):
        self.pkg = pkg
        adb("install", "-r", str(apk), timeout=160)
        check(shell("pm", "clear", pkg) == "Success", "Could not prepare a clean test install")
        self.launch(name)
        skip, _ = self.wait_ui(name + "-onboarding", labeled("Skip"), deny_again=True)
        self.tap(skip)
        self.chat(name + "-chat")

    def type_into(self, field, value, replace=False):
        self.tap(field)
        if replace:
            shell("input", "keycombination", "113", "29")
        shell("input", "text", shlex.quote(value.replace(" ", "%s")))

    def rename_fixture_pipeline(self, name):
        self.click(name + "-pipelines", labeled("Pipelines"))
        self.click(name + "-open-pipeline-actions", labeled("More actions for " + SAMPLE))
        self.click(name + "-rename", labeled("Rename"))
        self.wait_ui(name + "-rename-dialog", labeled("Rename pipeline"))
        field, _ = self.wait_ui(name + "-pipeline-name", edit_field)
        self.type_into(field, name, replace=True)
        self.click(name + "-save", labeled("Save"))
        return self.pipeline_state(name, name + "-pipeline-saved")

    def pipeline_state(self, title, case):
        _, nodes = self.wait_ui(case, labeled(title))
        count = next((label(n) for n in nodes if re.match(r"^\d+ saved · \d+ default$", label(n))), None)
        check(count is not None, "The pipeline count is missing from the library")
        return count

    def settings(self, name):
        self.click(name + "-more", labeled("More"))
        self.click(name + "-settings", labeled("Settings"), scroll_steps=3)
        self.wait_ui(name + "-hub", labeled("Generation"))

    def appearance(self, name, set_values=False):
        if set_values:
            self.click(name + "-dark", labeled("深色"), scroll_steps=3)
        self.wait_ui(name + "-dark-selected", labeled("✓ 深色"), scroll_steps=3)
        if set_values:
            self.click(name + "-vivid", labeled("鲜亮"))
        self.wait_ui(name + "-vivid-selected", labeled("✓ 鲜亮"))
        self.screenshot(name + "-appearance")

    def file_fixture(self, name):
        path = "files/agent_workspace/" + name + ".txt"
        self.app_shell(f"mkdir -p files/agent_workspace && printf %s {name} > {path}")
        return path

    def checksum(self, path):
        return self.app_shell(f"sha256sum {shlex.quote(path)}").split()[0]

    def open_backup(self, name):
        self.settings(name)
        self.click(name + "-privacy", labeled("Privacy"), scroll_steps=3)
        self.click(name + "-backup-settings", labeled("Backup & restore"), scroll_steps=3)

    def backup_files(self):
        result = shell("find /sdcard/Download -maxdepth 1 -name '*.knotwork' -type f")
        return {line.strip() for line in result.splitlines() if line.startswith("/sdcard/Download/")}

    def export_backup(self, name):
        before = self.backup_files()
        self.open_backup(name)
        self.click(name + "-start-backup", labeled("Back up…"))
        _, nodes = self.wait_ui(name + "-backup-form", labeled("Password again"))
        fields = [n for n in nodes if edit_field(n)]
        check(len(fields) == 2, "Expected a password and confirmation field")
        self.type_into(fields[0], BACKUP_PASSPHRASE)
        _, nodes = self.wait_ui(name + "-confirmation-field", labeled("Password again"), scroll_steps=2)
        fields = [n for n in nodes if edit_field(n)]
        check(len(fields) == 2, "Backup confirmation field was not available")
        self.type_into(fields[1], BACKUP_PASSPHRASE)
        self.click(name + "-create-document", labeled("Choose where to save"), scroll_steps=3)
        self.click(name + "-save-document", lambda n: label(n) in ("Save", "SAVE") and
                   "documentsui" in n.get("package", ""))
        self.wait_ui(name + "-saved", labeled("Backup saved"), timeout=135)
        self.wait_ui(name + "-without-secrets", labeled("API keys and sign-ins are not in this file."))
        self.screenshot(name + "-saved")
        files = self.backup_files() - before
        check(len(files) == 1, f"Expected exactly one local backup in Download, got {files}")
        path = files.pop()
        digest = shell(f"sha256sum {shlex.quote(path)}").split()[0]
        (self.evidence / f"{name}-backup.txt").write_text(f"{digest}  {path}\n")
        self.click(name + "-export-done", labeled("Done"))
        return path

    def open_backup_file(self, name, path):
        self.open_backup(name)
        self.click(name + "-open-document", labeled("Restore from file…"))
        filename = Path(path).name
        self.click(name + "-pick-backup", lambda n: label(n) == filename and "documentsui" in n.get("package", ""),
                   scroll_steps=3)
        field, _ = self.wait_ui(name + "-password-form", edit_field)
        return field

    def restore_backup(self, name, path, preserved_file=None):
        field = self.open_backup_file(name, path)
        if preserved_file:
            unchanged = self.checksum(preserved_file)
            self.type_into(field, "WrongFixturePassphrase")
            self.click(name + "-check-bad-password", labeled("Check"))
            self.wait_ui(name + "-password-rejected", labeled("That password doesn’t open this backup."), timeout=135)
            check(self.checksum(preserved_file) == unchanged, "An incorrect password modified destination data")
            field, _ = self.wait_ui(name + "-retry-password-field", edit_field)
        self.type_into(field, BACKUP_PASSPHRASE, replace=bool(preserved_file))
        self.click(name + "-check-password", labeled("Check"))
        self.wait_ui(name + "-restore-summary", labeled("Ready to restore"), timeout=135)
        self.screenshot(name + "-restore-summary")
        if preserved_file:
            check(self.checksum(preserved_file) == unchanged, "Preview modified destination data")
        self.click(name + "-request-replace", labeled("Replace my data"), scroll_steps=3)
        field, nodes = self.wait_ui(name + "-confirm-dialog", edit_field)
        buttons = [n for n in nodes if label(n) == "Replace" and n.get("action-enabled") is not None]
        check(buttons and all(not enabled_action(n) for n in buttons), "Replace was enabled without confirmation")
        self.type_into(field, "REPLACE")
        self.click(name + "-confirm-replace", lambda n: label(n) == "Replace" and enabled_action(n))
        _, nodes = self.wait_ui(name + "-restored", lambda n: label(n) == "Restored" or
                                (n.get("package") == self.pkg and edit_field(n)), deny_again=True, timeout=150)
        self.screenshot(name + "-restored")
        done = next((n for n in nodes if label(n) == "Done" and enabled_action(n)), None)
        if done is not None:
            self.tap(done)
        self.chat(name + "-restored-chat")

    def in_place_upgrade(self, earlier, latest):
        self.initial_install(CURRENT, earlier, "before-upgrade")
        count = self.rename_fixture_pipeline("Stage10Upgrade")
        fixture = self.file_fixture("Stage10Upgrade")
        sha = self.checksum(fixture)
        self.settings("upgrade-before")
        self.appearance("upgrade-before", set_values=True)
        self.stop()
        database = self.checksum(DB)
        adb("install", "-r", str(latest), timeout=160)
        check(self.checksum(DB) == database, "Covering installation changed the database file")
        self.launch("after-upgrade")
        self.chat("after-upgrade-chat")
        check(self.checksum(fixture) == sha, "Covering installation changed workspace content")
        self.settings("upgrade-after")
        self.appearance("upgrade-after")
        pid = shell("pidof", self.pkg)
        self.launch("warm-pipelines-shortcut", shortcut=True)
        check(self.pipeline_state("Stage10Upgrade", "warm-shortcut-target") == count, "Pipeline count changed")
        check(shell("pidof", self.pkg) == pid, "Warm shortcut replaced the existing process")
        self.screenshot("warm-shortcut-target")
        self.stop()
        self.launch("cold-pipelines-shortcut", shortcut=True)
        check(self.pipeline_state("Stage10Upgrade", "cold-shortcut-target") == count, "Cold shortcut missed the library")
        self.theme_backup = self.export_backup("current-data")
        return "APK updated in place; database, pipeline, file and appearance preserved; cold and warm shortcut passed"

    def cross_package(self, legacy, latest):
        self.initial_install(LEGACY, legacy, "old-package")
        count = self.rename_fixture_pipeline("Stage10Legacy")
        fixture = self.file_fixture("Stage10Legacy")
        sha = self.checksum(fixture)
        path = self.export_backup("legacy-data")
        self.initial_install(CURRENT, latest, "new-package")
        check(shell("pm", "path", LEGACY).startswith("package:"), "Legacy app disappeared while installing the new one")
        destination = self.file_fixture("Stage10Destination")
        self.restore_backup("legacy-to-zhiwen", path, preserved_file=destination)
        check(self.checksum(fixture) == sha, "The legacy workspace file did not restore")
        self.app_shell(f"test ! -e {destination}")
        self.click("open-restored-library", labeled("Pipelines"))
        check(self.pipeline_state("Stage10Legacy", "legacy-pipeline-restored") == count, "The legacy pipeline count changed")
        self.screenshot("legacy-pipeline-restored")
        self.pkg = LEGACY
        check(self.checksum(fixture) == sha, "Original install data changed during the cross-package restore")
        self.pkg = CURRENT
        return "Co-installation and cross-package import passed; incorrect password and preview preserved target data"

    def appearance_roundtrip(self):
        check(self.theme_backup is not None, "The current-version backup is unavailable")
        self.pkg = CURRENT
        self.stop()
        self.launch("before-theme-restore")
        self.chat("before-theme-restore-chat")
        self.restore_backup("theme-roundtrip", self.theme_backup)
        self.settings("restore-theme")
        self.appearance("restore-theme")
        return "Backup restore retained the selected dark mode and vivid intensity"

    def run(self, name, action):
        try:
            answer = {"case": name, "status": "pass", "note": action()}
        except (AssertionError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            answer = {"case": name, "status": "fail", "note": str(error)}
            try:
                self.screenshot(name + "-failed")
            except (AssertionError, RuntimeError, subprocess.TimeoutExpired):
                pass
        self.results.append(answer)
        (self.evidence / "results.json").write_text(json.dumps(self.results, indent=2, ensure_ascii=False))
        print(answer, flush=True)


def main():
    packages = Path(sys.argv[1])
    evidence = Path(sys.argv[2])
    api = sys.argv[3]
    evidence.mkdir(parents=True, exist_ok=True)
    serial = adb("get-serialno").decode().strip()
    check(serial.startswith("emulator-") and shell("getprop", "ro.kernel.qemu") == "1",
          "Use only disposable emulator data")
    check(shell("getprop", "ro.build.version.sdk") == api, "Wrong emulator API")
    hashes = {}
    for name in ("legacy.apk", "earlier.apk", "latest.apk"):
        with (packages / name).open("rb") as data:
            hashes[name] = hashlib.file_digest(data, "sha256").hexdigest()
    (evidence / "target.json").write_text(json.dumps({"main": BASELINE, "api": api, "apk": hashes}, indent=2))
    shell("input", "keyevent", "KEYCODE_WAKEUP")
    shell("wm", "dismiss-keyguard")
    shell("mkdir", "-p", "/sdcard/Download")
    adb("logcat", "-c")
    smoke = Smoke(evidence)
    smoke.theme_backup = None
    try:
        smoke.run("same_package_upgrade", lambda: smoke.in_place_upgrade(packages / "earlier.apk", packages / "latest.apk"))
        smoke.run("cross_package_backup_restore", lambda: smoke.cross_package(packages / "legacy.apk", packages / "latest.apk"))
        smoke.run("appearance_backup_roundtrip", smoke.appearance_roundtrip)
    finally:
        (evidence / "logcat.txt").write_bytes(adb("logcat", "-d", "-v", "threadtime"))
        (evidence / "crash.txt").write_bytes(adb("logcat", "-b", "crash", "-d"))
    return int(any(result["status"] != "pass" for result in smoke.results))


if __name__ == "__main__":
    sys.exit(main())
