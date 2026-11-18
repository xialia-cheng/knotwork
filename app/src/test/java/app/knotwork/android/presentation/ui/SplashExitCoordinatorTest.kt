package app.knotwork.android.presentation.ui

import org.junit.Assert.assertEquals
import org.junit.Test

/** Verifies splash handoff ordering for slow startup and immediately completed initialization. */
class SplashExitCoordinatorTest {
    @Test
    fun loadingOverlayRemainsUntilTheMarkIsReady() {
        val coordinator = SplashExitCoordinator()
        var removals = 0
        coordinator.onPlatformExit { removals++ }
        assertEquals(0, removals)
        coordinator.onContentReady()
        coordinator.onContentReady()
        assertEquals(1, removals)
    }

    @Test
    fun completedInitializationDoesNotWaitForTheAnimationOrMark() {
        val coordinator = SplashExitCoordinator()
        var removals = 0
        coordinator.onContentReady()
        coordinator.onPlatformExit { removals++ }
        assertEquals(1, removals)
    }
}
