# Phase 10: 设计追溯验证（单仓模式指令文件）

> 本文件为可配置步骤 `design_traceability` 的指令文件（单仓版）。仅在执行计划含 `key=design_traceability` 条目时被 Read。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**【禁止】主会话直接调用 cross-doc-checker Skill tool** — 主会话必须通过 Agent tool 启动子代理，由子代理调用 Skill tool
**【禁止】通过 Bash 调用 Python 脚本执行追溯验证** — cross-doc-checker 是 Agent 审查技能（使用 Read/Grep/Glob），不是 Python 脚本
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

**【强制执行证据】**：
- **必须**使用 Agent tool（subagent_type="general"）启动子代理执行追溯验证 — 禁止直接调用 Skill tool: cross-doc-checker
- **必须**显式声明"已通过 Agent tool 启动子代理执行 Phase 10 设计追溯验证" — 禁止仅声明"追溯验证已执行"而不说明执行方式
- **必须**展示子代理的返回结果（PASS/FAIL 及 findings 数量） — 禁止省略子代理返回结果
- **自检**：如果执行记录中出现 "SkillToolcross-doc-checker" 而非 "Agent tool" 启动子代理，说明违反了 subagent 强制执行要求，**必须**重新通过 Agent tool 启动子代理执行

**子代理启动方式**：
```
Agent tool: subagent_type="general", prompt="执行 core-design Phase 10 设计追溯验证。先调用 Skill tool: cross-doc-checker <change-name> --layer L2 验证 delta_spec→delta_design 追溯，再调用 Skill tool: cross-doc-checker <change-name> --layer L3 验证 delta_design→tasks 追溯。按 cross-doc-checker 的 CHECK-ID 集合执行验证，如有 ERROR 执行 3 轮自动修复循环。验证完成后报告结果。"
```

## L2 验证：delta_spec → delta_design

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L2：
```
Skill tool: cross-doc-checker <change-name> --layer L2
```
- **验证内容**：delta_spec.md 中的需求是否都有对应的 delta_design.md 设计
- **失败处理**：标记问题，上报用户具体失败原因

**L2 自动修复循环（最多 3 轮）**：
1. 读取 cross-doc-checker 输出的 findings 列表
2. 按 finding 类型执行修复：
   - 【文档保真类】delta_spec 需求未在 delta_design 中映射 → 在 delta_design.md 中补充该需求的设计章节和"对应需求"字段
   - 【文档保真类】截断/占位符 → 替换为具体内容
3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L2
4. 3 轮后仍有 FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现 FAIL 后仅报告问题不修复

## L3 验证：tasks → delta_design + delta_test_design

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L3：
```
Skill tool: cross-doc-checker <change-name> --layer L3
```
- **验证内容**：delta_design.md 中的设计模块是否都有对应的 tasks.md 任务
- **失败处理**：标记问题，上报用户具体失败原因

**L3 自动修复循环（最多 3 轮）**：
1. 读取 cross-doc-checker 输出的 findings 列表
2. 按 finding 类型执行修复：
   - 【文档保真类】设计需求未在 tasks 中覆盖 → 在 tasks.md 中补充对应任务，填写"关联需求"字段
   - 【文档保真类】截断/占位符 → 替换为具体内容
3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L3
4. 3 轮后仍有 FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现 FAIL 后仅报告问题不修复

## 判断

- L2+L3 验证通过 → 进入 Phase 11
- 验证失败 → 修复文档问题后重新验证（循环最多 3 次）

**主会话后处理**（子代理返回后执行）：
- 子代理返回验证通过 → 进入 Phase 11（如 `design_review` 开启）
- 子代理返回 3 轮 FAIL → 主会话上报用户处理
- 子代理执行失败或无法调起 → **【强制】先向用户明确告知**："子代理追溯验证执行失败（原因：{具体错误}），将降级为主会话直接执行 cross-doc-checker"，**然后**主会话降级直接调用 cross-doc-checker Skill 执行

**【降级策略】**：子代理执行失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行。**禁止跳过告知直接降级**（这会掩盖 subagent 执行失败的事实）。告知内容必须包含：1) 失败的具体原因 2) 即将执行的降级操作。

## 衔接豁免

- **`design_traceability` 关闭时**：跳过 Phase 10，Phase 9 完成或跳过后直接进入 Phase 11（如 `design_review` 开启）或 Phase 12（如 `design_review` 也关闭）。"禁止主会话直接执行"强制位随关闭豁免。
- **`design_review` 关闭但 `design_traceability` 开启时**：Phase 10 通过后直接进入 Phase 12，不进入 Phase 11。

## 关闭语义

**执行计划不含 `design_traceability` 条目时**：跳过 L2/L3 追溯验证，delta_spec→delta_design→tasks 追溯链无人校验。关闭语义 = "已有外部验证或用户明确放弃追溯验证"。
