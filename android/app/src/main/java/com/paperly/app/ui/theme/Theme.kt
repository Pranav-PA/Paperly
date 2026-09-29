package com.paperly.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.ExperimentalTextApi
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import com.paperly.app.R

// ---------- Palette ----------
val Indigo = Color(0xFF5B4BF5)
val Violet = Color(0xFF8B5CF6)
val Sky = Color(0xFF38BDF8)
val Success = Color(0xFF16A34A)
val Warning = Color(0xFFF59E0B)
val Danger = Color(0xFFE11D48)

private val LightColors = lightColorScheme(
    primary = Indigo,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE9E6FF),
    onPrimaryContainer = Color(0xFF1E1466),
    secondary = Violet,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFF1E9FF),
    onSecondaryContainer = Color(0xFF3B1A78),
    tertiary = Color(0xFF0EA5E9),
    background = Color(0xFFF6F7FB),
    onBackground = Color(0xFF0F1222),
    surface = Color.White,
    onSurface = Color(0xFF0F1222),
    surfaceVariant = Color(0xFFEEF0F7),
    onSurfaceVariant = Color(0xFF5B6178),
    surfaceContainer = Color(0xFFF1F2F8),
    surfaceContainerHigh = Color(0xFFE9EBF3),
    outline = Color(0xFFD5D8E5),
    outlineVariant = Color(0xFFE6E8F0),
    error = Danger,
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9D92FF),
    onPrimary = Color(0xFF160E52),
    primaryContainer = Color(0xFF2E2585),
    onPrimaryContainer = Color(0xFFE4E0FF),
    secondary = Color(0xFFC4A8FF),
    onSecondary = Color(0xFF2A1060),
    secondaryContainer = Color(0xFF3A2470),
    onSecondaryContainer = Color(0xFFEBDDFF),
    tertiary = Color(0xFF7DD3FC),
    background = Color(0xFF0B0D17),
    onBackground = Color(0xFFE8E9F2),
    surface = Color(0xFF141726),
    onSurface = Color(0xFFE8E9F2),
    surfaceVariant = Color(0xFF1E2236),
    onSurfaceVariant = Color(0xFFA3A8C0),
    surfaceContainer = Color(0xFF181B2C),
    surfaceContainerHigh = Color(0xFF212538),
    outline = Color(0xFF3A3F58),
    outlineVariant = Color(0xFF272B40),
    error = Color(0xFFFB7185),
)

@Immutable
data class PaperlyExtras(val brandGradient: Brush, val heroGradient: Brush, val isDark: Boolean)

val LocalPaperlyExtras = staticCompositionLocalOf {
    PaperlyExtras(Brush.linearGradient(listOf(Indigo, Violet)), Brush.linearGradient(listOf(Indigo, Violet)), false)
}

// ---------- Typography ----------
@OptIn(ExperimentalTextApi::class)
private fun jakarta(weight: FontWeight) = Font(
    R.font.jakarta,
    weight = weight,
    variationSettings = FontVariation.Settings(FontVariation.weight(weight.weight))
)

val Jakarta = FontFamily(
    jakarta(FontWeight.Normal),
    jakarta(FontWeight.Medium),
    jakarta(FontWeight.SemiBold),
    jakarta(FontWeight.Bold),
    jakarta(FontWeight.ExtraBold),
)

private fun style(size: Int, weight: FontWeight, line: Int, spacing: Double = 0.0) = TextStyle(
    fontFamily = Jakarta, fontWeight = weight, fontSize = size.sp, lineHeight = line.sp, letterSpacing = spacing.sp
)

private val PaperlyTypography = Typography(
    displaySmall = style(34, FontWeight.ExtraBold, 40, -0.5),
    headlineLarge = style(30, FontWeight.ExtraBold, 36, -0.4),
    headlineMedium = style(26, FontWeight.Bold, 32, -0.3),
    headlineSmall = style(22, FontWeight.Bold, 28, -0.2),
    titleLarge = style(19, FontWeight.Bold, 25),
    titleMedium = style(16, FontWeight.SemiBold, 22),
    titleSmall = style(14, FontWeight.SemiBold, 20),
    bodyLarge = style(15, FontWeight.Normal, 23),
    bodyMedium = style(14, FontWeight.Normal, 21),
    bodySmall = style(12, FontWeight.Normal, 17),
    labelLarge = style(14, FontWeight.SemiBold, 20, 0.1),
    labelMedium = style(12, FontWeight.SemiBold, 16, 0.2),
    labelSmall = style(11, FontWeight.SemiBold, 14, 0.4),
)

@Composable
fun PaperlyTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors = if (darkTheme) DarkColors else LightColors
    val extras = PaperlyExtras(
        brandGradient = Brush.linearGradient(listOf(Indigo, Violet)),
        heroGradient = if (darkTheme) {
            Brush.linearGradient(listOf(Color(0xFF2B2380), Color(0xFF4A2A8F), Color(0xFF1B2A6B)))
        } else {
            Brush.linearGradient(listOf(Color(0xFF4F46E5), Color(0xFF7C3AED), Color(0xFF6366F1)))
        },
        isDark = darkTheme
    )

    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
            WindowCompat.getInsetsController(window, view).isAppearanceLightNavigationBars = !darkTheme
        }
    }

    androidx.compose.runtime.CompositionLocalProvider(LocalPaperlyExtras provides extras) {
        MaterialTheme(colorScheme = colors, typography = PaperlyTypography, content = content)
    }
}
