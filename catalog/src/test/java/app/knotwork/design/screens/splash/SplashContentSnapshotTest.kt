package app.knotwork.design.screens.splash

import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.Density
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.knotwork.design.KnotworkRoborazziOptions
import app.knotwork.design.a11y.FixedKnotworkA11y
import app.knotwork.design.a11y.LocalKnotworkA11y
import app.knotwork.design.theme.KnotworkTheme
import app.knotwork.design.tokens.OklchColorMath
import app.knotwork.design.tokens.Srgb
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import java.security.MessageDigest
import javax.imageio.ImageIO
import android.graphics.Color as AndroidColor

/**
 * Roborazzi baseline for `SplashContent`. Covers the documented states
 * (Initializing / Loading / Error / DataLocked) in both themes.
 */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [36], qualifiers = "w360dp-h760dp-xhdpi")
class SplashContentSnapshotTest {
    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun splash_loading_light() = snapshot(name = "loading", dark = false) {
        SplashContent(appName = "Knotwork Agent", state = SplashPreview.loading())
    }

    @Test
    @Config(qualifiers = "w360dp-h760dp-night-xhdpi")
    fun splash_loading_dark() = snapshot(name = "loading", dark = true) {
        SplashContent(appName = "Knotwork Agent", state = SplashPreview.loading())
    }

    @Test
    fun splash_error_light() = snapshot(name = "error", dark = false) {
        SplashContent(appName = "Knotwork Agent", state = SplashPreview.error())
    }

    @Test
    @Config(qualifiers = "w360dp-h760dp-night-xhdpi")
    fun splash_error_dark() = snapshot(name = "error", dark = true) {
        SplashContent(appName = "Knotwork Agent", state = SplashPreview.error())
    }

    @Test
    fun splash_data_locked_light() = snapshot(name = "data_locked", dark = false) {
        SplashContent(appName = "Knotwork Agent", state = SplashPreview.dataLocked())
    }

    @Test
    @Config(qualifiers = "w360dp-h760dp-night-xhdpi")
    fun splash_data_locked_dark() = snapshot(name = "data_locked", dark = true) {
        SplashContent(appName = "Knotwork Agent", state = SplashPreview.dataLocked())
    }

    @Test
    fun splash_weave_light_frames() = weaveFrames(dark = false)

    @Test
    @Config(qualifiers = "w360dp-h760dp-night-xhdpi")
    fun splash_weave_dark_frames() = weaveFrames(dark = true)

    @Test
    fun platform_underlay_remains_visible_before_platform_timing_is_known() {
        composeTestRule.setContent {
            KnotworkTheme {
                SplashContent(
                    appName = "Knotwork Agent",
                    state = SplashPreview.loading(),
                )
            }
        }
        waitForStrokePainter()
        val pixels = composeTestRule.onNodeWithTag("splash_loading_mark").captureToImage().toPixelMap().buffer
        val inkPixels = pixels.count { pixel ->
            val red = pixel shr 16 and 0xff
            val green = pixel shr 8 and 0xff
            val blue = pixel and 0xff
            red < 160 && blue > red + 20 && blue > green + 20
        }
        assertTrue("The original wordmark must remain visible under the platform splash", inkPixels > 100)
    }

    @Test
    fun splash_reduced_motion_does_not_animate() {
        composeTestRule.mainClock.autoAdvance = false
        composeTestRule.setContent {
            KnotworkTheme {
                CompositionLocalProvider(LocalKnotworkA11y provides FixedKnotworkA11y(reducedMotion = true)) {
                    SplashContent(appName = "Knotwork Agent", state = SplashPreview.loading())
                }
            }
        }
        composeTestRule.mainClock.advanceTimeByFrame()
        val before = composeTestRule.onRoot().captureToImage().toPixelMap().buffer.copyOf()
        composeTestRule.mainClock.advanceTimeBy(1200)
        val after = composeTestRule.onRoot().captureToImage().toPixelMap().buffer
        assertArrayEquals(before, after)
    }

