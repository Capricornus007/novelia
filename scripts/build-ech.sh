#!/usr/bin/env bash
# 用法：./scripts/build-ech.sh [--test-only] [--offline]
set -u -o pipefail
root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# 与 Android Studio / gradlew 共享构建任务；Go 由 NOVELIA_GO_HOME 或 PATH 提供。
task=':app:buildEchNative'
args=()
while (( $# )); do
    case $1 in
        --test-only) task=':app:testEchNative'; shift ;;
        --offline) args+=(--offline); shift ;;
        *) echo "未知参数：$1" >&2; exit 2 ;;
    esac
done
exec "$root_path/build.sh" "$task" "${args[@]}"
