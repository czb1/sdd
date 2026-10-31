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

## 可配置步骤与编排点（多仓模式）

多仓模式下，可配置步骤（追溯验证/文档审查/清理/规范拉取/相似需求/专家经验/版本检查）与编排点插槽的**执行与否以构建执行计划持久化的执行计划为准**（`docs/.flow_context/execution-plan-core-design.json`），与单仓模式同一权威：

- **有 M 映射的可配置步骤**（`steps` 数组 `type=built_in` 条目，`ref_file.multi`）：`design_traceability`（M-3a）/ `design_review`（M-3b）/ `cleanup`（cleanup 节）
  - **执行计划 steps 数组含该 `config_key` 条目** → 从条目 `ref_file.multi` 字段取指令文件（动态路径解析参见 SKILL.md Reference文件路径解析章节）并 Read，按其中指令执行；强制位（必经关卡/禁止主会话/最后阶段禁止跳过）随条目存在而生效
  - **执行计划不含该 `config_key` 条目** → 该 M 阶段/步骤跳过，**不 Read 指令文件**（内容不进上下文），直接进入下一 M 阶段；强制位（必经关卡/禁止主会话/最后阶段禁止跳过）随条目缺失而豁免
- **无 M 映射的主会话可配置步骤**（与单仓同一机制、同一执行计划条目，`ref_file` 为单多仓通用文件）：`version_check`（M-1 之前执行）/ `fetch_rules`（M-1 之前执行，B 档双层语义：仅控 code-rule 拉取，GATE 不受控）/ `read_similar`（M-2 之前执行）/ `expert_experience`（M-2 之前执行）。存在性判断同单仓
- **编排点插槽**（`orchestration_points` 对象）：`post-rule-fetch` / `post-gather-context` / `post-code-understanding` / `pre-generate` / `post-generate` / `post-traceability` / `post-design-review` / `post-cleanup`
  - **对应插槽数组含条目** → 按条目 `type` 执行（`reference`：Read `file` 字段指令文件并执行；`skill`：调用 `skill` 字段指定 skill，`run_mode=subagent` 时 spawn 独立子代理）
  - **对应插槽数组为空** → 跳过，指令文件不加载，直接进入下一阶段
  - **多仓触发点**（change 级聚合）：`post-gather-context`（M-1 完成后）/ `pre-generate`（M-2 启动前）/ `post-generate`（M-2 全部仓完成后）/ `post-traceability`（M-3a 全部仓完成后）/ `post-design-review`（M-3b 全部仓完成后）/ `post-cleanup`（cleanup 完成后）
  - **新增 artifact 审查**：由 M-3b design-doc-reviewer 在 Stage 1 通过 `load_schema` 动态发现本环节产物（DAG 分层过滤 `requires` 含 `delta_design` 或更下游 artifact）一次性覆盖，不再设独立 `post-extra-review` 编排点

## 强制位豁免总表（M 关闭时）

| M 阶段/步骤 | 可配置键 | 关闭时的强制位豁免 |
|------------|---------|-------------------|
| M-3a（各仓追溯验证） | `design_traceability` | 必经关卡（"M-3a 全过后才执行 M-3b"）+ 禁止主会话直接执行 + ERROR 禁止推迟 全部豁免；M-2 完成后直接进入 M-3b |
| M-3b（各仓文档审查） | `design_review` | 必经关卡（"禁止跳过 M-3b 直接进入 cleanup"）+ 禁止主会话直接执行 全部豁免；M-3a 通过后（或 `design_traceability` 关闭跳过 M-3a）直接进入 cleanup |
| cleanup（清理） | `cleanup` | "最后阶段禁止跳过"豁免；需显式记录"cleanup 已关闭，临时文件残留"后收尾 |
| fetch-rules（B 档） | `fetch_rules` | 无强制位；Phase 2 code-rule 拉取跳过，**GATE（design-principles/design-views）不受开关控制**，仍无条件加载 |
| read-similar | `read_similar` | 无强制位；Phase 4 后直接进入 Phase 6 |
| expert-experience | `expert_experience` | 无强制位；Phase 6 后直接进入 Phase 8 |

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
   - **仓库范围**：设计是否覆盖 proposal.md 多仓环境说明章节确认的所有涉及仓库
   - **接口协调**：跨仓库接口设计与 proposal.md 中接口契约是否一致
   - **边界清晰**：tasks.md 中的任务是否按仓库边界清晰拆分
**Output**: is_multi_repo 标志 + involved_repos 列表
**Checkpoint**: repo_assignments.json 已读取，多仓/单仓环境已判定

## M-2: 各仓按仓生成

