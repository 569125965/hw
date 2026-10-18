package com.asharelab.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val Bg0 = Color(0xFF071318)
val Bg1 = Color(0xFF0B1C24)
val Ink = Color(0xFFE8F1F4)
val Muted = Color(0xFF8AA3AD)
val Amber = Color(0xFFE8A838)
val Up = Color(0xFFE53935)
val Down = Color(0xFF26A69A)

private val colors = darkColorScheme(
    primary = Amber,
    onPrimary = Color(0xFF1A1205),
    background = Bg1,
    onBackground = Ink,
    surface = Bg0,
    onSurface = Ink,
    secondary = Down,
    onSecondary = Ink
)

private val typography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Bold,
        fontSize = 40.sp,
        lineHeight = 44.sp,
        color = Ink
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 24.sp,
        color = Ink
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 16.sp,
        color = Ink
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontSize = 14.sp,
        color = Muted
    )
)

@Composable
fun AShareTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = colors,
        typography = typography,
        content = content
    )
}
