"""进程入口层（ADR-0001）。

`apps/` 是部署进程的可执行入口（API / worker / 工具脚本），只允许**编排** `bfgi/` 中的
业务模块，不承载业务逻辑本身。本包不参与 wheel 发布（pyproject 只发布 `bfgi`），
测试与运行时的导入由 pytest `pythonpath` / 启动目录提供。
"""