<!-- GATE:REF references/m2-multi.md -->
**MANDATORY GATE**: 进入 M-2 前必须先 Read 本SKILL所在目录下的 `references/m2-multi.md`（M-2 完整执行指令：读取 involved_repos、brainstorming design.md 读取、impl_questions 逐条确认、子代理任务描述模板、并发规则、容错机制、多仓文档读取确认、跨仓归档引用解析）。
绝对路径 = config_dir / 'skills/core-design/references/m2-multi.md'（动态路径解析参见 SKILL.md Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止降级为主会话直接生成。
读取后输出: "GATE PASSED: references/m2-multi.md loaded"。
<!-- /GATE:REF -->

**Replaces**: steps.md Step 8 generate-artifacts（单仓步骤）
**Input**: repo_assignments.json 中的 involved_repos、delta_spec.md（各仓）、language-specific design specifications
**同步/异步**: sync

**Execution**: 完整执行指令（读取 involved_repos、brainstorming design.md 读取、impl_questions 逐条确认、子代理任务描述模板含 10 行输入文件表、并发上限 3 分批启动、容错机制、多仓文档读取确认、跨仓归档引用解析）见 **references/m2-multi.md**（本 M 阶段唯一执行权威）。

**Output**: 各涉及仓的 `delta_design.md`、`tasks.md`、`delta_test_design.md` + 新增 artifact（T5.6 委托，详见 `references/m2-multi.md` 步骤 7）
**Checkpoint**: 所有涉及仓的设计文档已生成 + 多仓文档读取确认已输出 + impl_questions用户确认已完成

## M-3: 各仓审查并行执行（subagent并行 + 用户决策升级）

**适用阶段**：Phase 9（design-traceability L2/L3，**[可配置: design_traceability]**）、Phase 10（design-doc-reviewer审查，**[可配置: design_review]**）
**设计决策**：各仓审查是仓内独立操作，使用subagent并行执行以提升效率。当子代理遇到需要用户决策的问题时，通过升级机制交由主会话处理。

> **M-3a/M-3b 可配置说明**（执行与否以执行计划为准，见文件头部"可配置步骤与编排点"）：
> - **`design_traceability` 关闭** → M-3a 整体跳过，**不 Read `ref_file.multi` 指令文件**（内容不进上下文），M-2 完成后直接进入 M-3b；M-3a 的必经关卡/禁止主会话/ERROR 禁止推迟强制位同步豁免
> - **`design_review` 关闭** → M-3b 整体跳过，**不 Read `ref_file.multi` 指令文件**（内容不进上下文），M-3a 通过后（或 `design_traceability` 关闭跳过 M-3a）直接进入 cleanup；M-3b 的必经关卡/禁止主会话强制位同步豁免
> - **`design_traceability` 关闭但 `design_review` 开启** → "M-3a 全过后才执行 M-3b"依赖随 `design_traceability` 关闭豁免，M-2 完成后直接进入 M-3b

**【强制】Phase 9（cross-doc-checker）和Phase 10（design-doc-reviewer）是两个不同的审查阶段，必须按顺序依次执行**（`design_traceability` 和 `design_review` 均开启时）：
- **Phase 9先执行**：cross-doc-checker验证追溯链（delta_spec→delta_design→tasks），使用L2/L3层CHECK-ID集合
- **Phase 10后执行**：design-doc-reviewer审查文档质量（章节完整性/模糊词/视图完整性等），使用R7~R12 CHECK-ID集合
- **禁止混淆**：两个skill的CHECK-ID集合完全不同，不可互相替代。禁止在Phase 9调用design-doc-reviewer，禁止在Phase 10调用cross-doc-checker

**执行方式**：

### M-3a: Phase 9 — cross-doc-checker L2/L3 追溯验证 **[可配置: design_traceability]**

<!-- GATE:REF references/design-traceability-multi.md -->
**MANDATORY GATE（`design_traceability` 开启时生效）**: 进入 M-3a 前必须先 Read 本SKILL所在目录下的 `references/design-traceability-multi.md`（M-3a 完整执行指令：subagent 强制、子代理任务描述模板、L2/L3 分层验证、3轮自动修复循环、ESCALATE升级、主会话后处理、并发≤3、衔接豁免）。
绝对路径 = config_dir / 'skills/core-design/references/design-traceability-multi.md'（动态路径解析参见 SKILL.md Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止降级为主会话直接执行追溯验证。
读取后输出: "GATE PASSED: references/design-traceability-multi.md loaded"。
<!-- /GATE:REF -->

**Replaces**: 单仓 Phase 9 design-traceability
**Input**: 各仓 delta_design.md、tasks.md、delta_test_design.md
**同步/异步**: sync

**Execution**: 完整执行指令（subagent强制、子代理任务描述模板、L2→L3分层验证、3轮自动修复循环、ESCALATE升级、主会话后处理含降级策略、并发上限3分批启动、衔接豁免）见 **references/design-traceability-multi.md**（本 M 阶段唯一执行权威）。

