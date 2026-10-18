# 系统架构

## 1. 总览

```
┌─────────────┐  ┌──────────────┐
│  Web (Vite) │  │ Android App  │
└──────┬──────┘  └──────┬───────┘
       │ REST/JSON      │
       └────────┬───────┘
                ▼
        ┌───────────────┐
        │  FastAPI API  │
        │  /api/v1/*    │
        └───────┬───────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  Cache      Analyzer    Data Providers
 (内存/文件)  (技术/情绪)  (东财实盘/腾讯K线/演示降级)
```

## 2. 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| API | Python 3.11 + FastAPI | akshare 生态、异步、类型友好 |
| 分析 | pandas / numpy | 指标计算成熟 |
| Web | Vite + React + TypeScript + ECharts | 图表能力强，对标东财/TV |
| Android | Kotlin + Jetpack Compose + Retrofit | 原生体验、图表用 MPAndroidChart |
| 部署 | Docker Compose + Nginx | 一键、国内云友好 |
| 缓存 | 进程内 TTL + 可选 Redis | 默认零成本，可升级 |

## 3. 模块划分

### 3.1 `backend/app`

- `api/`：HTTP 路由
- `services/market.py`：行情与 K 线
- `services/fundamental.py`：产品/行业
- `services/news.py`：消息面
- `services/sentiment.py`：情绪评分
- `services/forecast.py`：操作思路与走势预测
- `services/research.py`：聚合编排
- `core/cache.py`：TTL 缓存
- `core/demo_data.py`：数据源不可用时的演示数据

### 3.2 API 契约（摘要）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| GET | `/api/v1/stocks/search?q=` | 搜索 |
| GET | `/api/v1/stocks/{code}/quote` | 盘面 |
| GET | `/api/v1/stocks/{code}/kline` | K线+指标+买卖点 signals |
| GET | `/api/v1/stocks/{code}/signals` | 短/中期成对买卖点 |
| GET | `/api/v1/stocks/{code}/fundamental` | 产品/行业 |
| GET | `/api/v1/stocks/{code}/news` | 消息 |
| GET | `/api/v1/stocks/{code}/sentiment` | 情绪 |
| GET | `/api/v1/stocks/{code}/research` | 完整研究报告 |

## 4. 数据流

1. 客户端请求 `research`。
2. 编排层并行拉取 quote / kline / fundamental / news。
3. 情绪与预测基于上述结果计算。
4. 结果写入 TTL 缓存（默认 5 分钟）。
5. 任一分片失败 → 使用演示数据并设置 `degraded: true`。

## 5. 安全

- 只读研究 API，无鉴权（内网/个人部署默认）。
- 生产可在 Nginx 加 Basic Auth / IP 白名单。
- 不存储用户敏感信息。

## 6. 扩展点

- 替换数据源为付费行情商。
- 接入 LLM 生成自然语言研报章节。
- Redis / 对象存储做多实例缓存。
