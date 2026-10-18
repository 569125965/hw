package com.asharelab.app.ui.research

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.asharelab.app.data.Research
import com.asharelab.app.ui.chart.CandleChart
import com.asharelab.app.ui.theme.Amber
import com.asharelab.app.ui.theme.Bg0
import com.asharelab.app.ui.theme.Bg1
import com.asharelab.app.ui.theme.Down
import com.asharelab.app.ui.theme.Ink
import com.asharelab.app.ui.theme.Muted
import com.asharelab.app.ui.theme.Up
import java.util.Locale

private val tabs = listOf("盘面", "基本面", "行业", "消息", "情绪", "结论")

@Composable
fun ResearchScreen(
    code: String,
    onBack: () -> Unit,
    onOpenPeer: (String) -> Unit,
    vm: ResearchViewModel = viewModel(factory = ResearchViewModel.Factory(code))
) {
    val state by vm.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Bg1)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextButton(onClick = onBack) {
                Text("← 研盘", color = Amber)
            }
            Text("原生研究页", color = Muted, fontSize = 12.sp)
        }

        when {
            state.loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Amber)
            }
            state.error != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(state.error ?: "", color = Amber)
                    Spacer(Modifier.height(12.dp))
                    Button(onClick = vm::refresh, colors = ButtonDefaults.buttonColors(containerColor = Amber)) {
                        Text("重试", color = Color(0xFF1A1205))
                    }
                }
            }
            state.data != null -> ResearchBody(
                data = state.data!!,
                tab = state.tab,
                onTab = vm::setTab,
                onOpenPeer = onOpenPeer
            )
        }
    }
}

@Composable
private fun ResearchBody(
    data: Research,
    tab: Int,
    onTab: (Int) -> Unit,
    onOpenPeer: (String) -> Unit
) {
    val q = data.quote
    val up = q.change >= 0
    val tone = if (up) Up else Down

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
    ) {
        Text(
            text = data.name + if (data.degraded == true) " · 演示" else "",
            style = MaterialTheme.typography.titleLarge
        )
        Text("${q.market}.${q.code} · ${data.fundamental.industry}", color = Muted)
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                text = String.format(Locale.CHINA, "%.2f", q.price),
                color = tone,
                fontSize = 34.sp,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "${if (up) "▲" else "▼"} ${String.format(Locale.CHINA, "%.2f", q.change)} (${String.format(Locale.CHINA, "%.2f", q.change_pct)}%)",
                color = tone,
                fontWeight = FontWeight.Medium
            )
        }
        Spacer(Modifier.height(10.dp))
        MetricGrid(data)
        Spacer(Modifier.height(8.dp))
        CandleChart(items = data.kline.items, signals = data.kline.signals)
        SignalLegend()
        Spacer(Modifier.height(4.dp))

        ScrollableTabRow(
            selectedTabIndex = tab,
            containerColor = Bg0,
            contentColor = Amber,
            edgePadding = 0.dp
        ) {
            tabs.forEachIndexed { index, title ->
                Tab(
                    selected = tab == index,
                    onClick = { onTab(index) },
                    text = { Text(title) }
                )
            }
        }

        AnimatedContent(
            targetState = tab,
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "tab"
        ) { t ->
            when (t) {
                0 -> Panel("盘面结构", "均线与支撑压力帮助判断位置。") {
                    LevelRow(data)
                }
                1 -> Panel("产品与业务", data.fundamental.business_summary) {
                    TagRow(data.fundamental.concepts)
                    data.fundamental.products.forEach { p ->
                        Text("${p.name} · ${(p.share * 100).toInt()}%", color = Ink, fontWeight = FontWeight.SemiBold)
                        Text(p.desc, color = Muted)
                        Spacer(Modifier.height(8.dp))
                    }
                }
                2 -> Panel("行业与同业", "所属行业：${data.fundamental.industry}") {
                    data.fundamental.peers.forEach { peer ->
                        TextButton(onClick = { onOpenPeer(peer.code) }) {
                            val pct = peer.change_pct ?: 0.0
                            Text(
                                "${peer.name} (${peer.code})  ${if (pct >= 0) "▲" else "▼"} ${String.format(Locale.CHINA, "%.2f", pct)}%",
                                color = if (pct >= 0) Up else Down
                            )
                        }
                    }
                }
                3 -> Panel("消息面", "公告/资讯时间线") {
                    data.news.items.forEach { n ->
                        val c = when (n.sentiment) {
                            "positive" -> Up
                            "negative" -> Down
                            else -> Ink
                        }
                        Text(n.title, color = c, fontWeight = FontWeight.SemiBold)
                        Text("${n.source} · ${n.published_at}", color = Muted, fontSize = 12.sp)
                        Text(n.summary, color = Muted)
                        Spacer(Modifier.height(10.dp))
                    }
                }
                4 -> Panel("市场情绪", data.sentiment.summary) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        Box(
                            modifier = Modifier
                                .size(84.dp)
                                .border(3.dp, Amber, CircleShape)
                                .background(Amber.copy(alpha = 0.12f), CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("${data.sentiment.score.toInt()}", color = Amber, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                        }
                        Text(data.sentiment.label, color = Ink, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Spacer(Modifier.height(12.dp))
                    data.sentiment.factors.forEach { f ->
                        val c = when (f.impact) {
                            "positive" -> Up
                            "negative" -> Down
                            else -> Muted
                        }
                        Text("${f.name}: ${f.value}", color = c)
                    }
                }
                else -> Panel("操作思路与走势预测", data.forecast.summary) {
                    Text(data.forecast.stance, color = Amber, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Text("周期 ${data.forecast.horizon} · 置信 ${(data.forecast.confidence * 100).toInt()}%", color = Muted)
                    Spacer(Modifier.height(8.dp))
                    data.forecast.actions.forEach { Text("• $it", color = Ink) }
                    Spacer(Modifier.height(10.dp))
                    data.forecast.scenarios.forEach {
                        Text("${it.name} (${(it.probability * 100).toInt()}%)", color = Ink, fontWeight = FontWeight.SemiBold)
                        Text(it.desc, color = Muted)
                        Spacer(Modifier.height(6.dp))
                    }
                    LevelRow(data)
                    Spacer(Modifier.height(8.dp))
                    Text(data.forecast.disclaimer, color = Muted, fontSize = 12.sp)
                }
            }
        }
        Spacer(Modifier.height(28.dp))
    }
}

@Composable
private fun SignalLegend() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 6.dp, bottom = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("短期 ▲买 ▼卖", color = Amber, fontSize = 12.sp)
        Text("中期 ○买 ■卖", color = Down, fontSize = 12.sp)
    }
}

