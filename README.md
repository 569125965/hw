# 研盘 AShare Lab

A 股个股研究系统：**Web + 原生 Android**，聚合盘面 / 产品 / 行业 / 消息 / 情绪，在 K 线上标注**短/中期成对买卖点**，并输出操作思路与走势预测。

买卖点规则见 [docs/07-TRADE-SIGNALS.md](docs/07-TRADE-SIGNALS.md)。

> 输出仅供研究学习，不构成投资建议。

## 文档（文档驱动）

| 文档 | 内容 |
|------|------|
| [docs/01-PRD.md](docs/01-PRD.md) | 产品需求 |
| [docs/02-ARCHITECTURE.md](docs/02-ARCHITECTURE.md) | 架构与 API |
| [docs/03-UI-BENCHMARK.md](docs/03-UI-BENCHMARK.md) | 对标东财/同花顺/TV |
| [docs/04-DEPLOYMENT.md](docs/04-DEPLOYMENT.md) | 国内低成本云部署 |
| [docs/05-ITERATION-PLAN.md](docs/05-ITERATION-PLAN.md) | 迭代清单 |

## 目录

```
backend/   FastAPI 分析服务（akshare + 演示降级）
web/       Vite React 研究台（ECharts）
android/   原生 Kotlin Compose 客户端（MPAndroidChart，非 WebView）
deploy/    一键 Docker 部署/停止
scripts/   本地一键启停与测试
docs/      产品与技术文档
```

## 一键本地启动 / 停止

```bash
./scripts/start.sh --demo   # 演示数据，适合无外网行情环境
./scripts/stop.sh
```

- Web: http://127.0.0.1:5173
- API: http://127.0.0.1:8000/docs

## 一键云部署（国内轻量云）

```bash
./deploy/one-click-deploy.sh   # Web :8080  API :8000
./deploy/one-click-stop.sh
```

详见 [docs/04-DEPLOYMENT.md](docs/04-DEPLOYMENT.md)。

## Android（原生）

见 [android/README.md](android/README.md)。UI 为 Jetpack Compose + 原生图表，不使用 WebView 作为主界面。

## 测试

```bash
./scripts/test-api.sh
./scripts/start.sh --demo
./scripts/test-web-sim.sh
./scripts/test-android-sim.sh
```
