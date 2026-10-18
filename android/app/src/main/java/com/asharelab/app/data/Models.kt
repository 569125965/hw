package com.asharelab.app.data

data class SearchResponse(val items: List<StockHit> = emptyList())

data class StockHit(
    val code: String,
    val name: String,
    val market: String = ""
)

data class Quote(
    val code: String = "",
    val name: String = "",
    val market: String = "",
    val price: Double = 0.0,
    val change: Double = 0.0,
    val change_pct: Double = 0.0,
    val open: Double = 0.0,
    val high: Double = 0.0,
    val low: Double = 0.0,
    val volume: Long = 0,
    val amount: Double = 0.0,
    val turnover_rate: Double = 0.0,
    val amplitude: Double = 0.0,
    val volume_ratio: Double = 0.0,
    val pe_ttm: Double = 0.0,
    val pb: Double = 0.0,
    val total_mv: Double = 0.0,
    val degraded: Boolean? = null
)

data class KlineItem(
    val date: String = "",
    val open: Double = 0.0,
    val high: Double = 0.0,
    val low: Double = 0.0,
    val close: Double = 0.0,
    val volume: Long = 0,
    val ma5: Double? = null,
    val ma20: Double? = null,
    val macd: Double? = null
)

/**
 * Buy/sell annotation on the K-line chart.
 * Same-cycle buy/sell share [pair_id]; pairing is computed by the backend.
 */
data class Signal(
    val id: String = "",
    /** `short` | `medium` */
    val cycle: String = "short",
    /** `buy` | `sell` */
    val side: String = "buy",
    val pair_id: String = "",
    /** Index into the corresponding kline [KlineItem] list. */
    val index: Int = 0,
    val date: String = "",
    val price: Double = 0.0,
    val label: String = ""
)

data class KlineResponse(
    val code: String = "",
    val period: String = "",
    val items: List<KlineItem> = emptyList(),
    val signals: List<Signal> = emptyList(),
    val degraded: Boolean? = null
)

data class Product(
    val name: String = "",
    val share: Double = 0.0,
    val desc: String = ""
)

data class Peer(
    val code: String = "",
    val name: String = "",
    val change_pct: Double? = null,
    val price: Double? = null
)

data class Fundamental(
    val code: String = "",
    val name: String = "",
    val industry: String = "",
    val concepts: List<String> = emptyList(),
    val products: List<Product> = emptyList(),
    val business_summary: String = "",
    val peers: List<Peer> = emptyList()
)

data class NewsItem(
    val id: String = "",
    val title: String = "",
    val source: String = "",
    val published_at: String = "",
    val summary: String = "",
    val sentiment: String = "neutral"
)

data class NewsResponse(
    val items: List<NewsItem> = emptyList()
)

data class Factor(
    val name: String = "",
    val value: Double = 0.0,
    val impact: String = "neutral"
)

data class Sentiment(
    val score: Double = 50.0,
    val label: String = "中性",
    val summary: String = "",
    val factors: List<Factor> = emptyList()
)

data class PathPoint(
    val days: Int = 0,
    val expected: Double = 0.0,
    val low: Double = 0.0,
    val high: Double = 0.0
)

data class Scenario(
    val name: String = "",
    val probability: Double = 0.0,
    val desc: String = ""
)

data class Forecast(
    val stance: String = "",
    val horizon: String = "",
    val summary: String = "",
    val actions: List<String> = emptyList(),
    val levels: Map<String, Double> = emptyMap(),
    val path: List<PathPoint> = emptyList(),
    val scenarios: List<Scenario> = emptyList(),
    val confidence: Double = 0.0,
    val disclaimer: String = ""
)

data class Research(
    val code: String = "",
    val name: String = "",
    val quote: Quote = Quote(),
    val kline: KlineResponse = KlineResponse(),
    val fundamental: Fundamental = Fundamental(),
    val news: NewsResponse = NewsResponse(),
    val sentiment: Sentiment = Sentiment(),
    val forecast: Forecast = Forecast(),
    val degraded: Boolean? = null
)
