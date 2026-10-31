# Phase 7: 准备已有设计经验

> 本文件为内置可启停步骤 `expert_experience` 的指令文件。仅在执行计划 `steps` 含 `type=built_in`、`config_key=expert_experience`、`enabled=true` 的条目时，由骨架读取该条目的 `ref_file.single` / `ref_file.multi` 后执行；单仓与多仓一致。

## 执行步骤

1. 在 Phase 6 后、Phase 8 前，提取需求目标、代码仓、约束及已有设计上下文。
2. 可复用当前项目中已获取且适用的设计经验，辅助设计决策；本阶段仅使用已有设计上下文。
3. 无可复用经验时直接继续生成任务，不要求创建临时经验文件。

## 关闭语义

配置 `expert_experience=false` 时，本内置步骤不进入启用计划；骨架直接进入 Phase 8，不加载本文件。其余步骤及编排点按各自计划继续执行。
