"""FastAPI 入口包（ADR-0012）。

导入本包不加载配置、不构造 app、不产生副作用——app 只能通过 `apps.api.app.create_app`
显式构造（`uvicorn --factory`）。
"""
