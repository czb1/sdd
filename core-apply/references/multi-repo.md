# Multi-Repo Enhancement: core-apply

**Skill**: core-apply
**Depends On**: repo_assignments.json
**Step Mapping Authority**: M-编号与 steps.md 序号一一对应（M-1→Step3, M-2→Step4~9, M-3→Step10, M-4→Step11, M-5→Step12, M-6→Step13）

## Prerequisites
1. repo_assignments.json 存在
2. involved_repos >= 2
3. 已输出 "GATE PASSED: references/multi-repo.md loaded"
4. 已输出 "GATE PASSED: references/code-gen-principles.md loaded"（主会话 Step 7 GATE 加载）

## M-1: 多仓检测
**Replaces**: steps.md Step 3 check-status（多仓模式下status脚本基于根目录路径不适用，M-1替代为Agent直接读取各仓文件检查状态）
**Input**: 项目根目录路径、变更名称
**Execution**:
1. 读取 `docs/changes/<change>/repo_assignments.json`：
   - 文件存在且 `involved_repos` 数量 >= 1 -> 多仓模式，设置 `is_multi_repo = True`
   - 文件不存在 -> 执行单仓流程（不报错），设置 `is_multi_repo = False`
   - 文件存在但 `involved_repos` 数量 < 1 -> 执行单仓流程（不报错），设置 `is_multi_repo = False`
2. 多仓模式下，解析 `repo_assignments.json` 中的 `involved_repos`、`anchor_repos`、`expanded_repos`、`expansion_reason` 字段
**Output**: is_multi_repo 标志 + involved_repos 列表
**Checkpoint**: repo_assignments.json 已读取，多仓/单仓环境已判定

## M-2: 按仓拓扑分批 + 子代理并行代码生成
**Replaces**: steps.md Step 4~9（单仓步骤，多仓模式替换为按拓扑分批并行代码生成）
**Input**: repo_assignments.json 中的 involved_repos、cross_repo_contracts.json
**Execution**:
1. 调用 `parse_tasks_multi(project_root, change_name, repos)` 从多个仓读取tasks.md概览：
   - 函数签名：`parse_tasks_multi(project_root: str, change_name: str, repos: List[str]) -> Dict[str, List[Dict[str, Any]]]`
   - 读取路径：`{repo}/docs/changes/<change>/tasks.md`
   - 返回格式：`{repo_name: [{"text": str, "done": bool}]}`
   - 仓的tasks.md不存在时返回空列表`[]`
2. 调用 `topological_sort_repos(project_root, change_name, repos)` 确定仓级执行批次：
   - 函数签名：`topological_sort_repos(project_root: str, change_name: str, repos: List[str]) -> Dict[str, Any]`
   - 读取 `cross_repo_contracts.json`，提取所有contracts的 `definition_repo` 和 `consumer_repos`
   - 构建有向图：`definition_repo -> consumer_repos`（定义仓必须在消费仓之前执行）
   - Kahn算法拓扑排序，按层级分批（同一层级的仓无依赖关系，可并行执行）
   - 返回 `{"sorted_repos": [...], "batches": [[batch1_repos], [batch2_repos], ...], "has_cycle": bool, "cycle_repos": [...], "unresolved": [...]}`
3. 循环依赖处理：
   - `has_cycle=True` -> AskUserQuestion让用户决定涉及仓的执行顺序
   - 用户提供顺序后，按用户指定顺序覆盖拓扑排序结果（每个仓独占一个批次）
4. 无跨仓依赖 -> 所有仓归入同一批次，按并发上限3分批启动子代理
5. 跨仓任务依赖字段格式：
   ```markdown
   - [ ] 1.5 实现sm模块接口适配
     - **编程语言**: python
     - **关联需求**: REQ-008
     - **跨仓依赖**: repoB::TASK-003    # 可选字段，格式：仓名::任务编号
     - **验收标准**: ...
   ```
   - 调用 `parse_cross_repo_dependencies(tasks_content)` 解析跨仓依赖字段
   - 无效仓引用（不在involved_repos中）输出WARNING并忽略该依赖
