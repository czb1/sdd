# Multi-Repo Enhancement: core-apply

**Skill**: core-apply
**Depends On**: repo_assignments.json
**Step Mapping Authority**: M-编号与 steps.md 序号一一对应（M-1→Step3, M-2→Step4~9, M-3→Step10, M-4→Step11, M-5→Step12, M-6→Step13）

## 可配置步骤与编排点（多仓模式）

多仓模式下，可配置步骤（L4/Code Review/UT/L5）与编排点插槽的**执行与否以 Step 0 持久化的执行计划为准**（`docs/.flow_context/execution-plan-core-apply.json`），与单仓模式同一权威：

- **可配置步骤**（`steps` 数组 `type=built_in` 条目，`ref_file.multi`）：`l4_review`（M-3）/ `code_review`（M-4）/ `unit_test`（M-5）/ `l5_coverage`（M-6）
  - **执行计划 steps 数组含该 `config_key` 条目** → 从条目 `ref_file.multi` 字段取指令文件（动态路径解析参见 SKILL.md Reference文件路径解析章节）并 Read，按其中指令执行
  - **执行计划不含该 `config_key` 条目** → 该步骤跳过，**不 Read 指令文件**（内容不进上下文），直接进入下一 M 阶段
  - `l5_coverage` 依赖 `unit_test`：UT 关闭则 L5 自动降级（执行计划 disabled 区标记），两文件均不 Read
- **主会话执行的可配置步骤**（不映射 M 阶段，与单仓同一机制、同一执行计划条目）：`version_check`（Step 1，M-1 之前执行）/ `show_progress`（Step 8，M-2 之前执行，**默认关闭**，执行计划含条目才执行）/ `completion_report`（Step 14，M-6 之后 on-completion 执行）。三者 `ref_file.multi` 为单仓多仓通用文件（references/version-check.md / show-progress.md / completion-report.md），存在性判断同单仓
- **编排点插槽**（`orchestration_points` 对象）：`pre-codegen`（M-2 子代理内 task 级）/ `post-codegen`（M-2 后）/ `post-l4`（M-3 后）/ `post-review`（M-4 后）/ `post-ut`（M-5 后）
  - **对应插槽数组含条目** → 按条目 `type` 执行（`reference`：Read `file` 字段指令文件并执行；`skill`：调用 `skill` 字段指定 skill，`run_mode=subagent` 时 spawn 独立子代理）
  - **对应插槽数组为空** → 跳过，指令文件不加载，直接进入下一阶段
- **任务 Skill 消费 [可配置: skill_consumption]（默认关闭）**：仅根执行计划及下发片段的 `pre-codegen` 含该 reference 条目时执行；无条目时不加载消费指令，准备、确认、下载、读取关联内容与回写均跳过；其他 pre-codegen 条目不受影响。
- **`skipped-core-apply.json` 只读**：Step 14 on-completion 展示可配置步骤状态时读取；agent 全程不写

## Skill 消费强制位豁免

| 阶段 | 可配置键 | 关闭时行为 |
|---|---|---|
| M-2 循环前准备 / task 级消费 | `skill_consumption`（reference，默认关闭） | 不加载消费指令，不执行候选准备、确认、下载、关联读取与回写；M-2 核心代码生成及其他编排条目照常执行 |

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
   - **【强制】循环对象边界**：M-2 代码生成循环对象**仅限**各仓 tasks.md `## 代码生成任务` 章节（1.x）。`## Code Review 任务`（2.x）属 M-4（`code_review`）、`## 单元测试任务`（3.x）属 M-5（`unit_test`）——执行计划 steps 数组不含对应 `config_key` 条目（M 关闭）时整章节跳过，**禁止**在 M-2 代码生成循环中执行；1.x 全部 `- [x]` 无待办时直接结束 M-2（进入 post-codegen 编排点判断），不得将 2.x/3.x 作为 M-2 循环对象
### 代码生成代理启动前：任务 Skill 消费准备 [可配置: skill_consumption]（默认关闭）

> 仅当执行计划 `execution-plan-core-apply.json` 的 `orchestration_points.pre-codegen` 含 `key=skill_consumption` 的 reference 条目时执行；未配置、已注释或计划中无该条目时跳过，不加载消费指令。仅启用且存在待办 1.x 任务时，由主会话按专属指令完成准备，再启动代码生成代理。

<!-- GATE:REF references/skill-consumption.md -->
**MANDATORY GATE（仅启用时）**：Read 本 SKILL 安装目录下的 `references/skill-consumption.md`；文件不存在时 MUST STOP。
读取后输出: "GATE PASSED: references/skill-consumption.md loaded"。
<!-- /GATE:REF -->

