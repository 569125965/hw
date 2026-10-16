package com.asharelab.app.ui.research

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.asharelab.app.data.ApiClient
import com.asharelab.app.data.Research
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ResearchUiState(
    val loading: Boolean = true,
    val error: String? = null,
    val data: Research? = null,
    val tab: Int = 0
)

class ResearchViewModel(private val code: String) : ViewModel() {
    private val _state = MutableStateFlow(ResearchUiState())
    val state: StateFlow<ResearchUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    fun setTab(index: Int) {
        _state.update { it.copy(tab = index) }
    }

    fun refresh() {
        viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            runCatching { ApiClient.api.research(code) }
                .onSuccess { data ->
                    _state.update { it.copy(loading = false, data = data) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(loading = false, error = e.message ?: "加载失败")
                    }
                }
        }
    }

    class Factory(private val code: String) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ResearchViewModel(code) as T
        }
    }
}
