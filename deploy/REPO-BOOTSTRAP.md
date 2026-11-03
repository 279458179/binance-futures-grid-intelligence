# 将本任务书上传为独立 GitHub 仓库

推荐私有仓库：`279458179/binance-futures-grid-intelligence`。仓库必须先在 GitHub 建立为空仓库，**不要选 Initialize with README**（任务书已有 README）。

## Web 操作

1. 登录 GitHub：右上角 `+` → New repository。
2. Owner 选择 `279458179`，Repository name 填 `binance-futures-grid-intelligence`。
3. Visibility 选 **Private**，不要预创建 README/.gitignore/license。
4. 点击 Create repository。
5. 在本任务书目录执行以下命令；如已有 GitHub SSH 凭据，使用 SSH remote，避免在命令行写 token。

## Linux/macOS/Windows Git Bash 上传

    cd binance-futures-grid-system
    git init -b main
    git add .
    git commit -m "docs: initialize futures grid intelligence specifications"
    git remote add origin git@github.com:279458179/binance-futures-grid-intelligence.git
    git push -u origin main

如果 SSH 未配置，使用 GitHub 官方 HTTPS + Credential Manager / 已登录 git credential helper；**不要把 Personal Access Token 粘贴到脚本或终端命令参数里**。

## 上传后

- 用 GitHub Issues / Project 看板承接 planning/BACKLOG.md 的唯一任务编号。
- main 分支设置 PR Review、CI 检查等仓库保护规则（权限允许时）。
- 第一个 PR 以 `SYS-002/DATA-001` 为目标，按 AGENTS.md 实施。