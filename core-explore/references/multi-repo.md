# Multi-Repo Enhancement: core-explore

**Skill**: core-explore
**Depends On**: repo_assignments.json
**Step Mapping Authority**: 本文档Section 2.2（M-编号与steps.md编号的对应关系以Section 2.2映射表为准）

## Prerequisites
1. repo_assignments.json 存在
2. involved_repos >= 2
3. 已输出 "GATE PASSED: references/multi-repo.md loaded"

## M-1: 多仓检测
**Replaces**: 单仓模式context-completion阶段（多仓模式下context-completion阶段已省略，M-1直接承接parse-design-docs）

**【连续执行规则】**：M-1~M-8各阶段之间**禁止等待用户"继续"输入** — 阶段完成后自动进入下一阶段。唯一需要用户交互的节点：M-1（用户确认涉及仓列表）、M-3（brainstorming澄清中的用户交互+最终方案确认）、M-7/M-8（ESCALATE升级时的用户决策）。其他阶段转换必须自动连续执行，仅在遇到阻塞错误时才暂停。**【禁止】写入result.json后输出"等待CMS推进"停止** — 必须立即开始下一阶段执行。
**Input**: 项目根目录路径
**Execution**:
1. 读取 `docs/changes/<change>/repo_assignments.json`：
   - 文件存在且 `involved_repos` 数量 > 1 -> 多仓模式，直接使用其中 `involved_repos` 和 `expansion_reason`，跳过步骤2-5
   - 文件不存在 -> 执行步骤2-5进行多仓检测
2. 调用 `detect_multi_repo(project_root)` 执行三级降级链检测：
   - P0: 读取 `docs/graph.json`，`mode=="multi-repo"` 则 `is_multi_repo=true`，`repos=graph.repos`，`source="graph.json"`
   - P1: 读取 `docs/language.json`，`keys>1` 则 `is_multi_repo=true`，`repos=list(keys)`，`source="language.json"`
   - P2: 目录扫描，包含 `.git` 的子目录数>=2 则 `is_multi_repo=true`，`repos=[子目录名]`，`source="directory_scan"`
3. graph.json JSON解析失败降级P1，language.json JSON解析失败降级P2，所有数据源不可用返回 `is_multi_repo=false`
4. 检测到多仓后，执行涉及仓分析三步流程：
   - **Agent语义初判**：读取需求+各仓spec/design，确定锚定仓（需求直接涉及的仓）
   - **graph.json依赖扩展**：从锚定仓沿 `cross_repo_edges` 扩展，调用 `expand_involved_repos(project_root, anchor_repos)`，聚合权重>=10的关联仓纳入 `expanded_repos`
   - **【强制】AskUserQuestion让用户确认涉及仓**：
     - 展示：锚定仓列表 + 扩展仓列表 + 每个扩展仓的推断依据（边权重）
     - 用户可增删调整涉及仓
     - **未获用户确认，禁止进入M-2及后续阶段**
     - 确认后调用 `write_repo_assignments()` 生成 `repo_assignments.json`
5. 调用 `write_repo_assignments(project_root, change_name, anchor_repos, expanded_repos, expansion_reason)` 生成 `repo_assignments.json`，包含 `change_name`、`involved_repos`、`confirmed_at`、`anchor_repos`、`expanded_repos`、`expansion_reason`
6. 检测来源非graph.json时，Agent应提示用户执行core-init以获取更精确的检测数据
7. 若检测为单仓（`is_multi_repo=false`），则不生成 `repo_assignments.json`，执行单仓流程（不报错）
**Output**: `repo_assignments.json`（写入 `docs/changes/<change>/repo_assignments.json`）
**Checkpoint**: repo_assignments.json 存在且 involved_repos >= 2
**自动继续**：M-1完成后**立即进入M-2**，禁止输出"等待CMS推进"后停止。写入M-1 result.json后，直接开始M-2子代理并行探索，不需要等待用户"继续"。

## M-2: 并行子仓探索
**Replaces**: 单仓模式context-completion中的子仓文档读取部分 + 历史归档打分
**Input**: repo_assignments.json 中的 involved_repos
**Execution**:
1. **【强制】使用子代理并行探索各仓**：

   **子代理类型**：`subagent_type="general"`
   - **【强制】必须使用general** — explore类型子代理**没有Write工具**（explore的工具列表排除了Write），无法写入drafts文件。只有general类型拥有Write工具，能直接写入文件。注意：Agent tool的subagent_type参数值为`"general"`（不是`"general-purpose"`，`"general-purpose"`会导致子代理启动失败）
   - **禁止因子代理类型不可用而回到主会话直接生成drafts**

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属探索代理。请对 {repo} 仓执行以下5步探索：
   1. 读取全局文档：{repo}/docs/specs/spec.md、{repo}/docs/specs/design.md、{repo}/docs/archive/archive-index.md
   2. 探索代码库（好奇心驱动）：绘制架构图、找集成点、揭示隐含复杂性
   3. 识别影响范围：直接涉及点 + 隐含影响点
   4. 列出模糊点和冲突点（AMB-XXX格式）
   5. 识别跨仓依赖：出向/入向调用 + 接口契约

   当前变更：{change_name}
   项目根目录：{project_root}

   输出文件（【强制】必须使用Write工具写入，禁止使用Bash调用PowerShell/cp/echo等命令写文件）：
   - 使用Write工具写入：{project_root}/docs/changes/{change}/drafts/{repo}.md（架构图+集成点+影响点+跨仓依赖）
   - 使用Write工具写入：{project_root}/docs/changes/{change}/drafts/ambiguities_{repo}.md（AMB-XXX格式模糊点清单）
   - 写入后使用Read工具验证文件内容完整性
   ```
2. 子代理执行5步探索方法论：
   - **第一步 读取各仓本地文档**：`{repo}/docs/specs/spec.md`、`{repo}/docs/specs/design.md`、`{repo}/docs/archive/archive-index.md`
     - 注意：这里的文档路径是各子仓目录下的（如 `cm/docs/specs/spec.md`），**不是**项目根目录的
     - `{repo}/docs/archive/archive-index.md`：读取后对历史归档进行相关性打分（≥4分的归档需要在delta_spec中标注引用）
   - **第二步 探索代码库**（好奇心驱动）：绘制架构图、找集成点、揭示隐含复杂性
   - **第三步 识别影响范围**：直接涉及 + 隐含影响
   - **第四步 模糊点+冲突点清单**（按AMB-XXX格式模板输出）：
     ```markdown
     ## AMB-001: [模糊点标题]
     - **描述**: [模糊点的具体描述]
     - **候选理解**: [可能的理解方向]
     - **涉及仓**: [涉及的仓名，逗号分隔]
     ```
     **【强制】AMB条目必须使用 `## AMB-XXX:` 格式**（二级标题），冲突点使用 `## CON-XXX:` 格式，便于M-3子代理解析汇总。
   - **第五步 跨仓依赖识别**：出向/入向调用 + 接口契约
3. **【强制】并行启动子代理（最多3个并发）**：
   - **并发上限**：同时运行的子代理数量**不得超过3个**（5个并行token消耗太快，极易引发模型限流）
   - 如果涉及仓数量<=3：使用 `run_in_background=True` 一次性并行启动所有子代理
   - 如果涉及仓数量>3：分批启动，每批最多3个子代理：
     1. 启动第一批3个子代理（`run_in_background=True`）
     2. 使用 WaitSubagents 等待任一子代理完成
     3. 每完成一个子代理，立即启动下一个排队仓的子代理（保持并发数<=3）
     4. 重复直到所有仓探索完成
   - 所有子代理完成后输出强制检查点
4. 容错机制：
   - 子代理失败 -> **重试1次**（使用同类型或降级类型子代理）
   - 重试仍失败 -> 标记"exploration_incomplete"，主会话补充探索**仅该失败仓**
   - 部分成功 -> 已成功仓不受影响，继续后续流程
5. 读取 `docs/relationship.md` 获取子仓列表，遍历各子仓文档，分析跨仓规格和设计一致性
6. 输出多仓文档读取确认（强制检查点）：
   ```
   多仓文档读取确认：
   - [x] docs/relationship.md 已读取
   - [x] repo_a/docs/specs/spec.md 已读取（如存在）
   - [x] repo_a/docs/specs/design.md 已读取（如存在）
   - [x] repo_b/docs/specs/spec.md 已读取（如存在）
   - [x] repo_b/docs/specs/design.md 已读取（如存在）
   ```

