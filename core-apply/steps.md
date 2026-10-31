# core-apply 必含步骤

以下步骤必须在 plan 的 phases 中逐一覆盖，每个步骤对应一个 Phase。

**【关键】plan 阶段前必须判断 is_multi_repo**，然后根据结果选择对应的阶段列表写入 plan。禁止在未检测的情况下写入 plan。

**plan 阶段多仓检测方式**：读取 `docs/changes/<change>/repo_assignments.json`，`involved_repos > 1` 则为多仓。文件不存在时为单仓。

---

## 单仓模式（is_multi_repo = False）

| 序号 | 步骤名 | 对应 SKILL.md Step | 说明 |
|------|--------|-------------------|------|
| 0 | build-execution-plan | Step 0 | 构建执行计划（MANDATORY）— 必须为第一个 Phase 的第一个动作，先于 version-check；`main.py flow-config --json --skill core-apply`，持久化 execution-plan-core-apply.json / skipped-core-apply.json，按 config_missing 与 scenario A~E 确认（首次运行无配置文件时先提供配置机会） |
| 1 | version-check | Step 1 | Version Check **[可配置: version_check]** — 第一个 Phase 的第二个动作，紧随 Step 0；指令文件 references/version-check.md，存在性判断见执行计划（含则 Read 执行，不含则跳过） |
| 2 | select-change | Step 2 | 选择 change；多个活跃 change 时用 AskUserQuestion 让用户选择 |
| 3 | multi-repo-detect | Step 3 | 多仓检测与路由 — 读取repo_assignments.json判断模式；单仓模式继续Step 4，多仓模式进入M-1~M-6 |
| 4 | check-status | Step 4 | 检查 change 状态（schema / artifacts / tasks）— **仅单仓模式** |
| 5 | get-apply-instructions | Step 5 | 获取执行指令（contextFiles / progress / task list） |
| 6 | read-context | Step 6 | 读取上下文文件 |
| 7 | load-code-gen-principles | Step 7 | GATE 加载代码生成原则（references/code-gen-principles.md） |
| 8 | show-progress | Step 8 | 展示当前进度 **[可配置: show_progress]**（默认关闭）：指令文件 references/show-progress.md，存在性判断见执行计划（含则 Read 执行，不含则跳过） |
| 9 | skill-consumption | Step 9 | 任务 Skill 准备与消费 **[可配置: skill_consumption]**（默认关闭）；主会话按启用条目的 `ref_file.single` 准备一次，Step 10 在每任务独立检查点消费；关闭时不加载指令文件 |
| 10 | implement-code-gen | Step 10 | 代码生成：GATE 加载 references/code-generation-procedure.md（10.1 代码理解 → 10.2 锚点解析 → 10.3 P0/P1/P2 展示 → [内置每任务检查点] → [pre-codegen 编排点] → 10.4 原则自检 → 10.5 代码生成）→ 标记完成。**循环对象仅限 tasks.md `## 代码生成任务` 章节（1.x）**；`## Code Review 任务`（2.x）属 Step 12（code_review）、`## 单元测试任务`（3.x）属 Step 13（unit_test），对应可配置步骤关闭时整章节跳过、禁止在 Step 10 执行 |
| 11 | gate-1-traceability | Step 11 | 门控1 L4 实现追溯验证 **[可配置: l4_review]**：指令文件 references/l4-review.md，存在性判断见执行计划（含则 Read 执行，不含则跳过） |
| 12 | code-review | Step 12 | Code Review **[可配置: code_review]**：指令文件 references/code-review.md，存在性判断见执行计划 |
| 13 | unit-test | Step 13 | 单元测试 **[可配置: unit_test]**：指令文件 references/unit-test.md，存在性判断见执行计划 |
| 14 | gate-2-coverage | Step 14 | 门控2 L5 UT覆盖度验证 **[可配置: l5_coverage]**：指令文件 references/l5-coverage.md，存在性判断见执行计划（依赖 unit_test，UT 关闭则自动降级） |
| 15 | on-completion | Step 15 | 完成或暂停时展示状态 **[可配置: completion_report]**：指令文件 references/completion-report.md，存在性判断见执行计划（含则 Read 执行，不含则直接结束流程）；读 skipped-core-apply.json 展示可配置步骤状态 |

**编排点插槽**（change 级，查执行计划存在性判断，有条目则执行、无条目则跳过）：`post-codegen`（Step 10 后）、`post-l4`（Step 11 后）、`post-review`（Step 12 后）、`post-ut`（Step 13 后）。

---

## 多仓模式（is_multi_repo = True）

**【强制】当 plan 阶段检测为多仓环境时，必须使用以下阶段替换单仓模式阶段：**

**【重要】多仓模式下 tasks.md 路径**：tasks.md 位于各仓目录下（如`cm/docs/changes/<change>/tasks.md`），**不是**项目根目录。M-2子代理从各仓目录读取 tasks.md。根目录 `docs/changes/<name>/tasks.md` 在多仓模式下不存在。

