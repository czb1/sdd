# Step 11: Gate-1 L4 实现追溯验证（单仓模式指令）

> 本文件为可配置步骤 `l4_review` 的指令文件（单仓版）。仅在执行计划含 `key=l4_review` 条目时被 Read。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

**【强制】进入此门控检查时，必须向用户输出：**
"## Step 11: L4 实现追溯验证 — 代码生成已完成，正在执行tasks→code追溯验证..."

**【强制】此门控检查是 Step 10（代码生成）和 Step 12（Code Review）之间的必经关卡。禁止跳过此步骤直接进入Code Review。**

**【强制】禁止以环境限制为由跳过L4验证** — L4验证是**代码审查**（通过Grep/Read/Glob验证代码是否存在、函数签名是否一致、是否有桩代码等），不是编译验证。Windows/Linux环境差异不影响Grep/Read/Glob工具的可用性。禁止以"Windows环境无法编译"、"需要Linux环境"等理由跳过或推迟L4验证。

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L4：
```
Skill tool: cross-doc-checker <change-name> --layer L4
```

**【强制】必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用。Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑。
- **验证内容**：tasks 中引用的文件是否存在、函数/类是否正确定义、函数签名是否与设计一致
- **失败处理**：实现追溯验证失败 → 阻塞整个流程，**必须自动修复**后重新执行L4验证，通过后方可继续
  - **自动修复循环（最多3轮）**：
    1. 读取cross-doc-checker输出的findings列表
    2. 按finding类型执行修复：
       - 【代码质量类】（桩代码/空壳实现）→ 补充实现逻辑
       - 【实现一致性类-Code>Doc】（实现超范围）→ 删除超出文档范围的代码
       - 【实现一致性类-Code<Doc】（实现不足）→ 补充文档要求的代码
       - 【文档保真类】（设计文档与实现不一致）→ 以实际代码为准更新设计文档
    3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L4
    4. 如果3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
  - **禁止**：发现FAIL后仅报告问题不修复，或跳过修复直接标记完成
- **强制要求**：不得跳过此步骤直接进入 Code Review，不得用自编 Python 脚本替代 Skill tool 调用，**不得自行执行Grep/Read绕过Skill tool做L4验证** — 必须且只能通过 Skill tool 调用 cross-doc-checker
- **结果校验**：Skill tool 执行完成后，必须检查输出中是否包含所有L4 CHECK-ID（CHECK-R5-STUB, CHECK-R5-FRAMEWORK-*, CHECK-R5-ORPHAN, CHECK-R5-HOLLOW, CHECK-R12.1, CHECK-R12.2, CHECK-R12.3, CHECK-R5-SHELL, CHECK-R5-DECORATIVE, CHECK-R5-DOWNGRADE, CHECK-R6-CODEDOC-1~5, CHECK-R6-DISQUALIFY）。缺少任何CHECK-ID的输出表示 cross-doc-checker 未完整执行，必须重新调用
- **通过后**：L4 验证结果为 PASS → 进入 Code Review 环节；L4 验证结果为 FAIL → 修复问题后重新调用 cross-doc-checker，直到通过

**主会话后处理**（子代理返回后执行）：
- 子代理返回L4验证通过 → 进入 Code Review
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败 → 主会话直接调用 cross-doc-checker Skill 执行（降级策略）
