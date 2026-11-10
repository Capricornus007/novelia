#!/usr/bin/env bash
# 环境自动检测；如需手动填写 JDK、SDK 或缓存路径，修改根目录 build.sh 顶部“手动环境配置区”。
# 应用版本号/版本码统一修改根目录 version.properties；修改后直接重新执行本脚本。
# 用法：./scripts/build-debug.sh [--abi <abi>] [--offline] [--verify]
set -u -o pipefail
root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
args=('--variant' 'debug')
while (( $# )); do
    case $1 in
        --abi) args+=('--abi' "$2"); shift 2 ;;
        --offline) args+=(--offline); shift ;;
        --verify) args+=(--verify); shift ;;
        *) echo "未知参数：$1" >&2; exit 2 ;;
    esac
done
exec "$root_path/scripts/build-package.sh" "${args[@]}"
