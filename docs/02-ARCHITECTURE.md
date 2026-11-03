# 02｜架构与技术选型

## 1. 设计原则

- 先单体模块化，后按数据/计算量拆分；2C2G VPS 优先轻量和可维护，不因“AI”堆叠微服务。
- 规则/数学计算必须是确定性 Python 代码，LLM 只负责解释结果、生成可读报告，不得绕过硬闸门或伪造价格。
- 后台分析只用 Binance USDⓈ-M 公开行情接口；外部研究数据显式标源、标时区。
- 数据采集、指标计算、信号生成、网格评估、报告输出逐层解耦；每个阶段可以回放和单独测试。

## 2. 建议技术栈（开发阶段锁定后写入依赖版本）

| 组件 | MVP | 扩展选项 | 原因 |
|---|---|---|---|
| Backend | Python 3.12 + FastAPI + Pydantic | 无 | 异步 I/O、自动 OpenAPI、类型约束 |
| 数据源 | httpx asyncio + Binance REST | Binance 公共 WS（运行时） | 读权限、批量抓取；连续监控再加 WS |
| 数值计算 | numpy/pandas（测试固定版本） | TA-Lib 可选 | 指标可单测、版本稳定 |
| 定时执行 | APScheduler 单独 worker | Redis/RQ/Celery 在规模扩大时 | 2C2G 低开销，避免重复调度 |
| 持久化 | SQLite WAL（单机 MVP） | PostgreSQL（并发/扩容） | 小型 VPS 可运维，数据迁移预留接口 |
| 缓存 | 进程内 TTL + 数据库 | Redis（可选） | 全市场避免 API 重复请求 |
| Web | Next.js / React + TypeScript + Tailwind + lightweight-charts | Vite React SPA | 可视化 TradingView 风格，但不嵌入未经授权图表 |
| 回测 | 自研事件/逐根回放最小内核 | Freqtrade/Hummingbot/NautilusTrader 验证 | 网格模拟需专用成交及库存核算 |
| 观测 | structlog/json logging + Prometheus 格式健康指标 | Grafana / Loki | 轻量先行 |
| 部署 | Docker Compose v2 + Caddy/Nginx | K8s 不建议第一期使用 | 简单迁移与回滚 |
| CI | GitHub Actions: lint/typecheck/unit/integration/secret scan | E2E/容器构建 | 防回归、部署前门禁 |

## 3. 模块边界

    Internet / Browser (HTTPS)
              |
        Reverse Proxy + Auth
              |
        Web UI --- FastAPI /api/v1
                        |
          +-------------+---------------------+
          |             |                     |
       Snapshot      Read API              Scheduler
       Store         (Reports)             / Worker
          |                                   |
          |                  +----------------+-----------------+
          |                  |                |                 |
          |               Market          Signal            Grid/Risk
          |               Adapter         Engine            Engine
          |                  |                |                 |
          |                Binance USDⓈ-M public API         |
          +------------------+----------------+-----------------+
                             |
                        SQLite/Postgres
                             |
                  Reports / Backtests / Alerts

## 4. 建议代码目录（待开发）

    apps/
      api/                 # FastAPI routes, dependencies, schemas
      web/                 # dashboard, charts, accessible layouts
      worker/              # scheduler, scan orchestration, alerts
    packages/
      market_data/         # Binance REST/WS, schema, retry, rate-limit
      indicators/          # EMA/MACD/RSI/ADX/ATR/RVOL/CVD proxy
      structure/           # swing, support-resistance, sweep/SFP/MSS
      scoring/             # directional/range score and hard gates
      grid_planner/        # bounds, activation, fees, quantity, TP/SL
      risk/                # portfolio/correlation/shock invalidation
      backtest/            # event-driven replay, fill/inventory/PnL
      persistence/         # storage, migrations, snapshot lineage
      reporting/           # Chinese narrative templates, evidence
    tests/fixtures/        # offline frozen Binance payloads, no secrets
    docs/ deploy/ planning/ contracts/

## 5. 数据与控制流

1. Worker 获取 `exchangeInfo` 和 `ticker/24hr` → `MarketUniverseSnapshot`。
2. BTC/ETH 优先采样，先形成 `BenchmarkState`。
3. 抓取预选合约 4h/1h/15m candles，统一已完成 K 线和时间戳。
4. 计算基础技术指标→粗排，并下载精选 OI、funding、depth、taker 数据。
5. 形成 `MarketEvidence`（原始来源/时间戳/数据覆盖）→ `SignalDecision`（方向评分、闸门、入场状态）。
6. GridEngine 在资金/费用/规则可验证时生成 `GridProposal`，否则 `PARTIAL/WATCH/NO_TRADE`。
7. 写入不可修改的 `DecisionSnapshot`；前端查询历史和当前版本；提醒模块只发送状态跃迁事件。

## 6. 并发与一致性

- REST 全市场请求设置 bounded semaphore，初始最多 3–5 个并发，运行时根据响应限流头调整。禁止跨区域/身份轮换绕限制。
- 使用 `exchange_server_time` 与本地时钟校准；每个数据系列带 provider 结束时间、采集时间和完整性标签。
- 扫描具唯一 `scan_id`、`strategy_version`、`snapshot_at`；同一计划重复写入幂等。
- 部署单 Worker；如未来多副本，必须加分布式锁/租约，避免每 15M 重复生成结果。
- 计算指标不依赖 LLM；自然语言解释可以被停用而不影响正确性。

## 7. 持久化实体

`symbol_metadata`, `ohlcv_candles`, `derivatives_snapshots`, `scan_runs`, `benchmark_snapshots`, `signal_evidence`, `signal_decisions`, `grid_proposals`, `plan_revisions`, `notifications`, `backtest_runs`, `strategy_versions`, `system_audit`, `user_settings`。

所有价格字段使用 Decimal 或字符串序列化；浮点仅做中间指标/统计，不可直接决定 tick/quantity 合规。