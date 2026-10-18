# 实盘数据对接说明

## 默认行为

`ASHARE_DEMO_MODE=0`（默认）：使用真实 A 股数据。

## 数据源

| 能力 | 主源 | 备源 |
|------|------|------|
| 搜索 | 东方财富 suggest API | 演示列表 |
| 报价 | 东财 push2delay ulist | K线推导 |
| K线 | 腾讯 `stock_zh_a_hist_tx` | 东财 push2his / akshare |
| 基本面 | 东财 F10 CompanySurvey / CoreConception | 演示 |
| 消息 | 东财公告 + 资讯搜索 | 演示 |

实盘模式下 **禁止用演示 K 线污染分析**（报价与 K 线价格必须一致量级）。

## 启动

```bat
scripts\start.cmd
```

```bash
./scripts/start.sh
```
