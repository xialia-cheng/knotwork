package app.knotwork.android.presentation.ui.splash

import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.core.view.WindowCompat
import androidx.test.ext.junit.runners.AndroidJUnit4
import app.knotwork.android.presentation.theme.setStatusBarAppearanceFor
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
    val compose = createAndroidComposeRule<ComponentActivity>()

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

    @Test
    fun lightSystemWithDarkAppUsesLightStatusBarIconsOnRecovery() {
        verifyRecoveryStatusBar(systemDark = false)
    }

    @Test
    fun darkSystemWithLightAppUsesDarkStatusBarIconsOnRecovery() {
        verifyRecoveryStatusBar(systemDark = true)
    }

    private fun verifyRecoveryStatusBar(systemDark: Boolean) {
        val activity = compose.activity
        val night = if (systemDark) Configuration.UI_MODE_NIGHT_YES else Configuration.UI_MODE_NIGHT_NO
        val configuration = Configuration(activity.resources.configuration).apply {
            uiMode = (uiMode and Configuration.UI_MODE_NIGHT_MASK.inv()) or night
        }
        val systemResources = activity.createConfigurationContext(configuration).resources
        val window = activity.window
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        var state by mutableStateOf<SplashViewState>(SplashViewState.Loading("Preparing", .5f))

        compose.setContent {
            CompositionLocalProvider(LocalResources provides systemResources) {
                KnotworkTheme(darkTheme = !systemDark) {
                    // Start each surface before a loading weave can pin the brand background.
                    key(state) {
                        SplashContent(
                            appName = "织问",
                            state = state,
                            onBackgroundChanged = controller::setStatusBarAppearanceFor,
                        )
                    }
                }
            }
        }

        compose.onNodeWithText("Preparing").assertIsDisplayed()
        compose.runOnIdle {
            assertEquals("Brand loading background", !systemDark, controller.isAppearanceLightStatusBars)
            state = SplashViewState.Error("Could not initialize")
        }
        compose.onNodeWithText("Could not initialize").assertIsDisplayed()
        compose.runOnIdle {
            assertEquals("Initialization error background", systemDark, controller.isAppearanceLightStatusBars)
            controller.isAppearanceLightStatusBars = !systemDark
            state = SplashViewState.DataLocked("Locked", "Recovery is available", "Reset request")
        }
        compose.onNodeWithText("Locked").assertIsDisplayed()
        compose.runOnIdle {
            assertEquals("Data lock recovery background", systemDark, controller.isAppearanceLightStatusBars)
        }
    }
}