    @Test
    fun loading_artwork_defaults_to_the_platform_icon_size() {
        composeTestRule.setContent {
            KnotworkTheme {
                CompositionLocalProvider(LocalKnotworkA11y provides FixedKnotworkA11y(reducedMotion = true)) {
                    SplashContent(appName = "Knotwork Agent", state = SplashPreview.loading())
                }
            }
        }
        val widthPx = composeTestRule.onNodeWithTag("splash_loading_mark").fetchSemanticsNode().boundsInRoot.width
        assertEquals(288f, widthPx / composeTestRule.density.density, 0.5f)
    }

    @Test
    @Config(qualifiers = "w320dp-h480dp-xhdpi")
    fun loading_artwork_fits_a_short_screen() {
        composeTestRule.setContent {
            KnotworkTheme {
                CompositionLocalProvider(LocalKnotworkA11y provides FixedKnotworkA11y(reducedMotion = true)) {
                    SplashContent(
                        appName = "Knotwork Agent",
                        state = SplashPreview.loading(),
                    )
                }
            }
        }
        val widthPx = composeTestRule.onNodeWithTag("splash_loading_mark").fetchSemanticsNode().boundsInRoot.width
        assertEquals(216f, widthPx / composeTestRule.density.density, 0.5f)
    }

    @Test
    @Config(qualifiers = "w320dp-h640dp-xhdpi")
    fun small_screen_with_large_text_keeps_artwork_clear_of_the_title() = assertLargeTextFits()

    @Test
    @Config(qualifiers = "w360dp-h760dp-xhdpi")
    fun standard_screen_with_large_text_keeps_artwork_clear_of_the_title() = assertLargeTextFits()

