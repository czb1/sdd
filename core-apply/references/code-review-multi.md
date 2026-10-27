# Step 11: Code Review（多仓模式指令）

> 本文件为可配置步骤 `code_review` 的指令文件（多仓版）。仅在执行计划含 `key=code_review` 条目时被 Read。
> 指令来源：`references/multi-repo.md` 的 **M-4**（多仓下 Code Review 的唯一执行权威，与 multi-repo.md 内容一致）。
> Code Review 检查范围：读取已完成（`- [x]`）代码生成任务的"生成文件"字段，汇总为增量变更文件列表——仅审查这些文件，禁止全量扫描。

## 多仓下的执行位置

多仓模式下，Code Review 由 **M-4** 承担（替代单仓 Step 11 code-review）。M-3（各仓 L4 验证）通过后，主会话分派 M-4 子代理并行执行各仓 Code Review：

- M-4: 各仓Code Review（subagent并行，替代Code Review环节）

## M-4 执行指令

**Replaces**: steps.md Step 9 code-review（单仓步骤）
**Input**: 各仓代码文件（仅增量变更文件）

### 1. 对每个涉及仓启动子代理执行Code Review

子代理任务描述模板：

```
你是仓 {repo} 的专属代码审查代理。请对 {repo} 仓执行 Code Review：

输入文件（必须全部读取后再开始执行步骤）：

| # | 文件 | 路径 | 消费用途 |
|---|------|------|----------|
| 1 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：读取已完成（`- [x]`）的代码生成任务，提取每个任务的"生成文件"字段，汇总为增量变更文件列表。仅对这些文件执行Code Review，禁止对全量代码做检查 |
| 2 | 增量变更文件 | tasks.md中各任务的生成文件 | **核心输入**：Code Review的目标文件，仅限本次代码生成环节新增/修改的文件，禁止扫描整个src/目录 |
| 3 | delta_design.md | {repo_path}/docs/changes/{change_name}/delta_design.md | **辅助参考**：设计文档，用于理解代码应实现的功能，辅助判断代码逻辑正确性 |
| 4 | 执行计划片段 | {project_root}/docs/.flow_context/execution-plan-fragment-core-apply-{repo}.json | **编排输入**：本仓执行计划片段。post-review 插槽条目在 Code Review 完成后执行；不在插槽中的编排点不执行 |

**【强制】增量检查范围约束**：
- Code Review**仅检查本次变更引入的增量代码**（tasks.md中已完成任务的生成文件），不做全量代码检查
- codecheck-for-cleancode通过 `--files` 参数传入增量文件列表，禁止不传--files参数的全量扫描
- cwd-audit仅对增量文件执行检测，禁止扫描未变更的既有代码
- 全量代码中存在的既有问题（如历史存量规范问题）不在本次Code Review的修复范围内，不应作为findings报告

执行步骤（3轮修复循环全部在子代理内部完成）：
1. 读取tasks.md，提取已完成代码生成任务的生成文件列表，作为增量变更文件清单
2. 根据编程语言选择对应的代码检视技能：
   - C/C++/Java/Python/Go: 规范加载 → codecheck-for-cleancode（--files增量文件）→ cwd-audit（仅增量文件）
3. 读取审查输出的findings列表
4. **【强制】3轮自动修复循环**（禁止跳过，禁止直接报告问题而不修复，修复循环全部在子代理内部完成）：

   **修复 = 编写/修改代码**，不是"验证发现"或"确认问题"。每一轮修复必须产生实际的代码变更（Edit/Write操作），不允许仅读取文件确认问题后进入下一轮。

   如果存在ERROR级finding，必须执行以下修复循环：
   ```
   修复轮次 = 0
   while 存在ERROR级finding AND 修复轮次 < 3:
       修复轮次 += 1
       输出 "修复轮次 {修复轮次}/3：发现 {ERROR数量} 个ERROR"
       对每个ERROR执行修复（使用Edit/Write工具修改增量代码文件）
       修复后重新执行审查（仅检查增量文件）
       读取新的findings列表
   ```
5. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表
6. **【强制】禁止发现ERROR后直接返回ESCALATE而不执行修复循环**
7. **【强制】子代理必须在内部完成3轮修复循环后才返回结果** — 禁止返回fix_rounds<3的ESCALATE，主会话不会重新启动子代理执行修复
8. **【强制】修复轮次必须包含实际代码变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮
9. Code Review 完成后，执行执行计划片段（输入 #4）中 `orchestration_points.post-review` 插槽条目：
   - `type=reference` → Read 条目 `file` 字段指令文件并执行
   - `type=skill` → 调用条目 `skill` 字段指定 skill（`run_mode=subagent` 时 spawn 独立子代理）
   - 插槽为空 → 跳过，不加载任何指令文件

当前变更：{change_name}
项目根目录：{project_root}
仓目录：{repo_path}

返回格式（必须包含修复过程记录）：
- 全部通过：status=PASSED, findings=[...], fix_rounds=0, changed_files=[...]
- 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N, changed_files=[...]
- 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3, changed_files=[...]
```

### 2. 汇总所有子代理结果，处理ESCALATE升级

- 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"：fix_rounds = 3 → 已尽力修复仍无法解决，升级；fix_rounds < 3 → 子代理逻辑异常，记录WARNING但仍升级，**禁止主会话重新启动子代理执行修复**）
- **【强制】禁止主会话将子代理返回的问题"记录后继续"**

### 3. 阶段间同步

- **所有仓Code Review通过后才进入M-5**

**Output**: 各仓Code Review报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的Code Review已完成