**【禁止】**：
- 禁止在主会话中直接生成drafts文件（子代理是唯一合法的drafts生成者）
- 禁止顺序处理各仓（必须并行）
- 唯一例外：子代理重试1次后仍失败，才允许主会话补充探索该单个失败仓
- **禁止子代理使用Bash调用PowerShell/cp/echo/cat等命令写文件** — Windows环境下PowerShell heredoc（`@"..."@`）和bash heredoc（`cat << EOF`）极易因内容中的双引号/特殊字符/中文导致解析失败或文件截断。必须使用Write工具写入文件
- **禁止子代理以"只读任务"为由跳过文件写入** — M-2探索任务的最终目的是生成drafts文件，分析结果不写入文件等于任务失败

**Output**: `drafts/{repo}.md` + `drafts/ambiguities_{repo}.md`（每个涉及仓各一份）
**Checkpoint**: 所有涉及仓的 drafts 文件已生成（或标记 exploration_incomplete）
**自动继续**：M-2完成后**立即进入M-3**，禁止输出"等待CMS推进"后停止。写入M-2 result.json后，直接开始M-3步骤1（统一brainstorming澄清），不需要等待用户"继续"。

## M-3: 统一brainstorming澄清
**Replaces**: steps.md Step 8 requirement-clarification（单仓步骤）
**Input**: drafts/ambiguities_{repo}.md + drafts/{repo}.md + 需求信息

**设计决策**：采用**统一brainstorming调用**而非逐条/逐仓澄清，理由：
- brainstorming技能设计为**综合探索+交互式澄清**，传入完整上下文后能自动综合判断需求层面vs实现层面的问题
- 一次brainstorming调用可跨仓去重同一主题的重复问题（如5仓都有"trace开关作用域"）
- 对齐单仓模式：单仓只调用一次brainstorming（传入requirement_desc+design_doc_content+context_files+knowledge_results），多仓同样应只调用一次
- 实现层面的疑点由brainstorming自动识别并记录到impl_questions_for_design.json，留给core-design阶段处理
- 避免逐条调用导致50+次brainstorming调用，Agent因感知成本过高而跳过

**Execution**:

1. **【强制】收集所有上下文**：

   读取以下文件，汇总为brainstorming的输入：
   - **所有仓的ambiguities文件**：`docs/changes/<change>/drafts/ambiguities_{repo}.md`（每个涉及仓）
   - **所有仓的蒸馏文件**：`docs/changes/<change>/drafts/{repo}.md`（每个涉及仓）
   - **需求信息**：requirement_desc（从CoreAlm获取）、design_doc_content（从阶段4解析）
   - **知识检索结果**：knowledge_results（从5.3获取，如可用）

   **ambiguities汇总格式**（传入brainstorming的ambiguities_content参数）：
   ```markdown
   ## 多仓模糊点和冲突点汇总

   ### cm仓
   [ambiguities_cm.md的完整内容]

   ### common仓
   [ambiguities_common.md的完整内容]

   ...（每个涉及仓一个子章节，仓标题使用仓实际名称）
   ```

   **repo_drafts_summary格式**（传入brainstorming的repo_drafts_summary参数）：
   ```markdown
   ## 各仓探索摘要

   ### cm仓
   [cm.md的核心摘要：架构图+集成点+影响点+跨仓依赖]

   ### common仓
   [common.md的核心摘要]

   ...（每个涉及仓一个子章节）
   ```

2. **【强制】调用一次brainstorming**：

   使用Skill工具调用brainstorming，**对齐单仓模式SKILL.md 5.4步骤2的调用方式**：
   ```
   Skill(skill="brainstorming",
     requirement_id="<需求ID>",
     requirement_desc="<从CoreAlm获取的需求描述>",
     context_files=["docs/specs/spec.md", "docs/specs/design.md", "docs/relationship.md"],
     design_doc_content="<从阶段4获取的设计文档内容>",
     knowledge_results="<从5.3获取的云见知识>",
     ambiguities_content="<所有仓AMB/CON条目汇总，含仓标签>",
     repo_drafts_summary="<各仓蒸馏文件摘要>")
   ```

   **brainstorming的行为**：
   - 读取传入的ambiguities_content，自动识别需求层面（REQ）和实现层面（IMPL）的问题
   - 对REQ层面的问题：向用户逐题提问，进行苏格拉底式澄清
   - 对IMPL层面的问题：记录到impl_questions_for_design.json，不在澄清环节打扰用户
   - 跨仓重复的同一主题问题：合并提问，避免重复
   - 生成design.md到 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

   **【强制约束】**：
   - **必须调用一次brainstorming** — 不能跳过，不能用AskUserQuestion替代
   - **【绝对禁止】使用Agent tool启动brainstorming** — brainstorming必须通过Skill tool在主会话中调用，禁止通过Agent tool以任何subagent_type启动。Agent tool会将brainstorming放入子代理上下文，导致用户无法直接与brainstorming交互对话，苏格拉底式澄清完全失效
   - **【绝对禁止】将brainstorming折叠到SubAgent中执行** — brainstorming必须在主会话中与用户直接对话
   - **【绝对禁止】因"brainstorming需要用户交互不适合自动化"而跳过brainstorming调用** — brainstorming的交互式对话是其核心设计，不可跳过
   - **禁止使用AskUserQuestion直接生成A/B/C/D选项替代brainstorming** — Agent不得自行编写候选理解选项
   - **禁止因为"问题太多"或"大部分是实现细节"而跳过brainstorming** — brainstorming会自动过滤IMPL问题
   - **【subagent回退检测】**：如果执行过程中brainstorming被系统自动折叠到subagent执行（执行记录出现"SubAgent: brainstorming"），说明用户无法与brainstorming交互，此时**禁止等待subagent完成**或依赖其结果，必须在主会话中直接与用户进行苏格拉底式澄清（对齐SKILL.md步骤3a）

3. **【强制】brainstorming执行完毕后，呈现设计方案并让用户确认**（对齐单仓流程SKILL.md 5.4步骤8-10 — **用户确认必须先于后处理**）：

   基于brainstorming的澄清结果，**生成推荐设计方案**并呈现给用户。呈现维度**必须对齐单仓流程SKILL.md 5.4步骤8的设计方案维度**，在保留多仓信息基础上扩展：

   ```
   ## M-3 最终推荐方案

   ### 核心思路
   [一句话概括需求实现方向]

   ### 方案细节
   #### API变更
   [基于澄清结果的具体API接口设计]
   #### 数据流
   [核心数据流转路径，含各仓职责边界]
   #### 接口设计
   [跨仓接口契约、数据结构定义]

   ### 兼容性说明
   [版本兼容、升级影响、配置兼容等，如涉及]

   ### 关键决策（按仓汇总）
   | 仓 | 决策项 | 选择 | 理由 |
   |----|--------|------|------|
   | cm | AMB-008 | [用户选择] | [选择理由] |
   | sm | AMB-010 | [用户选择] | [选择理由] |
   | ... | ... | ... | ... |

   ### 跨仓影响
   [基于澄清结果的跨仓接口设计和依赖关系]

   ### 延迟至core-design的实现问题
   共X个实现层面问题将在用户确认后记录到impl_questions_for_design.json，在core-design阶段处理。
   ```

   使用AskUserQuestion让用户确认（**对齐单仓流程SKILL.md 5.4步骤9的三问确认**）：
   ```
   AskUserQuestion({
     questions: [{
       question: "M-3最终推荐方案如上。请确认：1. 以上设计是否符合预期？2. 需要调整或补充的内容？3. 是否有其他需要澄清的模糊点？",
       header: "M-3确认",
       options: [
         { label: "确认，进入后处理", description: "方案符合预期，执行后处理生成文件" },
         { label: "需要补充", description: "有遗漏或需要修改的澄清项" },
         { label: "需要调整", description: "方案方向需要修改，重新呈现设计方案" }
       ]
     }]
   })
   ```
   **【强制门控】**（对齐单仓流程SKILL.md 5.4步骤10 — **用户确认后才执行后处理**）：
   - 用户选择"确认" → 输出"GATE PASSED: M-3 user approved"，进入步骤4后处理
   - 用户选择"需要补充" → 重新调用brainstorming，传递用户补充的问题
   - 用户选择"需要调整" → 基于用户意见更新方案，重新呈现设计方案（返回步骤3），直到用户确认
   - **未获用户确认，禁止执行步骤4后处理**
   - **【禁止】在用户未确认的情况下执行后处理生成文件**（对齐单仓SKILL.md步骤11："用户确认后才执行后处理"）

