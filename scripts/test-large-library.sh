#!/usr/bin/env bash
# 用法：./scripts/test-large-library.sh [--books <n>] [--iterations <n>] [--device <serial>] [--offline]
set -u -o pipefail

books=2000
iterations=3
device=''
offline=0
while (( $# )); do
    case $1 in
        --books)
            if (( $# < 2 )); then echo '--books 需要一个参数。' >&2; exit 2; fi
            books=$2; shift 2
            ;;
        --iterations)
            if (( $# < 2 )); then echo '--iterations 需要一个参数。' >&2; exit 2; fi
            iterations=$2; shift 2
            ;;
        --device)
            if (( $# < 2 )); then echo '--device 需要一个参数。' >&2; exit 2; fi
            device=$2; shift 2
            ;;
        --offline) offline=1; shift ;;
        *)
            echo "未知参数：$1" >&2
            exit 2
            ;;
    esac
done
if [[ ! $books =~ ^[0-9]+$ ]] || (( books < 1 || books > 5000 )); then
    echo '--books 需要 1–5000 的整数。' >&2
    exit 2
fi
if [[ ! $iterations =~ ^[0-9]+$ ]] || (( iterations < 1 || iterations > 10 )); then
    echo '--iterations 需要 1–10 的整数。' >&2
    exit 2
fi

root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$root_path/scripts/build-environment.sh"
report_root="$root_path/outputs/performance/large-library-$(date +%Y%m%d-%H%M%S-%3N)"
mkdir -p -- "$report_root"
if ! build_resolve_android_sdk '' "$root_path"; then
    exit 1
fi
adb="$BUILD_SDK_PATH/platform-tools/adb"
if [[ ! -x $adb ]]; then
    echo "未找到 adb：$adb" >&2
    exit 1
fi
if [[ -z $device ]]; then
    device_lines=$("$adb" devices) || { echo '无法查询 Android 设备。' >&2; exit 1; }
    ready=()
    while IFS= read -r line; do
        if [[ $line =~ ^([^[:space:]]+)[[:space:]]+device$ ]]; then
            ready+=("${BASH_REMATCH[1]}")
        fi
    done <<<"$device_lines"
    if (( ${#ready[@]} != 1 )); then
        echo '请连接一台已授权设备，或使用 --device 指定设备序列号。' >&2
        exit 1
    fi
    device=${ready[0]}
fi
if [[ ! $device =~ ^[A-Za-z0-9_.:-]+$ ]]; then
    echo '设备序列号包含不支持的字符。' >&2
    exit 1
fi

# 仅当前进程覆盖缓存位置，退出后恢复；不修改系统环境或现有用户书库。
previous_gradle_home=${GRADLE_USER_HOME:-}
previous_android_user=${ANDROID_USER_HOME:-}
previous_temp=${TEMP:-}
previous_tmp=${TMP:-}
restore_environment() {
    export GRADLE_USER_HOME=$previous_gradle_home
    export ANDROID_USER_HOME=$previous_android_user
    export TEMP=$previous_temp
    export TMP=$previous_tmp
}
trap restore_environment EXIT

export GRADLE_USER_HOME="$root_path/.gradle-home"
export ANDROID_USER_HOME="$root_path/.local/android/.android"
export TEMP="$root_path/outputs/tmp"
export TMP=$TEMP
mkdir -p -- "$TEMP"

build_args=(':app:assembleDebug' ':app:assembleDebugAndroidTest' '-PisolatedLibraryTests=true' '--log' "$report_root/build.log")
if (( offline )); then
    build_args+=(--offline)
fi
if ! "$root_path/build.sh" "${build_args[@]}"; then
    exit 1
fi
for apk in 'app/build/outputs/apk/debug/app-debug.apk' 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'; do
    if ! "$adb" -s "$device" install -r -t "$root_path/$apk"; then
        echo "测试安装失败：$apk；不会卸载或清除现有应用。" >&2
        exit 1
    fi
done
classes='cc.novelia.app.performance.LargeLibraryPerformanceTest,cc.novelia.app.data.backup.LibraryBackupFlowTest'
test_log="$report_root/instrumentation.log"
# 即使断言失败也尽量收集本次报告；不扫描设备上其他报告或用户文件。
"$adb" -s "$device" shell am instrument -w -r -e class "$classes" \
    -e performanceBooks "$books" -e performanceIterations "$iterations" \
    'cc.novelia.app.librarytest.test/androidx.test.runner.AndroidJUnitRunner' 2>&1 | tee -- "$test_log"
test_exit=${PIPESTATUS[0]}
test_output=$(cat -- "$test_log")
paths=()
while IFS= read -r remote; do
    if [[ ! $remote =~ ^/[^[:space:]]*/cc\.novelia\.app\.librarytest/files/performance/large-library-[a-f0-9-]+\.(json|txt)$ ]]; then
        echo '测试返回了不符合隔离目录约定的报告路径。' >&2
        exit 1
    fi
    if ! "$adb" -s "$device" pull "$remote" "$report_root"; then
        echo "无法取回性能报告：$remote" >&2
        exit 1
    fi
    paths+=("$remote")
done < <(grep -oP '(?<=^INSTRUMENTATION_STATUS: performance(?:Report|Summary)=).+' "$test_log" | sed 's/\r$//' || true)
if (( test_exit != 0 )) || ! grep -q 'OK ([0-9]\+ tests\?)' <<<"$test_output" \
    || grep -q 'FAILURES!!!\|INSTRUMENTATION_FAILED' <<<"$test_output"; then
    echo "设备测试未通过，请查看 $test_log" >&2
    exit 1
fi
if (( ${#paths[@]} != 2 )); then
    echo '未找到本次性能 JSON 和文本报告。' >&2
    exit 1
fi
echo "性能报告已保存：$report_root"