6. **【强制】使用子代理并行执行各仓代码生成**（禁止在主会话中逐仓顺序执行）：

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属代码生成代理。请对 {repo} 仓执行代码生成任务：

   输入文件（必须全部读取后再开始执行步骤）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | delta_design.md | {repo_path}/docs/changes/{change_name}/delta_design.md | **核心输入**：代码生成的基准设计文档，包含设计锚点、模块设计、接口定义、TDD强制流程 |
   | 2 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：代码生成任务清单（仅含1.x代码生成任务，不含CodeReview/UT任务），读取每个待执行任务的"设计锚点"、"编程语言"、"验收标准"字段 |
   | 3 | delta_spec.md | {repo_path}/docs/changes/{change_name}/delta_spec.md | **参考输入**：需求规格，理解代码应实现的功能需求 |
   | 4 | delta_test_design.md | {repo_path}/docs/changes/{change_name}/delta_test_design.md | **参考输入**：测试设计，理解UT任务应覆盖的测试用例 |
   | 5 | 已有代码文件 | {repo_path}/src/ 等代码目录 | **核心输入**：代码理解的目标文件，生成代码前必须先理解现有代码结构 |
   | 6 | code-gen-principles.md | {skill_dir}/references/code-gen-principles.md | **原则约束（必读）**：15条代码生成原则（C-1~C-15），每个代码生成任务执行前必须对照自检，违反=代码不合格 |
   | 7 | task-skills.md | {skill_dir}/references/task-skills.md | **领域 Skill 消费规则**：仅对含 Skill 字段的 1.x 任务，读取原始 tasks.md 元数据，按当前仓解析 Skill路径并加载 SKILL.md；低于设计锚点，缺失时 WARNING 后继续 |

   **路径说明**：{skill_dir} 为 core-apply 技能安装目录，主会话在构造子代理 prompt 时必须将 {skill_dir} 替换为实际绝对路径（解析方式见 SKILL.md Reference文件路径解析章节）。

   执行步骤：
   a. 读取所有输入文件；输入#7是可选增强参考，不可读时记录WARNING并按无领域Skill执行
   b. 对tasks.md中每个待执行的代码生成任务（`- [ ]`状态），执行以下代码生成流程：
      - 解析任务的"设计锚点"字段，定位delta_design.md中的设计模块
      - 按 task-skills.md（输入#7）从当前仓原始 tasks.md 读取本任务的可选 Skill 字段。没有 Skill 字段则按原流程；有字段时将 Skill路径 相对于 {repo_path} 解析并 Read 对应 SKILL.md。路径或文件无效则 WARNING 后继续。只作为当前任务附加上下文，设计锚点与项目约束优先，不重新匹配或下载，不影响其他仓或2.x及以后任务
      - 执行任务级代码理解：
        - 先尝试调用 CodeBase 工具（GetRemoteCallChain/CodeSemanticSearch/GetFeatureTree）
        - CodeBase 不可用或无结果 → 回退到 grep/read/glob
        - 最终必须通过 read 实际读取代码验证
      - 按P0→P1→P2三阶段展示设计信息（P0必须参考 → P1应当参考 → P2建议参考）
      - **代码生成原则自检**：对照 code-gen-principles.md（输入#6）C-1~C-15，每个任务执行前必须自检增量开发、代码复用、质量硬约束
      - 执行代码生成（Edit/Write工具）
      - 标记任务完成：将tasks.md中对应任务 `- [ ]` 改为 `- [x]`
   c. 所有任务完成后，汇总生成结果：
      - 已完成任务数/总任务数
      - 每个任务的生成文件列表
      - 每个任务实际使用的领域Skill及降级WARNING（如有）
      - 遇到的问题（如有）

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}

   返回格式：
   - status: COMPLETED / PARTIAL / FAILED
   - repo: {repo}
   - total_tasks: N
   - completed_tasks: M
   - generated_files: [file_path, ...]
   - issues: [description, ...]（如有）
   ```

7. 并发规则（对齐通用规则 subagent并行执行规则）：
   - **并发上限**：同时运行的子代理数量不得超过3个
   - 按拓扑批次顺序启动：同一批次内的仓并行启动，当前批次全部完成后再启动下一批次
   - 涉及仓数量<=3且无跨仓依赖：一次性并行启动所有子代理
   - 子代理失败 -> 重试1次（使用同类型或降级类型子代理）
   - 重试仍失败 -> 主会话补充执行**仅该失败仓**的代码生成
   - **禁止因子代理类型不可用而回到主会话逐仓顺序执行所有仓**
8. 主会话汇总检查点（每批次完成后输出）：
   ```
   M-2 代码生成检查点（批次 {batch_index}/{total_batches}）：
   - [x] common: COMPLETED, 30/30 tasks, 15 files generated
   - [x] frame: COMPLETED, 49/49 tasks, 22 files generated
   - [ ] pf: PARTIAL, 14/16 tasks, 主会话补充中...
   ```
9. 后续步骤（L4/审查/UT/L5）不在M-2内执行，而是在M-3~M-6中分阶段执行（对齐core-explore的L1模式：所有仓完成阶段X后再统一进入阶段Y）
**Output**: 各仓代码生成完成 + tasks.md 状态更新
**Checkpoint**: 所有涉及仓的代码生成已按拓扑分批并行完成

---

## 通用规则：subagent并行 + 用户决策升级

以下规则适用于M-2~M-6所有阶段（M-2仅适用subagent并行执行规则，用户决策升级机制适用于M-3~M-6）：

### subagent并行执行规则

1. **子代理类型**：`subagent_type="general"`
2. **禁止因子代理类型不可用而回到主会话直接执行**
3. **并发上限**：同时运行的子代理数量**不得超过3个**（5个并行token消耗太快，极易引发模型限流）
   - 涉及仓数量<=3：使用 `run_in_background=True` 一次性并行启动所有子代理
   - 涉及仓数量>3：分批启动，每批最多3个子代理，完成一个立即启动下一个
4. **容错机制**：
   - 子代理失败 -> 重试1次
   - 重试仍失败 -> 主会话补充执行**仅该失败仓**
   - 单仓失败不阻塞其他仓的同阶段执行

### 用户决策升级机制

**【前提】子代理内部必须完成3轮自动修复循环**：子代理模板中已内置3轮修复循环逻辑，子代理必须在内部完成修复后才返回结果。主会话不负责修复循环的编排，不因fix_rounds不足而重新启动子代理。

当子代理返回ESCALATE状态时，主会话执行以下流程：
1. **汇总所有升级问题**：收集所有子代理返回的blocking_issues
2. **验证修复过程**：检查子代理的fix_rounds字段
   - fix_rounds = 3 → 子代理已尽力修复但仍无法解决，升级到用户决策
   - fix_rounds < 3 → 属于子代理逻辑异常（子代理模板强制3轮），记录WARNING但仍升级到用户决策，**禁止主会话重新启动子代理执行修复**（修复循环是子代理内部职责）
3. **【强制】禁止静默记录**：主会话不能将子代理发现的ERROR静默记录然后标记PASS。每个仓的结果只能是PASSED/FIXED/ESCALATE之一，不能是"有ERROR但继续"
4. **使用AskUserQuestion展示给用户**：
   ```
   AskUserQuestion({
     questions: [{
       question: "仓 {repo} 的{review_type}发现以下问题经3轮自动修复仍未解决：\n{blocking_issue_description}\n请选择处理方式：",
       header: "审查升级",
       options: [
         { label: "人工修复", description: "暂停该仓审查，由您手动修复后继续" },
         { label: "忽略继续", description: "标注为WARNING，继续后续流程" },
         { label: "重新审查", description: "重新启动该仓的审查子代理" }
       ]
     }]
   })
   ```
5. **传递用户决策**：将用户选择传回子代理（重新启动子代理并传入决策上下文）
6. **决策结果记录**：记录用户决策到变更目录的审查报告中

### cross-doc-checker强制约束

- **【强制】必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用
- Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑

### 阶段间同步规则

- M-3~M-6按顺序执行：**所有仓完成阶段N后才进入阶段N+1**
- 对齐core-explore的L1模式："先全部完成X，再统一开始Y"
- 原因：L4验证代码是否存在 → CodeReview验证代码质量 → UT验证功能正确性 → L5验证UT覆盖度，每个阶段依赖前一阶段的结果

---

## M-3: 各仓L4实现追溯验证（subagent并行）
**Replaces**: steps.md Step 8 gate-1-traceability（单仓步骤）
**Input**: 各仓已生成的代码文件、tasks.md
**Execution**:
1. 对每个涉及仓启动子代理执行L4验证：
   ```
   你是仓 {repo} 的专属L4验证代理。请对 {repo} 仓执行 L4 实现追溯验证：

   输入文件（必须全部读取后再开始执行步骤）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | delta_design.md | {repo_path}/docs/changes/{change_name}/delta_design.md | **核心输入**：L4验证的基准文档，cross-doc-checker将检查代码实现是否覆盖设计中的每个模块 |
   | 2 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：任务清单，用于确认哪些任务已完成（代码已生成） |
   | 3 | 已生成的代码文件 | {repo_path}/src/ 等代码目录 | **核心输入**：L4验证的目标，检查代码是否可追溯到delta_design中的设计模块 |

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

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}

   返回格式（必须包含修复过程记录）：
   - 全部通过：status=PASSED, findings=[...], fix_rounds=0
   - 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
   ```
2. 汇总所有子代理结果，处理ESCALATE升级：
   - 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"）
   - **【强制】禁止主会话将子代理返回的问题"记录后继续"** — 每个仓的结果只能是PASSED/FIXED/ESCALATE之一
3. **所有仓L4通过后才进入M-4**
**Output**: 各仓L4验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L4验证已完成

## M-4: 各仓Code Review（subagent并行）
**Replaces**: steps.md Step 9 code-review（单仓步骤）
**Input**: 各仓代码文件（仅增量变更文件）
**Execution**:
1. 对每个涉及仓启动子代理执行Code Review：
   ```
   你是仓 {repo} 的专属代码审查代理。请对 {repo} 仓执行 Code Review：

   输入文件（必须全部读取后再开始执行步骤）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：读取已完成（`- [x]`）的代码生成任务，提取每个任务的"生成文件"字段，汇总为增量变更文件列表。仅对这些文件执行Code Review，禁止对全量代码做检查 |
   | 2 | 增量变更文件 | tasks.md中各任务的生成文件 | **核心输入**：Code Review的目标文件，仅限本次代码生成环节新增/修改的文件，禁止扫描整个src/目录 |
   | 3 | delta_design.md | {repo_path}/docs/changes/{change_name}/delta_design.md | **辅助参考**：设计文档，用于理解代码应实现的功能，辅助判断代码逻辑正确性 |

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

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}

   返回格式（必须包含修复过程记录）：
   - 全部通过：status=PASSED, findings=[...], fix_rounds=0, changed_files=[...]
   - 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N, changed_files=[...]
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3, changed_files=[...]
   ```
2. 汇总所有子代理结果，处理ESCALATE升级：
   - 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"）
   - **【强制】禁止主会话将子代理返回的问题"记录后继续"**
3. **所有仓Code Review通过后才进入M-5**
**Output**: 各仓Code Review报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的Code Review已完成

## M-5: 各仓单元测试（subagent并行）
**Replaces**: steps.md Step 10 unit-test（单仓步骤）
**Input**: 各仓代码文件、delta_test_design.md、tasks.md（编程语言/UT生成技能字段）
**Execution**:
1. 对每个涉及仓启动子代理执行UT生成/修复：
   ```
   你是仓 {repo} 的专属UT代理。请对 {repo} 仓执行单元测试生成和修复：

   输入文件（必须全部读取）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | delta_test_design.md | {repo}/docs/changes/<change>/delta_test_design.md | **核心输入**：UT代码必须覆盖其中定义的所有测试用例（TCxxx），验收标准为"生成的UT覆盖delta_test_design.md中所有测试用例" |
   | 2 | tasks.md | {repo}/docs/changes/<change>/tasks.md | 读取每个UT任务的"编程语言"和"UT生成技能"字段，确定调用哪个技能；检查依赖任务是否已完成 |

   执行步骤：
   1. 读取 delta_test_design.md 和 tasks.md
   2. 对每个UT任务，根据"编程语言"字段选择对应的UT技能链：

      **UT生成技能映射**（5环节，对齐单仓模式）：

      | 编程语言 | 环节1-UT生成 | 环节2-UT修复 | 环节3-覆盖率提升 | 环节4-断言审查 | 环节5-测试报告 |
      |----------|-------------|-------------|-----------------|---------------|---------------|
      | java | generate-java-ut | fix-java-ut | improve-java-ut-coverage | java-assertion-validity-review | java-test-report |
      | cpp/c/c++ | c-cpp-dt | c-cpp-dt-autofix | - | - | - |
      | go | go-ut | go-ut-compilation-execution-fixing | - | - | - |
      | python | python-ut | - | - | - | - |
      | js/ts/other | test-driven-development | - | - | - | - |

   3. 按环节顺序执行（环节间串行，同环节内不同任务可并行）：
      - **环节1**: UT生成 — 对每个UT任务调用对应的UT生成技能，生成的UT必须覆盖delta_test_design.md中定义的TCxxx测试用例
      - **环节2**: UT修复（仅Java/C/C++/Go）— 调用对应的UT修复技能，修复编译和运行错误（最多3轮）
      - **环节3**: 覆盖率提升（仅Java）— 调用improve-java-ut-coverage
      - **环节4**: 断言审查（仅Java）— 调用java-assertion-validity-review
      - **环节5**: 测试报告（仅Java）— 调用java-test-report
   4. 每个环节完成后标记对应任务完成: `- [ ]` → `- [x]`
   5. 3轮UT修复后仍有ERROR级问题 → 返回ESCALATE状态 + blocking_issues列表
   6. **【强制】子代理必须在内部完成3轮UT修复循环后才返回结果** — 禁止返回fix_rounds<3的ESCALATE，主会话不会重新启动子代理执行修复
   7. **【强制】修复轮次必须包含实际代码变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}

   返回格式（必须包含修复过程记录）：
   - 全部通过：status=PASSED, test_results=[...]
   - 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}]
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
   ```
2. 汇总所有子代理结果，处理ESCALATE升级：
   - 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"）
   - **【强制】禁止主会话将子代理返回的问题"记录后继续"**
**Output**: 各仓UT报告（PASSED/FIXED/ESCELATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的UT已完成

## M-6: 各仓L5 UT覆盖度验证（subagent并行）
**Replaces**: steps.md Step 11 gate-2-coverage（单仓步骤）
**Input**: 各仓UT代码、delta_test_design.md、业务代码头文件、tasks.md
**Execution**:
1. 对每个涉及仓启动子代理执行L5验证：
   ```
   你是仓 {repo} 的专属L5验证代理。请对 {repo} 仓执行 L5 UT覆盖度验证：

   输入文件（必须全部读取后再开始执行步骤）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | delta_test_design.md | {repo_path}/docs/changes/{change_name}/delta_test_design.md | **核心输入**：L5验证的基准文档，cross-doc-checker将检查UT覆盖度是否满足其中定义的测试用例要求 |
   | 2 | UT代码文件 | {repo_path}/test/ 等测试目录 | **核心输入**：L5验证的目标，检查UT代码是否覆盖了delta_test_design中的所有测试用例 |
   | 3 | tasks.md | {repo_path}/docs/changes/{change_name}/tasks.md | **核心输入**：读取已完成（`- [x]`）的代码生成任务，提取"编程语言"字段用于选择UT生成技能；提取"生成文件"字段定位增量代码 |
   | 4 | 业务代码头文件 | tasks.md中代码生成任务的生成文件 | **修复必需输入**：修复L5 findings需要理解业务代码接口定义，用于编写正确的UT代码 |

   执行步骤：
   1. 使用 Skill tool 调用 cross-doc-checker <change-name> --layer L5（禁止自行用Grep/Read替代skill调用）
   2. 读取审查输出的findings列表
   3. 如果存在ERROR级finding，**【强制】执行3轮自动修复循环**（禁止跳过，禁止直接报告问题而不修复）：

      **修复 = 编写/修改UT代码**，不是"验证发现"或"确认问题"。每一轮修复必须产生实际的代码变更（Edit/Write操作），不允许仅读取文件确认问题后进入下一轮。

      修复轮次 = 0
      while 存在ERROR级finding AND 修复轮次 < 3:
          修复轮次 += 1
          输出 "修复轮次 {修复轮次}/3：发现 {ERROR数量} 个ERROR"
          **按finding类型执行修复**（对齐单仓SKILL.md门控2修复逻辑）：

          | finding类型 | 对应CHECK-ID | 修复方式 |
          |------------|-------------|----------|
          | TC场景未被UT覆盖 | CHECK-R13-TC-SEMANTIC-COVERAGE | **补充UT代码**覆盖缺失场景：读取delta_test_design.md中缺失TC的场景描述和预期结果，使用对应编程语言的UT生成技能（见下方映射表）生成UT函数 |
          | UT空壳或恒真断言 | CHECK-R5-TESTSHELL | **补充实际测试逻辑**：在空壳UT函数中添加有效断言和测试逻辑（参考delta_test_design.md预期结果） |
          | UT仅操作mock未调用业务代码 | CHECK-R13-TC-CALLTARGET | **修改UT调用业务代码**：将UT函数中仅操作mock变量的逻辑改为调用实际业务函数/宏（通过#include业务头文件 + 直接调用业务函数） |
          | UT断言与预期结果不一致 | CHECK-R13-TC-ASSERTION | **修正UT断言**：将UT断言修改为与delta_test_design.md预期结果一致 |
          | 业务代码public函数无测试覆盖 | CHECK-R13-PUBLIC-TESTED | **为该函数生成UT**：使用对应编程语言的UT生成技能为未覆盖的public函数编写UT |
          | 设计文档引用的函数名与实际代码不一致 | 各CHECK-ID | **以实际代码为准**，更新delta_test_design.md中的函数名引用 |

          **UT生成技能映射**（用于补充/生成UT代码时选择技能）：

          | 编程语言 | UT生成技能 |
          |----------|-----------|
          | java | generate-java-ut |
          | cpp/c/c++ | c-cpp-dt |
          | go | go-ut |
          | python | python-ut |
          | js/ts/other | test-driven-development |

          修复完成后重新调用 Skill tool: cross-doc-checker <change-name> --layer L5
          读取新的findings列表
   4. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表
   5. **【强制】禁止发现ERROR后直接返回ESCALATE而不执行修复循环**
   6. **【强制】子代理必须在内部完成3轮修复循环后才返回结果** — 禁止返回fix_rounds<3的ESCALATE，主会话不会重新启动子代理执行修复
   7. **【强制】修复轮次必须包含实际代码变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}

   返回格式（必须包含修复过程记录）：
   - 全部通过：status=PASSED, findings=[...], fix_rounds=0
   - 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
   ```
2. 汇总所有子代理结果，处理ESCALATE升级：
   - 子代理返回ESCALATE → 升级到用户决策（对齐通用规则"用户决策升级机制"）
   - **【强制】禁止主会话将子代理返回的问题"记录后继续"**
3. **所有仓L5通过后进入on-completion**
**Output**: 各仓L5验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L5验证已完成

## Contracts Lifecycle (本 skill 职责)

| 阶段 | 操作 | status转换 | 副本刷新 |
|------|------|-----------|----------|
| M-2 按仓路由 | 实现时修改接口（更新last_updated_at） | `confirmed` -> `confirmed` | 刷新涉及仓副本 |
