# 09｜云主机部署蓝图（设计阶段，非现成部署脚本）

## 推荐资源
- MVP 验证目标：2 vCPU / 2 GiB RAM / 25+ GiB SSD / Ubuntu 24.04 LTS / Docker Engine + Compose v2。2C2G 是待压测目标，不保证全市场高频计算与前端构建都可运行。
- 更稳妥：4 vCPU / 4–8 GiB RAM，尤其 Web build、PostgreSQL、全市场扫描和回测同机。
- 生产主机不承载模型推理；LLM 摘要可选远端服务，失败时退化为确定性报告。核心扫描不依赖 GPU。
- 大规模历史回测放低优先级，限制并发，避免耗尽 VPS 资源。

## 计划 Docker 服务
| 服务 | 用途 | 暴露端口 |
|---|---|---|
| reverse-proxy (Caddy/Nginx) | HTTPS 唯一公网入口 | 443 |
| api | FastAPI | 内部 8000 |
| worker | APScheduler + 单例任务锁 | 无 |
| web | React/Next.js | 内部 3000 |
| database | SQLite volume，后续可迁移 PostgreSQL | 不公开 |
| redis | 暂不部署，负载增加再评估 | 不公开 |

本任务书不伪造 docker-compose.yml；Compose、迁移、volume 权限、日志轮转和探活必须在实现阶段编写并测试。

## 环境变量建议
APP_ENV=production；APP_TZ=UTC；BINANCE_FUTURES_API_BASE=https://fapi.binance.com；MARKET_SCAN_INTERVAL_MINUTES=15；MAX_CONCURRENT_MARKET_REQUESTS=4；MAX_MARKET_SYMBOLS_DEEP=100；MAX_DERIVATIVES_SYMBOLS=30；FUTURES_ONLY_READ_ONLY=true；DEFAULT_PLAN_VALID_MINUTES=240；DATABASE_URL=sqlite:////data/market.db；APP_PUBLIC_URL=https://YOUR-DOMAIN。AUTH_SECRET 与通知 token 只放服务器 secret store。

## 实施部署流程
1. 选择允许使用相关市场数据的部署地区，检查连通性与服务条款。
2. 更新 Ubuntu，创建非 root 用户，配置 SSH Key/UFW，安装 Docker Engine 与 Compose v2。
3. 配置 DNS/TLS、强制 HTTPS、安全头与访问认证。
4. Clone 独立仓库，在服务器生成 .env，运行 docker compose config。
5. 执行 DB migration，启动 api/worker/web，等待健康检查；首次保持 READ_ONLY=true。
6. 烟雾测试 exchangeInfo、BTC/ETH K 线、ticker、OI、funding、时间戳和限流退避。
7. Dry Run 全市场扫描，验证 NO_TRADE、信号降级、日志脱敏。
8. 配置备份、告警、资源监控和日志轮转；演练断网、重启、容器恢复。
9. 发布记录 Git commit SHA 与镜像 digest，保留上一个版本用于回滚。

## 上线验收与回滚
公网仅 443/授权 SSH，DB 不公开；Worker 停止或数据过期时 UI 不得把旧值显示为实时。必须完成真实数据库备份/恢复演练。升级失败先停新 Worker，确认 migration 可回退后再回滚 DB，镜像切回上一个 SHA。

## 后续部署输入
云主机 CPU/RAM/磁盘、Ubuntu 版本、部署地区、域名/TLS、访问范围、通知渠道，以及服务器能否合规访问 Binance 公共行情。暂不需要 API Key 或 SSH 密码。