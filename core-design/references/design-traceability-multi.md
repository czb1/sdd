# Phase 9: 各仓设计追溯验证（多仓模式指令文件）

> 本文件为可配置步骤 `design_traceability` 的指令文件（多仓版）。仅在执行计划含 `key=design_traceability` 条目时被 Read。
> 指令来源：`references/multi-repo.md` 的 **M-3a**（多仓下设计追溯验证的唯一执行权威）。

## 多仓下的执行位置

多仓模式下，设计追溯验证由 **M-3a** 承担（替代单仓 Phase 9）。M-2（各仓按仓生成）完成后，主会话分派 M-3a 子代理并行执行各仓 L2/L3 验证。

## M-3a 执行指令

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，**禁止主会话直接执行**
**Replaces**: 单仓 Phase 9 design-traceability
**Input**: 各仓 delta_design.md、tasks.md、delta_test_design.md
**同步/异步**: sync

**【强制】进入 M-3a 时，必须向用户输出：**
"M-3a: 各仓设计追溯验证 — 设计文档已生成，正在通过 subagent 并行执行各仓 cross-doc-checker L2/L3 验证..."

**【强制】M-3a 是 M-2（各仓按仓生成）和 M-3b（design-doc-reviewer 审查）之间的必经关卡。禁止跳过 M-3a 直接进入 M-3b。**

**【强制】禁止主会话直接执行追溯验证** — 多仓场景下，各仓的 L2/L3 验证必须在子代理中并行执行。主会话直接执行等于将各仓串行化，违反多仓并行设计。

**【强制】Phase 9 必须调用 cross-doc-checker，禁止调用 design-doc-reviewer 替代** — 两个 skill 的 CHECK-ID 集合完全不同，不可互相替代。

**Execution**:
1. **【强制】使用 Agent tool 启动子代理**（与 M-2 相同的调用模式）：

   对每个涉及仓，使用 Agent tool 启动一个子代理，每批最多 3 个并行：
   ```
   Agent tool调用示例（3仓一次性并行启动）：
   - name: "M3a-trace-cm", subagent_type: "general", description: "cm仓追溯验证", prompt: <cm仓任务描述>
   - name: "M3a-trace-common", subagent_type: "general", description: "common仓追溯验证", prompt: <common仓任务描述>
   - name: "M3a-trace-frame", subagent_type: "general", description: "frame仓追溯验证", prompt: <frame仓任务描述>
   ```
   - **子代理类型**：`subagent_type="general"`（不是 `"general-purpose"`）
   - **并发上限**：3 个（涉及仓 <=3 时一次性并行启动，>3 时分批启动每批 3 个）
   - **子代理失败时**：重试 1 次，仍失败则主会话补充执行该仓
   - **单仓失败不阻塞其他仓的同阶段执行**

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属追溯验证代理。请对 {repo} 仓执行 cross-doc-checker L2/L3 追溯验证：

   审查对象：
   - {repo}/docs/changes/<change>/delta_design.md
   - {repo}/docs/changes/<change>/tasks.md
   - {repo}/docs/changes/<change>/delta_test_design.md

   验证步骤：
   1. 使用 Skill tool 调用 cross-doc-checker <change-name> --layer L2（**禁止调用 design-doc-reviewer 替代**，禁止自行用 Grep/Read 替代 skill 调用）
   2. 读取 L2 验证输出的 findings 列表
   3. 如果存在 ERROR 级 finding，执行自动修复（最多 3 轮）：
      - delta_spec 需求未在 delta_design 中映射 → 在 delta_design.md 中补充该需求的设计章节和"对应需求"字段
      - 截断/占位符 → 替换为具体内容
   4. L2 修复完成后，重新调用 Skill tool: cross-doc-checker <change-name> --layer L2 验证
   5. L2 通过后，使用 Skill tool 调用 cross-doc-checker <change-name> --layer L3
   6. 读取 L3 验证输出的 findings 列表
   7. 如果存在 ERROR 级 finding，执行自动修复（最多 3 轮）：
      - 设计模块未在 tasks 中覆盖 → 在 tasks.md 中补充对应任务
      - 截断/占位符 → 替换为具体内容
   8. L3 修复完成后，重新调用 Skill tool: cross-doc-checker <change-name> --layer L3 验证
   9. 3 轮后仍有 ERROR 级 finding → 返回 ESCALATE 状态 + blocking_issues 列表

   当前变更：{change_name}
   项目根目录：{project_root}

   返回格式：
   - 全部通过：status=PASSED, L2_findings=[...], L3_findings=[...]
   - 自动修复成功：status=FIXED, L2_fixes_summary=[...], L3_fixes_summary=[...]
   - 需要升级：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes, layer}]
   ```

2. **【强制】子代理启动验证** — 启动子代理后，必须输出子代理启动确认：
   ```
   M-3a 子代理启动确认：
   - cm: 子代理 M3a-trace-cm 已启动 ✓
   - common: 子代理 M3a-trace-common 已启动 ✓
   - frame: 子代理 M3a-trace-frame 已启动 ✓
   ```
   **如果无法输出上述确认（即没有实际调用 Agent tool），则 M-3a 执行失败，禁止声明"M-3a 追溯验证 ✅"**

3. 汇总所有子代理结果，处理 ESCALATE 升级：
   - 当子代理返回 ESCALATE 状态时，使用 AskUserQuestion 展示给用户选择处理方式（人工修复/忽略继续/重新审查）
   - **【强制】验证子代理修复过程**：如果子代理返回 ESCALATE 但 fix_rounds < 3，说明子代理未完成 3 轮修复就提前退出 → **重新启动该仓子代理并强制执行 3 轮修复**
   - **【强制】禁止主会话代替子代理修复** — 子代理返回 FAIL 时，主会话**不能**直接使用 Edit/Write 修改文档来修复问题。必须重新启动该仓子代理执行修复循环。
4. **所有仓追溯验证通过后才进入 M-3b**（如 `design_review` 开启）或直接进入 cleanup（如 `design_review` 关闭）

**主会话后处理**（所有子代理返回后执行）：
- 所有仓追溯验证通过（PASSED/FIXED） → 直接进入 M-3b（如 `design_review` 开启）或 cleanup（如 `design_review` 关闭）
- 存在 ESCALATE（且 fix_rounds=3） → AskUserQuestion 让用户决策
- 存在 ESCALATE（但 fix_rounds<3） → 重新启动该仓子代理强制执行 3 轮修复
- 子代理执行失败（非 ESCALATE） → **【强制】先向用户明确告知**，然后主会话降级直接调用 cross-doc-checker Skill 执行该仓的追溯验证

**Output**: 各仓追溯验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的 L2/L3 追溯验证已完成

## 衔接豁免（多仓模式）

- **`design_traceability` 关闭时**：跳过 M-3a，M-2 完成后直接进入 M-3b（如 `design_review` 开启）或 cleanup（如 `design_review` 也关闭）。"Phase 9 必须调用 cross-doc-checker 禁止用 design-doc-reviewer 替代"强制位豁免。"禁止主会话直接执行"强制位豁免。
- **`design_review` 关闭但 `design_traceability` 开启时**：M-3a 通过后直接进入 cleanup，不进入 M-3b。"M-3a 全过后才执行 M-3b"依赖不阻断（因 M-3b 被跳过）。

## 关闭语义

**执行计划不含 `design_traceability` 条目时**：跳过 M-3a 全段，各仓 L2/L3 追溯验证无人校验。M-2 完成后直接进入 M-3b（如 `design_review` 开启）或 cleanup。
