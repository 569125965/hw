# 研盘 Android（原生）

**Kotlin + Jetpack Compose 原生 UI**，图表 **MPAndroidChart**（`AndroidView`），**不用 WebView 做主界面**。

## 用 Android Studio 一键跑（推荐）

你本机有 SDK / Studio 时按这个来：

1. **先起后端**（Windows）：
   ```bat
   scripts\start.cmd -Demo
   ```
   确认浏览器能打开 http://127.0.0.1:8000/docs

2. **用 Android Studio 打开仓库里的 `android/` 目录**（不是仓库根目录）。

3. 等待 Gradle Sync 完成（首次会下载依赖）。

4. 选模拟器或真机，点 **Run ▶** 运行 `app`。

### API 地址

| 场景 | 地址 |
|------|------|
| 模拟器 | 默认 `http://10.0.2.2:8000`（指向电脑本机） |
| 真机同一 WiFi | 复制 `local.properties.example` → `local.properties`，加一行：`ashare.api.baseUrl=http://192.168.x.x:8000`（电脑局域网 IP） |
| 正式环境 | Release 里改域名，或后续接部署域名 |

> 手机与电脑需能互通；Windows 防火墙放行 8000 端口。

### 命令行打包（可选）

Studio 打开过一次生成 wrapper 后，或已有 wrapper 时：

```bat
cd android
gradlew.bat :app:assembleDebug
```

APK：`android/app/build/outputs/apk/debug/app-debug.apk`

## 模块

| 页面 | 实现 |
|------|------|
| 搜索 | Compose `SearchScreen` |
| 研究 | Compose `ResearchScreen` + Tab |
| K线买卖点 | MPAndroidChart Scatter（短▲▼ / 中○■） |
| 网络 | Retrofit → FastAPI |

## 无 Studio 时的契约检查

```bash
./scripts/test-android-sim.sh
```
