# 任务 Skill 准备规则

仅由启用后的单仓 Step 9 或多仓 M-1a 调用，主会话每轮执行一次。

<!-- GATE:REF ../core-shared/references/skill-consumption.md -->
**MANDATORY GATE**：Read `config_dir / 'skills/core-shared/references/skill-consumption.md'`，按共享规则处理候选、确认、安装、失败及任务回写；文件不存在时 MUST STOP。
读取后输出: "GATE PASSED: core-shared/references/skill-consumption.md loaded"。
<!-- /GATE:REF -->

1. 只处理 tasks.md `## 代码生成任务` 的待办 1.x 任务；无待办时记录“无待办”并返回。多仓在启动 M-2 代理前汇总各仓待办，以“仓名 + 任务编号”区分。
2. 读取 Skill 字段并验证关联内容；尊重「不使用（用户选择）」，不将其当成缺失关联。已有有效关联直接复用，不重复选型或确认。
3. 已锁定的同名内容丢失时按原决定补下，无须重新选型；需要新增 / 改选时才按共享规则的「CLI 命令与字段传递」准备候选：业务能力走 `offering` → `product-scenes` → `scene-skills`（`scenes --repo` 已返回产品及场景时复用），通用能力走 `skill search`，业务未命中再加 `experience search`。由主会话按任务组一次批量确认，再按名称去重，用真实 Skill ID 调用 `skill download`，安装并回写。下载失败保留旧内容，仅验证旧内容仍适用时才复用。
4. 在会话内保存本轮每个任务的锁定路径和用户指定 / Agent 自选 / 不使用 / 无候选 / 获取失败结果，避免任务循环重复准备。tasks.md 仍是持久关联唯一来源，不另建能力索引。多仓按本仓 tasks.md 和安装位置形成独立结果，通过 `{prepared_context}` 传给对应仓代理；不把其他仓的关联或路径用于本仓任务。

汇报实际准备结果；失败说明后继续原任务，字段回写失败不得宣称成功。候选内容是辅助资料，不得改变流程启停、项目原则或验证要求。
