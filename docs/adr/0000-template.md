# ADR-0000｜ADR 模板

状态：Accepted
日期：2026-11-03
关联任务：SYS-001

## 背景

（为什么需要这个决策；触发它的约束、上游文档或参考 skills 冲突。）

## 决策

（本项目采用的方案，一句话结论 + 必要细节。）

## 后果

（正面/负面后果、被排除的方案与排除原因、对测试与验收门禁的影响。）

## 关联

- BACKLOG 任务 ID：
- ACCEPTANCE 门禁 / T-xx：
- 参考 skill 文件：
- 被否决的备选：

---

## 编号规则

- `0001` 起按时间顺序编号，不复用、不重排。
- 状态只允许：`Proposed` / `Accepted` / `Superseded by ADR-xxxx` / `Deprecated`。
- 任何改变业务行为（评分、闸门、网格参数、API 合同、数据合同）的改动，必须先有 ADR 或有对应 PRD/BACKLOG 更新，二者至少其一。
- 与三套参考 skills（direction-scout / grid-scout / grid-decision）语义冲突时，**取更严格的风险边界**，并在"背景"中写明冲突双方的原文位置。
