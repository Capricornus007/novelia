#!/usr/bin/env bash
# 用法：./scripts/configure-preview-signing.sh [--repo <owner>/<repo>] [--keystore <path>] [--check-only]
set -u -o pipefail

repository='nobYoQ/novelia'
keystore_path=''
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/build-environment.sh"
check_only=0
while (( $# )); do
    case $1 in
        --repo)
            if (( $# < 2 )); then echo '--repo 需要一个参数。' >&2; exit 2; fi
            repository=$2; shift 2
            ;;
        --keystore)
            if (( $# < 2 )); then echo '--keystore 需要一个参数。' >&2; exit 2; fi
            keystore_path=$2; shift 2
            ;;
        --check-only) check_only=1; shift ;;
        *)
            echo "未知参数：$1" >&2
            exit 2
            ;;
    esac
done
if [[ ! $repository =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    echo '--repo 需要形如 <owner>/<repo> 的仓库名。' >&2
    exit 2
fi

root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ -z $keystore_path ]]; then
    keystore_path=${NOVELIA_PREVIEW_KEYSTORE_PATH:-.android/debug.keystore}
fi
keystore_path=$(build_resolve_path "$keystore_path" "$root_path") || {
    echo '缺少原有预览密钥。请从私密备份恢复；本脚本不会生成或覆盖密钥。' >&2
    exit 1
}
if [[ ! -f $keystore_path ]]; then
    echo '缺少原有预览密钥。请从私密备份恢复；本脚本不会生成或覆盖密钥。' >&2
    exit 1
fi
expected=$(tr -d '[:space:]' < "$root_path/gradle/preview-signing.sha256")
if [[ ! $expected =~ ^[0-9a-f]{64}$ ]]; then
    echo '预览证书指纹配置无效。' >&2
    exit 1
fi

if [[ -n ${JAVA_HOME:-} ]]; then
    keytool="$JAVA_HOME/bin/keytool"
else
    keytool=$(command -v keytool 2>/dev/null || true)
    if [[ -z $keytool ]]; then
        echo '未找到 keytool；请设置 JAVA_HOME 或把 JDK bin 加入 PATH。' >&2
        exit 1
    fi
fi

# Android 测试密钥的标准口令；私密材料是现有密钥库本身。
certificate_output=$(NOVELIA_PREVIEW_STORE_PASSWORD=android \
    "$keytool" -list -rfc -alias androiddebugkey -keystore "$keystore_path" \
    -storepass:env NOVELIA_PREVIEW_STORE_PASSWORD 2>&1)
if (( $? != 0 )); then
    echo '读取预览证书失败；不会上传密钥。' >&2
    exit 1
fi
certificate=$(sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' <<<"$certificate_output" \
    | sed '1d;$d' | tr -d '[:space:]')
if [[ -z $certificate ]]; then
    echo '未能读取预览公开证书；不会上传密钥。' >&2
    exit 1
fi
actual=$(printf '%s' "$certificate" | base64 -d 2>/dev/null | sha256sum | cut -d' ' -f1)
if [[ $actual != "$expected" ]]; then
    echo '证书指纹不匹配；请使用原有本地密钥，不会上传替代密钥。' >&2
    exit 1
fi
if ! grep -q 'PrivateKeyEntry' <<<"$certificate_output"; then
    echo '密钥库仅含公开证书，没有预览签名私钥；不会上传。' >&2
    exit 1
fi
echo "预览公开证书 SHA-256：$actual"
if (( check_only )); then
    exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
    echo '未找到 GitHub CLI。安装 gh 并执行 gh auth login 后，再运行本脚本。' >&2
    exit 1
fi
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
    echo 'GitHub CLI 未登录。请在自己的终端执行 gh auth login 后重试。' >&2
    exit 1
fi

# 仅在内存中编码，通过 stdin 传给 gh；不落盘、不输出，也不放进命令行参数。
if ! base64 -w 0 -- "$keystore_path" \
    | gh secret set NOVELIA_PREVIEW_KEYSTORE_BASE64 --repo "$repository" --app actions; then
    echo '配置 GitHub Secret 失败；请检查仓库写入权限后重试。' >&2
    exit 1
fi
echo "已配置 $repository 的 NOVELIA_PREVIEW_KEYSTORE_BASE64；未改动本地密钥。"
