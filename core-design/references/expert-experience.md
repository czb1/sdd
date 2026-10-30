# Phase 7: 准备已有设计经验

> 保留现有配置键 `expert_experience`。仅在执行计划含该步骤时读取；单仓与多仓一致。

## 执行步骤

1. 在 Phase 6 后、Phase 8 前，提取需求目标、代码仓、约束及已有设计上下文。
2. 可复用当前项目中已获取且适用的设计经验，辅助设计决策；不检索、下载或触发任务关联 Skill 的读取与消费。
3. 无可复用经验时直接继续生成任务，不要求创建临时经验文件。
4. 保留任务仍引用的本地经验与 Skill。

## 关闭语义

关闭 `expert_experience` 仅跳过本阶段已有设计经验的准备。新增的任务 Skill 消费独立受 `post-generate` 中 `skill_consumption` reference 条目控制，默认关闭；二者互不隐式开启，也不存在级联依赖。启用 `expert_experience` 或提供 `--query` 均不能触发任务 Skill 检索、下载、消费或回写。
