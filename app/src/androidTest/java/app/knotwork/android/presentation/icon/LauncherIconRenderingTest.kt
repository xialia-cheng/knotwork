package app.knotwork.android.presentation.icon

import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.AdaptiveIconDrawable
import android.graphics.drawable.Drawable
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.knotwork.android.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/** Verifies PackageManager launcher icons and records Android framework renderings at several sizes. */
@RunWith(AndroidJUnit4::class)
class LauncherIconRenderingTest {
    @Test
    fun package_manager_icon_renders_proportionally_at_multiple_sizes_and_densities() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val packageIcon = context.packageManager.getApplicationIcon(context.packageName)
        assertTrue("PackageManager must load an adaptive icon", packageIcon is AdaptiveIconDrawable)
        val output = requireNotNull(context.getExternalFilesDir("icon-render"))
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
                        val measurements = listOf(64, 128, 256).map { size ->
                            val icon = if (!night && resource == R.mipmap.ic_launcher) {
                                requireNotNull(packageIcon.constantState).newDrawable(configured.resources).mutate()
                            } else {
                                configured.getDrawable(resource)!!.mutate()
                            } as AdaptiveIconDrawable
                            icon.setBounds(0, 0, size, size)
                            val foreground = if (monochrome) icon.monochrome else icon.foreground
                            assertNotNull("Adaptive foreground must exist", foreground)
                            val result = measure(requireNotNull(foreground), size)
                            if (!monochrome && resource == R.mipmap.ic_launcher && density == 160) {
                                saveIcon(icon, size, File(output, "icon-${if (night) "night" else "day"}-$size.png"))
                            }
                            result
                        }
                        measurements.forEach { result ->
                            result.zip(measurements.last()).forEach { (actual, expected) ->
                                assertEquals("Icon foreground changes with bounds", expected, actual, 0.04f)
                            }
                        }
                    }
                }
            }
        }
        val loaded = packageIcon as AdaptiveIconDrawable
        assertTrue("PackageManager icon must have a nonempty intrinsic width", loaded.intrinsicWidth > 0)
        assertTrue("PackageManager icon must have a nonempty intrinsic height", loaded.intrinsicHeight > 0)
        val optical = loaded.opticalInsets
        File(output, "drawable-metadata.txt").writeText(
            "intrinsic=${loaded.intrinsicWidth}x${loaded.intrinsicHeight}\n" +
                "opticalInsets=${optical.left},${optical.top},${optical.right},${optical.bottom}\n" +
                "package=${context.packageName}\n",
        )
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
        assertTrue("Foreground must contain the complete artwork", right > left && bottom > top)
        return listOf(
            (right - left + 1).toFloat() / size,
            (bottom - top + 1).toFloat() / size,
            (left + right + 1).toFloat() / (2 * size) - 1f,
            (top + bottom + 1).toFloat() / (2 * size) - 1f,
        )
    }

    private fun saveIcon(icon: Drawable, size: Int, file: File) {
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        icon.setBounds(0, 0, size, size)
        icon.draw(Canvas(bitmap))
        file.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
    }
}
