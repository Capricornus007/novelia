#!/usr/bin/env python3
"""Publish verified ARM64 preview artifacts through staged GitHub assets."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.parse
import zipfile


ROOT = Path(__file__).resolve().parent.parent
START_MARKER = "<!-- novelia-preview-build:start -->"
END_MARKER = "<!-- novelia-preview-build:end -->"
STABLE_NAMES = (
    "Novelia-preview-arm64-v8a.apk",
    "Novelia-preview-arm64-v8a.apk.sha256",
    "Novelia-preview-build-info.txt",
    "Novelia-preview-mapping.zip",
)
LEGACY_NAMES = ("Novelia-preview-universal.apk", "Novelia-preview-universal.apk.sha256")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_gh(arguments, allow_not_found=False):
    response = subprocess.run(
        ["gh", *arguments], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    output = response.stdout
    if response.returncode != 0:
        if allow_not_found and re.search(r"\bHTTP 404\b", output):
            return None
        status = re.search(r"\bHTTP [0-9]{3}\b", output)
        status_text = status.group(0) if status else "no HTTP status"
        operation = f"{arguments[2]} {arguments[3]}" if arguments[0] == "api" else arguments[0]
        raise RuntimeError(
            f"GitHub CLI failed ({status_text}, exit {response.returncode}) during {operation}."
        )
    return response.stdout


def get_json(endpoint, allow_not_found=False, paginate=False):
    arguments = ["api", "--method", "GET", endpoint, "-H", "X-GitHub-Api-Version: 2026-03-10"]
    if paginate:
        # Preserve page boundaries so every page can be validated as a JSON array.
        arguments.extend(("--paginate", "--slurp"))
    response = run_gh(arguments, allow_not_found=allow_not_found)
    if response is None:
        return None
    parsed = json.loads(response)
    if not paginate:
        return parsed
    if not isinstance(parsed, list) or not all(isinstance(page, list) for page in parsed):
        raise RuntimeError("Unexpected paginated GitHub API response; expected arrays of items.")
    return [item for page in parsed for item in page]


def get_release(repository, encoded_tag, tag):
    # The tag endpoint only resolves published releases. Drafts need the list endpoint.
    published = get_json(f"repos/{repository}/releases/tags/{encoded_tag}", allow_not_found=True)
    if published is not None:
        return published
    releases = get_json(f"repos/{repository}/releases?per_page=100", paginate=True)
    matching = [release for release in releases if release.get("tag_name") == tag]
    if len(matching) > 1:
        raise RuntimeError("Multiple releases use the preview tag; refusing an ambiguous update.")
    return matching[0] if matching else None


def merge_notes(existing_body, build_info):
    block = f"{START_MARKER}\n{build_info}\n{END_MARKER}"
    start_count = existing_body.count(START_MARKER)
    end_count = existing_body.count(END_MARKER)
    if start_count == 0 and end_count == 0:
        return block if not existing_body else f"{existing_body}\n\n{block}"
    if start_count != 1 or end_count != 1:
        raise RuntimeError(
            "Invalid preview build markers in release notes; repair the marker pair "
            "before publishing. Manual notes were preserved."
        )
    start = existing_body.index(START_MARKER)
    end = existing_body.index(END_MARKER)
    if end < start:
        raise RuntimeError("Preview build markers are in the wrong order. Manual notes were preserved.")
    return existing_body[:start] + block + existing_body[end + len(END_MARKER):]


def test_preview_head():
    branch = urllib.parse.quote(os.environ["PREVIEW_DEFAULT_BRANCH"], safe="")
    head = get_json(f"repos/{os.environ['GITHUB_REPOSITORY']}/git/ref/heads/{branch}")
    return head.get("object", {}).get("sha") == os.environ["GITHUB_SHA"]


def write_summary(message):
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary_file:
            summary_file.write(message + "\n")
    print(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-directory", required=True)
    parser.add_argument("--tag", default="preview")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.tag):
        raise RuntimeError("Invalid preview release tag.")
    if not os.environ.get("GH_TOKEN", "").strip():
        raise RuntimeError("Missing GitHub workflow token.")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    commit = os.environ.get("GITHUB_SHA", "")
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
    ):
        raise RuntimeError("Invalid repository or commit.")
    default_branch = os.environ.get("PREVIEW_DEFAULT_BRANCH", "")
    if not default_branch.strip() or os.environ.get("GITHUB_REF") != f"refs/heads/{default_branch}":
        raise RuntimeError("Only the default branch may update the preview release.")
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        if not re.fullmatch(r"[0-9]+", os.environ.get(name, "")):
            raise RuntimeError(f"Invalid {name}.")

    source_directory = (ROOT / args.artifacts_directory).resolve()
    if not source_directory.is_dir():
        raise RuntimeError("Preview artifacts directory is missing.")
    apks = sorted(source_directory.glob("*.apk"))
    if len(apks) != 1:
        raise RuntimeError("Expected exactly one verified preview APK.")
    apk = apks[0]
    checksum_path = Path(f"{apk}.sha256")
    mapping_path = source_directory / f"{apk.stem}-mapping.txt"
    info_path = source_directory / f"{apk.stem}-build-info.txt"
    for path in (checksum_path, mapping_path, info_path):
        if not path.is_file():
            raise RuntimeError("Missing preview checksum, build info or R8 mapping.")
    digest = sha256(apk)
    recorded_hash = checksum_path.read_text(encoding="utf-8").strip().split(" ")[0]
    if digest != recorded_hash:
        raise RuntimeError("Downloaded preview APK checksum mismatch.")
    info = {}
    for line in info_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            info[key] = value
    if info.get("commit") != commit or info.get("variant") != "release" or info.get("abi") != "arm64-v8a":
        raise RuntimeError("Preview build info does not match this ARM64 Release build.")

    if not test_preview_head():
        write_summary("跳过预发布更新：默认分支已有更新的提交，本次 APK 仍可从 Actions 下载。")
        return

    encoded_tag = urllib.parse.quote(args.tag, safe="")
    release = get_release(repository, encoded_tag, args.tag)
    if release is not None:
        if not release.get("prerelease"):
            raise RuntimeError("The selected tag belongs to a regular release; refusing to replace it.")
        if release.get("immutable"):
            raise RuntimeError(
                "The preview release is immutable. Use a mutable preview tag; "
                "immutable assets cannot be replaced."
            )

    # Staging names keep the previous download available until every new upload succeeds.
    generation = f"{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
    stage_directory = ROOT / "outputs/preview-release" / generation
    stage_directory.mkdir(parents=True, exist_ok=True)
    staged = [
        {
            "name": name,
            "staged_name": f"Novelia-preview-staging-{generation}-{name}",
            "path": stage_directory / f"Novelia-preview-staging-{generation}-{name}",
        }
        for name in STABLE_NAMES
    ]
    shutil.copyfile(apk, staged[0]["path"])
    staged[1]["path"].write_text(f"{digest}  {STABLE_NAMES[0]}\n", encoding="utf-8")
    shutil.copyfile(info_path, staged[2]["path"])
    with zipfile.ZipFile(staged[3]["path"], "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(mapping_path, arcname=mapping_path.name)

    server_url = os.environ["GITHUB_SERVER_URL"]
    release_url = f"{server_url}/{repository}/releases/tag/{encoded_tag}"
    apk_url = f"{server_url}/{repository}/releases/download/{encoded_tag}/{STABLE_NAMES[0]}"
    build_info = "\n".join([
        "### 自动构建信息", "",
        "此 Pre-release 随默认分支的成功构建自动更新，附件会被后续预览替换。", "",
        f"- 应用版本：{info['versionName']} ({info['versionCode']})",
        f"- 源码提交：[{commit}]({server_url}/{repository}/commit/{commit})",
        f"- 构建记录：[GitHub Actions]({server_url}/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']})",
        "- 设备架构：ARM64 (`arm64-v8a`)", f"- [下载 ARM64 Release APK]({apk_url})", "",
        "启用 R8 压缩和资源收缩，与本地构建共用固定预览测试证书。同签名本地包可覆盖安装，"
        "新包版本码须不低于已安装版本；其他签名来源迁移前请先备份阅读资料。",
    ])
    notes_path = stage_directory / "release-notes.md"
    notes_path.write_text(
        merge_notes((release or {}).get("body") or "", build_info), encoding="utf-8", newline=""
    )
    title = f"Novelia {info['versionName']} 预览版"
    if release is None:
        run_gh([
            "release", "create", args.tag, "--repo", repository, "--draft", "--prerelease",
            "--latest=false", "--target", commit, "--title", title, "--notes-file", str(notes_path),
        ])
        release = get_release(repository, encoded_tag, args.tag)
        if release is None:
            raise RuntimeError("The newly created preview draft could not be located.")
    run_gh([
        "release", "upload", args.tag, "--repo", repository, "--clobber",
        *[str(file["path"]) for file in staged],
    ])
    assets = get_json(f"repos/{repository}/releases/{release['id']}/assets?per_page=100", paginate=True)
    new_assets = {}
    for file in staged:
        matching = [asset for asset in assets if asset.get("name") == file["staged_name"]]
        if (
            len(matching) != 1
            or matching[0].get("state") != "uploaded"
            or matching[0].get("size") != file["path"].stat().st_size
        ):
            raise RuntimeError(
                "A staged Release asset is missing or incomplete; previous preview assets were preserved."
            )
        asset = matching[0]
        expected_digest = "sha256:" + sha256(file["path"])
        if asset.get("digest") and asset["digest"] != expected_digest:
            raise RuntimeError(
                "A staged Release asset digest does not match; previous preview assets were preserved."
            )
        new_assets[file["name"]] = asset
    if not test_preview_head():
        for asset in new_assets.values():
            run_gh(["api", "--method", "DELETE", f"repos/{repository}/releases/assets/{asset['id']}"])
        write_summary("跳过预发布替换：上传期间默认分支已有更新，上一版预览附件已保留。")
        return

    # Move only the rolling preview tag; versioned distribution tags are not selected automatically.
    tag_endpoint = f"repos/{repository}/git/ref/tags/{encoded_tag}"
    tag_ref = get_json(tag_endpoint, allow_not_found=True)
    if tag_ref is None:
        run_gh([
            "api", "--method", "POST", f"repos/{repository}/git/refs",
            "-f", f"ref=refs/tags/{args.tag}", "-f", f"sha={commit}",
        ])
    elif tag_ref["object"]["sha"] != commit:
        run_gh([
            "api", "--method", "PATCH", f"repos/{repository}/git/refs/tags/{encoded_tag}",
            "-f", f"sha={commit}", "-F", "force=true",
        ])
    for file in staged:
        for old in assets:
            if old.get("name") == file["name"]:
                run_gh(["api", "--method", "DELETE", f"repos/{repository}/releases/assets/{old['id']}"])
        run_gh([
            "api", "--method", "PATCH",
            f"repos/{repository}/releases/assets/{new_assets[file['name']]['id']}",
            "-f", f"name={file['name']}",
        ])

    # Refresh immediately before editing so manual changes made during upload are retained.
    latest = get_json(f"repos/{repository}/releases/{release['id']}")
    notes_path.write_text(merge_notes(latest.get("body") or "", build_info), encoding="utf-8", newline="")
    run_gh([
        "release", "edit", args.tag, "--repo", repository, "--draft=false", "--prerelease",
        "--latest=false", "--target", commit, "--title", title, "--notes-file", str(notes_path),
    ])
    new_ids = {asset["id"] for asset in new_assets.values()}
    for old in assets:
        if old.get("name", "").startswith("Novelia-preview-staging-") and old["id"] not in new_ids:
            run_gh(["api", "--method", "DELETE", f"repos/{repository}/releases/assets/{old['id']}"])
    for old in assets:
        if old.get("name") in LEGACY_NAMES:
            run_gh(["api", "--method", "DELETE", f"repos/{repository}/releases/assets/{old['id']}"])
    write_summary(f"[Preview Pre-release]({release_url}) 已更新，固定下载地址：[Release APK]({apk_url})。")


if __name__ == "__main__":
    main()
