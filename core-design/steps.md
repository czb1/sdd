# core-design 必含步骤

以下步骤必须在 plan 的 phases 中逐一覆盖，每个步骤对应一个 Phase。

**【强制】步骤10~12（追溯验证/design-review/cleanup）为可配置步骤** — 执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：steps 数组含对应 `config_key`（`design_traceability`/`design_review`/`cleanup`）条目 → 强制不可跳过，禁止在步骤8后宣布流程完毕；不含 → 跳过该步骤并豁免对应强制位（含"禁止宣布完毕"限制、"禁止主会话直接执行"限制）。

**【强制】步骤1（version_check）、2（fetch_rules）、5（read_similar）、7（expert_experience）、9（skill_consumption，默认关闭）为可配置步骤** — 执行与否以执行计划为准：含对应 `config_key` 条目 → 按 SKILL.md 占位行 + `ref_file.single` 指令文件执行；不含 → 跳过该步骤，直接进入下一步骤。

**【强制】步骤10（追溯验证，`design_traceability` 开启时）使用 cross-doc-checker，步骤11（design-review，`design_review` 开启时）使用 design-doc-reviewer** — 禁止合并或混淆这两个步骤，禁止用 design-doc-reviewer 替代 cross-doc-checker 执行步骤10。对应 `config_key` 不含于执行计划时，步骤跳过且本强制位豁免。

**【强制】步骤10（追溯验证，`design_traceability` 开启时）必须通过子代理执行**：禁止主会话直接调用 cross-doc-checker Skill tool 或 Bash 脚本。子代理失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行。`design_traceability` 不含于执行计划时，步骤跳过且本强制位豁免。

**【强制】步骤11（design-review，`design_review` 开启时）必须通过子代理执行**：禁止主会话直接调用 design-doc-reviewer Skill tool 或 Bash 脚本。子代理失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行。`design_review` 不含于执行计划时，步骤跳过且本强制位豁免。

**【B 档双层语义】步骤2（fetch-design-rules，`fetch_rules`）关闭时**：仅跳过 code-rule 拉取（Step 1~3），**GATE（design-principles.md / design-views.md）不受开关控制**，仍无条件加载。

**【关键】plan 阶段前必须判断 is_multi_repo**，然后根据结果选择对应的阶段列表写入 plan。禁止在未检测的情况下写入 plan。

**plan 阶段多仓检测方式**：读取 `docs/changes/<change>/repo_assignments.json`，`involved_repos > 1` 则为多仓。文件不存在时读取 `docs/relationship.md` 内容判断。

---

## 单仓模式（is_multi_repo = False）

| 序号 | 步骤名 | 对应 SKILL.md Phase | 说明 |
|------|--------|-------------------|------|
| 1 | version-check **[可配置: version_check]** | Phase 1 | Version Check (MANDATORY) — 必须为第一个 Phase 的第一个动作。`version_check` 不含于执行计划时跳过 |
| 2 | fetch-design-rules **[可配置: fetch_rules]** | Phase 2 | 多语言规范获取 + 设计原则/视图约束 GATE 加载。**B 档双层语义**：`fetch_rules` 关闭仅跳过 code-rule 拉取，GATE 仍无条件加载 |
| 3 | gather-context | Phase 3 | 读取 delta_spec.md + 全局文档 |
| 4 | code-understanding | Phase 4 | 代码理解：CodeBase 优先 → read/grep/glob 回退 → read 验证 |
| 5 | read-similar-changes **[可配置: read_similar]** | Phase 5 | 读取 Similar Requirements Reference 归档文件。`read_similar` 不含于执行计划时跳过 |
| 6 | read-brainstorming-output | Phase 6 | 读取 .brainstorming_output 元数据 + design.md |
| 7 | fetch-expert-experience **[可配置: expert_experience]** | Phase 7 | 准备已有项目经验及查找上下文；不独立拉取经验。`expert_experience` 不含于执行计划时跳过 |
| 8 | generate-artifacts | Phase 8 | 生成设计文档：读取参考 → 对照原则/视图约束 → 填充模板 → 锚点提取 |
| 9 | skill-consumption **[可配置: skill_consumption]** | Phase 9 | 任务 Skill 查找、确认、安装与关联；按启用条目的 `ref_file.single` 执行，关闭时跳过 |
| 10 | design-traceability **[可配置: design_traceability]** | Phase 10 | 设计追溯验证：cross-doc-checker --layer L2 + --layer L3（**必须使用 Skill tool 调用**，**强制 subagent 执行**）。`design_traceability` 不含于执行计划时跳过并豁免强制位（含 Phase 10→11 转换门控） |
| 11 | design-review **[可配置: design_review]** | Phase 11 | design-doc-reviewer 审查（**强制 subagent 执行**）。`design_review` 不含于执行计划时跳过并豁免强制位（含 Phase 11→12 转换门控） |
| 12 | cleanup-brainstorming **[可配置: cleanup]** | Phase 12 | 清理 brainstorming 临时文件 + clarification_summary.json。**core-design 流程最后一步（`cleanup` 开启时），禁止跳过**。`cleanup` 不含于执行计划时跳过，须显式记录"cleanup 已关闭，临时文件残留" |