4. **【强制】用户确认后执行后处理**（对齐单仓模式SKILL.md 5.4步骤11 — 用户确认后才执行后处理）：

   **4a. 检查brainstorming是否执行了交互式对话**：
   - 如果没有检测到至少3轮问答，视为brainstorming未正常执行，**必须重新调用brainstorming**

   **4b. 【强制门控】确保design.md已生成**：
   - 在 `docs/superpowers/specs/` 目录下使用Glob查找 `*-design.md` 文件
   - **如果brainstorming已生成design.md** → 记录其路径，继续步骤4c
   - **如果brainstorming未生成design.md** → **必须立即基于brainstorming对话历史生成design.md**，禁止跳过：
     - 生成路径：`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`（日期用当天，topic从requirement_desc提取）
     - 内容必须包含以下章节：
       - **架构设计**：基于brainstorming澄清结果的purpose和recommended_approach，描述整体架构方案
       - **组件设计**：基于各仓drafts/{repo}.md的架构图和集成点，描述各仓职责和组件关系
       - **数据流**：基于澄清结果，描述核心数据流转路径（含各仓职责边界）
       - **接口设计**：基于跨仓AMB/CON条目的澄清结果，描述跨仓接口契约和数据结构
       - **关键决策**：基于用户确认的设计方案，记录ambiguities_resolved和contradictions_resolved
     - **【禁止】**：禁止因"brainstorming已澄清完毕"而跳过design.md生成 — design.md是core-design Phase 1.5的必要输入，缺失将导致delta_design.md设计深度不足
   - **【强制验证】**：生成后必须用Read工具回读design.md，确认文件非空且包含上述5个章节标题

   **4c. 【强制】读取 references/clarify-enhance-rules.md 并执行术语对齐后处理**（对齐单仓模式SKILL.md 5.4步骤4）：
   - **【强制】必须先Read references/clarify-enhance-rules.md** — 禁止在未读取此规则文件的情况下执行术语对齐
   - 读取主仓 spec.md "领域术语"章节（多仓共享同一术语定义）
   - 扫描 brainstorming 对话历史中的术语冲突（同一概念使用不同词、与已有定义冲突的用法）
   - 扫描 brainstorming 对话历史中的模糊术语（无冲突但定义不清的词，需精确定义）
   - 术语确定后写入主仓 spec.md "领域术语"章节，格式：术语 / 英文 / 定义 / 避免使用（四列）
   - **【强制执行证据】**：即使无术语冲突且无模糊术语，也**必须显式声明**"扫描brainstorming对话历史，未发现术语冲突或模糊术语" — 禁止跳过本步骤而不留任何执行痕迹
   - 如有术语冲突或模糊术语 → **必须**写入spec.md，禁止仅记录到clarification_summary.json而不写入spec.md

   **4d. 【强制】决策记录后处理**（对齐单仓模式SKILL.md 5.4步骤5）：
   - 扫描 brainstorming 对话历史中的决策确认
   - 三条件检查（Hard to reverse / Surprising without context / Real trade-off），三个必须同时满足
   - 三条件全满足 → 写入主仓 **docs/specs/design.md**（项目级设计规格文档）"设计决策"章节（追加，不覆盖已有内容）
   - **【关键】决策记录写入的是主仓 `docs/specs/design.md`**（项目级设计规格），**不是** brainstorming生成的架构设计文件（docs/superpowers/specs/下的文件）
   - 任一条件不满足 → 不写入design.md（仅记录到 clarification_summary.json）
   - **【强制执行证据】**：对于每个用户确认的设计方案，**必须显式列出三条件检查结果**（如："决策X: hard_to_reverse=true, surprising_without_context=false, real_trade_off=true → 不满足全部三条件，仅记录到clarification_summary.json"）— 禁止仅声明"决策记录后处理已执行"而不展示检查过程
   - **【禁止】以"无设计决策"为由跳过4d** — brainstorming中用户确认了推荐方案即为设计决策，必须执行三条件检查

   **4e. 生成 clarification_summary.json**：
   必须在项目级变更目录生成 `clarification_summary.json`：
   - 路径：`docs/changes/<change>/clarification_summary.json`
   - **输入来源**：**必须从brainstorming的对话历史中提取**，禁止从参数直接生成
   - 此文件是explore-doc-reviewer CHECK-R3a决策基线的必要输入
   - **禁止省略此文件** — 缺失将导致审查阶段决策保真度降级
   - 格式对齐单仓模式SKILL.md 5.4的clarification_summary.json格式，多仓模式下增加 `repos` 字段：
   ```json
   {
     "version": "1.0",
     "requirement_id": "<ID>",
     "source": "brainstorming-skill",
     "generated_at": "<ISO时间>",
     "clarification": {
       "purpose": {...},
       "constraints": [],
       "success_criteria": [],
       "scope": {"included": [], "excluded": []},
       "approaches": [...],
       "recommended_approach": "",
       "ambiguities_resolved": [...],
       "contradictions_resolved": [...],
       "terms_resolved": [
         {
           "term": "<规范术语>",
           "term_en": "<英文>",
           "definition": "<定义>",
           "avoid": ["<避免使用词>"],
           "conflict_detected": true,
           "conflict_description": "<冲突描述>",
           "written_to": "<写入位置>"
         }
       ],
       "design_decisions": [
         {
           "decision": "<决策结论>",
           "background": "<背景>",
           "alternatives": ["<替代方案>"],
           "rationale": "<理由>",
           "three_gate_check": {
             "hard_to_reverse": true,
             "surprising_without_context": true,
             "real_trade_off": true
           },
           "written_to": "<写入位置>"
         }
       ]
     },
     "repos": {
       "cm": {"resolved_count": 3, "deferred_impl_count": 5},
       "common": {"resolved_count": 0, "deferred_impl_count": 10},
       "frame": {"resolved_count": 0, "deferred_impl_count": 12},
       "pf": {"resolved_count": 1, "deferred_impl_count": 9},
       "sm": {"resolved_count": 5, "deferred_impl_count": 12}
     },
     "user_approval": {...},
     "self_review": {...}
   }
   ```

   **4f. 【强制】生成 .brainstorming_output**：
   - **前提**：步骤4b必须已确认design.md存在（brainstorming生成或后处理生成均可）
   - 记录design.md路径到.brainstorming_output的`design_doc_path`字段
   - 此文件供core-design Phase 1.5读取brainstorming结果
   - **【禁止】**：禁止在design.md不存在时生成.brainstorming_output — design_doc_path必须指向真实存在的文件
   - 生成后必须验证：Read .brainstorming_output确认design_doc_path指向的文件存在

   **4g. 生成 impl_questions_for_design.json**：
   必须在项目级变更目录生成 `impl_questions_for_design.json`：
   - 路径：`docs/changes/<change>/impl_questions_for_design.json`
   - 内容：brainstorming识别的实现层面疑点，留给core-design阶段作为输入
   - 此文件是core-design的必要输入，确保实现层面的问题不会被遗漏
   ```json
   {
     "version": "1.0",
     "requirement_id": "<ID>",
     "source": "core-explore-M3",
     "generated_at": "<ISO时间>",
     "deferred_items": [
       {
         "repo": "cm",
         "id": "AMB-001",
         "title": "pktctrl trace location",
         "category": "implementation",
         "description": "Where exactly in the code to call the trace API",
         "design_consideration": "需在core-design阶段确定trace API调用位置"
       }
     ],
     "note": "Implementation-level questions identified during brainstorming and deferred to core-design for resolution."
   }
   ```

   **4h. 【强制】生成 cross_repo_contracts.json**：
   必须在项目级变更目录生成 `cross_repo_contracts.json`：
   - 路径：`docs/changes/<change>/clarifications/cross_repo_contracts.json`
   - 内容：基于brainstorming澄清结果和design.md中的接口设计，提取跨仓接口契约
   - 此文件是M-4 shared_context生成的必要输入（跨仓接口清单来源），也是core-design/core-apply多仓模式的必要输入（拓扑排序依赖、设计文档接口对齐）
   - **【强制】禁止跳过cross_repo_contracts.json生成** — 即使contracts为空列表也必须生成此文件
   - **【禁止】以"无跨仓接口"为由跳过4h** — 多仓需求必然存在跨仓交互，必须显式提取接口契约
   - **数据来源**：
     - brainstorming澄清的跨仓AMB/CON条目（哪些仓之间有接口依赖）
     - design.md的"接口设计"章节（接口名称、参数、数据结构）
     - M-2各仓探索蒸馏文件中的跨仓依赖信息（出向/入向调用）
   - **生成规则**：
     - 每个跨仓接口生成一个contract条目
     - `definition_repo`：接口定义方（提供实现的仓）
     - `consumer_repos`：接口消费方（调用该接口的仓列表）
     - `status`：初始为 `proposed`（core-design M-2完成后转为 `confirmed`）
     - `contract_type`：接口类型（`function_call`函数调用/`data_format`数据格式/`event_callback`事件回调）
     - 如果brainstorming未发现跨仓接口 → 生成空contracts列表（`{"contracts": []}`），**不报错**
   ```json
   {
     "version": "1.0",
     "change_name": "<change>",
     "generated_at": "<ISO时间>",
     "source": "core-explore-M3-brainstorming",
     "contracts": [
       {
         "id": "C001",
         "status": "proposed",
         "contract_type": "function_call",
         "definition_repo": "cm",
         "consumer_repos": ["sm", "pf"],
         "interface_name": "trace_enable",
         "description": "追踪开关接口，定义仓cm提供trace_enable()函数，消费仓sm/pf调用",
         "parameters": [
           {"name": "module_id", "type": "int", "description": "模块ID"},
           {"name": "enabled", "type": "bool", "description": "开关状态"}
         ],
         "return_type": "int",
         "last_updated_at": "<ISO时间>"
       }
     ]
   }
   ```
   - **生成后**：调用 `refresh_contracts_copies(project_root, change_name, involved_repos)` 刷新各仓副本
   - **【强制验证】**：生成后必须用Read工具回读cross_repo_contracts.json，确认文件非空且为有效JSON

