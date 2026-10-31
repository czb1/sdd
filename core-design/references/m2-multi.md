# M-2: 各仓按仓生成（多仓模式指令文件）

> 本文件为 M-2 各仓按仓生成的指令文件（多仓版）。仅在多仓模式 + Phase 8 进入 M-2 时被 Read。

**Replaces**: steps.md Step 8 generate-artifacts（单仓步骤）
**Input**: repo_assignments.json 中的 involved_repos、delta_spec.md（各仓）、language-specific design specifications

## Execution

### 步骤 1: 读取 involved_repos

读取 `docs/changes/<change>/repo_assignments.json` 获取 involved_repos

### 步骤 2: 读取 brainstorming 生成的 design.md

（对齐 SKILL.md Phase 6）
- 读取 `docs/changes/<change>/.brainstorming_output` 元数据文件
- 如果文件存在，解析 `design_doc_path` 字段，读取对应的 design.md 文件
- design.md 内容作为 delta_design.md 的参考输入（架构设计、组件设计、数据流、接口设计）
- 如果 `.brainstorming_output` 不存在，说明 brainstorming 未执行，跳过此步骤（不影响后续）

### 步骤 3: 确认延迟的实现层面问题

（impl_questions_for_design.json，对齐 SKILL.md Phase 6 步骤5）

a. 读取 `impl_questions_for_design.json`（`docs/changes/<change>/impl_questions_for_design.json`）
b. 如果文件不存在，说明 core-explore 未延迟实现层面问题，跳过步骤 3
c. **【强制】逐条向用户展示延迟问题并确认决策** — 每次只展示一个 deferred_item，使用 AskUserQuestion 让用户确认设计方向：
   ```
   AskUserQuestion({
     questions: [{
       question: "实现层面延迟问题 [{repo}#{id}] ({current}/{total}): {title}\n描述: {description}\n建议方向: {design_consideration}\n请确认设计方向：",
       header: "IMPL确认",
       options: [
         { label: "采纳建议", description: "采用 design_consideration 中的建议方向" },
         { label: "自定义方向", description: "指定其他设计方案" },
         { label: "延后处理", description: "在代码实现阶段再决定，不在设计文档中体现" }
       ]
     }]
   })
   ```
d. **【禁止】一次展示多条延迟问题** — 必须逐条滚动确认，避免信息过载
e. **【禁止】使用 multiSelect=true** — 每条延迟问题只能选择一个方向
f. 记录确认结果到内存中，供步骤 4 生成 delta_design.md 时使用：
   - 用户选择"采纳建议" → 将 design_consideration 内容写入 delta_design.md 对应章节
   - 用户选择"自定义方向" → 将用户指定的方案写入 delta_design.md
   - 用户选择"延后处理" → 不在 delta_design.md 中体现，在 delta_design.md "风险与对策"或"待解决问题"章节标注该延迟问题及建议方向，供 core-apply 参考

### 步骤 4: 子代理并行生成各仓设计文档

**【强制】使用子代理并行生成各仓设计文档**：

**子代理类型选择**（按优先级尝试）：
- P0: `subagent_type="general"` — 通用代理
- **禁止因子代理类型不可用而回到主会话直接生成文档**

#### 子代理任务描述模板

