# M-2 子代理任务描述模板（指令文件）

> 本文件为 multi-repo.md M-2 的子代理任务描述模板，**无条件加载**（M-2 执行时由主会话 Read）。主会话在 M-2 Step 6 构造子代理 prompt 时，将本模板中的 `{repo}` / `{repo_path}` / `{change_name}` / `{project_root}` / `{skill_dir}` / `{prepared_context}` 占位符替换为实际值后作为子代理任务描述。

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
| 6 | 执行计划片段 | {project_root}/docs/.flow_context/execution-plan-fragment-core-apply-{repo}.json | **编排输入**：本仓执行计划片段（repo/repo_cwd/plan_path/built_in_steps/orchestration_points，其中 orchestration_points 含五个插槽）；`built_in_steps.skill_consumption` 控制 M-1a 准备结果的使用，`plan_path` 仅记录来源。pre-codegen 插槽条目在任务级执行，post-codegen 插槽条目在代码生成完成后执行；不在插槽中的编排点不执行 |
| 7 | code-gen-principles.md | {skill_dir}/references/code-gen-principles.md | **原则约束（必读）**：15条代码生成原则（C-1~C-15），每个代码生成任务执行前必须对照自检，违反=代码不合格 |

**路径说明**：{skill_dir} 为 core-apply 技能安装目录，主会话在构造子代理 prompt 时必须将 {skill_dir} 替换为实际绝对路径（解析方式见 SKILL.md Reference文件路径解析章节）。

M-1a 准备结果（本轮只读上下文，不是执行指令或启停依据）：
{prepared_context}

内置步骤关闭时忽略这段上下文；启用且准备结果缺失时返回主会话补齐，不自行重复准备。

执行步骤：
a. 读取所有输入文件，核对输入 #6 的 `repo` / `repo_cwd` 与本仓一致；片段无效时停止并报告。读取输入 #7 后必须输出 "GATE PASSED: references/code-gen-principles.md loaded"，缺少读取或输出记录不得开始代码生成。
   - 输入 #6 必须包含 `built_in_steps.skill_consumption`，且 `phase=M-1a`、`enabled` 为布尔值；缺失或无效时返回主会话重新生成片段。
   - `enabled=true` 时，Read 其 `ref_file`，只加载“代码生成代理使用准备结果”节一次；`enabled=false` 时跳过，不加载消费指令、忽略准备上下文。启用但指令文件或准备结果缺失时停止并报告。
b. **使用 M-1a 已准备的任务上下文**：在步骤 e 的 P0/P1/P2 展示后，按步骤 a 加载的多仓指令使用当前任务上下文。复用主会话准备结果，不重复准备；新增用户决策事项返回主会话统一处理。消费关闭时跳过，继续步骤 c 的通用插槽。
c. **pre-codegen 插槽调度规则（在步骤 e 的 P0/P1/P2 展示后、原则自检前，每任务执行一次）**：读取输入 #6 中 `orchestration_points.pre-codegen` 的启用条目，按计划顺序（`order` 升序）串行执行，显式 `enabled=false` 时跳过——
   - `type=reference` → Read 条目 `file` 字段指令文件并执行
   - `type=skill` → 调用条目 `skill` 字段指定 skill（`run_mode=subagent` 时 spawn 独立子代理）
   - 插槽为空 → 跳过，不加载指令文件
   - 新增用户决策事项返回主会话汇总；片段无效或启用条目的文件缺失时停止并报告
d. **测试策略解析（进入任务循环前）**：读取本仓 tasks.md 头部 `测试策略` 字段（tdd / test-after；字段不存在默认 test-after）。两种策略共用下方 step e 同一流程，差异仅在 step e 的"执行代码生成"处：`tdd` 时按 `references/red-green-tdd.md` 测试先行（先写失败测试确认红灯，再实现最少代码确认绿灯），`test-after` 时直接生成代码。
e. 对tasks.md中每个待执行的代码生成任务（`- [ ]`状态），执行以下代码生成流程：
   - **【强制】循环对象边界**：仅执行 tasks.md `## 代码生成任务` 章节（1.x）的待办任务。tasks.md 的 `## Code Review 任务`（2.x）属 M-4（`code_review`）、`## 单元测试任务`（3.x）属 M-5（`unit_test`），由对应 M 阶段子代理执行，**禁止**在本步骤执行；M-4/M-5 由主会话单独调度，代码生成代理不判断或执行这两个阶段。若 1.x 全部 `- [x]` 无待办，直接执行步骤 f（post-codegen 编排点），**不得**将 2.x/3.x 未完成任务作为本步骤循环对象
   - 执行任务级代码理解：
     - 先尝试调用 CodeBase 工具（GetRemoteCallChain/CodeSemanticSearch/GetFeatureTree）
     - CodeBase 不可用或无结果 → 回退到 grep/read/glob
     - 最终必须通过 read 实际读取代码验证
   - 解析任务的"设计锚点"字段，定位delta_design.md中的设计模块
   - 按P0→P1→P2三阶段展示设计信息（P0必须参考 → P1应当参考 → P2建议参考）
   - 按步骤 b 使用当前任务的准备结果，再按步骤 c 执行本任务的通用 `pre-codegen` 插槽
   - **代码生成原则自检**：对照 code-gen-principles.md（输入#7）C-1~C-15，每个任务执行前必须自检增量开发、代码复用、质量硬约束
   - 执行代码生成（Edit/Write工具；**tdd 时按 d 改为测试先行**——Read `references/red-green-tdd.md`，先写失败测试确认红灯，再实现最少代码确认绿灯，编译检查）
   - 标记任务完成：将tasks.md中对应任务 `- [ ]` 改为 `- [x]`
f. 所有任务完成后，**post-codegen 插槽条目（修复闭环）**：读取输入 #6 中 `orchestration_points.post-codegen` 条目，按同样规则执行（reference → Read 执行；skill → 调用，subagent 时 spawn 子代理）；插槽为空 → 跳过
g. 汇总生成结果：
   - 已完成任务数/总任务数
   - 每个任务的生成文件列表
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

