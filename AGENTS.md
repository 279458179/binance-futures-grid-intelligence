# Agent/AI 开发执行合同

1. 开始任何实现前读取 README、docs/01-PRD.md、planning/BACKLOG.md、planning/ACCEPTANCE.md 和对应模块文档。将所有任务映射到唯一 SYS/DATA/IND/STR/SIG/GRID/BT/API/WEB/OPS/DEP/RND ID。
2. 一次 PR 处理一个合理的依赖闭包；先冻结行为与测试，再编码。不得先写完所有功能再补测试。
3. 与已存在三套 skills 对齐：`binance-futures-direction-scout` 方向评分、`binance-grid-decision` 风控、`binance-futures-grid-scout` 编排。冲突按更严格的风险边界解释并在 ADR 留痕。
4. 行情数据、指标和网格参数均由确定性代码与明确数据输入生成。LLM 文本解释不能修改信号或绕过 NO_TRADE。
5. 数据缺口、时间过期、费率未知、资金未知、交易所规则未知，必须降级；**禁止 fabricated price / exact liquidation / win probability / backtest**。
6. 不准执行交易、转账、撤单、配置杠杆或交易 API Key。任何新增账户/交易权限都是架构改变，需要单独书面审批与独立隔离流程。
7. 所有 indicator/swing/pivot/entry 必须基于当时已完成且可获取的 K 线。回放与实时产生相同输出；所有时间 UTC。
8. 保持 secrets 不进入 Git；所有修改通过 tests/CI；如果工具不可用如实标记 NOT_VERIFIED，不得假报成功。
9. 实现失败按“复现→定位→最小修复→失败用例→全量回归→审查 diff”处理。不得无缘由替换整套架构或新增昂贵依赖。
10. 每次合并填写：Task ID、改变的 API/策略、测试、风险、迁移/回滚、已知缺口。遇到需求冲突先更新任务书和验收标准。
11. 兼容目标 Ubuntu 24.04；优先普通 CPU 运行，云部署不能依赖 GPU、LLM 或 8GB 以上内存才能做核心扫描。
12. 发布时必须有可复核的 commit SHA、镜像 digest、配置样例、诊断/备份/恢复与回滚证据。