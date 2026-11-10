#!/usr/bin/env python3
"""Verify an ARM64 Release APK and prepare its preview artifacts."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    apk_directory = (ROOT / "app/build/outputs/apk/release").resolve()
    metadata = json.loads((apk_directory / "output-metadata.json").read_text(encoding="utf-8"))
    elements = metadata.get("elements")
    if metadata.get("applicationId") != "cc.novelia.app" or not isinstance(elements, list) or len(elements) != 1:
        raise RuntimeError("Unexpected Release APK metadata.")
    element = elements[0]
    if not isinstance(element, dict) or not isinstance(element.get("outputFile"), str):
        raise RuntimeError("Unexpected Release APK metadata.")

    apk = (apk_directory / element["outputFile"]).resolve()
    try:
        apk.relative_to(apk_directory)
    except ValueError as error:
        raise RuntimeError("Release APK is missing or outside its output directory.") from error
    if apk == apk_directory or apk.suffix != ".apk" or not apk.is_file():
        raise RuntimeError("Release APK is missing or outside its output directory.")

    mapping = ROOT / "app/build/outputs/mapping/release/mapping.txt"
    if not mapping.is_file():
        raise RuntimeError("Release R8 mapping is missing.")
    android_home = os.environ.get("ANDROID_HOME")
    if not android_home:
        raise RuntimeError("ANDROID_HOME is not set.")
    apksigner = Path(android_home) / "build-tools/37.0.0/apksigner"
    signature = subprocess.run(
        [str(apksigner), "verify", "--print-certs", str(apk)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if signature.returncode != 0:
        raise RuntimeError("Release APK signature verification failed.")
    expected = ROOT.joinpath("gradle/preview-signing.sha256").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("Preview certificate configuration is invalid.")
    certificates = re.findall(
        r"^(?:V\d+\s+)?Signer(?:\s+#\d+)?:?\s+certificate SHA-256 digest: ([0-9a-fA-F]{64})\s*$",
        signature.stdout,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if len(certificates) != 1 or certificates[0].lower() != expected:
        raise RuntimeError("Release APK was not signed with the shared preview certificate.")

    with zipfile.ZipFile(apk) as archive:
        native_abis = {
            name.split("/")[1]
            for name in archive.namelist()
            if re.fullmatch(r"lib/[^/]+/[^/]+\.so", name)
        }
    if native_abis != {"arm64-v8a"}:
        raise RuntimeError("Preview APK must contain only ARM64 native libraries.")

    output_directory = ROOT / "outputs/preview"
    output_directory.mkdir(parents=True, exist_ok=True)
    commit = os.environ["GITHUB_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError("Invalid source commit.")
    stem = (
        f"Novelia-{element['versionName']}-preview-arm64-v8a-{commit[:7]}-"
        f"{os.environ['GITHUB_RUN_NUMBER']}.{os.environ['GITHUB_RUN_ATTEMPT']}"
    )
    output_apk = output_directory / f"{stem}.apk"
    shutil.copyfile(apk, output_apk)
    shutil.copyfile(mapping, output_directory / f"{stem}-mapping.txt")
    Path(f"{output_apk}.sha256").write_text(f"{sha256(output_apk)}  {stem}.apk\n", encoding="utf-8")
    build_info = (
        f"commit={commit}\n"
        f"ref={os.environ['GITHUB_REF']}\n"
        f"run={os.environ['GITHUB_RUN_NUMBER']}\n"
        f"attempt={os.environ['GITHUB_RUN_ATTEMPT']}\n"
        f"versionName={element['versionName']}\n"
        f"versionCode={element['versionCode']}\n"
        "variant=release\n"
        "abi=arm64-v8a\n"
        "signing=shared-preview-test-certificate\n"
        f"certificateSha256={expected}\n"
    )
    (output_directory / f"{stem}-build-info.txt").write_text(build_info, encoding="utf-8")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output_file:
        output_file.write(f"apk-path={output_apk.relative_to(ROOT)}\n")
        output_file.write(f"artifact-name={stem}\n")


if __name__ == "__main__":
    main()