    private fun assertLargeTextFits() {
        composeTestRule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(
                LocalDensity provides Density(density.density, fontScale = 1.3f),
                LocalKnotworkA11y provides FixedKnotworkA11y(reducedMotion = true),
            ) {
                KnotworkTheme { SplashContent(appName = "Knotwork Agent", state = SplashPreview.loading()) }
            }
        }
        val mark = composeTestRule.onNodeWithTag("splash_loading_mark").fetchSemanticsNode().boundsInRoot
        val title = composeTestRule.onNodeWithText("Knotwork Agent").fetchSemanticsNode().boundsInRoot
        assertTrue("The artwork must stay above the title", mark.bottom < title.top)
    }

    @Test
    fun splash_uses_the_original_wordmark_within_the_safe_area() {
        val originalFile = File("../brand/reference-original.jpg")
        val digest = MessageDigest.getInstance("SHA-256").digest(originalFile.readBytes())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals("26e338db469052cb18a0030aecd42054521ec329efa469e14056db85eef1d452", digest)
        val source = ImageIO.read(originalFile)
        val mask = ImageIO.read(File("src/main/res/drawable-nodpi/brand_mark.png"))
        assertEquals(source.width, mask.width)
        assertEquals(source.height, mask.height)
        assertEquals(0, mask.getRGB(0, 0) ushr 24)
        var minX = mask.width
        var maxX = 0
        var samples = 0
        var maxRadius = 0.0
        for (y in 0 until mask.height) {
            for (x in 0 until mask.width) {
                val pixel = mask.getRGB(x, y)
                val alpha = pixel ushr 24
                if (alpha > 0) {
                    assertTrue("The original visible artwork bounds must remain unchanged", x in 127 until 1127)
                    assertTrue("The original visible artwork bounds must remain unchanged", y in 416 until 892)
                    val dx = (x - mask.width / 2.0) * 75.5 / mask.width
                    val dy = (y - mask.height / 2.0) * 75.5 / mask.height
                    maxRadius = maxOf(maxRadius, kotlin.math.hypot(dx, dy))
                }
                if (alpha < 128) continue
                minX = minOf(minX, x)
                maxX = maxOf(maxX, x)
                if (alpha != 255 || x % 31 != 0 || y % 31 != 0) continue
                assertSameArtworkColor(source.getRGB(x, y), pixel)
                samples++
            }
        }
        assertTrue("The original drawing must have opaque samples", samples > 20)
        val widthFraction = (maxX - minX + 1) * 75.5 / mask.width / 108
        assertTrue("The mark should occupy about 56% of the icon", widthFraction in 0.54..0.57)
        assertTrue("The artwork must stay inside the circular safe area", maxRadius <= 33.0)
        // The platform stage no longer mounts a mark at all, so the animated
        // platform icon is gone with it; the artwork assertions above keep
        // guarding the loading page's own pixels.
        // The platform stage is the launch colour and nothing else, so that the
        // wordmark is drawn exactly once — by the loading page, from blank. The
        // artwork checks above still guard the loading page's own pixels.
        val theme = File("../app/src/main/res/values/themes.xml").readText()
        assertTrue(
            "Theme.App.Splash must mount the blank platform icon",
            theme.contains("@drawable/splash_icon_blank"),
        )
        val blank = File("../app/src/main/res/drawable/splash_icon_blank.xml").readText()
        assertTrue(
            "The platform icon must be transparent",
            blank.contains("@android:color/transparent"),
        )
    }

    @Test
    fun launcher_uses_the_new_original_artwork_within_the_safe_area() {
        val originalFile = File("../brand/launcher-original.png")
        val digest = MessageDigest.getInstance("SHA-256").digest(originalFile.readBytes())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        assertEquals("8a505bee118bcf7bf984b594e8e01bcacd4b963cd7f5859f936caf3e34527bdc", digest)
        val original = ImageIO.read(originalFile)
        val foreground = ImageIO.read(File("../app/src/main/res/drawable-nodpi/launcher_mark.png"))
        assertEquals(original.width, foreground.width)
        assertEquals(original.height, foreground.height)
        var opaque = 0
        var differences = 0
        var maxRadius = 0.0
        var outsideRoundedDesign = 0
        for (y in 0 until foreground.height) {
            for (x in 0 until foreground.width) {
                val pixel = foreground.getRGB(x, y)
                val alpha = pixel ushr 24
                if (alpha == 0) continue
                val dx = (x - foreground.width / 2.0) * 60.0 / foreground.width
                val dy = (y - foreground.height / 2.0) * 60.0 / foreground.height
                maxRadius = maxOf(maxRadius, kotlin.math.hypot(dx, dy))
                // Map the 108dp design viewport to 96px, then test the largest allowed 20px corner.
                val designX = 48.0 + dx * 96.0 / 108.0
                val designY = 48.0 + dy * 96.0 / 108.0
                val nearestX = designX.coerceIn(20.0, 76.0)
                val nearestY = designY.coerceIn(20.0, 76.0)
                if (kotlin.math.hypot(designX - nearestX, designY - nearestY) > 20.0) outsideRoundedDesign++
                if (alpha != 255) continue
                opaque++
                if ((pixel and 0xffffff) != (original.getRGB(x, y) and 0xffffff)) differences++
            }
        }
        assertTrue("The new drawing must include opaque pixels", opaque > 20)
        assertEquals("Opaque pixels must retain their original RGB", 0, differences)
        assertTrue("All visible pixels must remain in the 66dp safe circle", maxRadius <= 33.0)
        assertEquals("Artwork must fit the 96px reference with 20px corners", 0, outsideRoundedDesign)
        listOf("ic_launcher_foreground", "ic_launcher_monochrome").forEach { name ->
            val xml = File("../app/src/main/res/drawable/$name.xml").readText()
            assertTrue(xml.contains("@drawable/launcher_mark"))
        }
        val night = File("../app/src/main/res/drawable-night/ic_launcher_foreground.xml").readText()
        assertTrue(night.contains("@drawable/launcher_mark"))
        assertTrue(night.contains("@color/brand_startup_ink"))
    }

    private fun assertSameArtworkColor(original: Int, pixel: Int) {
        for (shift in listOf(0, 8, 16)) {
            val diff = kotlin.math.abs((pixel shr shift and 255) - (original shr shift and 255))
            assertTrue("Opaque artwork pixels must preserve the original color", diff <= 3)
        }
    }

    @Test
    fun startup_ink_contrasts_with_its_background_in_both_modes() {
        listOf(false, true).forEach { dark ->
            val variant = if (dark) "values-night" else "values"
            val xml = File("src/main/res/$variant/brand_startup.xml").readText()
            fun color(name: String): Int {
                val match = requireNotNull(Regex("<color name=\"$name\">([^<]+)</color>").find(xml))
                return AndroidColor.parseColor(match.groupValues[1])
            }
            fun srgb(value: Int) = Srgb(
                AndroidColor.red(value) / 255.0,
                AndroidColor.green(value) / 255.0,
                AndroidColor.blue(value) / 255.0,
            )
            val background = srgb(color("brand_startup_background"))
            val ink = srgb(color("brand_startup_ink"))
            assertTrue(OklchColorMath.contrast(background, ink) >= 4.5)
        }
    }

    private fun weaveFrames(dark: Boolean) {
        composeTestRule.mainClock.autoAdvance = false
        composeTestRule.setContent {
            KnotworkTheme(darkTheme = dark) {
                CompositionLocalProvider(LocalKnotworkA11y provides FixedKnotworkA11y(reducedMotion = false)) {
                    SplashContent(appName = "Knotwork Agent", state = SplashPreview.loading())
                }
            }
        }
        waitForStrokePainter()
        val theme = if (dark) "dark" else "light"
        val frames = mutableListOf<IntArray>()
        composeTestRule.mainClock.advanceTimeByFrame()
        listOf(0L, 500L, 1000L).forEachIndexed { index, millis ->
            if (index > 0) composeTestRule.mainClock.advanceTimeBy(500L)
            composeTestRule.onRoot().captureRoboImage(
                roborazziOptions = KnotworkRoborazziOptions,
                filePath = "src/test/snapshots/splash_weave_${theme}_$millis.png",
            )
            frames += composeTestRule.onRoot().captureToImage().toPixelMap().buffer.copyOf()
        }
        assertFalse("The thread should be revealed over time", frames[0].contentEquals(frames[1]))
        assertFalse("The thread should continue until its end", frames[1].contentEquals(frames[2]))
    }

    private fun waitForStrokePainter() {
        composeTestRule.waitUntil(timeoutMillis = 10_000) {
            if (!composeTestRule.mainClock.autoAdvance) composeTestRule.mainClock.advanceTimeByFrame()
            composeTestRule.onAllNodes(SemanticsMatcher.expectValue(StrokePainterReady, true))
                .fetchSemanticsNodes().isNotEmpty()
        }
    }

    private fun snapshot(name: String, dark: Boolean, content: @Composable () -> Unit) {
        composeTestRule.setContent {
            KnotworkTheme(darkTheme = dark) {
                CompositionLocalProvider(LocalKnotworkA11y provides FixedKnotworkA11y(reducedMotion = true)) {
                    content()
                }
            }
        }
        waitForStrokePainter()
        val themeTag = if (dark) "dark" else "light"
        composeTestRule.onRoot().captureRoboImage(
            roborazziOptions = KnotworkRoborazziOptions,
            filePath = "src/test/snapshots/splash_${name}_$themeTag.png",
        )
    }
}

/** Snapshot fixtures backing the splash test suite. */
internal object SplashPreview {
    fun loading(): SplashViewState = SplashViewState.Loading(
        message = "Loading model • Gemma 4 E2B",
        progress = 0.62f,
    )

    fun error(): SplashViewState = SplashViewState.Error(
        message = "Initialisation failed: model file not found. Reinstall the model from Settings.",
    )

    fun dataLocked(): SplashViewState = SplashViewState.DataLocked(
        title = "Your data can’t be unlocked",
        body = "The encryption key protecting your local data could not be read. " +
            "This is often temporary — try again first. If the problem persists, " +
            "the only way forward is erasing all local data.",
        resetLabel = "Erase all data",
    )
}
