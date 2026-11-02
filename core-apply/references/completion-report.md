# Step 15: 完成或暂停时展示状态（指令文件）

> 本文件为可配置步骤 `completion_report` 的指令文件（单仓/多仓通用，无模式差异）。仅在执行计划含 `key=completion_report` 条目时被 Read。

**执行位置**：主流程末尾（Step 14 L5 覆盖度验证之后）。输出执行报告并展示可配置步骤状态。

Display:
- Tasks completed this session
- Overall progress: "N/M tasks complete"
- If all done: suggest archive
- If paused: explain why and wait for guidance

**可配置步骤状态展示**：Read `docs/.flow_context/skipped-core-apply.json`（只读，agent 全程不写）。存在键 → 对应步骤为"有意关闭"（展示关闭原因：`disabled_by_config` / `user_cancelled` / `dependency_downgraded`），非执行失败。完成报告展示格式：

```
## 执行计划状态
- L4 实现追溯验证: 已执行 / 已跳过（<reason>）
- Code Review: 已执行 / 已跳过（<reason>）
- 单元测试: 已执行 / 已跳过（<reason>）
- L5 UT覆盖度验证: 已执行 / 已跳过（<reason>）
```

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete! Ready to archive this change. Run /core-archive <change-name>
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```
