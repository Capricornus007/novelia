#!/usr/bin/env python3
"""Verify preview signing configuration using a mocked gh command, without network access."""

import base64
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
CONFIGURE = ROOT / "scripts/configure-preview-signing.sh"
EXPECTED_SECRET_COMMAND = [
    "secret", "set", "NOVELIA_PREVIEW_KEYSTORE_BASE64",
    "--repo", "nobYoQ/novelia", "--app", "actions",
]


class Fixture:
    def __init__(self, mode):
        self.mode = mode
        self.secret_writes = 0

    def gh(self, arguments, stdin):
        command = " ".join(arguments)
        if command == "auth status --hostname github.com":
            if self.mode == "unauthenticated":
                return 1, ""
            return 0, ""
        if arguments != EXPECTED_SECRET_COMMAND:
            raise RuntimeError("Unexpected gh command; refusing any real request.")
        self.secret_writes += 1
        try:
            decoded = base64.b64decode(stdin, validate=True)
        except (ValueError, binascii_error()) as error:
            raise RuntimeError("stdin did not contain valid Base64.") from error
        original = (ROOT / ".android/debug.keystore").read_bytes()
        if decoded != original:
            raise RuntimeError("stdin did not contain the original key.")
        if self.mode == "upload-failure":
            return 1, "gh: upload failed\n"
        return 0, ""


def binascii_error():
    import binascii
    return binascii.Error


def mock_gh(arguments):
    state_path = Path(os.environ["NOVELIA_PREVIEW_FIXTURE"])
    fixture = Fixture(state_path.parent.name)
    stdin = sys.stdin.read()
    status, output = fixture.gh(arguments, stdin)
    state_path.write_text(str(fixture.secret_writes), encoding="utf-8")
    if output:
        print(output, end="")
    return status


def run_configure(arguments, fixture_directory, mode, environment):
    state_path = fixture_directory / "fixture.txt"
    state_path.write_text("0", encoding="utf-8")
    mock_path = fixture_directory / "gh"
    mock_path.write_text(
        f"#!/bin/sh\nexec python3 {Path(__file__).resolve()} --gh-mock \"$@\"\n",
        encoding="utf-8",
    )
    mock_path.chmod(0o755)
    env = {
        **environment,
        "PATH": f"{fixture_directory}{os.pathsep}{environment['PATH']}",
        "NOVELIA_PREVIEW_FIXTURE": str(state_path),
        "NOVELIA_PREVIEW_KEYSTORE_PATH": environment.get("NOVELIA_PREVIEW_KEYSTORE_PATH", ""),
    }
    env.pop("NOVELIA_PREVIEW_KEYSTORE_PATH", None)
    result = subprocess.run(
        [str(CONFIGURE), *arguments],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False, cwd=str(ROOT),
    )
    fixture = Fixture(mode)
    fixture.secret_writes = int(state_path.read_text(encoding="utf-8") or 0)
    return result, fixture


def assert_failure(name, result, expected):
    if result.returncode == 0:
        raise AssertionError(f"{name} should have failed: {result.stdout}")
    if not re.search(expected, result.stdout):
        raise AssertionError(f"Unexpected failure in {name}: {result.stdout}")
    print(f"PASS: {name}")


