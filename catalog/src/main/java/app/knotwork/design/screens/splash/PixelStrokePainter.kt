package app.knotwork.design.screens.splash

import android.content.res.Resources
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BitmapShader
import android.graphics.BlendMode
import android.graphics.BlendModeColorFilter
import android.graphics.Paint
import android.graphics.RuntimeShader
import android.graphics.Shader
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.nativeCanvas
import app.knotwork.design.R
import java.nio.ByteBuffer

private const val MARK_FRACTION = 75.5f / 108f
private const val BYTE_MASK = 0xff

/** Experimental original-pixel reveal. The timestamp textures store high/low milliseconds. */
internal class PixelStrokePainter private constructor(
    private val width: Int,
    private val height: Int,
    private val shader: RuntimeShader,
) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { this.shader = this@PixelStrokePainter.shader }
    private var lastInk: Int? = null

    fun draw(scope: DrawScope, progress: Float, darkInk: Int?) = with(scope) {
        if (progress <= 0f) return@with
        shader.setFloatUniform("timeMs", progress.coerceIn(0f, 1f) * THREAD_DURATION_MS.toFloat())
        if (darkInk != lastInk) {
            paint.colorFilter = darkInk?.let { BlendModeColorFilter(it, BlendMode.SRC_IN) }
            lastInk = darkInk
        }
        drawIntoCanvas { canvas ->
            val native = canvas.nativeCanvas
            val markSize = size.width * MARK_FRACTION
            val inset = (size.width - markSize) / 2f
            val save = native.save()
            native.translate(inset, inset)
            native.scale(markSize / width, markSize / height)
            native.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
            native.restoreToCount(save)
        }
    }

    companion object {
        fun load(resources: Resources): PixelStrokePainter {
            val options = BitmapFactory.Options().apply { inScaled = false }
            val source = requireNotNull(BitmapFactory.decodeResource(resources, R.drawable.brand_mark, options))
            val hi = decodeAlpha(resources, R.drawable.brand_stroke_time_hi)
            val lo = decodeAlpha(resources, R.drawable.brand_stroke_time_lo)
            require(hi.width == source.width && hi.height == source.height)
            require(lo.width == source.width && lo.height == source.height)
            val shader = RuntimeShader(
                """
                uniform shader art;
                uniform shader highTime;
                uniform shader lowTime;
                uniform float timeMs;
                half4 main(float2 xy) {
                    float hi = floor(float(highTime.eval(xy).a) * 255.0 + 0.5);
                    float lo = floor(float(lowTime.eval(xy).a) * 255.0 + 0.5);
                    return art.eval(xy) * half(step(hi * 256.0 + lo, timeMs));
                }
                """.trimIndent(),
            )
            shader.setInputShader("art", bitmapShader(source, false))
            shader.setInputShader("highTime", bitmapShader(hi, true))
            shader.setInputShader("lowTime", bitmapShader(lo, true))
            return PixelStrokePainter(source.width, source.height, shader)
        }

        private fun bitmapShader(bitmap: Bitmap, nearest: Boolean): BitmapShader =
            BitmapShader(bitmap, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP).apply {
                setFilterMode(if (nearest) BitmapShader.FILTER_MODE_NEAREST else BitmapShader.FILTER_MODE_LINEAR)
            }

        private fun decodeAlpha(resources: Resources, resource: Int): Bitmap {
            val options = BitmapFactory.Options().apply { inScaled = false }
            val bitmap = requireNotNull(BitmapFactory.decodeResource(resources, resource, options))
            val pixels = IntArray(bitmap.width * bitmap.height)
            bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
            return Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ALPHA_8).apply {
                val bytes = ByteArray(rowBytes * height)
                for (y in 0 until height) {
                    for (x in 0 until width) {
                        bytes[y * rowBytes + x] = (pixels[y * width + x] and BYTE_MASK).toByte()
                    }
                }
                copyPixelsFromBuffer(ByteBuffer.wrap(bytes))
                bitmap.recycle()
            }
        }
    }
}