5. **【强制检查点输出】**：M-3完成时必须输出：
   ```
   M-3 Checkpoint:
   - [x] brainstorming已调用（1次统一调用，传入所有仓上下文）
   - [x] brainstorming与用户交互≥3轮
   - [x] 最终推荐方案已呈现并获用户确认（用户确认先于后处理）
   - [x] clarify-enhance-rules.md已读取（4c前置条件）
   - [x] 术语对齐后处理已执行（必须展示扫描结果：冲突词+模糊术语 → 主仓spec.md"领域术语"，或显式声明"未发现术语冲突"）
   - [x] 决策记录后处理已执行（必须展示每个决策的三条件检查结果 → 主仓docs/specs/design.md"设计决策"，或显式声明"仅记录到clarification_summary.json"）
   - [x] clarification_summary.json 已生成（项目级，含repos/terms_resolved/design_decisions字段）
   - [x] impl_questions_for_design.json 已生成（实现层面延迟项）
   - [x] cross_repo_contracts.json 已生成（跨仓接口契约，含各仓副本刷新）— 【强制】不可缺失，即使contracts为空也必须生成
   - [x] design.md 已生成（brainstorming生成 或 后处理基于澄清结果生成）— 【强制】不可缺失
   - [x] .brainstorming_output 已生成且design_doc_path指向真实文件 — 【强制】不可缺失
   ```

**Output**: `clarification_summary.json`（含terms_resolved/design_decisions） + `impl_questions_for_design.json` + `cross_repo_contracts.json`（**强制，M-4/core-design/core-apply必要输入**） + `design.md`（**强制，core-design必要输入**） + `.brainstorming_output`（**强制，design_doc_path必须有效**）
**Checkpoint**: brainstorming已执行 + 术语对齐已完成 + 决策记录已完成 + 用户已确认方案 + clarification_summary.json已生成 + cross_repo_contracts.json已生成 + design.md已生成 + .brainstorming_output已生成
**自动继续**：M-3用户确认方案后**立即进入M-4**，禁止输出"等待CMS推进"后停止。写入M-3 result.json后，直接开始M-4 shared_context生成，不需要等待用户"继续"。

## M-4: shared_context生成
**Replaces**: 无直接替换步骤（多仓专属新增阶段）

<!-- GATE:M3 M-3 Completion Gate -->
**MANDATORY GATE**: 进入M-4前必须验证M-3已完成。
**检查项**：
1. `clarification_summary.json` 存在于 `docs/changes/<change>/` 目录
2. clarification_summary.json 的 `repos` 字段包含所有 involved_repo 的条目
3. `impl_questions_for_design.json` 存在
4. `cross_repo_contracts.json` 存在于 `docs/changes/<change>/clarifications/` 目录
5. `.brainstorming_output` 存在于 `docs/changes/<change>/` 目录，且其 `design_doc_path` 指向的文件存在
6. design.md存在于 `docs/superpowers/specs/` 目录（brainstorming生成或后处理生成均可）

**【强制】如果检查不通过**：
1. 立即停止，不生成shared_context.md
2. 告知用户："M-3澄清未完成。缺失必要输出文件。请先完成brainstorming澄清。"
3. 返回M-3重新执行，**禁止降级跳过**
<!-- /GATE:M3 -->

**Input**: clarification_summary.json、impl_questions_for_design.json、cross_repo_contracts.json、drafts/{repo}.md（参考：架构图+集成点+影响点+跨仓依赖）
**Execution**:
1. 生成 `shared_context.md`（**【强制】文件名必须是 `shared_context.md`，格式为Markdown，禁止生成 `shared_context.json`**），包含：
   - 总需求描述（从proposal提炼的总体需求描述）
   - 总体功能清单（功能/优先级/实现仓/说明表格）
   - 跨仓接口清单（从cross_repo_contracts.json提取）
   - 不在范围内（从proposal提炼的排除范围）
   生成位置：`docs/changes/<change>/shared_context.md`
   **【禁止】**：禁止生成 `shared_context.json` — shared_context是供M-5/M-6子代理Read的Markdown文档，不是JSON数据文件
2. 调用 `verify_shared_context_consistency(shared_context_path, change_name, repos, project_root)` 执行SHA-256 hash比对一致性校验：
   - 提取各仓proposal共享章节与shared_context.md比对
   - hash不一致 -> **以shared_context.md为准**修正该仓对应章节，记录修正日志
   - `extract_section()`标题匹配失败时降级为逐行搜索（鲁棒性降级）
   - shared_context.md不存在时返回consistent=false并报告错误
3. 总分式生成各仓proposal/delta_spec：
   - 为每个涉及仓生成独立的proposal.md到 `{repo}/docs/changes/<change>/` 目录，共享章节引用shared_context.md
   - 为每个涉及仓生成独立的delta_spec.md到 `{repo}/docs/changes/<change>/` 目录
   - **【关键】路径说明**：`{repo}` 是仓的根目录路径（如项目根目录下的 `cm/`、`sm/` 子目录），因此完整路径为 `<project_root>/{repo}/docs/changes/<change>/proposal.md`
   - **【禁止】**：禁止将proposal/delta_spec生成到 `docs/changes/<change>/{repo}/` 路径下（这是错误路径！）
   - **正确路径示例**（假设project_root=D:/code/5gcore, change=SR20260128001211-overflow-billing, repo=cm）：
     - 正确：`D:/code/5gcore/cm/docs/changes/SR20260128001211-overflow-billing/proposal.md`
     - 错误：`D:/code/5gcore/docs/changes/SR20260128001211-overflow-billing/cm/proposal.md`
   - 各仓共享章节必须与shared_context.md字节级一致（hash校验）
   - 不一致时以shared_context.md为权威源自动修正
**Output**: `shared_context.md` + 各仓的 `proposal.md` 和 `delta_spec.md`（在对应仓目录下）
**Checkpoint**: shared_context.md 存在 + hash一致性校验通过
**自动继续**：M-4完成后直接进入M-5，不需要等待用户"继续"

## M-5: 各仓proposal
**Replaces**: steps.md Step 10 produce-proposal（单仓步骤，多仓模式替换为总分式）
**Input**: shared_context.md、clarification_summary.json、impl_questions_for_design.json

**【强制】执行模式**：subagent（并行）— 此步骤必须通过子代理执行，**禁止主会话直接生成proposal.md**
**【禁止】以下行为**：
- 主会话直接使用Write工具写入各仓proposal.md（最常见绕过方式）
- 主会话自行用Write逐仓生成（绕过子代理并行）
- 主会话将5个仓的proposal合并为一次Write调用
- 主会话对5个仓中仅生成2-3个就声明全部完成

