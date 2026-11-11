package cc.novelia.app.ui.i18n

import androidx.compose.foundation.text.InlineTextContent
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.Text as MaterialText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.unit.TextUnit

/**
 * 應用內語言變體。
 *
 * 這個專案的介面字串是直接寫在 Compose 程式碼裡的簡體中文，因此不做資源抽取，
 * 而是在顯示層（所有 `Text` 呼叫都走本檔的包裝）依設定做簡→繁轉換。
 * zh-CN 與來源一致，維持原文；zh-TW 逐字＋片語轉成繁體。
 */
object ZhLanguage {
    /** "system"、"zh-CN" 或 "zh-TW"。 */
    var tag: String by mutableStateOf("system")

    fun localize(text: String, traditional: Boolean): String =
        if (traditional) ZhConversion.toTraditional(text) else ZhConversion.toSimplified(text)

    fun isTraditional(systemIsTraditional: Boolean): Boolean = when (tag) {
        "zh-TW" -> true
        "zh-CN" -> false
        else -> systemIsTraditional
    }
}

@Composable
fun Text(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    fontSize: TextUnit = TextUnit.Unspecified,
    fontStyle: FontStyle? = null,
    fontWeight: FontWeight? = null,
    fontFamily: FontFamily? = null,
    letterSpacing: TextUnit = TextUnit.Unspecified,
    textDecoration: TextDecoration? = null,
    textAlign: TextAlign? = null,
    lineHeight: TextUnit = TextUnit.Unspecified,
    overflow: TextOverflow = TextOverflow.Clip,
    softWrap: Boolean = true,
    maxLines: Int = Int.MAX_VALUE,
    minLines: Int = 1,
    onTextLayout: ((TextLayoutResult) -> Unit)? = null,
    style: TextStyle = LocalTextStyle.current,
) {
    val traditional = localTraditional()
    MaterialText(
        text = ZhLanguage.localize(text, traditional),
        modifier = modifier,
        color = color,
        fontSize = fontSize,
        fontStyle = fontStyle,
        fontWeight = fontWeight,
        fontFamily = fontFamily,
        letterSpacing = letterSpacing,
        textDecoration = textDecoration,
        textAlign = textAlign,
        lineHeight = lineHeight,
        overflow = overflow,
        softWrap = softWrap,
        maxLines = maxLines,
        minLines = minLines,
        onTextLayout = onTextLayout,
        style = style,
    )
}

/** 保留富文字的連結、樣式與行內內容範圍，只轉換顯示文字。 */
@Composable
fun Text(
    text: AnnotatedString,
    modifier: Modifier = Modifier,
    color: Color = Color.Unspecified,
    fontSize: TextUnit = TextUnit.Unspecified,
    fontStyle: FontStyle? = null,
    fontWeight: FontWeight? = null,
    fontFamily: FontFamily? = null,
    letterSpacing: TextUnit = TextUnit.Unspecified,
    textDecoration: TextDecoration? = null,
    textAlign: TextAlign? = null,
    lineHeight: TextUnit = TextUnit.Unspecified,
    overflow: TextOverflow = TextOverflow.Clip,
    softWrap: Boolean = true,
    maxLines: Int = Int.MAX_VALUE,
    minLines: Int = 1,
    inlineContent: Map<String, InlineTextContent> = mapOf(),
    onTextLayout: ((TextLayoutResult) -> Unit)? = null,
    style: TextStyle = LocalTextStyle.current,
) {
    val traditional = localTraditional()
    val localized = buildAnnotatedString {
        // 逐段轉換整句，按新長度重算樣式、連結及行內內容的區間。
        val spans = text.spanStyles
        val paragraphs = text.paragraphStyles
        val annotations = text.getStringAnnotations(0, text.length)
        val boundaries = (
            spans.flatMap { listOf(it.start, it.end) } +
                paragraphs.flatMap { listOf(it.start, it.end) } +
                annotations.flatMap { listOf(it.start, it.end) } +
                0 + text.length
            ).distinct().sorted()
        boundaries.zipWithNext().forEach { (start, end) ->
            val outputStart = length
            append(ZhLanguage.localize(text.text.substring(start, end), traditional))
            val outputEnd = length
            spans.filter { it.start <= start && it.end >= end }
                .forEach { addStyle(it.item, outputStart, outputEnd) }
            paragraphs.filter { it.start <= start && it.end >= end }
                .forEach { addStyle(it.item, outputStart, outputEnd) }
            annotations.filter { it.start <= start && it.end >= end }
                .forEach { addStringAnnotation(it.tag, it.item, outputStart, outputEnd) }
        }
    }
    MaterialText(
        text = localized,
        modifier = modifier,
        color = color,
        fontSize = fontSize,
        fontStyle = fontStyle,
        fontWeight = fontWeight,
        fontFamily = fontFamily,
        letterSpacing = letterSpacing,
        textDecoration = textDecoration,
        textAlign = textAlign,
        lineHeight = lineHeight,
        overflow = overflow,
        softWrap = softWrap,
        maxLines = maxLines,
        minLines = minLines,
        inlineContent = inlineContent,
        onTextLayout = onTextLayout ?: {},
        style = style,
    )
}

/** 讓所有呼叫端在同一個組合週期看到同一個布林值。 */
@Composable
private fun localTraditional(): Boolean {
    val configuration = LocalConfiguration.current
    val locale = configuration.locales[0]
    val systemTraditional = locale.language == "zh" &&
        (locale.country == "TW" || locale.country == "HK" || locale.country == "MO")
    return ZhLanguage.isTraditional(systemTraditional)
}

/** 非 Compose 字串（通知、Toast 等）用；沒有 CompositionLocal 時退回系統語言判斷。 */
fun localizedText(text: String): String {
    val locale = java.util.Locale.getDefault()
    val systemTraditional = locale.language == "zh" &&
        (locale.country == "TW" || locale.country == "HK" || locale.country == "MO")
    return ZhLanguage.localize(text, ZhLanguage.isTraditional(systemTraditional))
}
