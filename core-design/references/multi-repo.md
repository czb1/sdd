# Multi-Repo Enhancement: core-design

**Skill**: core-design
**Depends On**: repo_assignments.json
**Step Mapping Authority**: M-编号与 steps.md 序号一一对应（M-1→Step3, M-2→Step8, M-3a→Step9, M-3b→Step10）

## Prerequisites
1. repo_assignments.json 存在
2. involved_repos >= 2
3. 已输出 "GATE PASSED: references/multi-repo.md loaded"
4. 已输出 "GATE PASSED: references/design-principles.md loaded"
5. 已输出 "GATE PASSED: references/design-views.md loaded"

## M-1: 多仓检测
**Replaces**: steps.md Step 3 gather-context 中的多仓检测部分
**Input**: 项目根目录路径、变更名称
**Execution**:
1. 读取 `docs/changes/<change>/repo_assignments.json`：
   - 文件存在且 `involved_repos` 数量 >= 1 -> 多仓模式，设置 `is_multi_repo = True`
   - 文件不存在 -> 执行单仓流程（不报错），设置 `is_multi_repo = False`
   - 文件存在但 `involved_repos` 数量 < 1 -> 执行单仓流程（不报错），设置 `is_multi_repo = False`
2. 多仓模式下，解析 `repo_assignments.json` 中的 `involved_repos`、`anchor_repos`、`expanded_repos`、`expansion_reason` 字段
3. 读取 `docs/relationship.md` 获取子仓列表，确认与 `repo_assignments.json` 一致
4. 多仓环境校验（对 explore 阶段的确认）：
   - **仓库范围**：设计是否覆盖 proposal.md 第6节确认的所有涉及仓库
   - **接口协调**：跨仓库接口设计与 proposal.md 中接口契约是否一致
   - **边界清晰**：tasks.md 中的任务是否按仓库边界清晰拆分
**Output**: is_multi_repo 标志 + involved_repos 列表
**Checkpoint**: repo_assignments.json 已读取，多仓/单仓环境已判定

## M-2: 各仓按仓生成
**Replaces**: steps.md Step 8 generate-artifacts（单仓步骤）
**Input**: repo_assignments.json 中的 involved_repos、delta_spec.md（各仓）、language-specific design specifications
**Execution**:
1. 读取 `docs/changes/<change>/repo_assignments.json` 获取 involved_repos
2. **读取brainstorming生成的design.md**（对齐SKILL.md Phase 1.5）：
   - 读取 `docs/changes/<change>/.brainstorming_output` 元数据文件
   - 如果文件存在，解析 `design_doc_path` 字段，读取对应的design.md文件
   - design.md内容作为delta_design.md的参考输入（架构设计、组件设计、数据流、接口设计）
   - 如果`.brainstorming_output`不存在，说明brainstorming未执行，跳过此步骤（不影响后续）
3. **确认延迟的实现层面问题**（impl_questions_for_design.json，对齐SKILL.md Phase 1.6）：
   a. 读取 `impl_questions_for_design.json`（`docs/changes/<change>/impl_questions_for_design.json`）
   b. 如果文件不存在，说明core-explore未延迟实现层面问题，跳过步骤3
   c. **【强制】逐条向用户展示延迟问题并确认决策** — 每次只展示一个deferred_item，使用AskUserQuestion让用户确认设计方向：
      ```
      AskUserQuestion({
        questions: [{
          question: "实现层面延迟问题 [{repo}#{id}] ({current}/{total}): {title}\n描述: {description}\n建议方向: {design_consideration}\n请确认设计方向：",
          header: "IMPL确认",
          options: [
            { label: "采纳建议", description: "采用design_consideration中的建议方向" },
            { label: "自定义方向", description: "指定其他设计方案" },
            { label: "延后处理", description: "在代码实现阶段再决定，不在设计文档中体现" }
          ]
        }]
      })
      ```
   d. **【禁止】一次展示多条延迟问题** — 必须逐条滚动确认，避免信息过载
   e. **【禁止】使用multiSelect=true** — 每条延迟问题只能选择一个方向
   f. 记录确认结果到内存中，供步骤4生成delta_design.md时使用：
      - 用户选择"采纳建议" → 将design_consideration内容写入delta_design.md对应章节
      - 用户选择"自定义方向" → 将用户指定的方案写入delta_design.md
      - 用户选择"延后处理" → 不在delta_design.md中体现，在delta_design.md"风险与对策"或"待解决问题"章节标注该延迟问题及建议方向，供core-apply参考
