package app.knotwork.android.presentation.ui.splash

import androidx.annotation.StringRes
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.res.stringResource
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import app.knotwork.android.R
import app.knotwork.android.domain.models.InitStage
import app.knotwork.design.screens.splash.SplashCallbacks
import app.knotwork.design.screens.splash.SplashContent
import app.knotwork.design.screens.splash.SplashResetDialogState
import app.knotwork.design.screens.splash.SplashViewState
import app.knotwork.design.R as DesignR

/**
 * Slim app-side splash mapper. Subscribes to [SplashViewModel.uiState],
 * maps the [SplashUiState] domain projection to the catalog
 * [SplashViewState], and renders [SplashContent].
 *
 * On successful initialisation the screen invokes [onInitialized], which the
 * activity wires to a `popUpTo(splash) { inclusive = true }` navigation so
 * the splash route is removed from the back stack.
 *
 * When initialization fails because the database passphrase is unavailable,
 * the screen renders the dedicated data-locked recovery surface instead of
 * the generic error layout: explanation + Retry + typed-confirm full reset.
 *
 * @param onInitialized Invoked once when the use case reaches `InitStage.Done`.
 * @param viewModel Hilt-injected [SplashViewModel].
 * @param modifier Optional layout modifier.
 * @param onSplashContentReady Signals that the system overlay can hand off to this screen.
 */
@Composable
fun SplashScreen(
    onInitialized: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: SplashViewModel = hiltViewModel(),
    onSplashContentReady: () -> Unit = {},
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    // The loading page leaves only once the wordmark has finished weaving *and*
    // initialization is done. Navigating on "done" alone cut the animation
    // short whenever the app started faster than the weave: the record showed
    // the mark reaching its last stroke and the chat home replacing it in the
    // same fifth of a second. The wait is bounded by the weave itself (under a
    // second) and never runs when loading is slower than that.
    var weaveFinished by remember { mutableStateOf(false) }
    LaunchedEffect(uiState.isDone, weaveFinished) {
        if (uiState.isDone && weaveFinished) {
            // The record showed the last stroke and the chat home in the same
            // fifth of a second: completing the weave is not the same as the user
            // seeing it complete. A short, fixed dwell makes the finished mark
            // readable without turning the splash into a wait.
            delay(SPLASH_COMPLETE_DWELL_MS)
            onInitialized()
        }
    }

    val startingMessage = stringResource(R.string.splash_starting)
    val retryLabel = stringResource(R.string.common_retry)
    val keyword = stringResource(DesignR.string.knotwork_typed_confirm_word)
    val dataLockedTexts = DataLockedTexts(
        title = stringResource(R.string.splash_data_locked_title),
        body = stringResource(R.string.splash_data_locked_body),
        resetLabel = stringResource(R.string.splash_data_locked_reset),
        dialogTitle = stringResource(R.string.splash_reset_dialog_title),
        dialogBody = stringResource(R.string.splash_reset_dialog_body, keyword),
        dialogHint = stringResource(R.string.splash_reset_dialog_hint, keyword),
        dialogConfirm = stringResource(R.string.splash_reset_dialog_confirm),
        dialogCancel = stringResource(R.string.common_cancel),
        keyword = keyword,
    )
    val resources = LocalResources.current
    val viewState = uiState.toViewState(
        defaultMessage = startingMessage,
        stageText = { stage -> resources.getString(stageLabel(stage)) },
        dataLockedTexts = dataLockedTexts,
    )
    val appName = stringResource(R.string.app_name)
    val callbacks = remember(viewModel) {
        SplashCallbacks(
            onRetry = viewModel::retry,
            onResetRequest = viewModel::requestReset,
            onResetInputChange = viewModel::updateResetTypedInput,
            onResetConfirm = viewModel::confirmReset,
            onResetDismiss = viewModel::dismissResetDialog,
        )
    }

    SplashContent(
        appName = appName,
        state = viewState,
        modifier = modifier,
        retryLabel = retryLabel,
        callbacks = callbacks,
        onMarkReady = onSplashContentReady,
        onWeaveFinished = { weaveFinished = true },
    )
}

/**
 * Pre-resolved string resources of the data-locked recovery surface, bundled
 * so [toViewState] stays a pure mapping function testable without Compose.
 *
 * @property title headline of the recovery surface.
 * @property body plain-language explanation paragraph.
 * @property resetLabel label of the destructive reset button.
 * @property dialogTitle reset dialog headline.
 * @property dialogBody reset dialog warning text (keyword already substituted).
 * @property dialogHint typed-confirm field placeholder (keyword substituted).
 * @property dialogConfirm label of the dialog's destructive confirm button.
 * @property dialogCancel label of the dialog's dismiss button.
 * @property keyword token the user must type to arm the confirm button.
 */
internal data class DataLockedTexts(
    val title: String,
    val body: String,
    val resetLabel: String,
    val dialogTitle: String,
    val dialogBody: String,
    val dialogHint: String,
    val dialogConfirm: String,
    val dialogCancel: String,
    val keyword: String,
)

/**
 * Map the cold-start [SplashUiState] onto the catalog
 * [SplashViewState] used by `SplashContent`.
 *
 * @param defaultMessage placeholder text shown while the use case has not
 * yet emitted a stage.
 * @param stageText names a stage in the interface language.
 * @param dataLockedTexts pre-resolved strings for the data-locked surface.
 */
internal fun SplashUiState.toViewState(
    defaultMessage: String,
    stageText: (InitStage) -> String,
    dataLockedTexts: DataLockedTexts,
): SplashViewState = when {
    isResetting -> SplashViewState.Loading(message = defaultMessage, progress = 0f)
    isDataLocked -> SplashViewState.DataLocked(
        title = dataLockedTexts.title,
        body = dataLockedTexts.body,
        resetLabel = dataLockedTexts.resetLabel,
        resetDialog = if (showResetDialog) {
            SplashResetDialogState(
                title = dataLockedTexts.dialogTitle,
                body = dataLockedTexts.dialogBody,
                keyword = dataLockedTexts.keyword,
                hint = dataLockedTexts.dialogHint,
                pendingInput = resetTypedInput,
                confirmLabel = dataLockedTexts.dialogConfirm,
                cancelLabel = dataLockedTexts.dialogCancel,
            )
        } else {
            null
        },
    )
    errorMessage != null -> SplashViewState.Error(message = errorMessage)
    stage == null && progressFraction == 0f -> SplashViewState.Initializing
    else -> {
        SplashViewState.Loading(
            message = stage?.let(stageText) ?: defaultMessage,
            progress = progressFraction.coerceIn(minimumValue = 0f, maximumValue = 1f),
        )
    }
}

/**
 * The words under the progress bar for each step of the cold start.
 *
 * @param stage The step in flight. A failed run shows its error instead, so
 *   [InitStage.Failed] reads as the stage it stopped at.
 * @return The string resource naming the step.
 */
@StringRes
internal fun stageLabel(stage: InitStage): Int = when (stage) {
    InitStage.Initializing -> R.string.splash_stage_preparing
    InitStage.FindingModels -> R.string.splash_stage_models
    InitStage.LoadingPipelines -> R.string.splash_stage_pipelines
    InitStage.LoadingChats -> R.string.splash_stage_chats
    InitStage.LoadingMemory -> R.string.splash_stage_memory
    InitStage.Done -> R.string.splash_stage_ready
    is InitStage.Failed -> stageLabel(stage.failedStage)
}

/** How long the finished mark stays on screen before the home replaces it. */
private const val SPLASH_COMPLETE_DWELL_MS = 350L
