package app.knotwork.design.screens.chat

import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.knotwork.design.KnotworkRoborazziOptions
import app.knotwork.design.theme.KnotworkTheme
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

/** Covers the replacement of the loader with a live assistant bubble. */
@RunWith(AndroidJUnit4::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [36], qualifiers = "w360dp-h760dp-xhdpi")
class ChatHomeStreamingReplyTest {
    @get:Rule
    val composeTestRule = createComposeRule()

    @Test
    fun `the first chunk replaces the loader and later chunks update the same bubble`() {
        val state = mutableStateOf(ChatHomePreview.generating().copy(loaderLabel = "Waiting for the reply"))
        composeTestRule.setContent {
            KnotworkTheme(darkTheme = false) { ChatHomeContent(state = state.value) }
        }
        composeTestRule.onNodeWithText("Waiting for the reply").assertIsDisplayed()

        composeTestRule.runOnIdle { state.value = state.value.copy(streamingReply = "The first part.") }
        composeTestRule.onNodeWithText("The first part.").assertIsDisplayed()
        composeTestRule.onNodeWithText("Waiting for the reply").assertDoesNotExist()

        composeTestRule.runOnIdle { state.value = state.value.copy(streamingReply = "The first part. And the next.") }
        composeTestRule.onNodeWithText("The first part. And the next.").assertIsDisplayed()
        composeTestRule.onNodeWithText("The first part.").assertDoesNotExist()
    }

    @Test
    fun `a growing reply follows the end until the reader scrolls away`() {
        val listState = LazyListState()
        val initial = (1..45).joinToString("\n") { "Line $it" }
        val state = mutableStateOf(ChatHomePreview.generating().copy(streamingReply = initial))
        composeTestRule.setContent {
            KnotworkTheme(darkTheme = false) {
                ChatHomeContent(state = state.value, messageListState = listState)
            }
        }
        composeTestRule.runOnIdle {
            listState.requestScrollToItem(listState.layoutInfo.totalItemsCount - 1, scrollOffset = 100_000)
        }
        composeTestRule.runOnIdle {
            assertFalse(listState.canScrollForward)
            state.value = state.value.copy(streamingReply = "$initial\nNew line.")
        }
        composeTestRule.runOnIdle {
            assertFalse("The new line should be visible at the end.", listState.canScrollForward)
            listState.requestScrollToItem(0)
        }
        composeTestRule.runOnIdle {
            assertTrue(listState.canScrollForward)
            state.value = state.value.copy(streamingReply = "$initial\nNew line.\nAnother line.")
        }
        composeTestRule.runOnIdle {
            assertEquals(0, listState.firstVisibleItemIndex)
            assertEquals(0, listState.firstVisibleItemScrollOffset)
        }
    }

    @Test
    fun chat_home_streaming_reply_light() {
        val state = ChatHomePreview.generating().copy(
            streamingReply = "A three-step plan works well here. First, review the latest changes.",
        )
        composeTestRule.setContent {
            KnotworkTheme(darkTheme = false) { ChatHomeContent(state = state) }
        }
        composeTestRule.onRoot().captureRoboImage(
            roborazziOptions = KnotworkRoborazziOptions,
            filePath = "src/test/snapshots/chat_home_streaming_reply_light.png",
        )
    }
}
