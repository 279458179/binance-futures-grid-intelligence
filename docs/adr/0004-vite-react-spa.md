# ADR-0004｜前端用 Vite + React + TS 静态 SPA，不用 Next.js

状态：Accepted
日期：2026-11-03
关联任务：WEB-001..WEB-005、DEP-001

## 背景

docs/02 §2 主选 Next.js/React+TS+Tailwind，并把 Vite React SPA 列为扩展选项；docs/09 明确警告 Next.js 在 2C2G VPS 上的构建内存代价。本项目前端的全部页面（Dashboard / Screener / Symbol Detail / Grid Planner / Backtest Lab / Alerts+Settings）都只读取自家 FastAPI JSON（docs/07），没有 SEO、没有服务端渲染需求、没有 ISR。Grid Planner 页面按 docs/07 明确"只读、不下单"。

## 决策

- `apps/web` 是 Vite + React + TypeScript SPA，构建产物是静态文件，由 Caddy 直接托管（docs/09 只暴露 443）。
- API 与前端同源部署（`APP_PUBLIC_URL`），前端通过 `/api/v1/*` 访问；CORS 保持同源默认关闭，跨域需显式配置。
- 图表沿用 docs/02 指定的 `lightweight-charts`。
- 前端不实现任何下单/撤单入口（WEB 页面不得出现下单按钮，docs/07）。

## 后果

- 正面：构建在 2GB 机器上可完成，无需 Node 常驻进程；部署只是静态文件 + Caddy 配置；CI 只做 `typecheck` + `build`。
- 负面：无 SSR/SEO。本项目是登录后的私有决策面板，不需要。
- 被否决的备选：Next.js（SSR 常驻进程 + 构建内存，docs/09 已警告，且没有 SSR 收益）。

## 参考判断（jev，模型判断，非已验证事实）

`mcp__jev_judgment__judge`（jev-1.14.0）：`vite_spa_static` 1.00 / `nextjs_ssr` 0.00。

## 关联

- BACKLOG：WEB-001（骨架与路由）、DEP-001（web 构建产物上线）
- 被否决的备选：Next.js SSR
