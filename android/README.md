# 研盘 Android（原生）

本客户端为 **Kotlin + Jetpack Compose 原生 UI**，图表使用 **MPAndroidChart**（`AndroidView` 嵌入），**不使用 WebView 承载主界面**。

## 模块

| 页面 | 实现 |
|------|------|
| 搜索页 | Compose 原生布局 + 品牌动效 |
| 研究页 | 原生报价条、Tab、列表、情绪环 |
| K线 | MPAndroidChart CombinedChart（蜡烛 + MA20） |
| 网络 | Retrofit + Moshi → FastAPI |

## 本地调试

1. 先启动后端：`./scripts/start.sh --demo`
2. Android Studio 打开 `android/` 目录
3. 模拟器默认 API：`http://10.0.2.2:8000`（见 `BuildConfig.API_BASE_URL`）
4. 真机请改为电脑局域网 IP，例如 `http://192.168.1.8:8000`

```bash
# 有 Android SDK 时
cd android
./gradlew :app:assembleDebug
```

## 模拟用户测试

无模拟器环境时运行仓库脚本（API 契约 + 导航路径校验）：

```bash
./scripts/test-android-sim.sh
```

有模拟器时建议手工路径：启动 → 搜索「茅台」→ 进入研究 → 切换 Tab → 查看结论。
