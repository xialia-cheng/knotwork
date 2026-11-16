package app.knotwork.design.screens.splash

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BlendMode
import android.graphics.BlendModeColorFilter
import android.graphics.HardwareRenderer
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RenderNode
import android.hardware.HardwareBuffer
import android.media.ImageReader
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Canvas
import androidx.compose.ui.graphics.drawscope.CanvasDrawScope
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.knotwork.design.R
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.nio.ByteBuffer
import kotlin.math.abs

/** Device-side check of the exported time textures and shader, not an AVD playback test. */
@RunWith(AndroidJUnit4::class)
class PixelStrokePainterTest {
    @Test
    fun sourcePixelsFollowExportedTimesAndNightTint() {
        val resources = InstrumentationRegistry.getInstrumentation().targetContext.resources
        val options = BitmapFactory.Options().apply { inScaled = false }
        val original = requireNotNull(BitmapFactory.decodeResource(resources, R.drawable.brand_mark, options))
        val high = requireNotNull(BitmapFactory.decodeResource(resources, R.drawable.brand_stroke_time_hi, options))
        val low = requireNotNull(BitmapFactory.decodeResource(resources, R.drawable.brand_stroke_time_lo, options))
        val painter = PixelStrokePainter.load(resources)
        val side = 1794
        val markSize = side * (75.5f / 108f)
        val inset = (side - markSize) / 2f
        for (time in listOf(0, 250, 500, 750, 1000)) {
            for (night in listOf(false, true)) {
                val node = RenderNode("pixel_stroke_test").apply { setPosition(0, 0, side, side) }
                val native = node.beginRecording()
                native.drawColor(android.graphics.Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR)
                val tint = if (night) 0xffd2ccff.toInt() else null
                val referenceNode = RenderNode("source_reference").apply { setPosition(0, 0, side, side) }
                val referenceCanvas = referenceNode.beginRecording()
                referenceCanvas.drawColor(android.graphics.Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR)
                referenceCanvas.translate(inset, inset)
                referenceCanvas.scale(markSize / original.width, markSize / original.height)
                val referencePaint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG).apply {
                    colorFilter = tint?.let { BlendModeColorFilter(it, BlendMode.SRC_IN) }
                }
                referenceCanvas.drawBitmap(original, 0f, 0f, referencePaint)
                referenceNode.endRecording()
                val reference = renderHardware(referenceNode, side)
                CanvasDrawScope().draw(
                    Density(1f),
                    LayoutDirection.Ltr,
                    Canvas(native),
                    Size(side.toFloat(), side.toFloat()),
                ) {
                    painter.draw(this, time / 1000f, tint)
                }
                node.endRecording()
                val target = renderHardware(node, side)
                val output = requireNotNull(InstrumentationRegistry.getInstrumentation().context.getExternalFilesDir(null))
                    .resolve("handoff-pixels").apply { mkdirs() }
                val mode = if (night) "night" else "day"
                File(output, "player-${time}ms-$mode.png").outputStream().use {
                    check(target.compress(Bitmap.CompressFormat.PNG, 100, it))
                }
                if (time == 1000) {
                    File(output, "source-$mode.png").outputStream().use {
                        check(reference.compress(Bitmap.CompressFormat.PNG, 100, it))
                    }
                }
                var samples = 0
                var edgeSamples = 0
                for (y in 1 until original.height - 1 step 3) {
                    for (x in 1 until original.width - 1 step 3) {
                        val src = original.getPixel(x, y)
                        val sourceAlpha = src ushr 24
                        if (time == 1000 && sourceAlpha in 5..245) {
                            val actualX = (inset + (x + .5f) * markSize / original.width).toInt()
                            val actualY = (inset + (y + .5f) * markSize / original.height).toInt()
                            val expectedAlpha = reference.getPixel(actualX, actualY) ushr 24
                            val actualAlpha = target.getPixel(actualX, actualY) ushr 24
                            assertTrue(
                                "source alpha at $x,$y: actual=$actualAlpha expected=$expectedAlpha",
                                abs(actualAlpha - expectedAlpha) <= 8,
                            )
                            edgeSamples++
                        }
                        if (sourceAlpha < 250) continue
                        val timeMs = (high.getPixel(x, y) and 255) * 256 + (low.getPixel(x, y) and 255)
                        if (abs(timeMs - time) < 10) continue
                        val stable = (-1..1).all { dy ->
                            (-1..1).all { dx ->
                                val neighborAlpha = original.getPixel(x + dx, y + dy) ushr 24
                                val neighborTime = (high.getPixel(x + dx, y + dy) and 255) * 256 +
                                    (low.getPixel(x + dx, y + dy) and 255)
                                neighborAlpha >= 250 && (neighborTime <= time) == (timeMs <= time)
                            }
                        }
                        if (!stable) continue
                        val actualX = (inset + (x + .5f) * markSize / original.width).toInt()
                        val actualY = (inset + (y + .5f) * markSize / original.height).toInt()
                        val actual = target.getPixel(actualX, actualY)
                        if (timeMs > time) {
                            assertEquals("unexpected ink at $x,$y t=$time", 0, actual ushr 24)
                        } else {
                            assertTrue("missing ink at $x,$y t=$time", actual ushr 24 >= 240)
                            val expected = reference.getPixel(actualX, actualY)
                            for (shift in listOf(0, 8, 16)) {
                                val difference = abs(((actual ushr shift) and 255) - ((expected ushr shift) and 255))
                                assertTrue("color differs at $x,$y t=$time", difference <= 8)
                            }
                        }
                        samples++
                    }
                }
                assertTrue("not enough source samples", samples > 1000)
                if (time == 1000) assertTrue("not enough edge samples", edgeSamples > 100)
                target.recycle()
                reference.recycle()
            }
        }
    }
    private fun renderHardware(node: RenderNode, side: Int): Bitmap {
        val usage = HardwareBuffer.USAGE_GPU_COLOR_OUTPUT or HardwareBuffer.USAGE_CPU_READ_OFTEN
        val reader = ImageReader.newInstance(side, side, PixelFormat.RGBA_8888, 2, usage)
        val renderer = HardwareRenderer()
        try {
            renderer.setOpaque(false)
            renderer.setSurface(reader.surface)
            renderer.setContentRoot(node)
            assertEquals(HardwareRenderer.SYNC_OK, renderer.createRenderRequest().setWaitForPresent(true).syncAndDraw())
            var acquired = reader.acquireLatestImage()
            repeat(100) {
                if (acquired == null) {
                    Thread.sleep(10)
                    acquired = reader.acquireLatestImage()
                }
            }
            val frame = requireNotNull(acquired) { "No hardware frame was produced" }
            try {
                val plane = frame.planes.single()
                assertEquals(4, plane.pixelStride)
                val rowBytes = side * plane.pixelStride
                val pixels = ByteArray(rowBytes * side)
                for (y in 0 until side) {
                    plane.buffer.position(y * plane.rowStride)
                    plane.buffer.get(pixels, y * rowBytes, rowBytes)
                }
                return Bitmap.createBitmap(side, side, Bitmap.Config.ARGB_8888).apply {
                    copyPixelsFromBuffer(ByteBuffer.wrap(pixels))
                }
            } finally {
                frame.close()
            }
        } finally {
            renderer.destroy()
            reader.close()
        }
    }
}
