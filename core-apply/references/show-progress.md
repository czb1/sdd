# Step 8: 展示当前进度（指令文件）

> 本文件为可配置步骤 `show_progress` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=show_progress` 条目时被 Read。

**执行位置**：主流程 Step 7（加载代码生成原则）之后、Step 10（代码生成任务）之前。纯展示，无产物依赖。

Display:
- Schema being used
- Progress: "N/M tasks complete"
- Remaining tasks overview
- Dynamic instruction from output
