# Phase 10: 各仓 design-doc-reviewer 审查（多仓模式指令文件）

> 本文件为可配置步骤 `design_review` 的指令文件（多仓版）。仅在执行计划含 `key=design_review` 条目时被 Read。
> 指令来源：`references/multi-repo.md` 的 **M-3b**（多仓下设计文档审查的唯一执行权威）。

## 多仓下的执行位置

多仓模式下，设计文档审查由 **M-3b** 承担（替代单仓 Phase 10）。M-3a（各仓追溯验证）全部通过后，主会话分派 M-3b 子代理并行执行各仓 design-doc-reviewer 审查。

## M-3b 执行指令

**【强制前置】M-3a（cross-doc-checker L2/L3）必须全部通过后才能执行 M-3b** — 追溯链验证不通过时，design-doc-reviewer 审查无意义。
**例外**：`design_traceability` 关闭时 M-3a 被跳过，M-2 完成后直接进入 M-3b（"M-3a 全过后才执行 M-3b"依赖随 `design_traceability` 关闭豁免）。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，**禁止主会话直接执行**
**Replaces**: 单仓 Phase 10 design-review
**Input**: 各仓 delta_design.md、delta_test_design.md、tasks.md
**同步/异步**: sync

**【强制】Phase 10 必须调用 design-doc-reviewer，禁止调用 cross-doc-checker 替代** — 两个 skill 的 CHECK-ID 集合完全不同，不可互相替代。

**Execution**:
1. **【强制】使用 Agent tool 启动子代理**（与 M-3a 相同的调用模式）：

   对每个涉及仓，使用 Agent tool 启动一个子代理，每批最多 3 个并行：
   ```
   Agent tool调用示例（3仓一次性并行启动）：
   - name: "M3b-review-cm", subagent_type: "general", description: "cm仓文档审查", prompt: <cm仓任务描述>
   - name: "M3b-review-common", subagent_type: "general", description: "common仓文档审查", prompt: <common仓任务描述>
   - name: "M3b-review-frame", subagent_type: "general", description: "frame仓文档审查", prompt: <frame仓任务描述>
   ```
   - **子代理类型**：`subagent_type="general"`（不是 `"general-purpose"`）
   - **并发上限**：3 个（涉及仓 <=3 时一次性并行启动，>3 时分批启动每批 3 个）
   - **子代理失败时**：重试 1 次，仍失败则主会话补充执行该仓
   - **单仓失败不阻塞其他仓的同阶段执行**

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属文档审查代理。请对 {repo} 仓执行 design-doc-reviewer 审查：

   审查对象：
   - {repo}/docs/changes/<change>/delta_design.md
   - {repo}/docs/changes/<change>/delta_test_design.md
   - {repo}/docs/changes/<change>/tasks.md

   审查步骤：
   1. 使用 Skill tool 调用 design-doc-reviewer <change-name>（**禁止调用 cross-doc-checker 替代**，禁止自行用 Grep/Read 替代 skill 调用）
   2. 读取审查输出的 findings 列表
   3. 如果存在 ERROR 级 finding，执行自动修复（最多 3 轮）：
      - 必需章节缺失 → 补充缺失章节
      - 截断/占位符 → 替换为具体内容
      - 验收条件缺失 → 补充可判定的验收条件
      - 视图缺失 → 补充 PlantUML 图
   4. 修复后重新调用 Skill tool: design-doc-reviewer <change-name> 验证
   5. 3 轮后仍有 ERROR 级 finding → 返回 ESCALATE 状态 + blocking_issues 列表

   当前变更：{change_name}
   项目根目录：{project_root}

   返回格式：
   - 全部通过：status=PASSED, findings=[...]
   - 自动修复成功：status=FIXED, fixes_summary=[...]
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}]
   ```

2. **【强制】子代理启动验证** — 启动子代理后，必须输出子代理启动确认：
   ```
   M-3b 子代理启动确认：
   - cm: 子代理 M3b-review-cm 已启动 ✓
   - common: 子代理 M3b-review-common 已启动 ✓
   - frame: 子代理 M3b-review-frame 已启动 ✓
   ```

3. 汇总所有子代理结果，处理 ESCALATE 升级：
   - 当子代理返回 ESCALATE 状态时，使用 AskUserQuestion 展示给用户选择处理方式（人工修复/忽略继续/重新审查）
   - **【强制】验证子代理修复过程**：如果子代理返回 ESCALATE 但 fix_rounds < 3 → **重新启动该仓子代理并强制执行 3 轮修复**
   - **【强制】禁止主会话代替子代理修复** — 子代理返回 FAIL 时，主会话**不能**直接使用 Edit/Write 修改文档来修复问题。必须重新启动该仓子代理执行修复循环。
4. **所有仓审查通过后才进入 cleanup**（如 `cleanup` 开启）或流程完毕

**主会话后处理**（所有子代理返回后执行）：
- 所有仓审查通过（PASSED/FIXED） → 直接进入 cleanup（如 `cleanup` 开启）
- 存在 ESCALATE（且 fix_rounds=3） → AskUserQuestion 让用户决策
- 存在 ESCALATE（但 fix_rounds<3） → 重新启动该仓子代理强制执行 3 轮修复
- 子代理执行失败（非 ESCALATE） → **【强制】先向用户明确告知**，然后主会话降级直接调用 design-doc-reviewer Skill 执行该仓的审查
- 子代理返回【用户意图类】finding → 主会话与用户交互澄清，完成后再次派发子代理执行审查

**Output**: 各仓审查报告（汇总 PASSED/FIXED/ESCALATE 状态 + 用户决策记录）
**Checkpoint**: 所有涉及仓的 design-doc-reviewer 审查已完成

## 衔接豁免（多仓模式）

- **`design_review` 关闭时**：跳过 M-3b，M-3a 通过后（如 `design_traceability` 开启）或 M-2 完成后（如 `design_traceability` 也关闭）直接进入 cleanup。"禁止主会话直接执行"强制位豁免。"禁止用 cross-doc-checker 替代"强制位豁免。
- **`design_traceability` 关闭但 `design_review` 开启时**：M-2 完成后直接进入 M-3b，"M-3a 全过后才执行 M-3b"依赖随 `design_traceability` 关闭豁免（因 M-3a 被跳过）。

## 关闭语义

**执行计划不含 `design_review` 条目时**：跳过 M-3b 全段，各仓 design-doc-reviewer 审查无人执行。M-3a 通过后（如 `design_traceability` 开启）或 M-2 完成后（如 `design_traceability` 也关闭）直接进入 cleanup。