```
你是仓 {repo} 的专属设计文档生成代理。请为 {repo} 仓生成以下3份设计文档：

输入文件（必须全部读取，各文件消费用途如下）：

**【强制】主仓解析分发（T2.10）**：主会话在进入 M-2 前必须先执行 `python -m core_templates resolve <artifact_id> --materialize <change_dir>`（每个 artifact 一次：delta_design/delta_test_design/tasks，所有子仓共享同一物化文件），将 L1+L2+主仓 L3 解析后有效模板物化到 `<change_dir>/.templates/resolved/<artifact>.md`。**每次执行 M-2 都必须重新物化**（覆盖式写入），确保物化文件反映用户层模板的最新修改——**禁止因物化文件已存在而跳过物化**。
- **【禁止】子代理各自解析模板层**：子代理 prompt 中必须明确禁止子代理用 `cwd` 解析各仓 L3 模板（会命中各仓本地 L3 而非主仓 L3，导致章节不一致）。
- **【强制】主会话物化 + 输入表传递**：主会话将解析结果物化后，通过输入表第 11 行（解析后有效模板）将物化文件绝对路径传递给子代理，子代理仅 Read 该文件获取章节骨架。

| # | 文件 | 路径 | 消费用途 |
|---|------|------|----------|
| 1 | delta_spec.md | {repo}/docs/changes/<change>/delta_spec.md | **核心输入**：提取需求内容（ADDED/MODIFIED/REMOVED），delta_design.md 的每个设计模块必须映射到 delta_spec 的需求 ID |
| 2 | 全局 spec.md | {repo}/docs/specs/spec.md（如存在） | 理解项目全局规格和模块关系，确保设计不与现有规格冲突；**术语约束**：delta_design.md 中所有术语必须与 spec.md "领域术语"保持一致 |
| 3 | 全局 design.md | {repo}/docs/specs/design.md（如存在） | 提取全局架构设计和技术选型，确保设计遵循现有架构；**决策约束**：设计必须遵守 design.md "设计决策"中已有记录，推翻需显式标注理由 |
| 4 | shared_context.md | docs/changes/<change>/shared_context.md | **多仓关键输入**：跨仓接口清单——delta_design.md 优先注入到 resolved 模板已有"跨仓接口"H2/H3；若模板无此章节，按规则2 追加独立 H2 `## N、跨仓上下文` 承载（详见下方"生成要求"规则2） |
| 5 | cross_repo_contracts.json | docs/changes/<change>/clarifications/cross_repo_contracts.json | 跨仓接口契约定义——如果本仓是定义仓，delta_design.md 必须包含该接口的实现设计；如果是消费仓，必须包含调用引用 |
| 6 | 探索蒸馏文件 | docs/changes/<change>/drafts/{repo}.md | **核心参考**：包含该仓的架构图、集成点、影响点、跨仓依赖——delta_design.md 的组件设计必须覆盖探索发现的集成点和影响点 |
| 7 | brainstorming design.md | （主会话传入摘要内容） | 架构设计、组件设计、数据流、接口设计、关键决策——将 design.md 对应内容整合到 delta_design.md |
| 8 | impl_questions 确认结果 | （主会话传入该仓相关项） | 用户已确认的实现层面延迟问题——采纳的必须在 delta_design.md 对应章节回应，延后的在 delta_design.md "风险与对策"或"待解决问题"章节标注 |
| 9 | design-principles.md | {skill_dir}/references/design-principles.md | **原则约束（必读）**：10 条设计原则（P-1~P-10），delta_design.md 每个章节必须体现"与 delta_design 章节的映射"表中所列原则，违反=设计文档不合格 |
| 10 | design-views.md | {skill_dir}/references/design-views.md | **视图约束（必读）**：4 个必须视图+5 个条件视图+视图质量约束，delta_design.md 必须产出 §1 必须视图和 §2 条件视图（按触发条件），空壳图=不合格 |
| 11 | 解析后有效模板（delta_design/delta_test_design/tasks） | docs/changes/<change>/.templates/resolved/delta_design.md 等 | **章节骨架（最高优先级基准）**：由主会话 `resolve --materialize` 物化的解析后有效模板。子代理**必须严格按其 H2 + 已有 H3 骨架生成产物**，不得增删/重编号/从归档或兄弟仓恢复章节；多仓场景 shared_context 注入按下方"生成要求"规则2 处理 |

**路径说明**：{skill_dir} 为 core-design 技能安装目录，主会话在构造子代理 prompt 时必须将 {skill_dir} 替换为实际绝对路径（解析方式见 SKILL.md Reference 文件路径解析章节）。

输出文件（必须全部生成）：
- {repo}/docs/changes/<change>/delta_design.md
- {repo}/docs/changes/<change>/tasks.md
- {repo}/docs/changes/<change>/delta_test_design.md

生成要求：
- **规则1（强制契约）**：产物 H2 + resolved 模板已有 H3 必须与 `.templates/resolved/<artifact_id>.md` **完全一致**，不得增删/重编号/从归档或兄弟仓恢复被删章节
  - **【禁止篡改物化模板】物化模板文件 `.templates/resolved/<artifact_id>.md` 是只读基准，子代理禁止使用 Edit/Write 工具修改其内容**——包括重编号为连续、删除章节、修改标题文本。物化模板编号跳跃是用户裁剪后的合法状态，产物必须按物化模板原始编号生成。审查器将通过 re-resolve 物化到临时目录后 diff 检测篡改，发现篡改即 ERROR 并以临时物化文件为基准重新校验
- **规则2（多仓条件追加 H2）**：多仓场景下，shared_context.md `## 3. 跨仓接口清单` 注入到 delta_design.md 的处理：
  - **优先**：若 resolved 模板含"跨仓接口"相关 H2/H3（如"## 三、跨仓接口设计"或"### 3.x 跨仓接口"），将 shared_context.md `## 3. 跨仓接口清单` 字节级嵌入到该章节
  - **回退**：若 resolved 模板无"跨仓接口"相关 H2/H3（用户裁剪掉），在 resolved 模板所有 H2 末尾追加独立 H2 `## N、跨仓上下文 (Multi-Repo Context)`（N = 模板最大 H2 编号 + 1，中文数字继续），其下追加 `### N.1 跨仓接口清单` ← 字节级嵌入 shared_context.md `## 3. 跨仓接口清单` 完整内容
  - **单仓场景不追加该 H2**（本规则仅多仓模式生效）
