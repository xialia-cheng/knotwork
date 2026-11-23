package app.knotwork.android.presentation.ui.pipeline.editor.canvas

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.unit.dp
import app.knotwork.android.presentation.ui.pipeline.editor.core.BezierEdge
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collectLatest

private const val TRAVERSAL_MILLIS = 420
private const val STILL_POSITION = 0.5f
private const val DOT_RADIUS_DP = 3.5f

/** Draws the most recent live traversal, using the same cubic as the connection. */
internal class RunningConnection(private val reducedMotion: Boolean) {
    private val connectionId = mutableStateOf<String?>(null)
    private val progress = Animatable(0f)

    suspend fun show(id: String) {
        if (!reducedMotion) progress.snapTo(0f)
        connectionId.value = id
        try {
            if (reducedMotion) {
                delay(TRAVERSAL_MILLIS.toLong())
            } else {
                progress.animateTo(1f, tween(durationMillis = TRAVERSAL_MILLIS, easing = LinearEasing))
            }
        } finally {
            connectionId.value = null
        }
    }

    fun drawOn(
        scope: DrawScope,
        id: String,
        start: Offset,
        control1: Offset,
        control2: Offset,
        end: Offset,
        color: Color,
    ) {
        if (id != connectionId.value) return
        val fraction = if (reducedMotion) STILL_POSITION else progress.value
        val (x, y) = BezierEdge.pointAt(
            fraction, start.x, start.y, control1.x, control1.y, control2.x, control2.y, end.x, end.y,
        )
        with(scope) { drawCircle(color, radius = DOT_RADIUS_DP.dp.toPx(), center = Offset(x, y)) }
    }
}

/** Collects only the traversals for the current canvas and respects reduced motion. */
@Composable
internal fun rememberRunningConnection(traversals: Flow<String>, reducedMotion: Boolean): RunningConnection {
    val activity = remember(traversals, reducedMotion) { RunningConnection(reducedMotion) }
    LaunchedEffect(activity) {
        traversals.collectLatest(activity::show)
    }
    return activity
}
