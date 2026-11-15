package app.knotwork.android.presentation.ui.splash

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.knotwork.design.screens.splash.SplashCallbacks
import app.knotwork.design.screens.splash.SplashContent
import app.knotwork.design.screens.splash.SplashViewState
import app.knotwork.design.theme.KnotworkTheme
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Exercises the actual Compose loading and recovery surfaces on the emulator. */
@RunWith(AndroidJUnit4::class)
class SplashRecoveryDeviceTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun errorRetryAndLockedRecoveryRemainAvailable() {
        var retryCount = 0
        var resetRequests = 0
        var state by mutableStateOf<SplashViewState>(SplashViewState.Loading("Preparing", .5f))
        compose.setContent {
            KnotworkTheme {
                SplashContent(
                    appName = "织问",
                    state = state,
                    retryLabel = "Retry",
                    callbacks = SplashCallbacks(
                        onRetry = { retryCount++ },
                        onResetRequest = { resetRequests++ },
                    ),
                )
            }
        }
        compose.onNodeWithText("Preparing").assertIsDisplayed()
        compose.runOnIdle { state = SplashViewState.Error("Could not initialize") }
        compose.onNodeWithText("Could not initialize").assertIsDisplayed()
        compose.onNodeWithText("Retry").performClick()
        compose.runOnIdle {
            assertEquals(1, retryCount)
            state = SplashViewState.DataLocked("Locked", "Recovery is available", "Reset request")
        }
        compose.onNodeWithText("Locked").assertIsDisplayed()
        compose.onNodeWithText("Retry").performClick()
        compose.onNodeWithText("Reset request").performClick()
        compose.runOnIdle {
            assertEquals(2, retryCount)
            assertEquals(1, resetRequests)
        }
    }
}
