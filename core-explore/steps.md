# core-explore 必含步骤

以下步骤必须在 plan 的 phases 中逐一覆盖，每个步骤至少对应一个 Phase：

**【强制】所有步骤必须按顺序执行，禁止跳过任何步骤**（仅条件分支允许跳过，如步骤4 IR_doc_info为空时跳过、步骤9多仓模式由M-3~M-5替代）。

**【强制】步骤6~8（5.1~5.4）必须依次执行，禁止跳过任何子步骤**。

**【强制】步骤7（5.3）即使需求看似清晰也必须执行**：必须调用core-knowledge-skill至少1次并将结果展示给用户确认。

**【强制】步骤8（5.4）必须完成至少3轮brainstorming问答 + 方案呈现 + 用户确认 + 后处理**：禁止以"需求已清晰"为由跳过brainstorming交互。

**【强制】步骤13~15（L1验证/explore-review/cleanup-temp）为不可跳过的强制步骤**，禁止在步骤12后宣布流程完毕。

**【强制】步骤13使用cross-doc-checker，步骤14使用explore-doc-reviewer** — 禁止合并或混淆这两个步骤，禁止用explore-doc-reviewer替代cross-doc-checker执行步骤13。

**【强制】步骤13（L1验证）必须通过子代理执行**：禁止主会话直接调用cross-doc-checker Skill tool或Bash脚本。子代理失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行（禁止跳过告知直接降级）。

**【强制】步骤14（explore-doc-reviewer）必须通过子代理执行**：禁止主会话直接调用explore-doc-reviewer Skill tool或Bash脚本。子代理失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行（禁止跳过告知直接降级）。

**【强制】步骤15（cleanup-temp）必须删除整个downloads/目录**：禁止仅删除个别文件而保留downloads/目录本身。禁止将downloads/中的文件标记为"保留"。

**【关键】plan阶段前必须判断is_multi_repo**，然后根据结果选择对应的阶段列表写入plan.json。禁止在未检测的情况下写入plan。

**plan阶段多仓检测方式**（CMS plan阶段只能使用Read/Glob等只读工具，禁止调用bash/python脚本）：
- **P0**: 用Read读取 `docs/graph.json`（mode=="multi-repo"）、`docs/language.json`（keys>1）、`docs/relationship.md`（内容包含多个子仓定义）判断
- **P1**: 从上下文推断（前序环节传递的信息、用户明确说明）
- **P2**: 脚本检测仅在M-1阶段可用
- **注意：relationship.md在单仓场景也会生成，必须读取内容判断而非仅凭文件存在**

## 单仓模式（is_multi_repo = False）

