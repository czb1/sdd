# core-apply 必含步骤

以下步骤必须在 plan 的 phases 中逐一覆盖，每个步骤对应一个 Phase。

**【关键】plan 阶段前必须判断 is_multi_repo**，然后根据结果选择对应的阶段列表写入 plan。禁止在未检测的情况下写入 plan。

**plan 阶段多仓检测方式**：读取 `docs/changes/<change>/repo_assignments.json`，`involved_repos > 1` 则为多仓。文件不存在时为单仓。

---

## 单仓模式（is_multi_repo = False）

| 序号 | 步骤名 | 对应 SKILL.md Step | 说明 |
|------|--------|-------------------|------|
| 1 | version-check | Step 1 | Version Check (MANDATORY) — 必须为第一个 Phase 的第一个动作 |
| 2 | select-change | Step 2 | 选择 change；多个活跃 change 时用 AskUserQuestion 让用户选择 |
| 3 | multi-repo-detect | Step 3 | 多仓检测与路由 — 读取repo_assignments.json判断模式；单仓模式继续Step 4，多仓模式进入M-1~M-6 |
| 4 | check-status | Step 4 | 检查 change 状态（schema / artifacts / tasks）— **仅单仓模式** |
| 5 | get-apply-instructions | Step 5 | 获取执行指令（contextFiles / progress / task list） |
| 6 | read-context | Step 6 | 读取上下文文件 |
| 7 | load-code-gen-principles | Step 7 | GATE 加载代码生成原则（references/code-gen-principles.md） |
| 8 | show-progress | Step 8 | 展示当前进度 |
| 9 | implement-code-gen | Step 9 | 代码生成：代码理解 → 锚点解析 → P0/P1/P2展示 → 原则自检 → 代码生成 → 标记完成 |
| 10 | gate-1-traceability | Step 10 | 门控1 L4 实现追溯验证：cross-doc-checker --layer L4（**必须使用Skill tool调用**） |
| 11 | code-review | Step 11 | Code Review：规范加载 → codecheck-for-cleancode → cwd-audit（C/C++/Java/Python/Go） |
| 12 | unit-test | Step 12 | 单元测试：UT生成 → UT修复 → 覆盖率提升 → 断言审查 → 测试报告 |
| 13 | gate-2-coverage | Step 13 | 门控2 L5 UT覆盖度验证：cross-doc-checker --layer L5（**必须使用Skill tool调用**） |
| 14 | on-completion | Step 14 | 完成或暂停时展示状态 |

---

## 多仓模式（is_multi_repo = True）

**【强制】当 plan 阶段检测为多仓环境时，必须使用以下阶段替换单仓模式阶段：**

**【重要】多仓模式下 tasks.md 路径**：tasks.md 位于各仓目录下（如`cm/docs/changes/<change>/tasks.md`），**不是**项目根目录。M-2子代理从各仓目录读取 tasks.md。根目录 `docs/changes/<name>/tasks.md` 在多仓模式下不存在。

| 序号 | 步骤名 | 对应 SKILL.md Step | 说明 |
|------|--------|-------------------|------|
| 1 | version-check | Step 1 | Version Check (MANDATORY) — 不变 |
| 2 | select-change | Step 2 | 选择 change — 不变 |
| 3 | M-1 | Step 3 | 多仓检测 + 多仓 change 状态检查 — 读取 repo_assignments.json，确认 involved_repos 列表 + Agent 直接 Glob/Read 检查各仓 artifacts/tasks 状态 + 加载 references/multi-repo.md GATE |
| 4~7 | M-2 | Step 4~9 | 按仓拓扑分批 + 子代理并行代码生成（含代码生成原则注入） — 按 references/multi-repo.md 执行，子代理按拓扑分批并行读取 context files + 原则文件 + 并行执行代码生成 |
| 8 | M-3 | Step 10 | 各仓 L4 实现追溯验证 — 按 references/multi-repo.md 执行（subagent 并行） |
| 9 | M-4 | Step 11 | 各仓 Code Review — 按 references/multi-repo.md 执行（subagent 并行） |
| 10 | M-5 | Step 12 | 各仓单元测试 — 按 references/multi-repo.md 执行（subagent 并行） |
| 11 | M-6 | Step 13 | 各仓 L5 UT 覆盖度验证 — 按 references/multi-repo.md 执行（subagent 并行） |
| 12 | on-completion | Step 14 | 完成或暂停时展示状态（汇总各仓状态） |

**【说明】多仓模式下单仓 Step 4~9 + 门控检查全部由 M-1~M-6 替代**：
- M-1：多仓检测（读取 repo_assignments.json + 多仓 change 状态检查 + 加载 GATE）— 多仓模式下 status 脚本基于根目录路径不适用，M-1 替代为 Agent 直接读取各仓文件检查状态
- M-2：按拓扑分批并行代码生成（定义仓先于消费仓，每仓1个子代理，并发上限3），子代理内部包含读取 context files + 代码生成原则 + 代码生成
- M-3~M-6：分阶段执行，每阶段内各仓 subagent 并行，阶段间串行（所有仓完成 L4 后才进入 Code Review，所有仓完成 Code Review 后才进入 UT，所有仓完成 UT 后才进入 L5）
- 子代理需要用户决策时升级到主会话通过 AskUserQuestion 让用户决策
- 阶段间同步规则对齐 core-explore 的 L1 模式："先全部完成 X，再统一开始 Y"

**【禁止】多仓模式下使用单仓模式的 phase 列表** — 这会导致 CMS 阶段与 M-* 步骤冲突，文件创建被阻止。