**Execution**:
1. 多仓proposal.md章节结构（6节+子节，**直接包含shared_context.md内容**）：
   ```markdown
   ## 1. 背景与动机（**必须直接包含**shared_context.md对应章节的完整内容）
   ## 2. 变更内容
   ### 2.1 总体功能清单（**必须直接包含**shared_context.md对应章节的完整内容）
   ### 2.2 本仓关注的功能
   ### 2.3 不在范围内
   ## 3. 影响分析
   ### 3.1 本仓受影响的规格/设计
   ### 3.2 本仓的破坏性变更
   ### 3.3 跨仓依赖关系
   ## 4. DFX约束
   ## 5. 里程碑
   ## 6. 多仓环境说明（锚定仓、本仓职责、跨仓接口）
   ```
2. **【强制】shared_context内容嵌入规则**：
   - "1. 背景与动机"和"2.1 总体功能清单"章节**必须直接包含shared_context.md对应章节的完整内容**，而非仅写"引用shared_context.md"或"详见shared_context.md"
   - **嵌入方式**：使用Read工具读取shared_context.md的对应章节内容，将完整文本复制到proposal.md对应章节中
   - **【禁止】**：禁止在共享章节位置仅写"参见shared_context.md"、"引用shared_context.md"或任何形式的引用占位符
   - "6. 多仓环境说明"必须列出：锚定仓、本仓职责、跨仓接口
3. **【强制】使用子代理并行生成各仓proposal.md**（对齐M-2并行探索模式）：
   - 子代理类型：`subagent_type="general"`
   - 每仓一个子代理
   - 并发上限3个，分批启动
   - 子代理失败时重试1次，仍失败则主会话补充生成该仓
   - 所有子代理完成后，主会话执行hash验证和内容抽查
   - **【强制】子代理必须使用Write工具写入proposal.md** — 禁止使用Bash调用PowerShell/cp/echo/cat等命令写文件（Windows环境下不稳定）

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属proposal生成代理。请为 {repo} 仓生成proposal.md：

   输入文件（必须全部读取后再开始生成）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | shared_context.md | {project_root}/docs/changes/{change_name}/shared_context.md | **核心输入**：proposal的"1. 背景与动机"和"2.1 总体功能清单"章节必须**直接包含**shared_context.md对应章节的完整内容（字节级一致），而非引用占位符 |
   | 2 | drafts/{repo}.md | {project_root}/docs/changes/{change_name}/drafts/{repo}.md | **核心参考**：该仓的架构图、集成点、影响点、跨仓依赖 — proposal的"3. 影响分析"章节必须覆盖探索发现的集成点和影响点 |
   | 3 | cross_repo_contracts.json | {project_root}/docs/changes/{change_name}/clarifications/cross_repo_contracts.json | **辅助参考**：跨仓接口契约 — proposal的"3.3 跨仓依赖关系"和"6. 多仓环境说明"章节需要引用其中定义仓和消费仓信息 |
   | 4 | clarification_summary.json | {project_root}/docs/changes/{change_name}/clarification_summary.json | **辅助参考**：澄清结论，用于确保proposal的需求范围和约束与澄清结果一致 |
   | 5 | impl_questions_for_design.json | {project_root}/docs/changes/{change_name}/impl_questions_for_design.json | **辅助参考**：延迟至core-design的实现问题列表，proposal中不需回应但需在"6. 多仓环境说明"中标注存在延迟问题 |

   生成要求：
   - 输出文件：{repo_path}/docs/changes/{change_name}/proposal.md
   - 必须使用Write工具写入（禁止使用Bash调用PowerShell/cp/echo/cat等命令写文件）
   - 章节结构按M-5步骤1的6节+子节格式
   - "1. 背景与动机"和"2.1 总体功能清单"必须直接包含shared_context.md对应章节完整内容（禁止写"参见shared_context.md"）
   - "2.2 本仓关注的功能"仅列出本仓需要实现的功能
   - "3.1 本仓受影响的规格/设计"基于drafts/{repo}.md的影响点
   - "6. 多仓环境说明"列出锚定仓、本仓职责、跨仓接口
   - 禁止保留未填充的占位符 `<...>`

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}
   ```
4. 仓库范围完整性、实现顺序、接口契约、边界清晰均从shared_context.md提取
5. **【强制验证】**：生成每个仓的proposal后，执行两项检查：
   - **hash验证**：使用verify_shared_context_consistency()比对共享章节的hash
   - **内容抽查**：Read每个仓proposal.md的"1. 背景与动机"章节，确认内容与shared_context.md对应章节一致（非引用占位符）
   - hash不一致时以shared_context.md为准自动修正
   - **抽查发现引用占位符**时，必须重新读取shared_context.md对应章节并替换
6. **【强制】子代理启动验证** — 启动子代理后，必须输出子代理启动确认：
   ```
   M-5 子代理启动确认：
   - cm: 子代理M5-proposal-cm已启动 ✓
   - common: 子代理M5-proposal-common已启动 ✓
   - frame: 子代理M5-proposal-frame已启动 ✓
   - pf: 子代理M5-proposal-pf已启动 ✓
   - sm: 子代理M5-proposal-sm已启动 ✓
   ```
   **如果无法输出上述确认（即没有实际调用Agent tool），则M-5执行失败，禁止声明"M-5 proposal ✅"**

**Output**: 各涉及仓的 `<project_root>/{repo}/docs/changes/<change>/proposal.md`
**路径示例**：`D:/code/5gcore/cm/docs/changes/SR20260128001211-overflow-billing/proposal.md`（**禁止** `D:/code/5gcore/docs/changes/SR20260128001211-overflow-billing/cm/proposal.md`）
**Checkpoint**: 所有涉及仓的proposal.md已生成 + shared_context共享章节hash一致性校验通过
**自动继续**：M-5完成后直接进入find-similar-changes，再进入M-6，不需要等待用户"继续"

## find-similar-changes: 查找相似需求（多仓模式）
**位置**：在M-5（各仓proposal）之后、M-6（各仓delta_spec）之前执行
**原因**：delta_spec生成需要参考相似需求的历史实现，避免重复设计或遗漏已知约束

**执行方式**（与单仓模式相同，但搜索范围扩大）：
1. 在所有涉及仓的 `docs/changes/` 目录下查找相似需求的delta_spec.md
2. 在项目根目录的 `docs/changes/` 目录下查找相似需求
3. 参考clarification_summary.json中的clarified scope，确保本需求scope与历史需求不重叠
4. 找到的相似需求delta_spec.md内容将作为M-6 delta_spec生成的参考输入

**判断**：
- 找到相似需求 → 记录参考信息，用于M-6 delta_spec生成
- 未找到 → 直接进入M-6

## M-6: 各仓delta_spec
**Replaces**: steps.md Step 12 produce-delta-spec（单仓步骤，多仓模式替换为总分式）
**Input**: 各仓proposal.md、shared_context.md、cross_repo_contracts.json、find-similar-changes参考结果

**【强制】执行模式**：subagent（并行）— 此步骤必须通过子代理执行，**禁止主会话直接生成delta_spec.md**
**【禁止】以下行为**：
- 主会话直接使用Write工具写入各仓delta_spec.md（最常见绕过方式）
- 主会话自行用Write逐仓生成（绕过子代理并行）
- 主会话将5个仓的delta_spec合并为一次Write调用
- 主会话对5个仓中仅生成2-3个就声明全部完成

**Execution**:
1. 多仓delta_spec.md章节结构（**直接包含shared_context.md内容**）：
   ```markdown
   ## 1. 总需求规格（**必须包含**shared_context.md的需求概述完整内容）
   ## 2. 本仓关注部分的ADDED/MODIFIED/REMOVED规则
   ## 3. 跨仓接口规格（**必须从shared_context.md提取**，字节级一致）
   ## 4. 数据约束变更（本仓相关）
   ## 5. 术语变更
   ## 6. 合并检查清单
   ```
2. **【强制】shared_context内容嵌入规则**：
   - "1. 总需求规格"章节**必须包含shared_context.md的需求概述完整内容**，而非仅写"引用shared_context.md"
   - **嵌入方式**：使用Read工具读取shared_context.md的对应章节内容，将完整文本复制到delta_spec.md对应章节中
   - **【禁止】**：禁止在共享章节位置仅写"参见shared_context.md"或任何形式的引用占位符
   - "3. 跨仓接口规格"**必须从shared_context.md提取**，而非Agent自行编写
   - 各仓delta_spec的跨仓接口描述必须与shared_context.md字节级一致
3. **ADDED/MODIFIED/REMOVED格式强制要求**：所有规格变更必须使用此格式标注变更类型，不允许自由文本替代
4. MODIFIED类型必须写出完整的修改后内容，并在末尾用 `← (原为: [原描述])` 标注原始内容
5. REMOVED类型必须显式说明删除原因；若涉及外部使用者，必须提供迁移路径
6. 新增或修改的每条规则必须附带验收条件，遵循1.2.3的编写规范
7. **【强制】使用子代理并行生成各仓delta_spec.md**（对齐M-2并行探索模式）：
   - 子代理类型：`subagent_type="general"`
   - 每仓一个子代理
   - 并发上限3个，分批启动
   - 子代理失败时重试1次，仍失败则主会话补充生成该仓
   - 所有子代理完成后，主会话执行ADDED/MODIFIED/REMOVED格式验证和shared_context内容一致性验证
   - **【强制】子代理必须使用Write工具写入delta_spec.md** — 禁止使用Bash调用PowerShell/cp/echo/cat等命令写文件（Windows环境下不稳定）

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属delta_spec生成代理。请为 {repo} 仓生成delta_spec.md：

   输入文件（必须全部读取后再开始生成）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | shared_context.md | {project_root}/docs/changes/{change_name}/shared_context.md | **核心输入**：delta_spec的"1. 总需求规格"章节必须**直接包含**shared_context.md的需求概述完整内容；"3. 跨仓接口规格"必须从shared_context.md提取，字节级一致 |
   | 2 | proposal.md | {repo_path}/docs/changes/{change_name}/proposal.md | **核心输入**：delta_spec的每个ADDED/MODIFIED/REMOVED规则必须覆盖proposal中"2.2 本仓关注的功能"列出的每项功能，需求ID必须与proposal一致 |
   | 3 | cross_repo_contracts.json | {project_root}/docs/changes/{change_name}/clarifications/cross_repo_contracts.json | **核心参考**：跨仓接口规格 — delta_spec的"3. 跨仓接口规格"必须与cross_repo_contracts.json中的接口签名一致（如果本仓是定义仓，必须包含该接口的规格定义；如果是消费仓，必须包含调用约束） |
   | 4 | drafts/{repo}.md | {project_root}/docs/changes/{change_name}/drafts/{repo}.md | **辅助参考**：该仓的影响点和集成点 — delta_spec的ADDED/MODIFIED/REMOVED规则应覆盖探索发现的影响范围 |
   | 5 | clarification_summary.json | {project_root}/docs/changes/{change_name}/clarification_summary.json | **辅助参考**：澄清结论 — delta_spec中的约束和验收条件必须与澄清结果一致，不得与澄清结论矛盾 |
   | 6 | find-similar-changes参考 | （主会话传入相似需求信息） | **辅助参考**：历史相似需求的delta_spec.md内容 — 避免重复设计或遗漏已知约束，参考相似需求的规格模式 |

   生成要求：
   - 输出文件：{repo_path}/docs/changes/{change_name}/delta_spec.md
   - 必须使用Write工具写入（禁止使用Bash调用PowerShell/cp/echo/cat等命令写文件）
   - 章节结构按M-6步骤1的6节格式
   - "1. 总需求规格"必须直接包含shared_context.md需求概述完整内容（禁止写"参见shared_context.md"）
   - "2. 本仓关注部分"必须使用ADDED/MODIFIED/REMOVED格式标注变更类型
   - MODIFIED类型必须写出完整修改后内容 + `← (原为: [原描述])`
   - REMOVED类型必须说明删除原因
   - "3. 跨仓接口规格"必须从shared_context.md提取，字节级一致
   - 每条规则必须附带验收条件
   - 禁止保留未填充的占位符 `<...>`

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}
   ```