| 序号 | 步骤名 | 对应 SKILL.md Step | 说明 |
|------|--------|-------------------|------|
| 0 | build-execution-plan | Step 0 | 构建执行计划（MANDATORY）— 必须为第一个 Phase 的第一个动作，先于 version-check；`main.py flow-config --json --skill core-apply`，持久化 execution-plan-core-apply.json / skipped-core-apply.json，按 config_missing 与 scenario A~E 确认（多仓下计划放根项目 docs/.flow_context/） |
| 1 | version-check | Step 1 | Version Check **[可配置: version_check]** — 第一个 Phase 的第二个动作，紧随 Step 0，多仓下不变；指令文件 references/version-check.md（单多仓通用），存在性判断见执行计划；Step 8 同为主会话可配置步骤（show_progress 默认关闭，M-2 之前存在性判断执行） |
| 2 | select-change | Step 2 | 选择 change — 不变 |
| 3 | M-1 | Step 3 | 多仓检测 + 多仓 change 状态检查 — 读取 repo_assignments.json，确认 involved_repos 列表 + Agent 直接 Glob/Read 检查各仓 artifacts/tasks 状态 + 加载 references/multi-repo.md GATE |
| 4 | skill-consumption | Step 9 | **[可配置: skill_consumption]**（默认关闭）；主会话在 M-2 启动前按启用条目的 `ref_file.multi` 准备一次，子代理从根计划读取同一开关执行每任务动作 |
| 5~8 | M-2 | Step 4~8、Step 10 | 按仓拓扑分批 + 子代理并行代码生成（含代码生成原则注入 + 内置每任务检查点 + pre-codegen 编排点） — 按 references/multi-repo.md 执行（GATE 加载 multi-codegen-template.md 子代理模板），子代理按拓扑分批并行读取 context files + 原则文件 + 并行执行代码生成（**循环对象仅限 tasks.md `## 代码生成任务` 章节 1.x**；2.x 属 M-4、3.x 属 M-5，对应 M 关闭时整章节跳过，禁止在 M-2 执行） |
| 9 | M-3 | Step 11 | 各仓 L4 实现追溯验证 **[可配置: l4_review]** — 指令文件 references/l4-review-multi.md，存在性判断见执行计划（subagent 并行） |
| 10 | M-4 | Step 12 | 各仓 Code Review **[可配置: code_review]** — 指令文件 references/code-review-multi.md，存在性判断见执行计划（subagent 并行） |
| 11 | M-5 | Step 13 | 各仓单元测试 **[可配置: unit_test]** — 指令文件 references/unit-test-multi.md，存在性判断见执行计划（subagent 并行） |
| 12 | M-6 | Step 14 | 各仓 L5 UT 覆盖度验证 **[可配置: l5_coverage]** — 指令文件 references/l5-coverage-multi.md，存在性判断见执行计划（依赖 unit_test，UT 关闭则自动降级）（subagent 并行） |
| 13 | on-completion | Step 15 | 完成或暂停时展示状态 **[可配置: completion_report]**：指令文件 references/completion-report.md（单多仓通用），存在性判断见执行计划；汇总各仓状态 + 读 skipped-core-apply.json 展示可配置步骤状态（show_progress 默认关闭，默认计划 skipped 中标记 default_disabled） |

**编排点插槽**（多仓下同样查执行计划）：`post-codegen` / `post-l4` / `post-review` / `post-ut` 在 M-2~M-5 对应阶段后存在性判断执行；`pre-codegen` 在 M-2 子代理内 task 级执行。关闭的步骤指令文件（references/*-multi.md）不被 Read。

**【说明】多仓模式下单仓 Step 4~10 + 门控检查全部由 M-1~M-6 替代**：
- M-1：多仓检测（读取 repo_assignments.json + 多仓 change 状态检查 + 加载 GATE）— 多仓模式下 status 脚本基于根目录路径不适用，M-1 替代为 Agent 直接读取各仓文件检查状态
- Step 9：`skill_consumption` 为默认关闭的内置步骤；主会话在 M-2 启动前从启用条目的 `ref_file.multi` 加载并准备一次，子代理按根计划 `steps` 执行每任务动作。
- M-2：按拓扑分批并行代码生成（定义仓先于消费仓，每仓1个子代理，并发上限3），子代理内部包含读取 context files + 代码生成原则 + 代码生成
- M-3~M-6：分阶段执行，每阶段内各仓 subagent 并行，阶段间串行（所有仓完成 L4 后才进入 Code Review，所有仓完成 Code Review 后才进入 UT，所有仓完成 UT 后才进入 L5）
- 子代理需要用户决策时升级到主会话通过 AskUserQuestion 让用户决策
- 阶段间同步规则对齐 core-explore 的 L1 模式："先全部完成 X，再统一开始 Y"

**【禁止】多仓模式下使用单仓模式的 phase 列表** — 这会导致 CMS 阶段与 M-* 步骤冲突，文件创建被阻止。
