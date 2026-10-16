# Android 原生客户端说明

## 约束

- **必须原生 UI**：Jetpack Compose 页面 + Material3
- **禁止**用 WebView 承载搜索/研究主流程
- 图表：MPAndroidChart（原生 View），经 `AndroidView` 嵌入 Compose

## 与 Web 的关系

| 能力 | Web | Android |
|------|-----|---------|
| 搜索 | React | Compose `SearchScreen` |
| 研究 Tab | React | Compose `ResearchScreen` |
| K线 | ECharts | MPAndroidChart |
| API | 同一 FastAPI | 同一 FastAPI（Retrofit） |

## 配置 API 地址

`android/app/build.gradle.kts` → `buildConfigField("String", "API_BASE_URL", ...)`

- Debug 模拟器：`http://10.0.2.2:8000`
- 真机调试：改为电脑局域网 IP
- Release：改为国内已部署域名（HTTPS）
