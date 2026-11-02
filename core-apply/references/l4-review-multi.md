# Step 11: Gate-1 L4 实现追溯验证（多仓模式指令）

> 本文件为可配置步骤 `l4_review` 的指令文件（多仓版）。仅在执行计划含 `key=l4_review` 条目时被 Read。
> 指令来源：`references/multi-repo.md` 的 **M-3**（多仓下 L4 验证的唯一执行权威，与 multi-repo.md 内容一致）。

## 多仓下的执行位置

多仓模式下，L4 验证由 **M-3** 承担（替代单仓 Step 11 gate-1-traceability）。M-2（各仓代码生成）完成后，主会话分派 M-3 子代理并行执行各仓 L4 验证：

- M-3: 各仓L4实现追溯验证（subagent并行，替代门控1 L4）

## M-3 执行指令

**Replaces**: steps.md Step 8 gate-1-traceability（单仓步骤）
**Input**: 各仓已生成的代码文件、tasks.md

### 1. 对每个涉及仓启动子代理执行L4验证

子代理任务描述模板：

```
你是仓 {repo} 的专属L4验证代理。请对 {repo} 仓执行 L4 实现追溯验证：

输入文件（必须全部读取后再开始执行步骤）：

| # | 文件 | 路径 | 消费用途 |
|---|------|------|----------|
| 1 | delta_design.md | {repo_path}/docs/changes/{change_name}/delta_design.md | **核心输入**：L4验证的基准文档，cross-doc-checker将检查代码实现是否覆盖设计中的每个模块 |
| 2 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：任务清单，用于确认哪些任务已完成（代码已生成） |
| 3 | 已生成的代码文件 | {repo_path}/src/ 等代码目录 | **核心输入**：L4验证的目标，检查代码是否可追溯到delta_design中的设计模块 |
| 4 | 执行计划片段 | {project_root}/docs/.flow_context/execution-plan-fragment-core-apply-{repo}.json | **编排输入**：本仓执行计划片段。post-l4 插槽条目在 L4 验证完成后执行；不在插槽中的编排点不执行 |

执行步骤：
1. 使用 Skill tool 调用 cross-doc-checker <change-name> --layer L4（禁止自行用Grep/Read替代skill调用）
2. 读取审查输出的findings列表
3. 如果存在ERROR级finding，**【强制】执行3轮自动修复循环**（禁止跳过，禁止直接报告问题而不修复）：

   **修复 = 编写/修改代码**，不是"验证发现"或"确认问题"。每一轮修复必须产生实际的代码变更（Edit/Write操作），不允许仅读取文件确认问题后进入下一轮。

   修复轮次 = 0
   while 存在ERROR级finding AND 修复轮次 < 3:
       修复轮次 += 1
       输出 "修复轮次 {修复轮次}/3：发现 {ERROR数量} 个ERROR"
       **按finding类型执行修复**（对齐单仓SKILL.md门控1修复逻辑）：

       | finding类型 | 修复方式 |
       |------------|----------|
       | 【代码质量类】桩代码/空壳实现 | 补充实现逻辑（Edit/Write代码文件） |
       | 【实现一致性类-Code>Doc】实现超范围 | 删除超出文档范围的代码 |
       | 【实现一致性类-Code<Doc】实现不足 | 补充文档要求的代码（Edit/Write代码文件） |
       | 【文档保真类】设计文档与实现不一致 | 以实际代码为准，更新delta_design.md |

       修复后重新调用 Skill tool: cross-doc-checker <change-name> --layer L4
       读取新的findings列表
4. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表
5. **【强制】禁止发现ERROR后直接返回ESCALATE而不执行修复循环**
6. **【强制】子代理必须在内部完成3轮修复循环后才返回结果** — 禁止返回fix_rounds<3的ESCALATE，主会话不会重新启动子代理执行修复
7. **【强制】修复轮次必须包含实际代码变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮
8. L4 验证完成后，执行执行计划片段（输入 #4）中 `orchestration_points.post-l4` 插槽条目：
   - `type=reference` → Read 条目 `file` 字段指令文件并执行
   - `type=skill` → 调用条目 `skill` 字段指定 skill（`run_mode=subagent` 时 spawn 独立子代理）
   - 插槽为空 → 跳过，不加载任何指令文件

当前变更：{change_name}
项目根目录：{project_root}
仓目录：{repo_path}

返回格式（必须包含修复过程记录）：
- 全部通过：status=PASSED, findings=[...], fix_rounds=0
- 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N
- 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
```

### 2. 汇总所有子代理结果，处理ESCALATE升级

- 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"：fix_rounds = 3 → 已尽力修复仍无法解决，升级；fix_rounds < 3 → 子代理逻辑异常，记录WARNING但仍升级，**禁止主会话重新启动子代理执行修复**）
- **【强制】禁止主会话将子代理返回的问题"记录后继续"** — 每个仓的结果只能是PASSED/FIXED/ESCALATE之一，不能是"有ERROR但继续"

### 3. 阶段间同步

- **所有仓L4通过后才进入M-4**

**Output**: 各仓L4验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L4验证已完成
