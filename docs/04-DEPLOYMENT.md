# 国内低成本云部署方案

## 1. 目标

- Web + API 国内访问流畅
- Android 指向同一 API 域名
- **一键打包部署**、**一键启停**
- 尽量省钱（个人/小团队）

## 2. 推荐拓扑（最省成本）

```
用户(Web/Android)
      │
      ▼
┌─────────────────────┐
│ 国内轻量云 2核2G起   │  ← 腾讯云 Lighthouse / 阿里云轻量 / 华为云耀云
│  Nginx :80/:443     │
│  API 容器 :8000     │
│  Web 静态 :80       │
└─────────────────────┘
```

**预估月费（2026 参考）**：轻量 2核2G ≈ ¥24–50/月；备案域名可选。

### 为什么不选「全家桶」

| 方案 | 月费量级 | 结论 |
|------|----------|------|
| 单机 Docker Compose | 低 | **首选** |
| K8s / ACK | 高 | 过度 |
| 前后端分拆多云产品 | 中高 | 流量小时浪费 |
| 纯海外 VPS | 低但慢 | 国内访问差，不推荐 |

## 3. 域名与备案

1. 有备案：绑定域名 + Nginx HTTPS（Let’s Encrypt / 云厂商免费证）。
2. 无备案：先用公网 IP + HTTP（仅自用）；或用云厂商「海外节点 + 国内加速」但体验与合规需自行评估。
3. Android `BuildConfig.API_BASE_URL` 指向 `https://your.domain`。

## 4. 一键本地调试

### Windows

```bat
scripts\start.cmd
scripts\stop.cmd
```

默认实盘。不要直接运行 `start.ps1`（易被 ExecutionPolicy 拦截）；`.cmd` 已带 `-ExecutionPolicy Bypass`。

### Linux / macOS

```bash
./scripts/start.sh          # 实盘启动 API + Web
./scripts/stop.sh           # 停止
./scripts/start.sh --demo   # 仅无外网时强制演示数据
```

## 5. 一键云部署

服务器需：Docker + Docker Compose、开放 80/443。

```bash
# 在服务器项目根目录
./deploy/one-click-deploy.sh
```

脚本完成：构建镜像 → `docker compose up -d` → 健康检查。

停止：

```bash
./deploy/one-click-stop.sh
```

## 6. 国内流畅优化清单

1. **镜像加速**：配置 Docker 国内 registry mirror。
2. **静态资源**：Nginx gzip + 长缓存 hash 文件。
3. **API 缓存**：服务端 TTL，避免频繁打行情源。
4. **Android**：Release 使用正式域名；Debug 可用 `10.0.2.2`（模拟器）或局域网 IP。
5. **可选 CDN**：对象存储 + CDN 仅托管 Web 静态（API 仍回源单机）。

## 7. 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `ASHARE_DEMO_MODE` | `0` | `1` 强制演示数据 |
| `ASHARE_CACHE_TTL` | `300` | 秒 |
| `ASHARE_CORS_ORIGINS` | `*` | 生产改为具体域名 |
| `LLM_API_KEY` | （空） | 本地 `.env`，勿入库；启用 AI 深度研判 |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容地址 |
| `LLM_MODEL` | （空） | 如 `deepseek-chat` |

LLM 配置见 `.env.example` 与 `docs/10-CAPITAL-LLM-MACRO.md`。

## 8. 备份与升级

- 无状态服务，升级即重新 `one-click-deploy.sh`。
- 若启用本地文件缓存目录 `./data`，部署脚本会做 volume 挂载。
