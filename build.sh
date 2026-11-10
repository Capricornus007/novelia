#!/usr/bin/env bash
# 跨平台统一 Gradle 入口。用法：
#   ./build.sh [任务...] [--offline] [--log <path>] [--check-env]
# 默认任务：:app:assembleDebug :app:testDebugUnitTest

set -u -o pipefail

# ===== 手动环境配置区：通常全部留空，自动查找失败时再填写 =====
# 填写后优先于自动检测；支持绝对路径，或相对于本脚本目录的路径。
# JDK 根目录，必须包含 bin/java 和 bin/javac。例如：/opt/jdk-21
BUILD_MANUAL_JAVA_HOME=''
# Android SDK 根目录，包含 platforms、build-tools 等。例如：/opt/android-sdk
BUILD_MANUAL_ANDROID_SDK=''
# 可选缓存目录；留空时优先沿用同名环境变量，否则使用项目 .gradle-home 和 .local/android/.android。
# 测试签名固定使用项目 .android/debug.keystore，与 ANDROID_USER_HOME 无关。
BUILD_MANUAL_GRADLE_USER_HOME=''
BUILD_MANUAL_ANDROID_USER_HOME=''
# ===== 手动环境配置区结束；版本号请修改根目录 version.properties =====

root_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$root_path/scripts/build-environment.sh"

tasks=()
offline=0
check_env=0
log_path=''
while (( $# )); do
    case $1 in
        --offline) offline=1; shift ;;
        --check-env) check_env=1; shift ;;
        --log)
            if (( $# < 2 )); then
                echo '--log 需要一个路径参数。' >&2
                exit 2
            fi
            log_path=$2
            shift 2
            ;;
        --*)
            echo "未知参数：$1" >&2
            exit 2
            ;;
        *)
            tasks+=("$1")
            shift
            ;;
    esac
done
if (( ${#tasks[@]} == 0 )); then
    tasks=(':app:assembleDebug' ':app:testDebugUnitTest')
fi

output_root="$root_path/outputs"
if [[ -z $log_path ]]; then
    log_path="$output_root/logs/build-gradle-$(date +%Y%m%d-%H%M%S-%3N).log"
fi
# 相对路径始终以仓库根目录为基准；自定义日志也必须留在 outputs 内。
log_path=$(build_resolve_path "$log_path" "$root_path") || { echo '日志路径无效。' >&2; exit 2; }
case $log_path in
    "$output_root"/*) ;;
    *)
        echo '--log 必须位于仓库根目录的 outputs/ 下，例如 outputs/logs/custom.log。' >&2
        exit 2
        ;;
esac

if ! build_resolve_jdk "$BUILD_MANUAL_JAVA_HOME" "$root_path"; then
    exit 1
fi
if ! build_resolve_android_sdk "$BUILD_MANUAL_ANDROID_SDK" "$root_path"; then
    exit 1
fi
gradle_home=${BUILD_MANUAL_GRADLE_USER_HOME:-${GRADLE_USER_HOME:-.gradle-home}}
android_user=${BUILD_MANUAL_ANDROID_USER_HOME:-${ANDROID_USER_HOME:-.local/android/.android}}
gradle_home=$(build_resolve_path "$gradle_home" "$root_path")
android_user=$(build_resolve_path "$android_user" "$root_path")
echo "JDK $BUILD_JDK_VERSION：$BUILD_JDK_HOME [$BUILD_JDK_SOURCE]"
echo "Android SDK：$BUILD_SDK_PATH [$BUILD_SDK_SOURCE]"
echo "Gradle 缓存：$gradle_home"
echo "Android 用户目录：$android_user"
if (( check_env )); then
    echo '环境路径检测完成；未运行 Gradle、下载依赖或修改 local.properties。SDK 组件完整性由实际构建检查。'
    exit 0
fi
# ECH AAR 由 Gradle 的 buildEchNative 任务按内容增量生成，所有构建入口使用同一依赖图。
build_sync_local_sdk "$BUILD_SDK_PATH" "$root_path"
mkdir -p -- "$(dirname -- "$log_path")"
echo "Gradle 日志：$log_path"
temporary_root="$output_root/tmp"
mkdir -p -- "$temporary_root"

arguments=(
    "-Djava.io.tmpdir=$temporary_root"
    -classpath "$root_path/gradle/wrapper/gradle-wrapper.jar"
    org.gradle.wrapper.GradleWrapperMain
    --no-daemon --console=plain
)
arguments+=("${tasks[@]}")
if (( offline )); then
    arguments+=('--offline')
fi
# 同时指定 Gradle daemon JDK，避免用户 gradle.properties 中旧机器路径覆盖检测结果。
arguments+=("-Dorg.gradle.java.home=$BUILD_JDK_HOME")

# 旧 analytics 直接使用父目录，新 AndroidLocations 会追加 .android；两者都留在项目缓存内。
# 自定义路径不是 .android 时不额外设置旧入口，避免产生互相冲突的路径。
android_prefs_root=''
if [[ ${android_user##*/} == '.android' ]]; then
    android_prefs_root=${android_user%/*}
fi

cd -- "$root_path"
JAVA_HOME=$BUILD_JDK_HOME \
ANDROID_HOME=$BUILD_SDK_PATH \
ANDROID_SDK_ROOT=$BUILD_SDK_PATH \
GRADLE_USER_HOME=$gradle_home \
ANDROID_USER_HOME=$android_user \
ANDROID_PREFS_ROOT=$android_prefs_root \
TEMP=$temporary_root \
TMP=$temporary_root \
    "$BUILD_JAVA" "${arguments[@]}" 2>&1 | tee -- "$log_path"
gradle_exit=${PIPESTATUS[0]}
if (( gradle_exit != 0 )); then
    echo "Gradle 构建失败，退出码 $gradle_exit" >&2
    exit "$gradle_exit"
fi
