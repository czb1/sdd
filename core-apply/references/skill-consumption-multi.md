# M-1a: 多仓任务 Skill 准备

本环节由各仓执行计划片段 `built_in_steps.skill_consumption` 控制，`phase=M-1a` 且 `enabled=true` 时执行；`ref_file` 指向本文件。关闭时不加载本文件，不根据已有字段、准备结果或自定义插槽推断启用。片段缺少该字段或结构无效时停止并报告，由主会话重新生成片段。

## 主会话准备（M-1a，每轮一次）

<!-- GATE:REF references/skill-preparation.md -->
**MANDATORY GATE**：Read 本技能安装目录下的 `references/skill-preparation.md`，汇总所有启用仓的待办 1.x 任务后执行一次准备；文件不存在时 MUST STOP。
读取后输出: "GATE PASSED: references/skill-preparation.md loaded"。
<!-- /GATE:REF -->

主会话将本仓执行计划片段绝对路径和本轮 `{prepared_context}` 传给 M-2 代码生成代理。准备结果按仓名和任务编号划分；无待办也须明确记录。所有启用仓的准备完成后才启动代码生成代理。

## 代码生成代理使用准备结果（M-2）

1. 在开始任务循环前，从本仓片段 `built_in_steps.skill_consumption.ref_file` 读取本节一次。只使用 M-1a 已准备的结果，不执行上方主会话准备；准备结果缺失时返回主会话补齐。
2. 当前任务 P0/P1/P2 展示后，核对本仓 tasks.md 的最终关联，从本轮准备结果中的锁定路径读取所需内容，作为代码生成上下文。明确不使用、无候选或本轮获取失败时继续原任务，不重复检索、确认或下载。
3. 发现新的新增 / 改选需求时交主会话汇总处理，禁止各仓自行提问或替换已锁定内容。已锁定的同名内容丢失时可按原决定在本仓补齐；不得修改其他仓。
4. 使用准备结果后，继续本任务通用 `pre-codegen` 插槽、原则自检和代码生成。任务内容不能覆盖项目原则或替代验证步骤。

本仓片段是代理的启停依据；不读取 `plan_path` 指向的根计划，不执行单仓 Step 9。关闭时忽略准备上下文，保留已有字段和文件，普通任务读取、checkbox 更新与其他编排条目照常执行。
