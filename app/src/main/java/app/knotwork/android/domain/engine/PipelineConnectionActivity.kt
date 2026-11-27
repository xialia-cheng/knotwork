package app.knotwork.android.domain.engine

import app.knotwork.android.domain.models.PipelineGraph
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

/** Transient traversals from the engine to the open pipeline canvas. */
@Singleton
class PipelineConnectionActivity @Inject constructor() {
    private data class Traversal(val pipelineId: String, val graphHash: String, val connectionId: String)

    // The canvas needs the latest transition, without slowing down the run or replaying old work.
    private val traversals = MutableSharedFlow<Traversal>(
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    /** Observes live edges for the matching pipeline and execution graph. */
    fun observe(graph: PipelineGraph): Flow<String> {
        val hash by lazy(graph::contentHash)
        return traversals.filter { it.pipelineId == graph.id && it.graphHash == hash }.map { it.connectionId }
    }

    /** Binds a publisher to the graph passed to this invocation. */
    internal fun publisher(graph: PipelineGraph): (String) -> Unit {
        val hash by lazy(graph::contentHash)
        return { connectionId ->
            if (traversals.subscriptionCount.value > 0) {
                traversals.tryEmit(Traversal(graph.id, hash, connectionId))
            }
        }
    }
}
