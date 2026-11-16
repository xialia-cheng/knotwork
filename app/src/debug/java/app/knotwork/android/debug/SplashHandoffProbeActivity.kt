package app.knotwork.android.debug

import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import app.knotwork.design.components.text.Text
import app.knotwork.design.screens.splash.SplashContent
import app.knotwork.design.screens.splash.SplashViewState
import app.knotwork.design.theme.KnotworkTheme

/** Debug-only real platform splash launch with a deliberately retained loading surface. */
class SplashHandoffProbeActivity : ComponentActivity() {
    private var startEpochMs by mutableStateOf<Long?>(null)
    private var ready = false
    private var remove: (() -> Unit)? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        val fastReady = intent.getBooleanExtra("fast_ready", false)
        trace("controlled_create fastReady=$fastReady")
        installSplashScreen().setOnExitAnimationListener { splash ->
            trace("controlled_exit platformStartEpochMs=${splash.iconAnimationStartMillis} " +
                "platformDurationMs=${splash.iconAnimationDurationMillis}")
            startEpochMs = splash.iconAnimationStartMillis
            val release = {
                trace("controlled_remove_requested")
                splash.view.postOnAnimation {
                    trace("controlled_remove_execute")
                    splash.remove()
                }
                Unit
            }
            if (ready || fastReady) release() else remove = release
        }
        super.onCreate(savedInstanceState)
        setContent {
            KnotworkTheme {
                if (fastReady) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("READY")
                    }
                } else {
                    SplashContent(
                        appName = "Controlled probe",
                        state = SplashViewState.Loading("Controlled loading", .3f),
                        splashAnimationStartMillis = startEpochMs,
                        platformUnderlay = true,
                        onMarkReady = {
                            trace("controlled_content_ready")
                            ready = true
                            remove?.invoke()
                            remove = null
                        },
                    )
                }
            }
        }
    }

    private fun trace(event: String) {
        if (Log.isLoggable("PR6Handoff", Log.DEBUG)) {
            Log.d("PR6Handoff", "elapsedNs=${SystemClock.elapsedRealtimeNanos()} epochMs=${System.currentTimeMillis()} $event")
        }
    }
}