- 章节结构按解析后有效模板的章节骨架（H2 级标题，由输入文件 #11 提供），不固定章节数
- 重新生成任务时保留任务编号、完成状态及已有扩展字段。
- delta_design.md 每个设计模块必须包含"对应需求"字段，映射到 delta_spec.md 的需求 ID
- 将 design.md 的架构设计、组件设计等信息整合到 delta_design.md
- 探索蒸馏文件中的集成点和影响点必须在 delta_design.md 中体现
- impl_questions 中用户确认的延迟问题必须在 delta_design.md 对应章节中回应
- tasks.md 使用 checkbox 格式 `- [ ]`，每个代码生成任务必须包含以下字段：
  - **编程语言**: <java/cpp/go/python/javascript/typescript/other>
  - **关联需求**: <需求ID>
  - **验收标准**: <完成标准>
  - **设计锚点**: <#3.1 #2.2 #1.1:约束 #1.2:证据驱动>
- **测试策略读取（生成 tasks.md 后、自检前，零交互）**：读取配置确定测试策略（对齐 SKILL.md Phase 8 测试策略读取）：
  1. 项目级：`<项目根>/docs/config.yaml` 的测试策略字段（优先；用户改这里即覆盖全局默认）
  2. 全局级：`~/.corespec/flow-config.json` 的顶层 `test_strategy`（默认值来源；core-init 生成项目 config.yaml 时参考此值，无项目级字段时生效）
  3. 缺省：`test-after`
  测试策略为 `tdd` 时，**调用派生脚本** `skills/core-design/scripts/tasks_tdd_deriver.py --change <change> --project-root {repo}` 对生成的 tasks.md 应用 tdd 差异（头部测试策略字段 / 每任务覆盖用例+测试文件路径+测试命令字段 / 依赖图节点标注），并保证全部 TC 被"覆盖用例"字段引用（派生脚本自检校验）；**生成顺序约束**：delta_test_design.md 必须先于 tasks.md 完成（对齐 SKILL.md Phase 8 测试策略读取的 tdd 分支），确保"覆盖用例"字段引用 TC 时有据可依
  测试策略为 `test-after` / 无字段（缺省）时：**不执行生成顺序约束**，按基线流程生成 delta_test_design.md 与 tasks.md（顺序与改造前一致）
- 设计锚点格式规范：
  - 章节锚点：`#X.X` → 引用 delta_design.md 第 X.X 章（如 `#3.1`）
  - 关键词锚点：`#X.X:关键词` → 引用第 X.X 章中包含关键词的段落（如 `#1.1:约束`）
  - 通配符锚点：`#4.x:*` → 引用第 4.x 节所有子章节
