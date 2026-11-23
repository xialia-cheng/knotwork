package app.knotwork.android.presentation.ui

/** Coordinates the system overlay with either a drawn loading mark or completed initialization. */
internal class SplashExitCoordinator {
    private var ready = false
    private var pending: (() -> Unit)? = null

    fun onPlatformExit(remove: () -> Unit) {
        if (ready) {
            remove()
        } else {
            pending = remove
        }
    }

    fun onContentReady() {
        ready = true
        val action = pending
        pending = null
        action?.invoke()
    }
}
