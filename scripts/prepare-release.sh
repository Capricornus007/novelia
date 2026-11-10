#!/usr/bin/env bash
# 用法：./scripts/prepare-release.sh --apksigner <path> --certificate <sha256> [--abi <abi>] [--offline]
set -u -o pipefail

apksigner_path=''
certificate_sha256=''
abi='arm64-v8a'
offline=0
while (( $# )); do
    case $1 in
        --apksigner)
            if (( $# < 2 )); then echo '--apksigner 需要一个参数。' >&2; exit 2; fi
            apksigner_path=$2; shift 2
            ;;
        --certificate)
            if (( $# < 2 )); then echo '--certificate 需要一个参数。' >&2; exit 2; fi
            certificate_sha256=$2; shift 2
            ;;
        --abi)
            if (( $# < 2 )); then echo '--abi 需要一个参数。' >&2; exit 2; fi
            abi=$2; shift 2
            ;;
        --offline) offline=1; shift ;;
        *)
            echo "未知参数：$1" >&2
            exit 2
            ;;
    esac
done
case $abi in
    arm64-v8a | armeabi-v7a | x86_64 | x86 | universal) ;;
    *)
        echo "--abi 只接受 arm64-v8a、armeabi-v7a、x86_64、x86、universal。" >&2
        exit 2
        ;;
esac

root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$root_path"

checked_git() {
    local result
    if ! result=$(git "$@" 2>&1); then
        echo 'Git 检查失败，请确认当前提交和版本标签。' >&2
        exit 1
    fi
    printf '%s\n' "$result"
}

if [[ -z $apksigner_path || -z $certificate_sha256 ]]; then
    echo '必须指定 --apksigner 和 --certificate。' >&2
    exit 2
fi
if [[ ! -f $apksigner_path ]]; then
    echo '找不到 apksigner，请指定 Android Build Tools 中的完整路径。' >&2
    exit 1
fi
apksigner_path=$(cd -- "$(dirname -- "$apksigner_path")" && pwd)/${apksigner_path##*/}
expected_certificate=${certificate_sha256//:/}
expected_certificate=${expected_certificate,,}
if [[ ! $expected_certificate =~ ^[a-f0-9]{64}$ ]]; then
    echo '证书 SHA-256 指纹必须包含 64 位十六进制数字。' >&2
    exit 1
fi
version_name=''
version_code=''
while IFS='=' read -r key value; do
    key=${key//[[:space:]]/}
    case $key in
        versionName) version_name=$value ;;
        versionCode) version_code=$value ;;
    esac
done < version.properties
if [[ ! $version_name =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || [[ ! $version_code =~ ^[0-9]+$ ]] || (( 10#$version_code <= 0 )); then
    echo '版本配置无效。' >&2
    exit 1
fi
version_code=$((10#$version_code))
tag="v$version_name"
if [[ -n $(git status --porcelain --untracked-files=normal) ]]; then
    echo '工作区存在未提交文件。请先审查并提交变更，再从对应标签准备发行包。' >&2
    exit 1
fi
commit=$(checked_git rev-parse HEAD)
commit=${commit//$'\n'/}
tag_commit=$(checked_git rev-parse --verify "refs/tags/$tag^{commit}")
tag_commit=${tag_commit//$'\n'/}
if [[ $commit != "$tag_commit" ]]; then
    echo 'HEAD 与版本标签不一致。请切换到待发布标签对应的提交。' >&2
    exit 1
fi
for name in NOVELIA_KEYSTORE_PATH NOVELIA_KEYSTORE_PASSWORD NOVELIA_KEY_ALIAS NOVELIA_KEY_PASSWORD; do
    if [[ -z ${!name:-//[[:space:]]/} ]]; then
        echo "缺少签名环境变量：$name。请在本机安全配置，不要粘贴到 Issue 或聊天中。" >&2
        exit 1
    fi
done
output_path="$root_path/outputs/releases/$tag-$abi"
if [[ -e $output_path ]]; then
    echo '发行目录已存在；为避免覆盖，先自行核对并归档旧目录。' >&2
    exit 1
fi

tasks=(':app:testReleaseUnitTest' ':app:lintRelease' ':app:assembleRelease' '-PreleaseSigning=true')
if [[ $abi != universal ]]; then
    tasks+=("-PtargetAbi=$abi")
fi
build_args=("${tasks[@]}")
if (( offline )); then
    build_args+=(--offline)
fi
if ! ./build.sh "${build_args[@]}"; then
    exit 1
fi

apk_directory="$root_path/app/build/outputs/apk/release"
metadata_file="$apk_directory/output-metadata.json"
if [[ ! -f $metadata_file ]]; then
    echo 'APK 输出信息与预期不符。' >&2
    exit 1
fi
if ! metadata=$(python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    metadata = json.load(source)
elements = metadata.get("elements")
if metadata.get("applicationId") != "cc.novelia.app" or not isinstance(elements, list) or len(elements) != 1:
    raise SystemExit("APK 输出信息与预期不符。")
element = elements[0]
if element.get("versionName") != sys.argv[2] or element.get("versionCode") != int(sys.argv[3]):
    raise SystemExit("APK 版本与 version.properties 不一致。")
print(element["outputFile"])
' "$metadata_file" "$version_name" "$version_code"); then
    exit 1
fi
apk="$apk_directory/$metadata"
case $apk in
    "$apk_directory"/*) ;;
    *)
        echo 'APK 输出路径不在构建目录内。' >&2
        exit 1
        ;;
esac
if ! verification=$("$apksigner_path" verify --verbose --print-certs "$apk" 2>&1); then
    echo 'APK 签名验证失败。' >&2
    exit 1
fi
if grep -qi 'CN=Android Debug' <<<"$verification"; then
    echo '检测到 Android Debug 证书，拒绝整理为正式发行版。' >&2
    exit 1
fi
certificate_matches=$(grep -Eio '^Signer #[0-9]+ certificate SHA-256 digest:[[:space:]]*[a-f0-9]{64}[[:space:]]*$' <<<"$verification" | grep -Eo '[a-f0-9]{64}' | tr '[:upper:]' '[:lower:]')
if [[ $(grep -c . <<<"$certificate_matches") != 1 || $certificate_matches != "$expected_certificate" ]]; then
    echo 'APK 签名证书与指定的长期发布证书指纹不一致。' >&2
    exit 1
fi
if [[ -n $(git status --porcelain --untracked-files=normal) ]] \
    || [[ $(git rev-parse HEAD) != "$commit" ]] \
    || [[ $(git rev-parse --verify "refs/tags/$tag^{commit}") != "$commit" ]]; then
    echo '构建期间源码或标签发生变化，拒绝生成来源不一致的发行附件。' >&2
    exit 1
fi

mkdir -p -- "$output_path"
stem="Novelia-$version_name-$abi"
cp -- "$apk" "$output_path/$stem.apk"
cp -- 'app/build/generated/openSourceAssets/open-source/NOTICE.txt' "$output_path/OPEN_SOURCE_NOTICES.txt"
source_archive="$output_path/Novelia-$version_name-source.zip"
git archive --format=zip "--prefix=Novelia-$versionName/" "--output=$source_archive" "$commit" >/dev/null
zip -q -j "$output_path/$stem-mapping.zip" 'app/build/outputs/mapping/release/mapping.txt'
python3 - "$output_path" "$stem" "$tag" "$commit" "$version_name" "$version_code" "$abi" "$expected_certificate" <<'PY'
import json, sys
from pathlib import Path
output_path, stem, tag, commit, version_name, version_code, abi, certificate = sys.argv[1:]
metadata = {
    "repository": "https://github.com/nobYoQ/novelia",
    "tag": tag,
    "commit": commit,
    "versionName": version_name,
    "versionCode": int(version_code),
    "abi": abi,
    "certificateSha256": certificate,
}
target = Path(output_path) / f"{stem}-metadata.json"
target.write_text(json.dumps(metadata) + "\n", encoding="utf-8")
PY
checksums=()
while IFS= read -r file; do
    checksums+=("$(sha256sum -- "$file" | cut -d' ' -f1)  ${file##*/}")
done < <(find "$output_path" -maxdepth 1 -type f ! -name "SHA256SUMS-$abi.txt" -print | sort)
printf '%s\n' "${checksums[@]}" > "$output_path/SHA256SUMS-$abi.txt"
echo "发行附件已准备：$output_path"
echo '请完成设备验收后上传 GitHub Release 草稿；本脚本不会推送代码、上传文件或发布。'
