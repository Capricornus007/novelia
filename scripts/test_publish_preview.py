#!/usr/bin/env python3
"""Verify publication behavior using a mocked gh command, without network access."""

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import subprocess


ROOT = Path(__file__).resolve().parent.parent
PUBLISHER = ROOT / "scripts/publish_preview.py"
START_MARKER = "<!-- novelia-preview-build:start -->"
END_MARKER = "<!-- novelia-preview-build:end -->"
STABLE_NAMES = (
    "Novelia-preview-arm64-v8a.apk", "Novelia-preview-arm64-v8a.apk.sha256",
    "Novelia-preview-build-info.txt", "Novelia-preview-mapping.zip",
)
LEGACY_NAMES = ("Novelia-preview-universal.apk", "Novelia-preview-universal.apk.sha256")



class Fixture:
    def __init__(self, state):
        self.__dict__.update(state)

    def save(self, path):
        path.write_text(json.dumps(self.__dict__), encoding="utf-8")

    def command(self, arguments):
        self.calls.append(" ".join(arguments))
        if arguments[0] == "release":
            action = arguments[1]
            if action == "create":
                self.created = True
                self.body = Path(arguments[arguments.index("--notes-file") + 1]).read_bytes().decode("utf-8")
                return 0, "https://github.com/example/novelia/releases/untagged/draft-fixture\n"
            if action == "upload":
                if self.mode == "upload-failure":
                    return 1, "gh: Service Unavailable (HTTP 503)\n"
                for argument in arguments:
                    path = Path(argument)
                    if not path.is_file():
                        continue
                    self.next_id += 1
                    self.assets.append({
                        "id": self.next_id, "name": path.name, "state": "uploaded",
                        "size": path.stat().st_size,
                        "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                    })
                if self.mode == "notes-edited-during-upload":
                    self.body = self.edited_body
                return 0, ""
            if action == "edit":
                self.body = Path(arguments[arguments.index("--notes-file") + 1]).read_bytes().decode("utf-8")
                self.published = True
                return 0, ""
        if arguments[0] == "api":
            method, endpoint = arguments[2], arguments[3]
            if method == "GET":
                if endpoint.endswith("/git/ref/heads/main"):
                    if self.mode == "head-not-found":
                        return 1, "gh: Not Found (HTTP 404)\n"
                    self.head_reads += 1
                    sha = self.commit
                    if self.mode == "stale" or (self.mode == "race" and self.head_reads > 1):
                        sha = "2" * 40
                    return 0, json.dumps({"object": {"sha": sha}})
                if endpoint.endswith("/releases/tags/preview"):
                    if self.mode == "forbidden":
                        return 1, "gh: Resource not accessible by integration (HTTP 403)\n"
                    if self.mode in ("create", "resume-draft", "duplicate-drafts") and not self.published:
                        return 1, "gh: Not Found (HTTP 404)\n"
                    return 0, json.dumps({
                        "id": 7, "body": self.body, "prerelease": self.mode != "regular",
                        "immutable": self.mode == "immutable",
                    })
                if endpoint.endswith("/releases?per_page=100"):
                    pages = [[{"id": 8, "tag_name": "v0.0.1", "draft": False, "prerelease": False, "immutable": True}]]
                    if self.created or self.mode in ("resume-draft", "duplicate-drafts"):
                        pages.append([{"id": 7, "tag_name": "preview", "body": self.body, "draft": True, "prerelease": True, "immutable": False}])
                    if self.mode == "duplicate-drafts":
                        pages[1].append({"id": 9, "tag_name": "preview", "draft": True, "prerelease": True, "immutable": False})
                    return 0, json.dumps(pages)
                if endpoint.endswith("/releases/7"):
                    return 0, json.dumps({"id": 7, "body": self.body})
                if endpoint.endswith("/assets?per_page=100"):
                    if self.mode == "digest-mismatch":
                        self.assets[-1]["digest"] = "sha256:bad"
                    return 0, json.dumps([self.assets[:3], self.assets[3:]])
                if endpoint.endswith("/git/ref/tags/preview"):
                    if self.tag_sha is None:
                        return 1, "gh: Not Found (HTTP 404)\n"
                    return 0, json.dumps({"object": {"sha": self.tag_sha}})
            if method == "POST" and endpoint.endswith("/git/refs"):
                self.tag_sha = self.commit
                return 0, "{}"
            if method == "PATCH" and endpoint.endswith("/git/refs/tags/preview"):
                if self.mode == "tag-protected":
                    return 1, "gh: Resource not accessible by integration (HTTP 403)"
                self.tag_sha = self.commit
                return 0, "{}"
            match = re.search(r"/releases/assets/([0-9]+)$", endpoint)
            if match:
                asset_id = int(match.group(1))
                asset = next(asset for asset in self.assets if asset["id"] == asset_id)
                if method == "DELETE":
                    self.deleted.append(asset_id)
                    self.assets.remove(asset)
                    return 0, ""
                if method == "PATCH":
                    field = next(argument for argument in arguments if argument.startswith("name="))
                    asset["name"] = field[5:]
                    return 0, "{}"
        raise RuntimeError("Unexpected mock GitHub command: " + " ".join(arguments))


def mock_gh(arguments):
    state_path = Path(os.environ["NOVELIA_PREVIEW_FIXTURE"])
    fixture = Fixture(json.loads(state_path.read_text(encoding="utf-8")))
    fixture.mode = state_path.parent.name
    status, output = fixture.command(arguments)
    state_path.write_text(json.dumps(fixture.__dict__), encoding="utf-8")
    if output:
        print(output, end="")
    return status


def make_fixture(mode, directory):
    commit = "1" * 40
    directory.mkdir(parents=True)
    apk = directory / "Novelia-fixture.apk"
    apk.write_text("synthetic APK fixture\n", encoding="utf-8")
    digest = "0" * 64 if mode == "checksum-mismatch" else hashlib.sha256(apk.read_bytes()).hexdigest()
    Path(f"{apk}.sha256").write_text(f"{digest}  Novelia-fixture.apk\n", encoding="utf-8")
    (directory / "Novelia-fixture-mapping.txt").write_text("synthetic R8 mapping\n", encoding="utf-8")
    abi = "universal" if mode == "wrong-abi" else "arm64-v8a"
    (directory / "Novelia-fixture-build-info.txt").write_text(
        f"commit={commit}\nversionName=0.0.1\nversionCode=1\nvariant=release\nabi={abi}\n",
        encoding="utf-8",
    )
    manual_prefix = "# 维护者说明\r\n中文说明与 [手动链接](https://example.invalid/docs)。\r\n\r\n"
    manual_suffix = "\r\n\r\n## 手写升级提示\n保留末尾空行。\n\n"
    old_block = f"{START_MARKER}\n旧版自动信息，应该替换。\n{END_MARKER}"
    initial_body = {
        "notes-managed-block": manual_prefix + old_block + manual_suffix,
        "notes-empty": "", "notes-null": None,
        "notes-unclosed-start": manual_prefix + START_MARKER + manual_suffix,
        "notes-unclosed-end": manual_prefix + END_MARKER + manual_suffix,
        "notes-duplicate-block": manual_prefix + old_block + "\n" + old_block + manual_suffix,
        "notes-reversed-markers": manual_prefix + END_MARKER + "\n" + START_MARKER + manual_suffix,
    }.get(mode, manual_prefix)
    fixture = Fixture({
        "mode": mode, "calls": [], "deleted": [], "assets": [], "next_id": 100,
        "created": False, "published": False, "head_reads": 0, "commit": commit,
        "tag_sha": None if mode in ("create", "resume-draft") else "0" * 40,
        "body": initial_body,
        "edited_body": "# 上传期间更新的人工描述\r\n保留这次修改。\r\n",
    })
    if mode != "create":
        for index, name in enumerate(STABLE_NAMES):
            if mode == "legacy-universal" and index < 2:
                continue
            fixture.assets.append({"id": index + 1, "name": name, "state": "uploaded", "size": 1, "digest": "sha256:old"})
        fixture.assets.extend([
            {"id": 5, "name": "manual-notes.txt", "state": "uploaded", "size": 1, "digest": "sha256:manual"},
            {"id": 6, "name": "Novelia-preview-staging-999-1-leftover.apk", "state": "uploaded", "size": 1, "digest": "sha256:leftover"},
            {"id": 7, "name": LEGACY_NAMES[0], "state": "uploaded", "size": 1, "digest": "sha256:universal"},
            {"id": 8, "name": LEGACY_NAMES[1], "state": "uploaded", "size": 1, "digest": "sha256:universal"},
        ])
    state_path = directory / "fixture.json"
    fixture.save(state_path)
    mock_path = directory / "gh"
    mock_path.write_text(f"#!/bin/sh\nexec python3 {Path(__file__).resolve()} --gh-mock \"$@\"\n", encoding="utf-8")
    mock_path.chmod(0o755)
    environment = {
        **os.environ, "PATH": f"{directory}{os.pathsep}{os.environ['PATH']}",
        "NOVELIA_PREVIEW_FIXTURE": str(state_path), "GH_TOKEN": "validation-placeholder",
        "GITHUB_REPOSITORY": "example/novelia", "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_SHA": commit, "GITHUB_REF": "refs/heads/feature" if mode == "non-default" else "refs/heads/main",
        "PREVIEW_DEFAULT_BRANCH": "main", "GITHUB_RUN_ID": "12345", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_STEP_SUMMARY": str(directory / "summary.md"),
    }
    result = subprocess.run(
        [sys.executable, str(PUBLISHER), "--artifacts-directory", str(directory), "--tag", "preview"],
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    return result, Fixture(json.loads(state_path.read_text(encoding="utf-8"))), environment, initial_body, manual_prefix, manual_suffix




def main():
    success_modes = ["create", "resume-draft", "update", "legacy-universal", "notes-manual-only", "notes-managed-block", "notes-empty", "notes-null", "notes-edited-during-upload"]
    modes = success_modes + ["wrong-abi", "notes-unclosed-start", "notes-unclosed-end", "notes-duplicate-block", "notes-reversed-markers", "duplicate-drafts", "head-not-found", "stale", "race", "upload-failure", "digest-mismatch", "tag-protected", "immutable", "regular", "forbidden", "checksum-mismatch", "non-default"]
    with tempfile.TemporaryDirectory(prefix="novelia-preview-tests-") as temporary_root:
        for mode in modes:
            result, fixture, environment, initial_body, manual_prefix, manual_suffix = make_fixture(
                mode, Path(temporary_root) / mode
            )
            failure = result.stdout if result.returncode != 0 else ""
            def check(condition, message):
                if not condition:
                    raise AssertionError(f"{mode}: {message}; {failure}")
            check((result.returncode == 0) if mode in success_modes or mode in ("stale", "race") else (result.returncode != 0), f"{mode} failed: {failure}")
            if mode in success_modes:
                check(fixture.published and fixture.tag_sha == environment["GITHUB_SHA"], f"{mode} did not publish the expected commit.")
                for name in STABLE_NAMES:
                    check(sum(asset["name"] == name for asset in fixture.assets) == 1, f"{mode} did not replace {name}")
                check(not any(asset["name"].startswith("Novelia-preview-staging-") for asset in fixture.assets), f"{mode} left staged assets after success.")
                check(any("--latest=false" in call for call in fixture.calls), f"{mode} could change the stable Latest release.")
                check(not any(asset["name"] in LEGACY_NAMES for asset in fixture.assets), f"{mode} retained an obsolete universal package.")
                check("/Novelia-preview-arm64-v8a.apk" in fixture.body, f"{mode} published the wrong APK link.")
                check(fixture.body.count(START_MARKER) == 1 and fixture.body.count(END_MARKER) == 1, f"{mode} changed automatic markers.")
                check(f"[GitHub Actions]({environment['GITHUB_SERVER_URL']}/{environment['GITHUB_REPOSITORY']}/actions/runs/{environment['GITHUB_RUN_ID']})" in fixture.body, f"{mode} did not update build information.")
                if mode == "notes-managed-block":
                    check(fixture.body.startswith(manual_prefix) and fixture.body.endswith(manual_suffix), "Manual text or its whitespace was changed.")
                    check("旧版自动信息" not in fixture.body, "The previous automatic block was retained.")
                elif mode == "notes-edited-during-upload":
                    check(fixture.body.startswith(fixture.edited_body), "A manual edit made during upload was lost.")
                elif mode != "create":
                    check(fixture.body.startswith(initial_body or ""), f"{mode} did not retain the original notes.")
                if mode == "resume-draft":
                    check(not fixture.created, "An existing draft was not reused.")
                if mode == "update":
                    check(5 not in fixture.deleted, "A manually attached release asset was removed.")
                    upload_index = next(i for i, call in enumerate(fixture.calls) if call.startswith("release upload "))
                    delete_index = next(i for i, call in enumerate(fixture.calls) if call.startswith("api --method DELETE "))
                    check(delete_index > upload_index, "Old release assets were deleted before upload success.")
                if mode == "legacy-universal":
                    check(5 not in fixture.deleted, "Migration removed a manual attachment.")
                    publish_index = next(i for i, call in enumerate(fixture.calls) if call.startswith("release edit "))
                    legacy_delete = next(i for i, call in enumerate(fixture.calls) if call.startswith("api --method DELETE ") and "/assets/7" in call)
                    check(legacy_delete > publish_index, "The universal package was removed before ARM64 publication succeeded.")
            else:
                check((result.returncode != 0) if mode not in ("stale", "race") else True, f"{mode} returned an unexpected result: {result.stdout}")
                check(not fixture.published, f"{mode} published unexpectedly.")
                for asset_id in (1, 2, 3, 4, 5, 7, 8):
                    check(asset_id not in fixture.deleted, f"{mode} removed a previous preview or manual attachment.")
                check(fixture.tag_sha == "0" * 40, f"{mode} moved the preview tag unexpectedly.")
                check(not fixture.created, f"{mode} created a release unexpectedly.")
                if mode == "head-not-found":
                    check("GET repos/example/novelia/git/ref/heads/main" in result.stdout, "API diagnostics omitted the failing endpoint.")
                if mode == "wrong-abi":
                    check(not fixture.calls, "A non-ARM64 package reached GitHub.")
                if mode.startswith("notes-"):
                    check(fixture.body == initial_body, f"{mode} changed malformed notes.")
                    check(not any(call.startswith("release upload ") for call in fixture.calls), f"{mode} uploaded assets despite malformed note markers.")
            print(f"PASS: {mode}")
    print(f"Preview publication checks passed: {len(modes)} scenarios, no network requests.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--gh-mock"]:
        raise SystemExit(mock_gh(sys.argv[2:]))
    main()