4. **【强制】使用子代理并行生成各仓设计文档**：

   **子代理类型选择**（按优先级尝试）：
   - P0: `subagent_type="general"` — 通用代理
   - **禁止因子代理类型不可用而回到主会话直接生成文档**

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属设计文档生成代理。请为 {repo} 仓生成以下3份设计文档：

   输入文件（必须全部读取，各文件消费用途如下）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | delta_spec.md | {repo}/docs/changes/<change>/delta_spec.md | **核心输入**：提取需求内容（ADDED/MODIFIED/REMOVED），delta_design.md的每个设计模块必须映射到delta_spec的需求ID |
   | 2 | 全局spec.md | {repo}/docs/specs/spec.md（如存在） | 理解项目全局规格和模块关系，确保设计不与现有规格冲突；**术语约束**：delta_design.md中所有术语必须与spec.md"领域术语"保持一致 |
   | 3 | 全局design.md | {repo}/docs/specs/design.md（如存在） | 提取全局架构设计和技术选型，确保设计遵循现有架构；**决策约束**：设计必须遵守design.md"设计决策"中已有记录，推翻需显式标注理由 |
   | 4 | shared_context.md | docs/changes/<change>/shared_context.md | **多仓关键输入**：总体功能清单、跨仓接口清单、不在范围内——delta_design.md的跨仓接口章节必须与shared_context.md字节级一致 |
   | 5 | cross_repo_contracts.json | docs/changes/<change>/clarifications/cross_repo_contracts.json | 跨仓接口契约定义——如果本仓是定义仓，delta_design.md必须包含该接口的实现设计；如果是消费仓，必须包含调用引用 |
   | 6 | 探索蒸馏文件 | docs/changes/<change>/drafts/{repo}.md | **核心参考**：包含该仓的架构图、集成点、影响点、跨仓依赖——delta_design.md的组件设计必须覆盖探索发现的集成点和影响点 |
   | 7 | brainstorming design.md | （主会话传入摘要内容） | 架构设计、组件设计、数据流、接口设计、关键决策——将design.md对应内容整合到delta_design.md |
   | 8 | impl_questions确认结果 | （主会话传入该仓相关项） | 用户已确认的实现层面延迟问题——采纳的必须在delta_design.md对应章节回应，延后的在delta_design.md"风险与对策"或"待解决问题"章节标注 |
   | 9 | design-principles.md | {skill_dir}/references/design-principles.md | **原则约束（必读）**：10条设计原则（P-1~P-10），delta_design.md每个章节必须体现"与delta_design章节的映射"表中所列原则，违反=设计文档不合格 |
   | 10 | design-views.md | {skill_dir}/references/design-views.md | **视图约束（必读）**：4个必须视图+5个条件视图+视图质量约束，delta_design.md必须产出§1必须视图和§2条件视图（按触发条件），空壳图=不合格 |

   **路径说明**：{skill_dir} 为 core-design 技能安装目录，主会话在构造子代理 prompt 时必须将 {skill_dir} 替换为实际绝对路径（解析方式见 SKILL.md Reference文件路径解析章节）。

   输出文件（必须全部生成）：
   - {repo}/docs/changes/<change>/delta_design.md
   - {repo}/docs/changes/<change>/tasks.md
   - {repo}/docs/changes/<change>/delta_test_design.md

   生成要求：
   - delta_design.md每个设计模块必须包含"对应需求"字段，映射到delta_spec.md的需求ID
   - 将design.md的架构设计、组件设计等信息整合到delta_design.md
   - 跨仓接口章节必须与shared_context.md和cross_repo_contracts.json一致
   - 探索蒸馏文件中的集成点和影响点必须在delta_design.md中体现
   - impl_questions中用户确认的延迟问题必须在delta_design.md对应章节中回应
   - tasks.md使用checkbox格式 `- [ ]`，每个代码生成任务必须包含以下字段：
     - **编程语言**: <java/cpp/go/python/javascript/typescript/other>
     - **关联需求**: <需求ID>
     - **验收标准**: <完成标准>
     - **设计锚点**: <#3.1 #2.2 #1.1:约束 #1.2:证据驱动>
   - 设计锚点格式规范：
     - 章节锚点：`#X.X` → 引用 delta_design.md 第 X.X 章（如 `#3.1`）
     - 关键词锚点：`#X.X:关键词` → 引用第 X.X 章中包含关键词的段落（如 `#1.1:约束`）
     - 通配符锚点：`#4.x:*` → 引用第 4.x 节所有子章节
   - 设计锚点优先级：P0=详细设计章节(#3.x)+架构锚点(#2.1/#2.2)、P1=约束锚点(#1.1:约束)+原则锚点(#1.2:原则名)、P2=流程锚点(#4.x:流程名)
   - 生成每个代码生成任务时，从delta_design.md中提取关联章节作为设计锚点（参考SKILL.md Phase 8.5锚点提取流程）
   - **【强制】tasks.md仅包含代码生成任务（1.x），禁止包含Code Review任务（2.x）和单元测试任务（3.x~7.x）** — 多仓模式下Code Review和UT由core-apply M-4/M-5子代理按仓独立执行，不由tasks.md驱动
   - delta_test_design.md中每个测试用例必须包含TC编号（如TC001），供core-apply UT生成环节引用
   - 禁止保留未填充的占位符 `<...>`
   - **【强制】对照 design-principles.md（输入#9）**：delta_design.md 每个章节必须体现 design-principles.md 中"与 delta_design 章节的映射"表所列原则。**子代理必须在生成前先读取该文件**——主会话 GATE 加载的内容不传递给子代理
   - **【强制】对照 design-views.md（输入#10）**：delta_design.md 必须产出 design-views.md §1 必须视图和 §2 条件视图（按触发条件）。**子代理必须在生成前先读取该文件**——主会话 GATE 加载的内容不传递给子代理
   - **【强制】术语约束**：delta_design.md 中所有术语必须与 spec.md "领域术语"保持一致；如需引入新术语，必须同时更新 spec.md "领域术语"章节
   - **【强制】决策约束**：设计必须遵守 design.md "设计决策"中已有记录；如设计需要推翻已有决策，必须在 delta_design.md 的"设计决策"章节显式标注推翻理由

   当前变更：{change_name}
   项目根目录：{project_root}
   ```

   **并发规则**（对齐core-explore M-2）：
   - **并发上限**：同时运行的子代理数量**不得超过3个**（5个并行token消耗太快，极易引发模型限流）
   - 如果涉及仓数量<=3：使用 `run_in_background=True` 一次性并行启动所有子代理
   - 如果涉及仓数量>3：分批启动，每批最多3个子代理，完成一个立即启动下一个
   - 所有子代理完成后输出强制检查点

   **容错机制**：
   - 子代理失败 -> **重试1次**（使用同类型或降级类型子代理）
   - 重试仍失败 -> 标记"generation_incomplete"，主会话补充生成**仅该失败仓**的文档
   - 部分成功 -> 已成功仓不受影响，继续后续流程

5. 输出多仓文档读取确认（强制检查点）：
   ```
   多仓文档读取确认：
   - [x] docs/relationship.md 已读取
   - [x] brainstorming design.md 已读取（如.brainstorming_output存在）
   - [x] impl_questions_for_design.json 已读取 + 用户确认已完成（如文件存在）
   - [x] drafts/{repo}.md 各仓探索蒸馏文件已读取
   - [x] design-principles.md 已读取（主会话 GATE + 子代理输入#9）
   - [x] design-views.md 已读取（主会话 GATE + 子代理输入#10）
   - [x] repo_a/docs/specs/spec.md 已读取（如存在）
   - [x] repo_a/docs/specs/design.md 已读取（如存在）
   - [x] repo_b/docs/specs/spec.md 已读取（如存在）
   - [x] repo_b/docs/specs/design.md 已读取（如存在）
   ```
6. 若未执行或遗漏，**必须回退重新读取**
7. 跨仓归档引用解析规则：
   - 引用中包含路径（如 `docs/archive/...`）-> 按路径读取归档目录下的 `delta_design.md` 和 `delta_spec.md`
   - 多仓环境：路径可能指向子仓（如 `repoA/docs/archive/...`），需按路径读取对应子仓的归档文件
**Output**: 各涉及仓的 `delta_design.md`、`tasks.md`、`delta_test_design.md`
**Checkpoint**: 所有涉及仓的设计文档已生成 + 多仓文档读取确认已输出 + impl_questions用户确认已完成

## M-3: 各仓审查并行执行（subagent并行 + 用户决策升级）

**适用阶段**：Phase 9（design-traceability L2/L3）、Phase 10（design-doc-reviewer审查）
**设计决策**：各仓审查是仓内独立操作，使用subagent并行执行以提升效率。当子代理遇到需要用户决策的问题时，通过升级机制交由主会话处理。

**【强制】Phase 9（cross-doc-checker）和Phase 10（design-doc-reviewer）是两个不同的审查阶段，必须按顺序依次执行**：
- **Phase 9先执行**：cross-doc-checker验证追溯链（delta_spec→delta_design→tasks），使用L2/L3层CHECK-ID集合
- **Phase 10后执行**：design-doc-reviewer审查文档质量（章节完整性/模糊词/视图完整性等），使用R7~R12 CHECK-ID集合
- **禁止混淆**：两个skill的CHECK-ID集合完全不同，不可互相替代。禁止在Phase 9调用design-doc-reviewer，禁止在Phase 10调用cross-doc-checker

**执行方式**：

### M-3a: Phase 9 — cross-doc-checker L2/L3 追溯验证

1. **使用子代理并行执行各仓L2/L3追溯验证**：

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属追溯验证代理。请对 {repo} 仓执行 cross-doc-checker L2/L3 追溯验证：

   审查对象：
   - {repo}/docs/changes/<change>/delta_design.md
   - {repo}/docs/changes/<change>/tasks.md
   - {repo}/docs/changes/<change>/delta_test_design.md

   验证步骤：
   1. 使用 Skill tool 调用 cross-doc-checker <change-name> --layer L2（**禁止调用design-doc-reviewer替代**，禁止自行用Grep/Read替代skill调用）
   2. 读取L2验证输出的findings列表
   3. 如果存在ERROR级finding，执行自动修复（最多3轮）：
      - delta_spec需求未在delta_design中映射 → 在delta_design.md中补充该需求的设计章节和"对应需求"字段
      - 截断/占位符 → 替换为具体内容
   4. L2修复完成后，重新调用 Skill tool: cross-doc-checker <change-name> --layer L2 验证
   5. L2通过后，使用 Skill tool 调用 cross-doc-checker <change-name> --layer L3
   6. 读取L3验证输出的findings列表
   7. 如果存在ERROR级finding，执行自动修复（最多3轮）：
      - 设计模块未在tasks中覆盖 → 在tasks.md中补充对应任务
      - 截断/占位符 → 替换为具体内容
   8. L3修复完成后，重新调用 Skill tool: cross-doc-checker <change-name> --layer L3 验证
   9. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表

   当前变更：{change_name}
   项目根目录：{project_root}

   返回格式：
   - 全部通过：status=PASSED, L2_findings=[...], L3_findings=[...]
   - 自动修复成功：status=FIXED, L2_fixes_summary=[...], L3_fixes_summary=[...]
   - 需要升级：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes, layer}]
   ```

2. **主会话后处理（所有M-3a子代理返回后执行）**：
   - 子代理返回PASSED/FIXED → 进入M-3b
   - 子代理返回ESCALATE → 执行用户决策升级机制（见下文）
   - 子代理执行失败 → 主会话直接调用 cross-doc-checker Skill 执行（降级策略）

3. **并发规则**（同M-2步骤4）：
   - 并发上限3个子代理
   - 分批启动（每批最多3个）
   - 所有子代理完成后汇总结果

### M-3b: Phase 10 — design-doc-reviewer 审查

**【强制前置】M-3a（cross-doc-checker L2/L3）必须全部通过后才能执行M-3b** — 追溯链验证不通过时，design-doc-reviewer审查无意义。

1. **使用子代理并行执行各仓design-doc-reviewer审查**：

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属文档审查代理。请对 {repo} 仓执行 design-doc-reviewer 审查：

   审查对象：
   - {repo}/docs/changes/<change>/delta_design.md
   - {repo}/docs/changes/<change>/delta_test_design.md
   - {repo}/docs/changes/<change>/tasks.md

   审查步骤：
   1. 使用 Skill tool 调用 design-doc-reviewer <change-name>（**禁止调用cross-doc-checker替代**，禁止自行用Grep/Read替代skill调用）
   2. 读取审查输出的findings列表
   3. 如果存在ERROR级finding，执行自动修复（最多3轮）：
      - 必需章节缺失 → 补充缺失章节
      - 截断/占位符 → 替换为具体内容
      - 验收条件缺失 → 补充可判定的验收条件
      - 视图缺失 → 补充PlantUML图
   4. 修复后重新调用 Skill tool: design-doc-reviewer <change-name> 验证
   5. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表

   当前变更：{change_name}
   项目根目录：{project_root}

   返回格式：
   - 全部通过：status=PASSED, findings=[...]
   - 自动修复成功：status=FIXED, fixes_summary=[...]
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}]
   ```

2. **主会话后处理（所有M-3b子代理返回后执行）**：
   - 子代理返回审查通过 → 进入 Phase 11
   - 子代理返回【用户意图类】finding → 主会话与用户交互澄清，完成后再次派发子代理执行审查
   - 子代理返回3轮FAIL/ESCALATE → 执行用户决策升级机制（见下文）
   - 子代理执行失败 → 主会话直接调用 design-doc-reviewer Skill 执行（降级策略）

3. **并发规则**（同M-2步骤4）：
   - 并发上限3个子代理
   - 分批启动（每批最多3个）
   - 所有子代理完成后汇总结果

### 用户决策升级机制（M-3a和M-3b共用）

当子代理返回ESCALATE状态时，主会话执行以下流程：
a. **汇总所有升级问题**：收集所有子代理返回的blocking_issues
b. **使用AskUserQuestion展示给用户**：
   ```
   AskUserQuestion({
     questions: [{
       question: "仓 {repo} 的审查发现以下问题经3轮自动修复仍未解决：\n{blocking_issue_description}\n请选择处理方式：",
       header: "审查升级",
       options: [
         { label: "人工修复", description: "暂停该仓审查，由您手动修复后继续" },
         { label: "忽略继续", description: "标注为WARNING，继续后续流程" },
         { label: "重新审查", description: "重新启动该仓的审查子代理" }
       ]
     }]
   })
   ```
c. **传递用户决策**：将用户选择传回子代理（重新启动子代理并传入决策上下文）
d. **决策结果记录**：记录用户决策到变更目录的审查报告中

**Output**: 各仓审查报告（汇总PASSED/FIXED/ESCALATE状态 + 用户决策记录）
**Checkpoint**: M-3a所有涉及仓的L2/L3追溯验证已完成 + M-3b所有涉及仓的design-doc-reviewer审查已完成（含用户决策升级处理）

## Contracts Lifecycle (本 skill 职责)

| 阶段 | 操作 | status转换 | 副本刷新 |
|------|------|-----------|----------|
| M-2 按仓生成 | 设计阶段发现新接口，追加contract | -> `proposed` | 刷新definition_repo和consumer_repos的副本 |
| M-2 按仓生成 | 设计完成，接口确认 | `proposed` -> `confirmed` | 刷新涉及仓副本 |
