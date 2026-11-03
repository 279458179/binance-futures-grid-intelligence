# ADR-0001｜单一可安装 Python 包 `bfgi` + apps 目录的 monorepo

状态：Accepted
日期：2026-11-03
关联任务：SYS-001、SYS-002

## 背景

`docs/02-ARCHITECTURE.md` §4 给出的目录布局是 `apps/{api,web,worker}` + `packages/{market_data,indicators,structure,scoring,grid_planner,risk,backtest,persistence,reporting}`。字面实现意味着 9 个独立 Python 包 + 2 个应用包：需要 11 份 `pyproject.toml`、path-dependency 或 workspace 工具（uv workspace / hatch）来打通，CI 要按包矩阵跑，本地 `pip install -e` 步骤多、Windows 上易出错。而本项目是单人维护、单一部署单元（worker + api 共用同一套领域内核），包与包之间不存在独立版本、独立发布、独立复用需求。

## 决策

- Python 侧只发布**一个可安装包** `bfgi`（binance-futures-grid-intelligence），docs/02 §4 的每个 `packages/*` 对应 `bfgi/<name>` 子包，模块边界与依赖方向按 §4 冻结，靠**导入约束测试**保证，而不是靠物理分包。
  - `bfgi/core`：DTO/契约、错误码、时间、Decimal、版本、配置
  - `bfgi/market_data`、`bfgi/indicators`、`bfgi/structure`、`bfgi/scoring`、`bfgi/grid_planner`、`bfgi/risk`、`bfgi/backtest`、`bfgi/persistence`、`bfgi/reporting`
- 应用进程放在 `apps/`：`apps/api`（FastAPI）、`apps/worker`（调度）、`apps/web`（前端，独立 npm 工程，不参与 Python 包）。
- 依赖方向由测试强制：`indicators/structure/scoring/grid_planner/risk/backtest` 不得导入 `market_data` 的网络层与 `persistence`；只有 `apps/*` 与 `bfgi/reporting` 可以组合它们。CI 用导入检查（AST 扫描）而不是口头约定。
- 单 `pyproject.toml` + `uv.lock` 锁定依赖；`uv run` 是本地一键入口。

## 后果

- 正面：安装/CI/类型检查一次覆盖全部内核；内核保持纯净（无 I/O、无网络、无 DB），回测与实时共用同一份代码（BT-002 实时与回放输出一致的前提）；无 workspace 工具链复杂度。
- 负面：将来若要把某个内核单独发布（例如 indicators 库）需要重新分包。缓解：子包边界即未来包边界，移动目录不改变导入名以外的东西。
- 被否决的备选：(a) 字面 9 包 monorepo——多份 pyproject、path 依赖、CI 矩阵翻倍，收益（独立版本）本项目不需要；(b) 无 `packages/` 概念的大平铺——违反 docs/02 §4，且无法表达依赖方向。

## 关联

- BACKLOG：SYS-001（仓库骨架）、SYS-002（包结构 + 依赖锁定 + 本地一键安装）
- ACCEPTANCE：本地一键安装成功；CI 全绿
- 被否决的备选：9 个独立 Python 包 / 完全平铺