1. **version-check**: Version Check (MANDATORY) — 必须为第一个 Phase 的第一个动作
2. **check-input**: 检查用户输入，判断需求来源；未提供 ID 则直接进入阶段5
3. **fetch-requirement**: 从 CoreAlm 获取需求信息
4. **download-attachments**: 下载相关附件（3.1 IDP / 3.2 DBOX）；IR_doc_info 为空则跳过
5. **parse-design-docs**: 解析设计文档，提取"简介"和"功能实现设计"章节
6. **context-completion**: 5.1 多仓检测确认（plan阶段已执行detect_multi_repo()，此处确认is_multi_repo标志）+ 5.2 补全上下文：读取全局文档 + 历史归档打分（≥4分写入 Similar Requirements Reference）；多仓模式仅保留历史归档打分
7. **knowledge-pre-clarification**: 5.3 领域知识预澄清：知识性问题调用 core-knowledge-skill 预解答，置信度<75%返回用户
8. **requirement-clarification**: 5.4 需求澄清：brainstorming 苏格拉底式逐题澄清 + 后处理（术语对齐4c + 决策记录4d + clarification_summary.json + .brainstorming_output）；不可用时回退需求澄清指南；多仓模式跳过（由M-3替代）
9. **multi-repo-branch**: 5.5 多仓环境分支 — 检查点验证（clarification_summary.json + design.md + .brainstorming_output 存在）；单仓直接进入阶段6，多仓按references/multi-repo.md执行M-1~M-8
10. **produce-proposal**: 生成 proposal.md（【强制前置】必须先读取 clarification_summary.json + design.md + spec.md，缺少时返回步骤8）
11. **find-similar-changes**: 查找相似需求
12. **produce-delta-spec**: 生成 delta_spec.md
13. **verify-completeness**: L1 需求完整性验证（【强制】subagent执行 + Skill tool调用cross-doc-checker --layer L1，禁止Bash脚本/trace_validator.py）— **【强制执行证据】**：必须通过Agent tool启动子代理执行；必须显式声明"已通过Agent tool启动子代理"；必须展示子代理返回结果；禁止直接调用Skill tool: cross-doc-checker
14. **explore-review**: explore-doc-reviewer 审查（【强制】subagent执行 + Skill tool调用explore-doc-reviewer，禁止主会话直接调用/Bash脚本）— **【强制执行证据】**：必须通过Agent tool启动子代理执行；必须显式声明"已通过Agent tool启动子代理"；必须展示子代理返回结果；禁止直接调用Skill tool: explore-doc-reviewer
15. **cleanup-temp**: 清理临时文件（保留 proposal.md / delta_spec.md / clarification_summary.json，**必须删除整个downloads/目录**）— **【强制】core-explore流程的最后一步，禁止跳过** — **【强制执行证据】**：必须使用rm -rf删除整个downloads/目录（禁止Remove-Item逐个删除）；必须显式声明"已删除整个downloads/目录"；必须Glob验证downloads/*返回空

## 多仓模式（is_multi_repo = True）

**【强制】当5.1检测为多仓环境时，plan必须使用以下阶段替换单仓模式阶段：**

1. **version-check**: Version Check (MANDATORY) — 必须为第一个 Phase 的第一个动作
2. **check-input**: 检查用户输入
3. **fetch-requirement**: 从 CoreAlm 获取需求信息
4. **download-attachments**: 下载相关附件（3.1 IDP / 3.2 DBOX）；IR_doc_info 为空则跳过
5. **parse-design-docs**: 解析设计文档
6. **M-1**: 多仓检测 + 涉及仓确认（repo_assignments.json） — 按references/multi-repo.md执行
7. **M-2**: 并行子仓探索（drafts文件生成） — 按references/multi-repo.md执行
8. **M-3**: 统一brainstorming澄清（一次brainstorming调用 + 方案呈现 + 用户确认 + 后处理4a~4h全部步骤） — 按references/multi-repo.md执行。**【强制】后处理4c术语对齐+4d决策记录+4h cross_repo_contracts.json不可跳过**
9. **M-4**: shared_context生成 + hash一致性校验 — 按references/multi-repo.md执行
10. **M-5**: 各仓proposal生成 — 按references/multi-repo.md执行
11. **find-similar-changes**: 查找相似需求（在各仓delta_spec生成前执行，为delta_spec提供相似需求参考）
12. **M-6**: 各仓delta_spec生成 — 按references/multi-repo.md执行
13. **M-7**: 各仓L1需求完整性验证（【强制】subagent并行执行，禁止主会话直接调用cross-doc-checker） — 按references/multi-repo.md执行 — **【强制执行证据】**：必须通过Agent tool启动子代理执行；必须显式声明"已通过Agent tool启动子代理"；必须展示子代理返回结果 — **【强制】禁止将M-7发现的ERROR级问题推迟到core-design阶段修复**：子代理修复为第一优先，子代理3轮修复失败(ESCALATE)时主会话兜底修复
14. **M-8**: 各仓explore-doc-reviewer审查（【强制】subagent并行执行，禁止主会话直接调用explore-doc-reviewer） — 按references/multi-repo.md执行 — **【强制执行证据】**：必须通过Agent tool启动子代理执行；必须显式声明"已通过Agent tool启动子代理"；必须展示子代理返回结果 — **【强制】禁止将M-8发现的ERROR级问题推迟到core-design阶段修复**：子代理修复为第一优先，子代理3轮修复失败(ESCALATE)时主会话兜底修复
15. **cleanup-temp**: 清理临时文件 — 多仓模式按references/multi-repo.md cleanup-temp章节执行 — **【强制】core-explore流程的最后一步，禁止跳过** — **【强制执行证据】**：必须使用rm -rf删除整个downloads/目录（禁止Remove-Item逐个删除）；必须显式声明"已删除整个downloads/目录"；必须Glob验证downloads/*返回空

**【说明】多仓模式下省略context-completion+detect-multi-repo阶段**：
- 多仓检测已在plan阶段完成（Read/Glob读取graph.json/language.json/relationship.md）
- 全局文档（spec.md/design.md）和子仓文档读取由M-2子代理完成
- 历史归档打分由M-2子代理在探索各仓时同步完成
- 因此context-completion阶段在多仓模式下完全冗余，直接进入M-1

**【禁止】多仓模式下使用单仓模式的15个phase** — 这会导致CMS阶段与M-*步骤冲突，文件创建被阻止。