8. **【强制】子代理启动验证** — 启动子代理后，必须输出子代理启动确认：
   ```
   M-6 子代理启动确认：
   - cm: 子代理M6-deltaspec-cm已启动 ✓
   - common: 子代理M6-deltaspec-common已启动 ✓
   - frame: 子代理M6-deltaspec-frame已启动 ✓
   - pf: 子代理M6-deltaspec-pf已启动 ✓
   - sm: 子代理M6-deltaspec-sm已启动 ✓
   ```
   **如果无法输出上述确认（即没有实际调用Agent tool），则M-6执行失败，禁止声明"M-6 delta_spec ✅"**
9. 所有子代理完成后，主会话执行ADDED/MODIFIED/REMOVED格式验证和shared_context内容一致性验证

**Output**: 各涉及仓的 `<project_root>/{repo}/docs/changes/<change>/delta_spec.md`
**路径示例**：`D:/code/5gcore/cm/docs/changes/SR20260128001211-overflow-billing/delta_spec.md`（**禁止** `D:/code/5gcore/docs/changes/SR20260128001211-overflow-billing/cm/delta_spec.md`）
**Checkpoint**: 所有涉及仓的delta_spec.md已生成 + ADDED/MODIFIED/REMOVED格式正确 + shared_context内容一致性验证通过
**自动继续**：M-6完成后直接进入M-7（各仓L1验证），不需要等待用户"继续"

## M-7: 各仓L1需求完整性验证（subagent并行）

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，**禁止主会话直接执行**
**Replaces**: steps.md Step 13 verify-completeness（单仓步骤）
**Input**: 各仓proposal.md、delta_spec.md
**同步/异步**: sync

**【强制】进入M-7时，必须向用户输出：**
"## M-7: 各仓L1需求完整性验证 — delta_spec已生成，正在通过subagent并行执行各仓cross-doc-checker L1验证..."

**【强制】M-7是M-6（delta_spec生成）和M-8（explore-doc-reviewer审查）之间的必经关卡。禁止跳过M-7直接进入M-8。**

**【强制】禁止主会话直接执行L1验证** — 多仓场景下，5个仓的L1验证必须在子代理中并行执行。主会话直接执行等于将5个仓串行化，违反多仓并行设计。以下行为均被禁止：
- 主会话直接调用 `Skill tool: cross-doc-checker` 后自行用Grep/Read验证（这是最常见绕过方式 — agent加载skill内容后自行执行，不启动子代理）
- 主会话自行用Grep/Read逐仓验证（绕过Skill tool）
- 主会话将5个仓的L1验证合并为一次cross-doc-checker调用
- 主会话对5个仓中仅2个做"抽样检查"就声明全部通过