**Execution**：完整执行指令见 `references/skill-consumption.md`；配置方式见 `../core-shared/references/skill-consumption-config.md`。

6. **【强制】使用子代理并行执行各仓代码生成**（禁止在主会话中逐仓顺序执行）：

   <!-- GATE:REF multi-codegen-template.md -->
   **MANDATORY GATE**: M-2 执行前必须先 Read 本SKILL所在目录下的 `references/multi-codegen-template.md`。
   绝对路径 = config_dir / 'skills/core-apply/references/multi-codegen-template.md'（动态路径解析参见 SKILL.md Reference文件路径解析章节）。
   文件不存在时 MUST STOP，禁止降级为主会话顺序执行。
   读取后输出: "GATE PASSED: references/multi-codegen-template.md loaded"。
   <!-- /GATE:REF -->

   子代理任务描述模板：使用 `references/multi-codegen-template.md`（GATE 已加载）中的模板，将 `{repo}` / `{repo_path}` / `{change_name}` / `{project_root}` / `{skill_dir}` 占位符替换为实际值后作为子代理任务描述。**禁止改写模板中的输入文件表与执行步骤**——子代理按模板流程执行（步骤 c 内嵌 9.1~9.5 等价流程：代码理解 → 锚点解析 → P0/P1/P2 展示 → 按执行计划执行 pre-codegen（Skill 消费默认关闭）→ 原则自检 → 代码生成；模板内已含测试策略解析，tdd 时按红-绿循环执行）。

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

## M-3: 各仓L4实现追溯验证（subagent并行） **[可配置: l4_review]**

> **本步骤为可配置步骤**。执行与否以执行计划为准（见文件头部"可配置步骤与编排点"）：
> - **执行计划 steps 数组含 `config_key=l4_review` 条目** → 读取其 `ref_file.multi` 指令文件并执行，本 M 阶段指令见该文件
> - **执行计划不含本步骤** → 跳过，指令文件不加载，直接进入 M-4

**Replaces**: steps.md Step 8 gate-1-traceability（单仓步骤）
**Input**: 各仓已生成的代码文件、tasks.md
**Output**: 各仓L4验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L4验证已完成

## M-4: 各仓Code Review（subagent并行） **[可配置: code_review]**

> **本步骤为可配置步骤**。执行与否以执行计划为准（见文件头部"可配置步骤与编排点"）：
> - **执行计划 steps 数组含 `config_key=code_review` 条目** → 读取其 `ref_file.multi` 指令文件并执行，本 M 阶段指令见该文件
> - **执行计划不含本步骤** → 跳过，指令文件不加载，直接进入 M-5

**Replaces**: steps.md Step 9 code-review（单仓步骤）
**Input**: 各仓代码文件（仅增量变更文件）
**Output**: 各仓Code Review报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的Code Review已完成

## M-5: 各仓单元测试（subagent并行） **[可配置: unit_test]**

> **本步骤为可配置步骤**。执行与否以执行计划为准（见文件头部"可配置步骤与编排点"）：
> - **执行计划 steps 数组含 `config_key=unit_test` 条目** → 读取其 `ref_file.multi` 指令文件并执行，本 M 阶段指令见该文件
> - **执行计划不含本步骤** → 跳过，指令文件不加载，直接进入 M-6

**Replaces**: steps.md Step 10 unit-test（单仓步骤）
**Input**: 各仓代码文件、delta_test_design.md、tasks.md（编程语言/UT生成技能字段）
**Output**: 各仓UT报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的UT已完成

## M-6: 各仓L5 UT覆盖度验证（subagent并行） **[可配置: l5_coverage]**

> **本步骤为可配置步骤**。执行与否以执行计划为准（见文件头部"可配置步骤与编排点"）：
> - **执行计划 steps 数组含 `config_key=l5_coverage` 条目** → 读取其 `ref_file.multi` 指令文件并执行，本 M 阶段指令见该文件
> - **执行计划不含本步骤** → 跳过，指令文件不加载，直接结束流程进入 on-completion
> - **依赖规则**：`l5_coverage` 依赖 `unit_test`。`unit_test` 关闭 → L5 自动降级，本文件不 Read

**Replaces**: steps.md Step 11 gate-2-coverage（单仓步骤）
**Input**: 各仓UT代码、delta_test_design.md、业务代码头文件、tasks.md
**Output**: 各仓L5验证报告（PASSED/FIXED/ESCALATE + 用户决策记录）
**Checkpoint**: 所有涉及仓的L5验证已完成

## Contracts Lifecycle (本 skill 职责)

| 阶段 | 操作 | status转换 | 副本刷新 |
|------|------|-----------|----------|
| M-2 按仓路由 | 实现时修改接口（更新last_updated_at） | `confirmed` -> `confirmed` | 刷新涉及仓副本 |