**Output**: 各仓追溯验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的 L2/L3 追溯验证已完成

### M-3b: Phase 10 — design-doc-reviewer 审查 **[可配置: design_review]**

<!-- GATE:REF references/design-review-multi.md -->
**MANDATORY GATE（`design_review` 开启时生效）**: 进入 M-3b 前必须先 Read 本SKILL所在目录下的 `references/design-review-multi.md`（M-3b 完整执行指令：subagent强制、子代理任务描述模板、design-doc-reviewer审查维度、3轮自动修复循环、ESCALATE升级、主会话后处理、M-3a→M-3b依赖豁免、衔接豁免）。
绝对路径 = config_dir / 'skills/core-design/references/design-review-multi.md'（动态路径解析参见 SKILL.md Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止降级为主会话直接执行文档审查。
读取后输出: "GATE PASSED: references/design-review-multi.md loaded"。
<!-- /GATE:REF -->

**Replaces**: 单仓 Phase 10 design-review
**Input**: 各仓 delta_design.md、delta_test_design.md、tasks.md
**同步/异步**: sync

**【强制前置】M-3a（cross-doc-checker L2/L3）必须全部通过后才能执行M-3b** — 追溯链验证不通过时，design-doc-reviewer审查无意义。**例外**：`design_traceability` 关闭时 M-3a 被跳过，M-2 完成后直接进入 M-3b（"M-3a 全过后才执行 M-3b"依赖随 `design_traceability` 关闭豁免）。

**Execution**: 完整执行指令（subagent强制、子代理任务描述模板、审查维度、3轮自动修复循环、ESCALATE升级、主会话后处理含降级策略、并发上限3分批启动、衔接豁免）见 **references/design-review-multi.md**（本 M 阶段唯一执行权威）。

**Output**: 各仓审查报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的 design-doc-reviewer 审查已完成

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

## cleanup: 清理临时文件（多仓模式） **[可配置: cleanup]**

> 本步骤为可配置步骤。执行与否以执行计划为准（见文件头部"可配置步骤与编排点"）：
> - **执行计划 steps 数组含 `config_key=cleanup` 条目** → 读取其 `ref_file.multi` 指令文件并执行，本阶段完整指令见该文件
> - **执行计划不含本步骤** → 跳过，指令文件不加载，**"最后阶段禁止跳过"强制位同步豁免**；需显式记录"cleanup 已关闭，临时文件残留"后输出执行总结并宣布流程完毕（残留由用户或后续人工处理）

<!-- GATE:REF references/cleanup-multi.md -->
**MANDATORY GATE（`cleanup` 开启时生效）**: 进入 cleanup 前必须先 Read 本SKILL所在目录下的 `references/cleanup-multi.md`（cleanup 完整执行指令：项目级清理清单 + 各仓级清理清单 + 跨阶段引用文件保留列表 + 清理验证 + 执行时机 + 关闭语义）。
绝对路径 = config_dir / 'skills/core-design/references/cleanup-multi.md'（动态路径解析参见 SKILL.md Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止降级为主会话直接执行清理。
读取后输出: "GATE PASSED: references/cleanup-multi.md loaded"。
<!-- /GATE:REF -->

**Replaces**: 单仓 Phase 11 cleanup（多仓模式下清理范围扩大到各仓变更目录）
**Input**: 各仓变更目录 + 项目级变更目录

**Execution**: 完整执行指令（项目级清理：design.md/clarification_summary.json/drafts/shared_context.md/impl_questions_for_design.json/downloads/；各仓级清理：各仓 downloads/ 子目录；跨阶段引用文件保留：repo_assignments.json/cross_repo_contracts.json；清理验证；执行时机；关闭语义）见 **references/cleanup-multi.md**（本阶段唯一执行权威）。

**Output**: 项目级 + 各仓级变更目录已清理（仅保留核心交付物和跨阶段引用文件）
**Checkpoint**: 可清理文件已删除；禁止删除列表中的文件全部保留
**自动继续**：清理完成后，输出执行总结并宣布"core-design流程执行完毕"。**禁止在M-3b或更早阶段宣布流程完毕** — M-3b所有仓审查通过后必须继续执行cleanup（`cleanup` 关闭时豁免，见上方引用块）。

## Contracts Lifecycle (本 skill 职责)

| 阶段 | 操作 | status转换 | 副本刷新 |
|------|------|-----------|----------|
| M-2 按仓生成 | 设计阶段发现新接口，追加contract | -> `proposed` | 刷新definition_repo和consumer_repos的副本 |
| M-2 按仓生成 | 设计完成，接口确认 | `proposed` -> `confirmed` | 刷新涉及仓副本 |

