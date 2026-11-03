# Step 9: 任务 Skill 准备（单仓指令）

仅由已启用的 `skill_consumption` 内置步骤加载，执行计划条目的 `ref_file.single` 指向本文件。本轮未启用时不产生准备结果，不读取或使用旧的 Skill / 经验关联内容。

<!-- GATE:REF references/skill-preparation.md -->
**MANDATORY GATE**：Read 本技能安装目录下的 `references/skill-preparation.md`，由主会话针对本仓待办 1.x 任务执行一次准备；文件不存在时 MUST STOP。
读取后输出: "GATE PASSED: references/skill-preparation.md loaded"。
<!-- /GATE:REF -->

## 交给 Step 10 的结果

本轮准备结果按任务编号记录锁定路径、用户指定 / Agent 自选 / 不使用 / 获取失败等状态。Step 10 在当前任务的 P0/P1/P2 展示后，从准备结果的锁定路径读取所需内容，作为代码生成上下文；不再次调度 Step 9，也不重复检索、确认或安装。

明确不使用、无合适候选或本轮获取失败时继续原任务。执行中发现需新增或改选的关联时，汇总其余待办的同类问题，由主会话统一处理；已有可用关联的任务可继续，不逐任务弹窗。已有同名内容丢失时按已确认的决定补齐，不重新选型。

任务上下文不能改写项目原则或替代后续验证。关闭消费不影响普通任务读取、checkbox 更新和通用编排插槽。
