package app.knotwork.android.presentation.ui.splash

import android.graphics.BitmapFactory
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.knotwork.design.screens.splash.SplashContent
import app.knotwork.design.screens.splash.SplashViewState
import app.knotwork.design.theme.KnotworkTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import app.knotwork.design.R as DesignR

/** Confirms a hardware frame is committed and that its ink clears the short-screen footer. */
@RunWith(AndroidJUnit4::class)
class SplashFrameDeviceTest {
    @get:Rule
    val compose = createComposeRule()

    @Volatile
    private var markReady = false

    @Test
    fun firstFrameCommitsAndShortLargeFontLayoutDoesNotOverlap() {
        compose.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, 1.5f)) {
                KnotworkTheme {
                    Box(Modifier.size(width = 274.dp, height = 487.dp)) {
                        SplashContent(
                            appName = "织问",
                            state = SplashViewState.Loading("Preparing", .5f),
                            splashAnimationStartMillis = 0L,
                            onMarkReady = { markReady = true },
                        )
                    }
                }
            }
        }
        compose.waitUntil(timeoutMillis = 20_000) { markReady }
        val mark = compose.onNodeWithTag("splash_loading_mark").assertIsDisplayed().getUnclippedBoundsInRoot()
        val title = compose.onNodeWithText("织问").assertIsDisplayed().getUnclippedBoundsInRoot()
        val resources = InstrumentationRegistry.getInstrumentation().targetContext.resources
        val options = BitmapFactory.Options().apply { inScaled = false }
        val source = requireNotNull(BitmapFactory.decodeResource(resources, DesignR.drawable.brand_mark, options))
        val pixels = IntArray(source.width * source.height)
        source.getPixels(pixels, 0, source.width, 0, 0, source.width, source.height)
        var lastInkRow = 0
        for (y in 0 until source.height) {
            if ((0 until source.width).any { x -> pixels[y * source.width + x] ushr 24 >= 128 }) lastInkRow = y
        }
        val glyphBottomFraction = (1f - MARK_FRACTION) / 2f + MARK_FRACTION * (lastInkRow + 1f) / source.height
        val glyphBottom = mark.top + (mark.bottom - mark.top) * glyphBottomFraction
        assertTrue("wordmark overlaps the footer", glyphBottom + 4.dp <= title.top)
        source.recycle()
    }

    /**
     * Production passes no platform clock any more: the platform stage is a bare
     * launch colour, so the loading page has to announce its own first frame.
     * Gating that announcement on a non-null clock left the platform overlay up
     * until initialization finished — this case is the one that catches it.
     */
    @Test
    fun firstFrameCommitsWithoutAPlatformClock() {
        compose.setContent {
            KnotworkTheme {
                Box(Modifier.size(width = 274.dp, height = 487.dp)) {
                    SplashContent(
                        appName = "织问",
                        state = SplashViewState.Loading("Preparing", .5f),
                        splashAnimationStartMillis = null,
                        onMarkReady = { markReady = true },
                    )
                }
            }
        }
        compose.waitUntil(timeoutMillis = 20_000) { markReady }
        compose.onNodeWithTag("splash_loading_mark").assertIsDisplayed()
    }

    private companion object {
        const val MARK_FRACTION = 75.5f / 108f
    }
}
