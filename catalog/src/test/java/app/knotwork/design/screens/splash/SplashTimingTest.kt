package app.knotwork.design.screens.splash

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.runtime.MonotonicFrameClock
import androidx.compose.ui.MotionDurationScale
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Verifies platform timing conversion and Compose animation scaling at supported system speeds. */
class SplashTimingTest {
    @Test
    fun platformElapsedUsesWallTimeDividedByDurationScale() {
        assertEquals(400L, splashThreadElapsed(1_000L, 1_200L, .5f))
        assertEquals(400L, splashThreadElapsed(1_000L, 1_400L, 1f))
        assertEquals(400L, splashThreadElapsed(1_000L, 1_800L, 2f))
        assertEquals(1_000L, splashThreadElapsed(1_000L, 1_200L, 0f))
    }

    @Test
    fun composeScalesOnlyTheRemainingTimelineOnce() {
        for (factor in listOf(0f, .5f, 1f, 2f)) {
            var nowNanos = 0L
            val clock = object : MonotonicFrameClock {
                override suspend fun <R> withFrameNanos(onFrame: (Long) -> R): R {
                    nowNanos += 16_000_000L
                    return onFrame(nowNanos)
                }
            }
            val durationScale = object : MotionDurationScale {
                override val scaleFactor = factor
            }
            runBlocking(clock + durationScale) {
                Animatable(.4f).animateTo(1f, tween(600, easing = LinearEasing))
            }
            val elapsedMillis = nowNanos / 1_000_000L - 16L
            val expectedMillis = (600 * factor).toLong()
            assertTrue("scale=$factor elapsed=$elapsedMillis", elapsedMillis in expectedMillis..expectedMillis + 16)
        }
    }
}
