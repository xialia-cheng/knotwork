package app.knotwork.android.presentation.screenshots

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import app.knotwork.android.domain.models.ConnectionModel
import app.knotwork.android.domain.models.NodeModel
import app.knotwork.android.domain.models.NodeType
import app.knotwork.android.presentation.ui.pipeline.editor.canvas.EditorEdges
import app.knotwork.android.presentation.ui.pipeline.editor.core.CanvasTransform
import app.knotwork.design.theme.KnotworkTheme
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.flow.MutableSharedFlow
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Snapshots the selected runtime edge with motion enabled and with a stationary marker. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [36], qualifiers = "w360dp-h640dp-xhdpi")
class EditorRunningConnectionSnapshotTest {
    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun canvas_live_connection() = snapshot(reducedMotion = false, suffix = "moving")

    @Test
    fun canvas_live_connection_reduced_motion() = snapshot(reducedMotion = true, suffix = "still")

    private fun snapshot(reducedMotion: Boolean, suffix: String) {
        val events = MutableSharedFlow<String>(extraBufferCapacity = 1)
        val nodes = listOf(
            NodeModel("if", NodeType.IF_CONDITION, 30f, 20f),
            NodeModel("out", NodeType.OUTPUT, 130f, 280f),
        )
        composeTestRule.setContent {
            KnotworkTheme(darkTheme = false) {
                Box(Modifier.size(360.dp, 370.dp).background(MaterialTheme.colorScheme.surface)) {
                    EditorEdges(
                        connections = listOf(
                            ConnectionModel("true", "if", "out", "True"),
                            ConnectionModel("false", "if", "out", "False"),
                        ),
                        nodesById = nodes.associateBy(NodeModel::id),
                        transform = CanvasTransform(density = LocalDensity.current.density),
                        connectionDraft = null,
                        selectedEdgeId = null,
                        connectionTraversals = events,
                        reducedMotion = reducedMotion,
                    )
                }
            }
        }
        composeTestRule.waitForIdle()
        composeTestRule.mainClock.autoAdvance = false
        composeTestRule.runOnIdle {
            check(events.subscriptionCount.value == 1)
            check(events.tryEmit("false"))
        }
        composeTestRule.mainClock.advanceTimeBy(160)
        composeTestRule.onRoot().captureRoboImage(
            roborazziOptions = AppRoborazziOptions,
            filePath = "src/test/snapshots/editor_running_connection_$suffix.png",
        )
    }
}