**Execution**:
1. **【强制】使用Agent tool启动子代理**（与M-2并行探索相同的调用模式）：

   对每个涉及仓，使用Agent tool启动一个子代理，每批最多3个并行：
   ```
   Agent tool调用示例（5仓分2批：第一批3个+第二批2个）：
   第一批：
   - name: "M7-L1-cm", subagent_type: "general", description: "cm仓L1验证", prompt: <cm仓任务描述>
   - name: "M7-L1-common", subagent_type: "general", description: "common仓L1验证", prompt: <common仓任务描述>
   - name: "M7-L1-frame", subagent_type: "general", description: "frame仓L1验证", prompt: <frame仓任务描述>
   第二批（第一批完成后启动）：
   - name: "M7-L1-pf", subagent_type: "general", description: "pf仓L1验证", prompt: <pf仓任务描述>
   - name: "M7-L1-sm", subagent_type: "general", description: "sm仓L1验证", prompt: <sm仓任务描述>
   ```
   - **子代理类型**：`subagent_type="general"`（不是`"general-purpose"`，`"general-purpose"`会导致子代理启动失败）
   - **并发上限**：3个（涉及仓<=3时一次性并行启动，>3时分批启动每批3个）
   - **子代理失败时**：重试1次，仍失败则主会话补充执行该仓
   - **单仓失败不阻塞其他仓的同阶段执行**

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属L1验证代理。请对 {repo} 仓执行 L1 需求完整性验证：

   输入文件（必须全部读取后再开始执行步骤）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | proposal.md | {repo_path}/docs/changes/{change_name}/proposal.md | **核心输入**：L1验证的基础文档，cross-doc-checker将检查其中的需求ID与delta_spec的追溯关系 |
   | 2 | delta_spec.md | {repo_path}/docs/changes/{change_name}/delta_spec.md | **核心输入**：L1验证的目标文档，cross-doc-checker将检查其中每个需求ID是否可追溯到proposal |
   | 3 | clarification_summary.json | {project_root}/docs/changes/{change_name}/clarification_summary.json | **辅助参考**：澄清结论，用于理解需求范围和约束 |

   执行步骤：
   1. 使用 Skill tool 调用 cross-doc-checker <change-name> --layer L1
      - **【强制】必须使用 Skill tool 调用** — Skill tool会加载cross-doc-checker的完整审查指令，加载后按指令执行审查。禁止自行用Grep/Read替代skill调用
      - **【强制】禁止通过Bash调用Python脚本执行cross-doc-checker** — cross-doc-checker是Agent审查技能，不是Python脚本。禁止调用 cross_doc_checker.py / trace_validator.py 等脚本文件
      - 传入参数：change_name 为变更目录名（如 SR20260128001211-billing-flow-tracking）
      - 工作目录：{repo_path}
   2. 读取审查输出的findings列表
   3. **【强制】3轮自动修复循环**（禁止跳过，禁止直接报告问题而不修复）：
      **修复 = 使用Edit/Write工具修改文档**，不是"验证发现"或"确认问题"。每一轮修复必须产生实际的文件变更（Edit/Write操作），不允许仅读取文件确认问题后进入下一轮。

      如果存在ERROR级finding，必须执行以下修复循环：
      ```
      修复轮次 = 0
      while 存在ERROR级finding AND 修复轮次 < 3:
          修复轮次 += 1
          输出 "修复轮次 {修复轮次}/3：发现 {ERROR数量} 个ERROR"
          对每个ERROR执行修复：
          - 【文档保真类】proposal有但delta_spec缺需求ID → 使用Edit工具在delta_spec.md中补充缺失需求
          - 【文档保真类】delta_spec有但proposal缺需求ID → 使用Edit工具在proposal.md中补充或从delta_spec中删除
          - 【文档保真类】需求ID名称不匹配 → 使用Edit工具统一两份文档中同一需求ID的名称
          - 【文档保真类】截断/占位符 → 使用Edit工具替换为具体内容
          - **【强制】修复文档必须使用Edit/Write工具** — 禁止使用Bash调用PowerShell/echo/cat等命令修改文件
          修复完成后重新调用 Skill tool: cross-doc-checker <change-name> --layer L1
          读取新的findings列表
      ```
   4. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表
   5. **【强制】禁止以下行为**：
      - 禁止发现ERROR后直接返回ESCALATE而不执行修复循环
      - 禁止仅修复部分ERROR就声明完成（必须修复所有ERROR或完成3轮）
      - 禁止将ERROR降级为WARNING后跳过修复
   6. **【强制】修复轮次必须包含实际文件变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}
   仓变更目录：{repo_path}/docs/changes/{change_name}

   返回格式（必须包含修复过程记录）：
   - 全部通过：status=PASSED, findings=[...], fix_rounds=0
   - 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
   ```

2. **【强制】子代理启动验证** — 启动子代理后，必须输出子代理启动确认：
   ```
   M-7 子代理启动确认：
   - cm: 子代理M7-L1-cm已启动 ✓
   - common: 子代理M7-L1-common已启动 ✓
   - frame: 子代理M7-L1-frame已启动 ✓
   - pf: 子代理M7-L1-pf已启动 ✓
   - sm: 子代理M7-L1-sm已启动 ✓
   ```
   **如果无法输出上述确认（即没有实际调用Agent tool），则M-7执行失败，禁止声明"M-7 L1验证 ✅"**

3. 汇总所有子代理结果，处理ESCALATE升级：
   - 当子代理返回ESCALATE状态时，使用AskUserQuestion展示给用户选择处理方式（人工修复/忽略继续/重新审查）
   - **【强制】验证子代理修复过程**：如果子代理返回ESCALATE但fix_rounds<3，说明子代理未完成3轮修复就提前退出 → **重新启动该仓子代理并强制执行3轮修复**，而非直接交给用户决策
   - **【强制】禁止主会话代替子代理修复** — 子代理返回L1 FAIL时，主会话**不能**直接使用Edit/Write修改delta_spec.md来修复问题。必须重新启动该仓子代理执行修复循环。主会话直接修复违反了子代理内部修复循环的设计
   - **【强制】禁止主会话将子代理返回的问题"记录后继续"** — 主会话不能将子代理发现的ERROR静默记录然后标记PASS。每个仓的结果只能是PASSED/FIXED/ESCALATE之一，不能是"有ERROR但继续"
4. **所有仓L1通过后才进入M-8**（**【强制】禁止跳过M-8直接进入cleanup-temp** — M-8 explore-doc-reviewer是L1验证后的必经审查步骤，禁止以"L1验证已通过"为由跳过M-8）

**主会话后处理**（所有子代理返回后执行）：
- 所有仓L1验证通过（PASSED/FIXED） → 直接进入M-8（不需要等待用户"继续"）
- 存在ESCALATE（且fix_rounds=3） → AskUserQuestion让用户决策
- 存在ESCALATE（但fix_rounds<3） → 重新启动该仓子代理强制执行3轮修复
- 子代理执行失败（非ESCALATE） → **【强制】先向用户明确告知**："仓{repo}子代理L1验证执行失败（原因：{具体错误}），将降级为主会话直接执行cross-doc-checker"，**然后**主会话降级直接调用cross-doc-checker Skill执行该仓的L1验证。**禁止跳过告知直接降级**
- **【禁止】**：禁止主会话直接使用Edit/Write修改子代理发现的问题后跳过M-8进入cleanup-temp

**Output**: 各仓L1验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L1验证已完成
**自动继续**：M-7所有仓L1验证通过后直接进入M-8，不需要等待用户"继续"

## M-8: 各仓explore-doc-reviewer审查（subagent并行）

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，**禁止主会话直接执行**
**Replaces**: steps.md Step 14 explore-review（单仓步骤）
**Input**: 各仓proposal.md、delta_spec.md、clarification_summary.json
**同步/异步**: sync

**【强制】进入M-8时，必须向用户输出：**
"## M-8: 各仓explore-doc-reviewer审查 — L1验证已通过，正在通过subagent并行执行各仓explore-doc-reviewer文档质量审查..."

**【强制】M-8是M-7（L1验证）和cleanup-temp（清理临时文件）之间的必经关卡。禁止跳过M-8直接进入cleanup-temp。**

**【强制】禁止主会话直接执行文档审查** — 多仓场景下，5个仓的文档审查必须在子代理中并行执行。主会话直接执行等于将5个仓串行化，违反多仓并行设计。以下行为均被禁止：
- 主会话直接调用 `Skill tool: explore-doc-reviewer` 后自行用Grep/Read审查（这是最常见绕过方式 — agent加载skill内容后自行执行，不启动子代理）
- 主会话自行用Grep/Read逐仓审查（绕过Skill tool）
- 主会话将5个仓的审查合并为一次explore-doc-reviewer调用
- 主会话对5个仓中仅2个做"抽样检查"就声明全部通过

**Execution**:
1. **【强制】使用Agent tool启动子代理**（与M-2/M-7相同的调用模式）：

   对每个涉及仓，使用Agent tool启动一个子代理，每批最多3个并行：
   ```
   Agent tool调用示例（5仓分2批：第一批3个+第二批2个）：
   第一批：
   - name: "M8-review-cm", subagent_type: "general", description: "cm仓doc-review", prompt: <cm仓任务描述>
   - name: "M8-review-common", subagent_type: "general", description: "common仓doc-review", prompt: <common仓任务描述>
   - name: "M8-review-frame", subagent_type: "general", description: "frame仓doc-review", prompt: <frame仓任务描述>
   第二批（第一批完成后启动）：
   - name: "M8-review-pf", subagent_type: "general", description: "pf仓doc-review", prompt: <pf仓任务描述>
   - name: "M8-review-sm", subagent_type: "general", description: "sm仓doc-review", prompt: <sm仓任务描述>
   ```
   - **子代理类型**：`subagent_type="general"`（不是`"general-purpose"`，`"general-purpose"`会导致子代理启动失败）
   - **并发上限**：3个（涉及仓<=3时一次性并行启动，>3时分批启动每批3个）
   - **子代理失败时**：重试1次，仍失败则主会话补充执行该仓
   - **单仓失败不阻塞其他仓的同阶段执行**

   子代理任务描述模板：
   ```
   你是仓 {repo} 的专属文档审查代理。请对 {repo} 仓执行 explore-doc-reviewer 文档质量审查：

   输入文件（必须全部读取后再开始执行步骤）：

   | # | 文件 | 路径 | 消费用途 |
   |---|------|------|----------|
   | 1 | proposal.md | {repo_path}/docs/changes/{change_name}/proposal.md | **核心输入**：文档质量审查的主要目标，检查章节完整性、需求覆盖、验收条件等 |
   | 2 | delta_spec.md | {repo_path}/docs/changes/{change_name}/delta_spec.md | **核心输入**：文档质量审查的第二个目标，检查ADDED/MODIFIED/REMOVED格式、跨仓接口一致性等 |
   | 3 | clarification_summary.json | {project_root}/docs/changes/{change_name}/clarification_summary.json | **辅助参考**：澄清结论，用于验证文档是否与澄清结果一致 |

   执行步骤：
   1. 使用 Skill tool 调用 explore-doc-reviewer <change-name>
      - **【强制】必须使用 Skill tool 调用** — Skill tool会加载explore-doc-reviewer的完整审查指令，加载后按指令执行审查。禁止自行用Grep/Read替代skill调用
      - **【强制】禁止通过Bash调用Python脚本执行explore-doc-reviewer** — explore-doc-reviewer是Agent审查技能，使用Read/Grep/Glob工具按Stage 1→2→3→4顺序执行，不是Python脚本
      - 传入参数：change_name 为变更目录名（如 SR20260128001211-billing-flow-tracking）
      - 工作目录：{repo_path}
   2. 读取审查输出的findings列表
   3. **【强制】3轮自动修复循环**（禁止跳过，禁止直接报告问题而不修复）：
      **修复 = 使用Edit/Write工具修改文档**，不是"验证发现"或"确认问题"。每一轮修复必须产生实际的文件变更（Edit/Write操作），不允许仅读取文件确认问题后进入下一轮。

      如果存在ERROR级finding，必须执行以下修复循环：
      ```
      修复轮次 = 0
      while 存在ERROR级finding AND 修复轮次 < 3:
          修复轮次 += 1
          输出 "修复轮次 {修复轮次}/3：发现 {ERROR数量} 个ERROR"
          对每个ERROR执行修复：
          - 【文档保真类】必需章节缺失 → 使用Edit工具补充缺失章节
          - 【文档保真类】截断/占位符 → 使用Edit工具替换为具体内容
          - 【文档保真类】验收条件缺失 → 使用Edit工具补充可判定的验收条件
          - 【文档保真类】模糊词 → 使用Edit工具替换为具体表述
          - 【文档保真类】未授权决策/隐式越权 → 使用Edit工具删除越权内容，回到用户确认
          - 【用户意图类】NEEDS CLARIFICATION超标 → 返回ESCALATE，禁止自行修改文档掩盖问题
          - **【强制】修复文档必须使用Edit/Write工具** — 禁止使用Bash调用PowerShell/echo/cat等命令修改文件
          修复完成后重新调用 Skill tool: explore-doc-reviewer <change-name>
          读取新的findings列表
      ```
   4. 3轮后仍有ERROR级finding → 返回ESCALATE状态 + blocking_issues列表
   5. **【强制】禁止以下行为**：
      - 禁止发现ERROR后直接返回ESCALATE而不执行修复循环
      - 禁止仅修复部分ERROR就声明完成（必须修复所有ERROR或完成3轮）
      - 禁止将ERROR降级为WARNING后跳过修复
   6. **【强制】修复轮次必须包含实际文件变更** — 如果某轮修复没有任何Edit/Write操作，该轮不计入fix_rounds，必须重新执行该轮

   当前变更：{change_name}
   项目根目录：{project_root}
   仓目录：{repo_path}
   仓变更目录：{repo_path}/docs/changes/{change_name}

   返回格式（必须包含修复过程记录）：
   - 全部通过：status=PASSED, findings=[...], fix_rounds=0
   - 自动修复成功：status=FIXED, fixes_summary=[{round, errors_found, errors_fixed, code_changes_made}], fix_rounds=N
   - 需要用户决策：status=ESCALATE, blocking_issues=[{id, description, severity, attempted_fixes}], fix_rounds=3
   ```

2. **【强制】子代理启动验证** — 启动子代理后，必须输出子代理启动确认：
   ```
   M-8 子代理启动确认：
   - cm: 子代理M8-review-cm已启动 ✓
   - common: 子代理M8-review-common已启动 ✓
   - frame: 子代理M8-review-frame已启动 ✓
   - pf: 子代理M8-review-pf已启动 ✓
   - sm: 子代理M8-review-sm已启动 ✓
   ```
   **如果无法输出上述确认（即没有实际调用Agent tool），则M-8执行失败，禁止声明"M-8 审查 ✅"**

3. 汇总所有子代理结果，处理ESCALATE升级（对齐M-7的升级机制）：
   - **【强制】验证子代理修复过程**：如果子代理返回ESCALATE但fix_rounds<3，说明子代理未完成3轮修复就提前退出 → **重新启动该仓子代理并强制执行3轮修复**，而非直接交给用户决策
   - **【强制】禁止主会话将子代理返回的问题"记录后继续"** — 主会话不能将子代理发现的ERROR静默记录然后标记PASS。每个仓的结果只能是PASSED/FIXED/ESCALATE之一，不能是"有ERROR但继续"
4. **所有仓审查通过后才进入cleanup-temp**（**【强制】禁止在M-8后停止或宣布流程完毕，必须继续执行cleanup-temp**）

**主会话后处理**（所有子代理返回后执行）：
- 所有仓审查通过（PASSED/FIXED） → 直接进入cleanup-temp（不需要等待用户"继续"）
- 存在ESCALATE（且fix_rounds=3） → AskUserQuestion让用户决策
- 存在ESCALATE（但fix_rounds<3） → 重新启动该仓子代理强制执行3轮修复
- 子代理执行失败（非ESCALATE） → **【强制】先向用户明确告知**："仓{repo}子代理审查执行失败（原因：{具体错误}），将降级为主会话直接执行explore-doc-reviewer"，**然后**主会话降级直接调用explore-doc-reviewer Skill执行该仓的审查。**禁止跳过告知直接降级**

**Output**: 各仓审查报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的explore-doc-reviewer审查已完成
**自动继续**：M-8所有仓审查通过后直接进入cleanup-temp，不需要等待用户"继续"

## cleanup-temp: 清理临时文件（多仓模式）
**Replaces**: steps.md Step 15 cleanup-temp（单仓步骤，多仓模式下清理范围扩大到各仓变更目录）
**Input**: 各仓变更目录 + 项目级变更目录
**Execution**:

**【强制】逐目录清理清单** — 按以下清单逐项执行，不要凭记忆判断哪些文件可删除：

### 项目级变更目录 `docs/changes/<change>/`

**必须删除**：
- `downloads/` 整个子目录（包含下载的原始docx和解析出的md文件）
- `drafts/ambiguities_*.md`（各仓模糊点文件，已蒸馏到clarification_summary.json中）

**必须保留**（删除将导致后续阶段断裂）：
- `drafts/{repo}.md` — **【禁止】删除整个drafts/目录**，仅可删除 `ambiguities_{repo}.md`。drafts/目录下的 `{repo}.md` 是各仓蒸馏文件（架构图/集成点/影响点/跨仓依赖），core-design设计参考
- `repo_assignments.json` — **【禁止】删除**，core-design/core-apply/core-verify/core-archive的M-1都需读取
- `shared_context.md` — **【禁止】删除**，core-design M-2需读取（注意文件名是.md不是.json）
- `cross_repo_contracts.json` — **【禁止】删除**，core-design M-2/core-apply M-2需读取
- `clarification_summary.json` — **【禁止】删除**，core-design reviewer需读取
- `impl_questions_for_design.json` — **【禁止】删除**，core-design Phase 1.6需读取
- `.brainstorming_output` — **【禁止】删除**，core-design需读取

### 各仓变更目录 `{repo}/docs/changes/<change>/`

**必须删除**：
- `downloads/` 子目录（如有）

**必须保留**：
- `proposal.md` — 核心交付物
- `delta_spec.md` — 核心交付物

### 清理验证

1. 清理完成后，使用Glob列出项目级变更目录和各仓变更目录的文件清单
2. 逐项核对上述"必须保留"列表，确认所有保留文件仍然存在
3. 确认所有"必须删除"的文件/目录已被删除
4. **如果不确定某个文件是否可删，保留而非删除**

**Output**: 变更目录已清理（仅保留核心交付物和跨阶段引用文件）
**Checkpoint**: 可清理文件已删除；禁止删除列表中的文件全部保留

**【强制】cleanup-temp是core-explore多仓模式的最后一个阶段**。清理完成后，输出执行总结并宣布"core-explore流程执行完毕"。**禁止在M-8或更早阶段宣布流程完毕** — M-8所有仓审查通过后必须继续执行cleanup-temp。

## Contracts Lifecycle (本 skill 职责)

| 阶段 | 操作 | status转换 | 副本刷新 |
|------|------|-----------|----------|
| M-3 统一brainstorming澄清 | brainstorming澄清时确认接口 | -> `proposed` | 即时复制到所有涉及仓 |