---

## 多仓模式（is_multi_repo = True）

**【强制】当 plan 阶段检测为多仓环境时，必须使用以下阶段替换单仓模式阶段：**

| 序号 | 步骤名 | 对应 SKILL.md Phase | 说明 |
|------|--------|-------------------|------|
| 1 | version-check **[可配置: version_check]** | Phase 1 | Version Check (MANDATORY) — 不变 |
| 2 | fetch-design-rules **[可配置: fetch_rules]** | Phase 2 | 多语言规范获取 + 设计原则/视图约束 GATE 加载（不变）。B 档双层语义同单仓 |
| 3 | gather-context | Phase 3 | 读取 delta_spec.md + 全局文档；多仓校验按 multi-repo.md M-1 执行 |
| 4 | code-understanding | Phase 4 | 代码理解（不变） |
| 5 | read-similar-changes **[可配置: read_similar]** | Phase 5 | 读取 Similar Requirements Reference（不变） |
| 6 | read-brainstorming-output | Phase 6 | 读取 .brainstorming_output 元数据 + design.md（不变） |
| 7 | fetch-expert-experience **[可配置: expert_experience]** | Phase 7 | 准备已有项目经验及查找上下文（不变） |
| 8 | M-2 | Phase 8 | 各仓按仓生成设计文档 — 按 multi-repo.md 执行（含 impl_questions 用户确认 + subagent 并行文档生成，替代单仓 generate-artifacts） |
| 9 | skill-consumption **[可配置: skill_consumption]** | Phase 9 | M-2 全部仓完成后由主会话聚合执行一次；按启用条目的 `ref_file.multi` 执行，关闭时跳过 |
| 10 | M-3a **[可配置: design_traceability]** | Phase 10 | 设计追溯验证 — 按 multi-repo.md M-3a + `ref_file.multi` 指令文件 subagent 并行执行（**强制调用 cross-doc-checker，禁止用 design-doc-reviewer 替代**）。`design_traceability` 不含于执行计划时跳过 M-3a 并豁免强制位 |
| 11 | M-3b **[可配置: design_review]** | Phase 11 | design-doc-reviewer 审查 — 按 multi-repo.md M-3b + `ref_file.multi` 指令文件 subagent 并行执行（**强制调用 design-doc-reviewer，禁止用 cross-doc-checker 替代；`design_traceability` 开启时 M-3a 全部通过后方可执行**）。`design_review` 不含于执行计划时跳过 M-3b 并豁免强制位 |
| 12 | cleanup **[可配置: cleanup]** | Phase 12 | 清理临时文件 — 按 multi-repo.md cleanup + `ref_file.multi` 指令文件执行（项目级 + 各仓级双层清理）。**core-design 流程最后一步（`cleanup` 开启时），禁止跳过**。`cleanup` 不含于执行计划时跳过，须显式记录"cleanup 已关闭，临时文件残留" |

**【禁止】多仓模式下使用单仓模式的 phase 列表** — 这会导致 CMS 阶段与 M-* 步骤冲突，文件创建被阻止。
