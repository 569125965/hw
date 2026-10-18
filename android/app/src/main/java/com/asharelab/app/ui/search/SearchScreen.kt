package com.asharelab.app.ui.search

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asharelab.app.ui.theme.Amber
import com.asharelab.app.ui.theme.Bg0
import com.asharelab.app.ui.theme.Bg1
import com.asharelab.app.ui.theme.Ink
import com.asharelab.app.ui.theme.Muted

@Composable
fun SearchScreen(
    onOpen: (String) -> Unit,
    vm: SearchViewModel = viewModel()
) {
    val state by vm.state.collectAsState()
    val rise = remember { Animatable(18f) }
    val alpha = remember { Animatable(0f) }

    LaunchedEffect(Unit) {
        rise.animateTo(0f, tween(800))
        alpha.animateTo(1f, tween(800))
        vm.search("")
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(Color(0xFF122A33), Bg1, Bg0)
                )
            )
            .padding(20.dp)
    ) {
        Column(
            modifier = Modifier
                .align(Alignment.Center)
                .fillMaxWidth()
                .padding(bottom = 48.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = rise.value.dp)
            ) {
                Text(
                    text = "研盘",
                    style = androidx.compose.material3.MaterialTheme.typography.displayLarge.copy(
                        color = Ink.copy(alpha = alpha.value.coerceIn(0f, 1f))
                    )
                )
                Text(
                    text = "AShare Lab",
                    style = androidx.compose.material3.MaterialTheme.typography.titleLarge.copy(color = Amber)
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "原生 Android 研究台：盘面、产品、行业、消息、情绪与操作思路。",
                    color = Muted
                )
            }

            OutlinedTextField(
                value = state.query,
                onValueChange = vm::onQueryChange,
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("代码 / 名称，如 600519") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = {
                        val code = state.query.ifBlank { state.hits.firstOrNull()?.code }
                        if (!code.isNullOrBlank()) onOpen(code)
                    }
                ),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Amber,
                    unfocusedBorderColor = Muted,
                    focusedTextColor = Ink,
                    unfocusedTextColor = Ink,
                    cursorColor = Amber
                )
            )

            Button(
                onClick = {
                    val code = state.query.ifBlank { state.hits.firstOrNull()?.code }
                    if (!code.isNullOrBlank()) onOpen(code)
                },
                colors = ButtonDefaults.buttonColors(containerColor = Amber, contentColor = Color(0xFF1A1205)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("开始研究")
            }

            if (state.error != null) {
                Text(text = state.error ?: "", color = Amber)
            }

            LazyColumn {
                items(state.hits) { hit ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onOpen(hit.code) }
                            .padding(vertical = 12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(hit.name, color = Ink)
                        Text("${hit.market}.${hit.code}", color = Muted)
                    }
                }
            }
        }
    }
}
