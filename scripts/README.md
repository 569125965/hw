# 启停脚本

## Windows（你截图里的环境）

不要直接敲 `start.ps1`（PowerShell 默认不从当前目录加载，且常被 ExecutionPolicy 拦截）。

在仓库根目录或 `scripts` 目录执行：

```bat
scripts\start.cmd -Demo
scripts\stop.cmd
```

等价：

```powershell
cd scripts
.\start.cmd -Demo
```

若坚持用 `.ps1`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Demo
```

前置：已安装 Python 3.11+、Node.js 18+，并在 PATH 中。

## Linux / macOS

```bash
./scripts/start.sh --demo
./scripts/stop.sh
```

## 启动后

- Web: http://127.0.0.1:5173
- API: http://127.0.0.1:8000/docs
- Android 模拟器连 API：`http://10.0.2.2:8000`
- 真机：见 `android/README.md`
