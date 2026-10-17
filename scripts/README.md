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

## Linux / macOS（含 /Users/rouser/Documents/dev/hw）

```bash
cd /Users/rouser/Documents/dev/hw   # 换成你的实际路径
chmod +x scripts/*.sh
./scripts/doctor.sh                 # 先检查 Python/Node/端口
./scripts/start.sh                  # 实盘启动
./scripts/stop.sh                   # 停止
```

若 `Permission denied`：`chmod +x scripts/*.sh`  
若缺依赖（macOS）：`brew install python@3.12 node`  
若端口占用：先 `./scripts/stop.sh` 再启动。  
看失败原因：`tail -50 .run/api.log` / `tail -50 .run/web.log`

### 页面提示「无法连接研究服务」

说明 **只开了前端，后端 :8000 没起来**（或旧进程残留）。不要只跑 `npm run dev`，请：

```bash
cd /Users/rouser/Documents/dev/hw
./scripts/stop.sh
./scripts/start.sh
curl http://127.0.0.1:8000/api/v1/health   # 应返回 {"status":"ok"...}
```

终端必须出现 `[ok] API` 和 `[ok] Web`，再刷新浏览器。

## 启动后

- Web: http://127.0.0.1:5173
- API: http://127.0.0.1:8000/docs
- Android 模拟器连 API：`http://10.0.2.2:8000`
- 真机：见 `android/README.md`
