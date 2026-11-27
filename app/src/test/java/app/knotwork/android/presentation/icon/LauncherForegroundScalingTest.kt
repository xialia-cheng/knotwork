package app.knotwork.android.presentation.icon

import android.content.Context
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.AdaptiveIconDrawable
import android.graphics.drawable.Drawable
import android.graphics.drawable.InsetDrawable
import androidx.test.core.app.ApplicationProvider
import app.knotwork.android.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Checks that adaptive icon foreground artwork scales proportionally across bounds, densities and themes. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class LauncherForegroundScalingTest {
    @Test
    fun adaptive_foregrounds_scale_with_bounds_in_both_themes() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        for (density in listOf(160, 320)) {
            for (night in listOf(false, true)) {
                val config = Configuration(context.resources.configuration).apply {
                    densityDpi = density
                    uiMode = (uiMode and Configuration.UI_MODE_NIGHT_MASK.inv()) or
                        if (night) Configuration.UI_MODE_NIGHT_YES else Configuration.UI_MODE_NIGHT_NO
                }
                val configured = context.createConfigurationContext(config)
                for (resource in listOf(R.mipmap.ic_launcher, R.mipmap.ic_launcher_round)) {
                    for (monochrome in listOf(false, true)) {
                        val results = listOf(64, 128, 256).map { size ->
                            val icon = configured.getDrawable(resource)!!.mutate() as AdaptiveIconDrawable
                            icon.setBounds(0, 0, size, size)
                            val foreground = if (monochrome) icon.monochrome else icon.foreground
                            assertNotNull("Adaptive foreground must exist", foreground)
                            val inset = requireNotNull(foreground) as InsetDrawable
                            assertEquals(
                                "Foreground viewport must be 60dp inside the 108dp design viewport",
                                60f / 108f,
                                requireNotNull(inset.drawable).bounds.width().toFloat() / inset.bounds.width(),
                                0.025f,
                            )
                            measure(inset, size)
                        }
                        results.forEach { result ->
                            result.zip(results.last()).forEach { (actual, expected) ->
                                assertEquals(
                                    "Foreground must scale with its bounds at $density dpi",
                                    expected,
                                    actual,
                                    0.04f,
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    private fun measure(foreground: Drawable, size: Int): List<Float> {
        val bitmap = Bitmap.createBitmap(size * 3, size * 3, Bitmap.Config.ARGB_8888)
        foreground.draw(Canvas(bitmap).apply { translate(size.toFloat(), size.toFloat()) })
        var left = bitmap.width
        var top = bitmap.height
        var right = -1
        var bottom = -1
        for (y in 0 until bitmap.height) {
            for (x in 0 until bitmap.width) {
                if ((bitmap.getPixel(x, y) ushr 24) < 32) continue
                left = minOf(left, x)
                top = minOf(top, y)
                right = maxOf(right, x)
                bottom = maxOf(bottom, y)
            }
        }
        assertTrue("Foreground must contain visible artwork", right > left && bottom > top)
        return listOf(
            (right - left + 1).toFloat() / size,
            (bottom - top + 1).toFloat() / size,
            (left + right + 1).toFloat() / (2 * size) - 1f,
            (top + bottom + 1).toFloat() / (2 * size) - 1f,
        )
    }
}
