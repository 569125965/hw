package com.asharelab.app.ui.chart

import android.graphics.Canvas
import android.graphics.Color as AndroidColor
import android.graphics.Paint
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.asharelab.app.data.KlineItem
import com.asharelab.app.data.Signal
import com.github.mikephil.charting.charts.CombinedChart
import com.github.mikephil.charting.charts.ScatterChart
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.CandleData
import com.github.mikephil.charting.data.CandleDataSet
import com.github.mikephil.charting.data.CandleEntry
import com.github.mikephil.charting.data.CombinedData
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.data.ScatterData
import com.github.mikephil.charting.data.ScatterDataSet
import com.github.mikephil.charting.interfaces.datasets.IScatterDataSet
import com.github.mikephil.charting.renderer.scatter.IShapeRenderer
import com.github.mikephil.charting.utils.ViewPortHandler

private const val COLOR_SHORT = "#E8A838"
private const val COLOR_MEDIUM = "#26A69A"

/**
 * Native MPAndroidChart candle view embedded in Compose — not a WebView.
 * Short/medium buy-sell markers use ScatterData with distinct shapes.
 */
@Composable
fun CandleChart(
    items: List<KlineItem>,
    signals: List<Signal> = emptyList(),
    modifier: Modifier = Modifier
) {
    AndroidView(
        modifier = modifier
            .fillMaxWidth()
            .height(320.dp),
        factory = { context ->
            CombinedChart(context).apply {
                description.isEnabled = false
                legend.isEnabled = false
                setBackgroundColor(AndroidColor.parseColor("#071318"))
                setDrawGridBackground(false)
                axisRight.isEnabled = false
                axisLeft.textColor = AndroidColor.parseColor("#8AA3AD")
                axisLeft.gridColor = AndroidColor.parseColor("#22343C")
                xAxis.position = XAxis.XAxisPosition.BOTTOM
                xAxis.textColor = AndroidColor.parseColor("#8AA3AD")
                xAxis.gridColor = AndroidColor.parseColor("#22343C")
                xAxis.setDrawLabels(false)
                setScaleEnabled(true)
                isDragEnabled = true
                // Draw scatter markers above candles / MA lines.
                drawOrder = arrayOf(
                    CombinedChart.DrawOrder.CANDLE,
                    CombinedChart.DrawOrder.LINE,
                    CombinedChart.DrawOrder.SCATTER
                )
            }
        },
        update = { chart ->
            if (items.isEmpty()) return@AndroidView
            val candles = items.mapIndexed { idx, k ->
                CandleEntry(
                    idx.toFloat(),
                    k.high.toFloat(),
                    k.low.toFloat(),
                    k.open.toFloat(),
                    k.close.toFloat()
                )
            }
            val candleSet = CandleDataSet(candles, "K线").apply {
                shadowColorSameAsCandle = true
                shadowWidth = 0.8f
                decreasingColor = AndroidColor.parseColor("#26A69A")
                decreasingPaintStyle = Paint.Style.FILL
                increasingColor = AndroidColor.parseColor("#E53935")
                increasingPaintStyle = Paint.Style.FILL
                neutralColor = AndroidColor.parseColor("#8AA3AD")
                setDrawValues(false)
            }

            val maEntries = items.mapIndexedNotNull { idx, k ->
                k.ma20?.let { Entry(idx.toFloat(), it.toFloat()) }
            }
            val maSet = LineDataSet(maEntries, "MA20").apply {
                color = AndroidColor.parseColor(COLOR_SHORT)
                setDrawCircles(false)
                lineWidth = 1.4f
                setDrawValues(false)
            }

            val scatterSets = buildSignalScatterSets(signals, items.size)

            chart.data = CombinedData().apply {
                setData(CandleData(candleSet))
                setData(LineData(maSet))
                if (scatterSets.isNotEmpty()) {
                    setData(ScatterData(scatterSets))
                }
            }
            chart.invalidate()
        }
    )
}

/**
 * Four scatter layers: short▲ / short▼ / medium○ / medium■.
 * Colors: short #E8A838, medium #26A69A.
 */
private fun buildSignalScatterSets(
    signals: List<Signal>,
    barCount: Int
): List<IScatterDataSet> {
    if (signals.isEmpty() || barCount <= 0) return emptyList()

    fun entriesFor(cycle: String, side: String): List<Entry> =
        signals.filter { it.cycle == cycle && it.side == side }
            .filter { it.index in 0 until barCount }
            .map { Entry(it.index.toFloat(), it.price.toFloat()) }

    val sets = mutableListOf<IScatterDataSet>()

    fun addSet(
        label: String,
        entries: List<Entry>,
        colorHex: String,
        shape: ScatterChart.ScatterShape? = null,
        customRenderer: IShapeRenderer? = null,
        hollow: Boolean = false
    ) {
        if (entries.isEmpty()) return
        sets += ScatterDataSet(entries, label).apply {
            color = AndroidColor.parseColor(colorHex)
            when {
                customRenderer != null -> setShapeRenderer(customRenderer)
                shape != null -> setScatterShape(shape)
            }
            scatterShapeSize = 14f
            setDrawValues(false)
            if (hollow) {
                // Hollow ○ / ■ for medium cycle
                setScatterShapeHoleColor(AndroidColor.parseColor("#071318"))
                scatterShapeHoleRadius = 3.5f
            }
        }
    }

    // Short: amber — buy ▲, sell ▼
    addSet("短买", entriesFor("short", "buy"), COLOR_SHORT, shape = ScatterChart.ScatterShape.TRIANGLE)
    addSet("短卖", entriesFor("short", "sell"), COLOR_SHORT, customRenderer = DownTriangleShapeRenderer())
    // Medium: teal — buy ○, sell ■
    addSet(
        "中买",
        entriesFor("medium", "buy"),
        COLOR_MEDIUM,
        shape = ScatterChart.ScatterShape.CIRCLE,
        hollow = true
    )
    addSet(
        "中卖",
        entriesFor("medium", "sell"),
        COLOR_MEDIUM,
        shape = ScatterChart.ScatterShape.SQUARE,
        hollow = true
    )

    return sets
}

/** Filled downward triangle (▼) for short-term sell markers. */
private class DownTriangleShapeRenderer : IShapeRenderer {
    override fun renderShape(
        c: Canvas,
        dataSet: IScatterDataSet,
        viewPortHandler: ViewPortHandler,
        posX: Float,
        posY: Float,
        renderPaint: Paint
    ) {
        val shapeHalf = dataSet.scatterShapeSize / 2f
        renderPaint.style = Paint.Style.FILL
        val path = android.graphics.Path().apply {
            moveTo(posX, posY + shapeHalf)
            lineTo(posX + shapeHalf, posY - shapeHalf)
            lineTo(posX - shapeHalf, posY - shapeHalf)
            close()
        }
        c.drawPath(path, renderPaint)
    }
}