def main():
    with tempfile.TemporaryDirectory(prefix="novelia-signing-tests-") as temporary_root:
        fixture_root = Path(temporary_root)
        fixture_path = fixture_root / "preview-signing"
        fixture_path.mkdir()
        environment = {**os.environ}
        environment.pop("NOVELIA_PREVIEW_KEYSTORE_PATH", None)
        environment.pop("NOVELIA_PREVIEW_KEYSTORE_BASE64", None)
        environment.pop("RUNNER_TEMP", None)
        environment.pop("GITHUB_ENV", None)

        result, fixture = run_configure(["--check-only"], fixture_path, "success", environment)
        if result.returncode != 0:
            raise AssertionError(f"original certificate check failed: {result.stdout}")
        if fixture.secret_writes != 0:
            raise AssertionError("CheckOnly attempted to upload a secret.")
        print("PASS: original certificate")

        result, _ = run_configure(
            ["--keystore", str(fixture_path / "missing.keystore"), "--check-only"],
            fixture_path, "success", environment,
        )
        assert_failure("missing key", result, "缺少原有预览密钥")

        invalid_keystore = fixture_path / "invalid.keystore"
        invalid_keystore.write_text("invalid test data", encoding="utf-8")
        result, _ = run_configure(
            ["--keystore", str(invalid_keystore), "--check-only"],
            fixture_path, "success", environment,
        )
        assert_failure("invalid key", result, "读取预览证书失败")

        # 只保存公开证书的测试密钥库，私钥始终留在内存，不导出到文件。
        public_certificate_path = fixture_path / "public-only.cer"
        public_keystore_path = fixture_path / "public-only.keystore"
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", str(fixture_path / "temp.key"),
             "-out", str(public_certificate_path), "-days", "1", "-nodes",
             "-subj", "/CN=Preview signing test"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        (fixture_path / "temp.key").unlink()
        import_result = subprocess.run(
            ["keytool", "-importcert", "-noprompt", "-alias", "androiddebugkey",
             "-file", str(public_certificate_path), "-keystore", str(public_keystore_path),
             "-storepass", "android"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
        )
        if import_result.returncode != 0:
            raise AssertionError(f"Unable to prepare the public certificate fixture: {import_result.stdout}")
        result, _ = run_configure(
            ["--keystore", str(public_keystore_path), "--check-only"],
            fixture_path, "success", environment,
        )
        assert_failure("wrong certificate", result, "证书指纹不匹配")

        result, fixture = run_configure([], fixture_path, "unauthenticated", environment)
        assert_failure("missing login", result, "未登录")
        if fixture.secret_writes != 0:
            raise AssertionError("Invalid signing or authentication attempted to upload a secret.")

        result, fixture = run_configure([], fixture_path, "success", environment)
        if result.returncode != 0:
            raise AssertionError(f"original key upload failed: {result.stdout}")
        if fixture.secret_writes != 1:
            raise AssertionError("Expected one stdin upload.")
        print("PASS: original key uploaded only through stdin")

        result, fixture = run_configure([], fixture_path, "upload-failure", environment)
        assert_failure("upload failure", result, "配置 GitHub Secret 失败")

        # 直接运行工作流中的恢复步骤，验证缺失与错误编码均不会生成密钥。
        workflow = (ROOT / ".github/workflows/preview-apk.yml").read_text(encoding="utf-8")
        restore_lines = []
        in_restore = False
        in_run = False
        for line in workflow.splitlines():
            if line == "      - name: Restore shared preview signing key":
                in_restore = True
                continue
            if not in_restore:
                continue
            if line == "        run: |":
                in_run = True
                continue
            if in_run:
                if line.startswith("          "):
                    restore_lines.append(line[10:])
                else:
                    break
        if not restore_lines:
            raise AssertionError("Preview signing restore step is missing.")
        restore_script = "\n".join(restore_lines)

        def run_restore(env_overrides):
            env = {**environment, "RUNNER_TEMP": str(fixture_path),
                   "GITHUB_ENV": str(fixture_path / "github-env.txt"), **env_overrides}
            return subprocess.run(
                ["bash", "-c", restore_script],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, check=False, cwd=str(ROOT),
            )

        result = run_restore({"NOVELIA_PREVIEW_KEYSTORE_BASE64": ""})
        assert_failure("missing Secret", result, "Missing NOVELIA_PREVIEW_KEYSTORE_BASE64")
        result = run_restore({"NOVELIA_PREVIEW_KEYSTORE_BASE64": "invalid-base64!"})
        assert_failure("invalid Base64", result, "not valid Base64")
        result = run_restore({"NOVELIA_PREVIEW_KEYSTORE_BASE64": "A" * (48 * 1024 + 1)})
        assert_failure("oversized Secret", result, "too large")
        if (fixture_path / "novelia-preview.keystore").exists():
            raise AssertionError("Invalid Secret created a key file.")
        print("Preview signing checks passed: 10 scenarios, no network requests or private key files created.")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--gh-mock"]:
        raise SystemExit(mock_gh(sys.argv[2:]))
    main()
