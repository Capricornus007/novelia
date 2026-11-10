@file:OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
package cc.novelia.app.ui.i18n

import androidx.compose.foundation.Indication
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.material3.Icon as MaterialIcon
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsPropertyReceiver
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.semantics

/** 保留 Icon 原有的可空描述，只轉換朗讀用的介面字串。 */
@Composable
fun Icon(imageVector: ImageVector, contentDescription: String?, modifier: Modifier = Modifier,
    tint: Color = androidx.compose.material3.LocalContentColor.current) {
    MaterialIcon(imageVector, contentDescription?.let(::localizedText), modifier, tint)
}

/** 語義屬性不是 Composable；在外層取得語言後，將純轉換函式傳入設定區塊。 */
@Composable
fun Modifier.localizedSemantics(block: SemanticsPropertyReceiver.(localize: (String) -> String) -> Unit): Modifier =
    localizedSemantics(clearAndSet = false, block = block)

@Composable
fun Modifier.localizedClearAndSetSemantics(block: SemanticsPropertyReceiver.(localize: (String) -> String) -> Unit): Modifier =
    localizedSemantics(clearAndSet = true, block = block)

@Composable
private fun Modifier.localizedSemantics(
    clearAndSet: Boolean,
    block: SemanticsPropertyReceiver.(localize: (String) -> String) -> Unit,
): Modifier {
    val configuration = LocalConfiguration.current
    val locale = configuration.locales[0]
    val systemTraditional = locale.language == "zh" &&
        (locale.country == "TW" || locale.country == "HK" || locale.country == "MO")
    val traditional = ZhLanguage.isTraditional(systemTraditional)
    return if(clearAndSet) clearAndSetSemantics { block { ZhLanguage.localize(it, traditional) } }
    else semantics { block { ZhLanguage.localize(it, traditional) } }
}

@Composable
fun Modifier.localizedClickable(
    enabled: Boolean = true,
    onClickLabel: String? = null,
    role: Role? = null,
    onClick: () -> Unit,
): Modifier {
    val label = onClickLabel?.let(::localizedText)
    return clickable(enabled = enabled, onClickLabel = label, role = role, onClick = onClick)
}

@Composable
fun Modifier.localizedClickable(
    interactionSource: MutableInteractionSource,
    indication: Indication?,
    enabled: Boolean = true,
    onClickLabel: String? = null,
    role: Role? = null,
    onClick: () -> Unit,
): Modifier {
    val label = onClickLabel?.let(::localizedText)
    return clickable(interactionSource = interactionSource, indication = indication, enabled = enabled,
        onClickLabel = label, role = role, onClick = onClick)
}

@Composable
fun Modifier.localizedCombinedClickable(
    enabled: Boolean = true,
    onClickLabel: String? = null,
    onLongClickLabel: String? = null,
    onLongClick: (() -> Unit)? = null,
    onDoubleClick: (() -> Unit)? = null,
    hapticFeedbackEnabled: Boolean = true,
    onClick: () -> Unit,
): Modifier {
    val clickLabel = onClickLabel?.let(::localizedText)
    val longClickLabel = onLongClickLabel?.let(::localizedText)
    return combinedClickable(enabled = enabled, onClickLabel = clickLabel, onLongClickLabel = longClickLabel,
        onLongClick = onLongClick, onDoubleClick = onDoubleClick,
        hapticFeedbackEnabled = hapticFeedbackEnabled, onClick = onClick)
}

@Composable
fun Modifier.localizedCombinedClickable(
    interactionSource: MutableInteractionSource,
    indication: Indication?,
    enabled: Boolean = true,
    onClickLabel: String? = null,
    onLongClickLabel: String? = null,
    onLongClick: (() -> Unit)? = null,
    onDoubleClick: (() -> Unit)? = null,
    hapticFeedbackEnabled: Boolean = true,
    onClick: () -> Unit,
): Modifier {
    val clickLabel = onClickLabel?.let(::localizedText)
    val longClickLabel = onLongClickLabel?.let(::localizedText)
    return combinedClickable(interactionSource = interactionSource, indication = indication,
        enabled = enabled, onClickLabel = clickLabel, onLongClickLabel = longClickLabel,
        onLongClick = onLongClick, onDoubleClick = onDoubleClick,
        hapticFeedbackEnabled = hapticFeedbackEnabled, onClick = onClick)
}
