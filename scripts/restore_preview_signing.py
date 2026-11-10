#!/usr/bin/env python3
"""Restore and validate the shared preview signing key without printing it."""

import base64
import binascii
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent.parent


def main():
    encoded = os.environ.get("NOVELIA_PREVIEW_KEYSTORE_BASE64", "")
    if not encoded.strip():
        raise RuntimeError(
            "Missing NOVELIA_PREVIEW_KEYSTORE_BASE64. Restore the original signing key "
            "and configure the Actions secret on the signing machine."
        )
    if len(encoded) > 48 * 1024:
        raise RuntimeError("Preview keystore Secret is too large.")

    keystore_path = Path(os.environ["RUNNER_TEMP"]) / "novelia-preview.keystore"
    if os.path.lexists(keystore_path):
        raise RuntimeError("Refusing to overwrite an existing preview keystore.")
    key_bytes = None
    try:
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise RuntimeError("Preview keystore Secret is not valid Base64.") from error
        if not decoded:
            raise RuntimeError("Preview keystore Secret is empty.")
        key_bytes = bytearray(decoded)
        keystore_path.write_bytes(key_bytes)
        del os.environ["NOVELIA_PREVIEW_KEYSTORE_BASE64"]

        expected = (ROOT / "gradle/preview-signing.sha256").read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RuntimeError("预览证书指纹配置无效。")
        keytool = (
            Path(os.environ["JAVA_HOME"]) / "bin/keytool"
            if os.environ.get("JAVA_HOME")
            else shutil.which("keytool")
        )
        if not keytool:
            raise RuntimeError("未找到 keytool；请设置 JAVA_HOME 或把 JDK bin 加入 PATH。")
        result = subprocess.run(
            [
                os.fspath(keytool),
                "-list",
                "-rfc",
                "-alias",
                "androiddebugkey",
                "-keystore",
                str(keystore_path),
                "-storepass:env",
                "NOVELIA_PREVIEW_STORE_PASSWORD",
            ],
            env={**os.environ, "NOVELIA_PREVIEW_STORE_PASSWORD": "android"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("读取预览证书失败；不会上传密钥。")
        match = re.search(
            r"-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----",
            result.stdout,
            re.DOTALL,
        )
        if not match:
            raise RuntimeError("未能读取预览公开证书；不会上传密钥。")
        try:
            certificate = base64.b64decode(re.sub(r"\s", "", match.group(1)), validate=True)
        except (ValueError, binascii.Error) as error:
            raise RuntimeError("未能读取预览公开证书；不会上传密钥。") from error
        actual = hashlib.sha256(certificate).hexdigest()
        if actual != expected:
            raise RuntimeError("证书指纹不匹配；请使用原有本地密钥，不会上传替代密钥。")
        if not re.search(r"\bPrivateKeyEntry\b", result.stdout):
            raise RuntimeError("密钥库仅含公开证书，没有预览签名私钥；不会上传。")
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
            output.write(f"NOVELIA_PREVIEW_KEYSTORE_PATH={keystore_path}\n")
        print(f"预览公开证书 SHA-256：{actual}")
    finally:
        if key_bytes is not None:
            key_bytes[:] = b"\0" * len(key_bytes)
        os.environ.pop("NOVELIA_PREVIEW_KEYSTORE_BASE64", None)


if __name__ == "__main__":
    main()