- 设计锚点优先级：P0=详细设计章节(#3.x)+架构锚点(#2.1/#2.2)、P1=约束锚点(#1.1:约束)+原则锚点(#1.2:原则名)、P2=流程锚点(#4.x:流程名)
- 生成每个代码生成任务时，从 delta_design.md 中提取关联章节作为设计锚点（参考 SKILL.md Phase 8 子步骤"剩余 artifact 循环"锚点提取流程）
- **【强制】tasks.md 仅包含代码生成任务（1.x），禁止包含 Code Review 任务（2.x）和单元测试任务（3.x~7.x）** — 多仓模式下 Code Review 和 UT 由 core-apply M-4/M-5 子代理按仓独立执行，不由 tasks.md 驱动
- delta_test_design.md 中每个测试用例必须包含 TC 编号（如 TC001），供 core-apply UT 生成环节引用
- 禁止保留未填充的占位符 `<...>`
- **【强制】对照 design-principles.md（输入#9）**：delta_design.md 每个章节必须体现 design-principles.md 中"与 delta_design 章节的映射"表所列原则。**子代理必须在生成前先读取该文件**——主会话 GATE 加载的内容不传递给子代理
- **【强制】对照 design-views.md（输入#10）**：delta_design.md 必须产出 design-views.md §1 必须视图和 §2 条件视图（按触发条件）。**子代理必须在生成前先读取该文件**——主会话 GATE 加载的内容不传递给子代理
- **【强制】术语约束**：delta_design.md 中所有术语必须与 spec.md "领域术语"保持一致；如需引入新术语，必须同时更新 spec.md "领域术语"章节
- **【强制】决策约束**：设计必须遵守 design.md "设计决策"中已有记录；如设计需要推翻已有决策，必须在 delta_design.md 的"设计决策"章节显式标注推翻理由

当前变更：{change_name}
项目根目录：{project_root}
```

#### 并发规则

（对齐 core-explore M-2）
- **并发上限**：同时运行的子代理数量**不得超过 3 个**（5 个并行 token 消耗太快，极易引发模型限流）
- 如果涉及仓数量 <= 3：使用 `run_in_background=True` 一次性并行启动所有子代理
- 如果涉及仓数量 > 3：分批启动，每批最多 3 个子代理，完成一个立即启动下一个
- 所有子代理完成后输出强制检查点

#### 容错机制

- 子代理失败 -> **重试 1 次**（使用同类型或降级类型子代理）
- 重试仍失败 -> 标记 "generation_incomplete"，主会话补充生成**仅该失败仓**的文档
- 部分成功 -> 已成功仓不受影响，继续后续流程

### 步骤 5: 输出多仓文档读取确认（强制检查点）

```
多仓文档读取确认：
- [x] docs/relationship.md 已读取
- [x] brainstorming design.md 已读取（如 .brainstorming_output 存在）
- [x] impl_questions_for_design.json 已读取 + 用户确认已完成（如文件存在）
- [x] drafts/{repo}.md 各仓探索蒸馏文件已读取
- [x] design-principles.md 已读取（主会话 GATE + 子代理输入#9）
- [x] design-views.md 已读取（主会话 GATE + 子代理输入#10）
- [x] repo_a/docs/specs/spec.md 已读取（如存在）
- [x] repo_a/docs/specs/design.md 已读取（如存在）
- [x] repo_b/docs/specs/spec.md 已读取（如存在）
- [x] repo_b/docs/specs/design.md 已读取（如存在）
```

若未执行或遗漏，**必须回退重新读取**。

### 步骤 6: 跨仓归档引用解析规则

- 引用中包含路径（如 `docs/archive/...`）-> 按路径读取归档目录下的 `delta_design.md` 和 `delta_spec.md`
- 多仓环境：路径可能指向子仓（如 `repoA/docs/archive/...`），需按路径读取对应子仓的归档文件

### 步骤 7: 剩余 artifact 循环委托（T5.6）

> **M5b T5.6 新增**：生成完内置 5 artifact 后，**必须**遍历有效 schema.yaml 的剩余 artifact（非内置），委托 M-2 子代理按仓生成。**本步骤为强制执行，禁止跳过**——即使"预期无非内置 artifact"，也必须先调 `load_schema()` 获取清单确认后才能跳过。

**【强制执行流程】**（M-2 各仓内置 artifact 生成完成后立即执行）：
1. **【强制】主会话调 `load_schema('spec-driven')` 获取有效 schema.yaml 的 artifacts id 清单**
2. 从清单中筛除内置 5 artifact（`proposal` / `delta_spec` / `delta_design` / `delta_test_design` / `tasks`），剩余即为非内置 artifact
3. **【DAG 分层过滤】** 只生成 `requires` 字段含 `delta_design` 或更下游 artifact 的非内置 artifact（属 core-design 环节）。`requires: []` 或 `requires` 仅含 proposal/delta_spec 的非内置 artifact（如 `proposal-data`）属 core-explore 环节，**core-design 跳过不生成**（已在 core-explore T5.2 生成）
4. **存在符合 DAG 分层的非内置 artifact 时**：主会话对每个剩余 artifact，先 `python -m core_templates resolve <artifact_id> --materialize <change_dir>` 物化模板（所有子仓共享同一物化文件，**禁止篡改物化模板**），再委托子代理按仓并行生成（参考步骤 4 子代理任务模板的"生成要求"段，artifact 维度替换），子代理使用 Write 工具写入 `<repo_path>/docs/changes/<change>/<artifact_id>.md`
5. **无符合 DAG 分层的非内置 artifact 时**：记录"无剩余 artifact（core-design 分层），T5.6 跳过"并继续
6. **【禁止】**：禁止不调 `load_schema()` 就声称"无非内置 artifact"；禁止跳过本步骤直接进入下一阶段；禁止生成属 core-explore 环节的 artifact

**触发条件**（信息性说明，非豁免理由）：
- L2 schema.yaml 声明了非内置 artifact（M5b 开放后）
- `load_schema()` 返回的 artifacts 列表中存在 `REQUIRED_BUILTIN_ARTIFACTS` 之外的 artifact id，且其 `requires` 含 `delta_design` 或更下游 artifact

**Output**: 各涉及仓的 `delta_design.md`、`tasks.md`、`delta_test_design.md`（含新增 artifact）
**Checkpoint**: 所有涉及仓的设计文档已生成（存在性自检通过）+ 多仓文档读取确认已输出 + impl_questions 用户确认已完成 + 新增 artifact 已按物化骨架生成；骨架/跨仓接口一致性/规范校验由 `design-doc-reviewer` 审查阶段执行（CHECK-R7.1 T1.10a 规则1 + T1.10b 规则2）

