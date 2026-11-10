package cc.novelia.app.data.network

import coil3.intercept.Interceptor
import coil3.request.ErrorResult
import coil3.request.ImageResult
import java.io.IOException

internal fun isRemoteImage(data: Any?) = data.toString().let { it.startsWith("https://") || it.startsWith("http://") }

/** Coil consumes the entire image before publishing it, so replacing a failed read is safe. */
internal class NetworkImageRecovery(private val connections: NetworkConnections) : Interceptor {
    override suspend fun intercept(chain: Interceptor.Chain): ImageResult {
        if (!isRemoteImage(chain.request.data)) return chain.proceed()
        return try {
            withRequestBudget(20_000) {
                recoverRead(connections) {
                    chain.proceed().also { result ->
                        if (result is ErrorResult && result.throwable.isRecoverableNetworkFailure()) throw result.throwable
                    }
                }
            }
        } catch (error: IOException) { ErrorResult(null, chain.request, error) }
    }
}
