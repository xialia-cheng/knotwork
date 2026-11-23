package app.knotwork.android.presentation.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalResources
import androidx.core.view.WindowInsetsControllerCompat
import app.knotwork.android.domain.repositories.AppearanceSettings
import app.knotwork.design.theme.KnotworkTheme
import app.knotwork.design.tokens.ThemeSeed
import app.knotwork.design.tokens.themePresets
import app.knotwork.design.tokens.themeSeed

/** Wallpaper supplies only a seed; our fixed-lightness OKLCH roles construct the palette. */
@Composable
fun KnotworkAppTheme(
    appearance: AppearanceSettings = AppearanceSettings(),
    darkTheme: Boolean = appearance.resolveDarkTheme(isSystemInDarkTheme()),
    content: @Composable () -> Unit,
) {
    val resources = LocalResources.current
    val seed = when (appearance.source) {
        "preset" -> themePresets.firstOrNull { it.id == appearance.preset }
            ?.let { ThemeSeed(it.hue, it.chroma) } ?: ThemeSeed()
        "custom" -> themeSeed(Color(appearance.customColor))
        else -> wallpaperThemeSeed {
            Color(resources.getColor(android.R.color.system_accent1_500, null))
        }
    }
    KnotworkTheme(
        darkTheme = darkTheme,
        seed = seed,
        vivid = appearance.vivid,
        pureBlack = appearance.pureBlack,
        content = content,
    )
}

internal fun AppearanceSettings.resolveDarkTheme(systemDarkTheme: Boolean): Boolean = when (mode) {
    "light" -> false
    "dark" -> true
    else -> systemDarkTheme
}

internal fun WindowInsetsControllerCompat.setStatusBarAppearanceFor(background: Color) {
    isAppearanceLightStatusBars = background.luminance() > STATUS_BAR_ICON_CONTRAST_CROSSOVER
}

// Relative luminance where black and white have equal contrast against the background.
private const val STATUS_BAR_ICON_CONTRAST_CROSSOVER = 0.179f
