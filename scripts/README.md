# 启停脚本

## Windows（你截图里的环境）

不要直接敲 `start.ps1`（PowerShell 默认不从当前目录加载，且常被 ExecutionPolicy 拦截）。

在仓库根目录或 `scripts` 目录执行：

**默认实盘数据**（东方财富行情/公告/基本面）。只有加 `-Demo` / `--demo` 才用演示数据。

```bat
scripts\start.cmd
scripts\stop.cmd

REM 无外网/调试时才用演示：
scripts\start.cmd -Demo
```

若坚持用 `.ps1`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

前置：已安装 Python 3.11+、Node.js 18+，并在 PATH 中。

## Linux / macOS

```bash
./scripts/start.sh          # 实盘
./scripts/start.sh --demo   # 演示
./scripts/stop.sh
```

## 启动后

- Web: http://127.0.0.1:5173
- API: http://127.0.0.1:8000/docs
- Android 模拟器连 API：`http://10.0.2.2:8000`
- 真机：见 `android/README.md`
