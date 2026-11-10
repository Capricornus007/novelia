#!/usr/bin/env bash
# 供 build.sh 复用的检测逻辑；手动配置请统一填写 build.sh 顶部的配置区。
# 检测结果写入 BUILD_JDK_HOME / BUILD_JAVA / BUILD_JDK_VERSION / BUILD_JDK_SOURCE
# 与 BUILD_SDK_PATH / BUILD_SDK_SOURCE。

# 相对路径以仓库根目录为基准；返回规范化后的绝对路径。
build_resolve_path() {
    local path=$1 root=$2 resolved
    path="${path%\"}"; path="${path#\"}"
    [[ -n ${path//[[:space:]]/} ]] || return 1
    if [[ $path == /* ]]; then resolved=$path; else resolved="$root/$path"; fi
    if command -v realpath >/dev/null 2>&1; then
        realpath -m -- "$resolved"
    else
        printf '%s\n' "$resolved"
    fi
}

# 按 Java properties 规则解码取值：\uXXXX 与标准单字符转义。
build_decode_properties_value() {
    local value=$1 out='' i=0 len=${#1} ch next code
    while (( i < len )); do
        ch=${value:i:1}
        if [[ $ch == '\' && $((i + 1)) < len ]]; then
            next=${value:i+1:1}
            case $next in
                u)
                    code=${value:i+2:4}
                    if [[ $code =~ ^[0-9a-fA-F]{4}$ ]]; then
                        out+=$(printf '%b' "\\u$code")
                    else
                        out+=$next
                    fi
                    i=$((i + 6))
                    ;;
                t) out+=$'\t'; i=$((i + 2)) ;;
                n) out+=$'\n'; i=$((i + 2)) ;;
                r) out+=$'\r'; i=$((i + 2)) ;;
                f) out+=$'\f'; i=$((i + 2)) ;;
                *) out+=$next; i=$((i + 2)) ;;
            esac
        else
            out+=$ch
            i=$((i + 1))
        fi
    done
    printf '%s' "$out"
}

# 按 Java properties 规则编码 sdk.dir：非 ASCII 用 \uXXXX，冒号转义。
build_encode_properties_value() {
    local value=$1 out='' i ch code
    value=${value//\\//}
    value=${value//:/\\:}
    for (( i = 0; i < ${#value}; i++ )); do
        ch=${value:i:1}
        # properties 按 Latin-1 保存；用字符码判断非 ASCII，避免模式解析歧义。
        code=$(printf '%d' "'$ch")
        if (( code > 126 )) || [[ $ch == [[:space:]] ]]; then
            out+=$(printf '\\u%04x' "$code")
        else
            out+=$ch
        fi
    done
    printf '%s' "$out"
}

# 读取 local.properties：解析 sdk.dir（含续行与转义），其余行原样保留。
# 结果写入 BUILD_LOCAL_SDK 与数组 BUILD_LOCAL_OTHER_LINES。
build_read_local_sdk() {
    local file=$1
    BUILD_LOCAL_SDK=''
    BUILD_LOCAL_OTHER_LINES=()
    [[ -f $file ]] || return 0
    local lines=() logical next i=0 n
    mapfile -t lines < "$file"
    n=${#lines[@]}
    while (( i < n )); do
        local -a physical=("${lines[i]}")
        logical=${lines[i]}
        # Java properties 的续行规则：末尾奇数个反斜杠表示继续下一行。
        while [[ $logical =~ \\+$ ]] && (( ${#BASH_REMATCH[0]} % 2 == 1 )) && (( i + 1 < n )); do
            i=$((i + 1))
            physical+=("${lines[i]}")
            next=${lines[i]}
            next=${next#"${next%%[![:space:]]*}"}
            logical=${logical%?}$next
        done
        if [[ $logical =~ ^[[:space:]]*sdk\.dir([[:space:]]*[=:][[:space:]]*|[[:space:]]+)(.*)$ ]]; then
            BUILD_LOCAL_SDK=$(build_decode_properties_value "${BASH_REMATCH[2]}")
        else
            BUILD_LOCAL_OTHER_LINES+=("${physical[@]}")
        fi
        i=$((i + 1))
    done
}

# 校验单个 JDK：$1 为 java 可执行文件，结果经 nameref 写回。
build_check_jdk() {
    local java=$1
    local -n out_home=$2
    local -n out_version=$3
    [[ -x $java ]] || { echo '缺少 bin/java'; return 1; }
    local details tmp_home tmp_version
    if ! details=$("$java" -XshowSettings:properties -version 2>&1); then
        echo 'Java 无法运行'; return 1
    fi
    tmp_home=$(sed -n 's/^[[:space:]]*java\.home[[:space:]]*=[[:space:]]*//p' <<<"$details" | tail -n 1)
    tmp_version=$(sed -n 's/^[[:space:]]*java\.specification\.version[[:space:]]*=[[:space:]]*\([0-9]\+\).*/\1/p' <<<"$details" | tail -n 1)
    [[ -n $tmp_home && -n $tmp_version ]] || { echo '无法读取 Java 版本和实际安装目录'; return 1; }
    # 当前 AGP 8.13.2 要求至少 17，Gradle 8.13 最高支持运行于 23。
    # 升级 Wrapper 时一并核对 https://docs.gradle.org/current/userguide/compatibility.html
    (( tmp_version >= 17 && tmp_version <= 23 )) || { echo "JDK $tmp_version 不适用于当前构建工具，请使用 JDK 17–23（推荐 17 或 21）"; return 1; }
    [[ -x $tmp_home/bin/javac ]] || { echo '缺少 bin/javac，需要完整 JDK'; return 1; }
    out_home=$tmp_home
    out_version=$tmp_version
}

# 检测 JDK：手动配置 → JAVA_HOME/JDK_HOME/STUDIO_JDK → PATH → /usr/lib/jvm/*。
build_resolve_jdk() {
    local manual=$1 root=$2
    local candidates=() sources=()
    local -A seen=()
    if [[ -n $manual ]]; then
        candidates+=("$manual")
        sources+=('build.sh 手动配置')
    else
        local name value java_path dir
        for name in JAVA_HOME JDK_HOME STUDIO_JDK; do
            value=${!name:-}
            if [[ -n $value ]]; then
                candidates+=("$value")
                sources+=("$name")
            fi
        done
        if java_path=$(command -v java 2>/dev/null); then
            candidates+=("$java_path")
            sources+=('PATH')
        fi
        local jvm_dirs=()
        if compgen -G '/usr/lib/jvm/*' >/dev/null 2>&1; then
            mapfile -t jvm_dirs < <(compgen -G '/usr/lib/jvm/*' | sort -r)
        fi
        for dir in "${jvm_dirs[@]}"; do
            if [[ -d $dir ]]; then
                candidates+=("$dir")
                sources+=('常见 JDK 安装目录')
            fi
        done
    fi
    local i candidate source java resolved_home resolved_version
    for i in "${!candidates[@]}"; do
        candidate=${candidates[i]}
        source=${sources[i]}
        if [[ $source == PATH ]]; then java=$candidate; else java="$candidate/bin/java"; fi
        [[ -z ${seen[$java]:-} ]] || continue
        seen[$java]=1
        if resolved_home=$(build_resolve_path "$candidate" "$root") \
            && build_check_jdk "$java" resolved_home resolved_version; then
            BUILD_JDK_HOME=$resolved_home
            BUILD_JAVA="$resolved_home/bin/java"
            BUILD_JDK_VERSION=$resolved_version
            BUILD_JDK_SOURCE=$source
            return 0
        fi
        if [[ -n $manual ]]; then
            echo "build.sh 的 BUILD_MANUAL_JAVA_HOME 无效：$?" >&2
            return 1
        fi
        case $source in
            JAVA_HOME | JDK_HOME | STUDIO_JDK | PATH)
                echo "警告：跳过 $source 的 JDK。" >&2
                ;;
        esac
    done
    echo '未找到可用 JDK 17–23。请安装 JDK，设置 JAVA_HOME，或在 build.sh 顶部填写 BUILD_MANUAL_JAVA_HOME（JDK 根目录，不是 bin）。' >&2
    return 1
}

# 检测 Android SDK：手动配置 → local.properties → ANDROID_HOME/ANDROID_SDK_ROOT → ~/Android/Sdk。
build_resolve_android_sdk() {
    local manual=$1 root=$2
    build_read_local_sdk "$root/local.properties"
    local candidates=() sources=()
    if [[ -n $manual ]]; then
        candidates+=("$manual")
        sources+=('build.sh 手动配置')
    else
        if [[ -n $BUILD_LOCAL_SDK ]]; then
            candidates+=("$BUILD_LOCAL_SDK")
            sources+=('local.properties')
        fi
        if [[ -n ${ANDROID_HOME:-} ]]; then
            candidates+=("$ANDROID_HOME")
            sources+=('ANDROID_HOME')
        fi
        if [[ -n ${ANDROID_SDK_ROOT:-} ]]; then
            candidates+=("$ANDROID_SDK_ROOT")
            sources+=('ANDROID_SDK_ROOT')
        fi
        if [[ -d $HOME/Android/Sdk ]]; then
            candidates+=("$HOME/Android/Sdk")
            sources+=('Android SDK 默认目录')
        fi
    fi
    local i candidate sdk_path folder found
    for i in "${!candidates[@]}"; do
        candidate=${candidates[i]}
        if sdk_path=$(build_resolve_path "$candidate" "$root") && [[ -d $sdk_path ]]; then
            found=0
            for folder in platforms build-tools cmdline-tools platform-tools; do
                if [[ -d $sdk_path/$folder ]]; then found=1; break; fi
            done
            if (( found )); then
                BUILD_SDK_PATH=$sdk_path
                BUILD_SDK_SOURCE=${sources[i]}
                return 0
            fi
        fi
        if [[ -n $manual ]]; then
            echo "build.sh 的 BUILD_MANUAL_ANDROID_SDK 无效：目录不存在或没有 Android SDK 组件。" >&2
            return 1
        fi
        echo "警告：跳过 ${sources[i]} 的 SDK：目录不存在或没有 Android SDK 组件。" >&2
    done
    echo '未找到 Android SDK。请通过 Android Studio 安装 SDK，设置 ANDROID_HOME，或在 build.sh 顶部填写 BUILD_MANUAL_ANDROID_SDK（SDK 根目录，不是 platform-tools）。' >&2
    return 1
}

# 同步 sdk.dir 到 local.properties：保留其他行，非 ASCII 路径用 \uXXXX 转义。
build_sync_local_sdk() {
    local sdk_path=$1 root=$2
    local file="$root/local.properties"
    build_read_local_sdk "$file"
    if [[ -n $BUILD_LOCAL_SDK ]]; then
        local resolved
        if resolved=$(build_resolve_path "$BUILD_LOCAL_SDK" "$root") && [[ $resolved == "$sdk_path" ]]; then
            return 0
        fi
    fi
    # 仅同步被 Git 忽略的本机 SDK 配置，保留其他属性和注释。
    # properties 由 Java 按 Latin-1 读取，非 ASCII 路径用标准 Unicode 转义保存。
    local value
    value=$(build_encode_properties_value "$sdk_path")
    {
        if (( ${#BUILD_LOCAL_OTHER_LINES[@]} )); then
            printf '%s\n' "${BUILD_LOCAL_OTHER_LINES[@]}"
        fi
        printf 'sdk.dir=%s\n' "$value"
    } > "$file"
    echo '已同步 local.properties 的 sdk.dir（本机配置，不提交到 Git）。'
}
