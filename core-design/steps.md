# core-design 必含步骤

以下步骤必须在 plan 的 phases 中逐一覆盖，每个步骤对应一个 Phase。

**【关键】plan 阶段前必须判断 is_multi_repo**，然后根据结果选择对应的阶段列表写入 plan。禁止在未检测的情况下写入 plan。

**plan 阶段多仓检测方式**：读取 `docs/changes/<change>/repo_assignments.json`，`involved_repos > 1` 则为多仓。文件不存在时读取 `docs/relationship.md` 内容判断。

---

## 单仓模式（is_multi_repo = False）

| 序号 | 步骤名 | 对应 SKILL.md Phase | 说明 |
|------|--------|-------------------|------|
| 1 | version-check | Phase 1 | Version Check (MANDATORY) — 必须为第一个 Phase 的第一个动作 |
| 2 | fetch-design-rules | Phase 2 | 多语言规范获取 + 设计原则/视图约束 GATE 加载 |
| 3 | gather-context | Phase 3 | 读取 delta_spec.md + 全局文档 |
| 4 | code-understanding | Phase 4 | 代码理解：CodeBase 优先 → read/grep/glob 回退 → read 验证 |
| 5 | read-similar-changes | Phase 5 | 读取 Similar Requirements Reference 归档文件 |
| 6 | read-brainstorming-output | Phase 6 | 读取 .brainstorming_output 元数据 + design.md |
| 7 | fetch-expert-experience | Phase 7 | 调用 paradigm-exp-use 获取专家知识；使用后删除 expert_experience.md |
| 8 | generate-artifacts | Phase 8 | 生成设计文档：读取参考 → 对照原则/视图约束 → 填充模板 → 锚点提取 |
| 9 | design-traceability | Phase 9 | 设计追溯验证：cross-doc-checker --layer L2 + --layer L3（**必须使用 Skill tool 调用**） |
| 10 | design-review | Phase 10 | design-doc-reviewer 审查 |
| 11 | cleanup-brainstorming | Phase 11 | 清理 brainstorming 临时文件 + clarification_summary.json |

---

## 多仓模式（is_multi_repo = True）

**【强制】当 plan 阶段检测为多仓环境时，必须使用以下阶段替换单仓模式阶段：**

| 序号 | 步骤名 | 对应 SKILL.md Phase | 说明 |
|------|--------|-------------------|------|
| 1 | version-check | Phase 1 | Version Check (MANDATORY) — 不变 |
| 2 | fetch-design-rules | Phase 2 | 多语言规范获取 + 设计原则/视图约束 GATE 加载（不变） |
| 3 | gather-context | Phase 3 | 读取 delta_spec.md + 全局文档；多仓校验按 multi-repo.md M-1 执行 |
| 4 | code-understanding | Phase 4 | 代码理解（不变） |
| 5 | read-similar-changes | Phase 5 | 读取 Similar Requirements Reference（不变） |
| 6 | read-brainstorming-output | Phase 6 | 读取 .brainstorming_output 元数据 + design.md（不变） |
| 7 | fetch-expert-experience | Phase 7 | 调用 paradigm-exp-use 获取专家知识（不变） |
| 8 | M-2 | Phase 8 | 各仓按仓生成设计文档 — 按 multi-repo.md 执行（含 impl_questions 用户确认 + subagent 并行文档生成，替代单仓 generate-artifacts） |
| 9 | design-traceability | Phase 9 | 设计追溯验证 — 按 multi-repo.md M-3a subagent 并行执行（**强制调用cross-doc-checker，禁止用design-doc-reviewer替代**） |
| 10 | design-review | Phase 10 | design-doc-reviewer 审查 — 按 multi-repo.md M-3b subagent 并行执行（**强制调用design-doc-reviewer，禁止用cross-doc-checker替代；M-3a全部通过后方可执行**） |
| 11 | cleanup-brainstorming | Phase 11 | 清理 brainstorming 临时文件 + clarification_summary.json + drafts 目录 + shared_context.md + downloads/目录 + 多仓各仓变更目录清理（**强制不可跳过**） |

**【禁止】多仓模式下使用单仓模式的 phase 列表** — 这会导致 CMS 阶段与 M-* 步骤冲突，文件创建被阻止。
