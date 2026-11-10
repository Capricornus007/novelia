#!/usr/bin/env bash
# 读取 version.properties、组装任务、调用 build.sh、验证产物并归档 APK。
# 用法：./scripts/build-package.sh --variant debug|release [--abi <abi>] [--offline] [--verify] [--unsigned]

set -u -o pipefail

variant=''
abi='universal'
offline=0
verify=0
unsigned=0
while (( $# )); do
    case $1 in
        --variant)
            if (( $# < 2 )); then echo '--variant 需要一个参数。' >&2; exit 2; fi
            variant=$2; shift 2
            ;;
        --abi)
            if (( $# < 2 )); then echo '--abi 需要一个参数。' >&2; exit 2; fi
            abi=$2; shift 2
            ;;
        --offline) offline=1; shift ;;
        --verify) verify=1; shift ;;
        --unsigned) unsigned=1; shift ;;
        *)
            echo "未知参数：$1" >&2
            exit 2
            ;;
    esac
done
case ${variant,,} in
    debug) variant=Debug ;;
    release) variant=Release ;;
    '')
        echo '必须指定 --variant debug 或 release。' >&2
        exit 2
        ;;
    *)
        echo "--variant 只接受 debug 或 release。" >&2
        exit 2
        ;;
esac
case $abi in
    universal | arm64-v8a | armeabi-v7a | x86_64 | x86) ;;
    *)
        echo "--abi 只接受 universal、arm64-v8a、armeabi-v7a、x86_64、x86。" >&2
        exit 2
        ;;
esac
abi=${abi,,}

if (( unsigned && variant != Release )); then
    echo '--unsigned 仅适用于 Release。' >&2
    exit 2
fi
if (( variant == Debug )); then
    mode=debug
elif (( unsigned )); then
    mode=release-unsigned
else
    mode=release-local
fi
root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

version_name=''
version_code=''
while IFS='=' read -r key value; do
    key=${key//[[:space:]]/}
    case $key in
        versionName) version_name=$value ;;
        versionCode) version_code=$value ;;
    esac
done < "$root_path/version.properties"
if [[ ! $version_name =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || [[ ! $version_code =~ ^[0-9]+$ ]] || (( 10#$version_code <= 0 )); then
    echo 'version.properties 中的版本配置无效。' >&2
    exit 1
fi
version_code=$((10#$version_code))

log_directory="$root_path/outputs/logs"
mkdir -p -- "$log_directory"
log_path="$log_directory/build-$mode-$abi-$(date +%Y%m%d-%H%M%S-%3N).log"
tasks=()
if (( verify )); then
    tasks+=(":app:test${variant}UnitTest" ":app:lint$variant")
fi
tasks+=(":app:assemble$variant")
# 显式传入 false，覆盖机器本地的 Gradle 属性及其默认值。
tasks+=('-PreleaseSigning=false')
if [[ $mode == release-local ]]; then
    tasks+=('-PlocalReleaseSigning=true')
else
    tasks+=('-PlocalReleaseSigning=false')
fi
tasks+=("-PtargetAbi=$abi")

echo "构建：$mode / $abi / $version_name ($version_code)"
if [[ $mode == release-local ]]; then
    echo '签名：与 Actions 共用的固定预览测试证书；已启用 Release 压缩优化。'
fi
if (( unsigned )); then
    echo '签名：未签名；此 APK 不能直接安装。'
fi
echo "日志：$log_path"

build_args=("${tasks[@]}" --log "$log_path")
if (( offline )); then
    build_args+=(--offline)
fi
if ! "$root_path/build.sh" "${build_args[@]}"; then
    echo "构建或产物整理失败，请检查上述错误及日志：$log_path" >&2
    exit 1
fi

variant_lower=${variant,,}
apk_directory="$root_path/app/build/outputs/apk/$variant_lower"
metadata_file="$apk_directory/output-metadata.json"
if [[ ! -f $metadata_file ]]; then
    echo "构建或产物整理失败，请检查上述错误及日志：$log_path" >&2
    echo '缺少 output-metadata.json。' >&2
    exit 1
fi
if ! metadata=$(python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    metadata = json.load(source)
elements = metadata.get("elements")
if metadata.get("applicationId") != "cc.novelia.app" or not isinstance(elements, list) or len(elements) != 1:
    raise SystemExit("APK 输出信息与预期不符；没有整理安装包。")
element = elements[0]
if element.get("versionName") != sys.argv[2] or element.get("versionCode") != int(sys.argv[3]):
    raise SystemExit("APK 版本与本次构建读取的 version.properties 不一致；没有整理安装包。")
print(element["outputFile"])
' "$metadata_file" "$version_name" "$version_code"); then
    echo "构建或产物整理失败，请检查上述错误及日志：$log_path" >&2
    exit 1
fi
apk=$(build_resolve_path "$apk_directory/$metadata" "$root_path") || apk="$apk_directory/$metadata"
case $apk in
    "$apk_directory"/*) ;;
    *)
        echo "构建或产物整理失败，请检查上述错误及日志：$log_path" >&2
        echo 'APK 输出文件无效或不在构建目录内。' >&2
        exit 1
        ;;
esac
if [[ ${apk##*.} != apk || ! -f $apk ]]; then
    echo "构建或产物整理失败，请检查上述错误及日志：$log_path" >&2
    echo 'APK 输出文件无效或不在构建目录内。' >&2
    exit 1
fi
mapping="$root_path/app/build/outputs/mapping/release/mapping.txt"
if [[ $variant == Release && ! -f $mapping ]]; then
    echo "构建或产物整理失败，请检查上述错误及日志：$log_path" >&2
    echo 'Release 构建缺少 mapping.txt；没有整理安装包。' >&2
    exit 1
fi

output_directory="$root_path/outputs/packages/$mode"
mkdir -p -- "$output_directory"
stem="Novelia-$version_name-$mode-$abi"
output_apk="$output_directory/$stem.apk"
cp -f -- "$apk" "$output_apk"
sha256=$(sha256sum -- "$output_apk" | cut -d' ' -f1)
printf '%s  %s.apk\n' "$sha256" "$stem" > "$output_apk.sha256"
if [[ $variant == Release ]]; then
    cp -f -- "$mapping" "$output_directory/$stem-mapping.txt"
fi

echo
echo "构建完成：$output_apk"
echo "SHA-256：$output_apk.sha256"
if [[ $variant == Release ]]; then
    echo "混淆映射：$output_directory/$stem-mapping.txt"
fi
echo "构建日志：$log_path"