@Composable
private fun Panel(title: String, lead: String, content: @Composable () -> Unit) {
    Column(modifier = Modifier.padding(vertical = 14.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(6.dp))
        Text(lead, color = Muted)
        Spacer(Modifier.height(12.dp))
        content()
    }
}

@Composable
private fun TagRow(tags: List<String>) {
    Row(
        modifier = Modifier
            .horizontalScroll(rememberScrollState())
            .padding(bottom = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        tags.forEach { tag ->
            Text(
                text = tag,
                color = Amber,
                modifier = Modifier
                    .border(1.dp, Amber.copy(alpha = 0.45f))
                    .padding(horizontal = 10.dp, vertical = 4.dp)
            )
        }
    }
}

@Composable
private fun MetricGrid(data: Research) {
    val q = data.quote
    val rows = listOf(
        "今开" to String.format(Locale.CHINA, "%.2f", q.open),
        "最高" to String.format(Locale.CHINA, "%.2f", q.high),
        "最低" to String.format(Locale.CHINA, "%.2f", q.low),
        "换手" to String.format(Locale.CHINA, "%.2f%%", q.turnover_rate),
        "量比" to String.format(Locale.CHINA, "%.2f", q.volume_ratio),
        "振幅" to String.format(Locale.CHINA, "%.2f%%", q.amplitude)
    )
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        rows.chunked(3).forEach { chunk ->
            Row(Modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                chunk.forEach { (k, v) ->
                    Column(modifier = Modifier.weight(1f)) {
                        Text(k, color = Muted, fontSize = 12.sp)
                        Text(v, color = Ink, fontWeight = FontWeight.Medium)
                    }
                }
            }
        }
    }
}

@Composable
private fun LevelRow(data: Research) {
    val levels = data.forecast.levels
    val keys = listOf("ma20" to "MA20", "ma60" to "MA60", "support" to "支撑", "resistance" to "压力")
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        keys.forEach { (k, label) ->
            Column {
                Text(label, color = Muted, fontSize = 12.sp)
                Text(String.format(Locale.CHINA, "%.2f", levels[k] ?: 0.0), color = Ink, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}
