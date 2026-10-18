package com.asharelab.app.ui.search

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.asharelab.app.data.ApiClient
import com.asharelab.app.data.StockHit
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SearchUiState(
    val query: String = "",
    val hits: List<StockHit> = emptyList(),
    val error: String? = null,
    val loading: Boolean = false
)

class SearchViewModel : ViewModel() {
    private val _state = MutableStateFlow(SearchUiState())
    val state: StateFlow<SearchUiState> = _state.asStateFlow()
    private var job: Job? = null

    fun onQueryChange(q: String) {
        _state.update { it.copy(query = q) }
        search(q)
    }

    fun search(q: String) {
        job?.cancel()
        job = viewModelScope.launch {
            delay(200)
            _state.update { it.copy(loading = true, error = null) }
            runCatching { ApiClient.api.search(q) }
                .onSuccess { res ->
                    _state.update { it.copy(hits = res.items, loading = false) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(
                            loading = false,
                            error = "无法连接服务：${e.message ?: "unknown"}"
                        )
                    }
                }
        }
    }
}
