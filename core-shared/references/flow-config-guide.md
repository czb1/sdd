# CoreSpec flow-config 配置指南

> 本指南是**全局共享指南**（框架级）：描述 flow-config 框架的通用配置能力，并按 skill 分节列出各 core-* 技能的可用配置项。
> 唯一真相源文件位于 core-shared（框架共享）目录：`coreharness-spec/skills/core-shared/references/flow-config-guide.md`，随 coreharness-spec 包分发。
> 任何 core-* 技能的 `main.py flow-config --init` 都会把它同步到用户级目录 `~/.corespec/flow-config-guide.md`（与 `flow-config.json` 同目录）；`--guide` 输出全文。多技能同步到同一路径，无覆盖冲突（同源单文件）。

目录：§1–3 配置模型 → §4 各技能配置 → §5 字段 → §6 执行计划与确认 → §7 辅助命令 → §8–9 默认行为 → §10 示例 → §11 常见问题。

---

## 1. 配置文件位置

- `~/.corespec/flow-config.json` —— 持久配置源（JSONC：支持 `//` 行注释，main.py 剥离注释后解析）
- `~/.corespec/flow-config-guide.md` —— 本指南（与配置文件同目录）

## 2. 顶层结构（按 skill 名分组）

顶层键 = skill 名。每个 core-* skill 的配置包在各自对象里，互不混用：

```jsonc
{
  "core-apply": { /* core-apply 的配置 */ },
  "core-design": { /* core-design 的配置 */ }
}
```

- 某 skill 对象不存在 = 该 skill 全默认（内置步骤按注册表各自默认值启停，无自定义步骤）
- 每个 skill 调用 `main.py flow-config --json --skill <name>` 只解析自己的命名空间
- 执行计划 / 关闭标记按 skill 分文件：
  - `docs/.flow_context/execution-plan-<skill>.json`（执行期唯一数据源）
  - `docs/.flow_context/skipped-<skill>.json`（关闭步骤标记）

## 3. 三种值类型（skill 对象内部）

| 值类型 | 含义 | 必填字段 | 可选字段 |
|--------|------|---------|---------|
| true / false | 内置步骤启停 | 无 | 无 |
| `{ type: reference, ... }` | 知识注入型自定义步骤（给 agent 看资料） | type, file, at | order, description, depends_on, dependency_type |
| `{ type: skill, ... }` | 能力执行型自定义步骤（让 agent 干活） | type, skill, at | order, description, depends_on, dependency_type, run_mode |

内置步骤通过布尔值启停；自定义步骤通过完整对象声明，整块注释即关闭，取消整块注释即开启。两种形式不混用。框架随包提供的自定义声明由 `flow_config.py` 的 `TEMPLATE_JSONC` 承载，经 `--init` 写入配置模板；用户也可以按第 5 节自行编排。自定义业务说明放在对应指令文件中，执行时统一由计划调度。

## 4. 已接入 skill 一览

每个已接入 flow-config 框架的 core-* 技能在此分节列出**自己的**内置步骤键与编排点。未接入的技能无需任何配置（该 skill 对象不存在 = 全默认）。

### 4.1 core-apply

**内置步骤**：

| 配置键 | 对应步骤 | 默认 | 依赖 |
|--------|---------|------|------|
| version_check | Step 1 版本检查 | true | — |
| show_progress | Step 8 展示当前进度 | **false** | — |
| l4_review | Step 10 L4 实现追溯验证 | true | — |
| code_review | Step 11 Code Review | true | — |
| unit_test | Step 12 单元测试 | true | — |
| l5_coverage | Step 13 L5 UT 覆盖度验证 | true | unit_test（关闭 UT 则 L5 自动降级） |
| completion_report | Step 14 完成或暂停时展示状态 | true | — |

**编排点**（core-apply 的 SKILL.md 预置插槽）：

| 编排点 | 粒度 | 位置 |
|--------|------|------|
| pre-codegen | task | Step 9 的 9.3 和 9.4 之间（任务循环内） |
| post-codegen | change | Step 9 之后 |
| post-l4 | change | Step 10 之后 |
| post-review | change | Step 11 之后 |
| post-ut | change | Step 12 之后 |

### 4.2 core-init

**内置步骤**：

| 配置键 | 对应步骤 | 默认    | 依赖 |
|--------|---------|-------|------|
| version_check | Step 0 版本检查 | true  | — |
| okf_knowledge_fetch | Step 4 拉取产品知识中心代码仓（asset/ 扁平到 docs/knowledge/产品名/） | false | — |
| multi_analysis | Step 5 多仓依赖分析（subagent 强制） | true  | — |
| check_sync | Step 6a 同步必要性检查 | true  | — |
| execute_sync | Step 6b 代码仓逆向文档获取 | true  | check_sync（关闭 check_sync 则 execute_sync 依赖降级跳过） |

**编排点**（core-init 的 SKILL.md 预置插槽）：

| 编排点 | 粒度 | 位置 |
|--------|------|------|
| post-init-structure | change | Step 2 目录结构初始化之后 |
| post-scan-language | change | Step 3 语言扫描之后 |
| post-multi-analysis | change | Step 5 多仓依赖分析之后 |
| pre-execute-sync | repo | Step 6b 每仓同步前（逐仓触发） |
| post-execute-sync | repo | Step 6b 每仓完成后（逐仓触发） |

**关闭语义**：
- `okf_knowledge_fetch=false`：跳过产品知识中心仓拉取（`docs/knowledge/` 不生成）。下游 explore/design 如需产品知识参考，需用户手动准备 `docs/knowledge/` 或通过 okf-knowledge skill 的 get 流程单独拉取。本步骤软失败容错（网络错误/offering 未找到/project_id 未找到时警告继续，不阻塞主流程）
- `check_sync=false`：跳过同步必要性检查，execute_sync 因依赖规则同步跳过（`dependency_downgraded`，reason 见执行计划 disabled 区）——项目不会拉取 specs，也不会本地生成。**请确保 specs 已存在**（docs/specs/spec.md 与 docs/specs/design.md），否则下游 explore/design 无全量文档输入
- `execute_sync=false`（check_sync 仍开启）：仅跳过文档拉取与本地生成，同步检查仍执行——**请确保 specs 已存在**（docs/specs/spec.md 与 docs/specs/design.md），否则下游 explore/design 无全量文档输入

**ref_file 策略**：`okf_knowledge_fetch` 为内容型（single == multi，单仓/多仓共用 `references/okf-knowledge-fetch.md`，单仓/多仓行为一致：都通过 `.git/config` 获取 repo_url，按 offering_id 去重，拉取到 `docs/knowledge/{offering_cn_name}/`）。

### 4.3 core-explore

**内置步骤**：

| 配置键 | 对应步骤 | 默认 | 依赖 |
|--------|---------|------|------|
| version_check | Step 0 版本检查 | true | — |
| req_refine | 阶段5.1.5 需求文档细化补全（B 档；启用后 step-4 自动降级） | false | — |
| knowledge_precheck | 阶段5.3 领域知识预澄清（检查点三条件；req_refine 产出时追加第四条件豁免） | true | — |
| brainstorming | 阶段5.4 需求澄清 brainstorming（检查点七条件；req_refine 产出时追加第八条件豁免） | true | — |
| find_similar | 阶段7 查找相似需求 | true | — |
| l1_review | 阶段9 L1 需求完整性验证（subagent 强制） | true | — |
| explore_review | 阶段10 explore-doc-reviewer 文档审查（subagent 强制） | true | — |
| cleanup_temp | 阶段11 清理临时文件 | true | — |

**编排点**（core-explore 的 SKILL.md 预置插槽）：

| 编排点 | 粒度 | 位置 |
|--------|------|------|
| pre-clarification | change | 阶段5.4 澄清前 |
| post-clarification | change | 阶段5.4 澄清后（后处理完成） |
| pre-proposal | change | 阶段6 proposal 生成前 |
| post-proposal | change | 阶段7 find-similar 前（proposal 生成后） |
| pre-delta-spec | change | 阶段8 delta_spec 生成前 |
| post-delta-spec | change | 阶段9 L1 验证前（delta_spec 生成后） |
| post-l1 | change | 阶段9 之后、阶段10 之前 |
| post-review | change | 阶段10 之后、阶段11 之前 |
| post-cleanup | change | 阶段11 之后 |

**关闭语义**：

- **双层语义（knowledge_precheck / brainstorming）**：两键指令文件均挂 `ref_file` 条件加载（`knowledge_precheck` → references/knowledge-precheck.md；`brainstorming` → references/requirement-clarification.md，均单多仓共用）——关闭时文件不加载、内容不进上下文，检查点豁免（knowledge_precheck 三条件 / brainstorming 七条件）+ 后处理降级（多仓侧 M-3 同步豁免）。**关闭后产物仍须保留**（clarification_summary.json / .brainstorming_output），否则下游检查点断链
- **双层语义（req_refine，默认关闭）**：指令文件挂 `ref_file` 条件加载（`req_refine` → references/req-refine.md / references/req-refine-multi.md，**通道型**——多仓产出全局一份，不按仓拆分）——关闭时文件不加载、内容不进上下文，跳过需求文档细化，步骤5 parse-design-docs 正常执行。启用时：
  - **互斥规则**（`flow_config.py` `apply_dependency_rules` 硬编码）：`req_refine=true` → step-4「解析设计文档」自动降级为 fixed disabled（`dependency_downgraded`，`dependency_of=req_refine`），需求文档解析职能由 req_refine 替代
  - **产出**：requirement.md + story.md 到 `docs/.explore_context/req-refine/{需求ID}/`（需求 ID 取自 CoreAlm 返回字段）
  - **执行模式**：**强制 subagent 执行**——必须通过 Agent tool 启动专用 subagent（`subagent_type=general-purpose`）执行步骤1~5，禁止主会话直接执行；主会话仅负责启动 subagent、接收返回结果、回读验证产出物、进入 5.2
  - **下游读取源切换**：阶段5.2 补全上下文读取源切到 refined 文档（`requirement.md`），不再读取 step-4 解析结果
  - **联动豁免**：产出后 `knowledge_precheck` 三条件检查点追加第四条件豁免、`brainstorming` 七条件检查点追加第八条件豁免（详见各 ref_file）
- **l1_review / explore_review**：单仓承载阶段9/10，多仓承载 M-7/M-8（ref_file.multi 指向独立 `*-multi.md`）。关闭时对应阶段/关卡豁免（含"必经关卡"、"禁止主会话直接执行"、"禁止推迟修复"等强制位），指令文件不被 Read
- `cleanup_temp=false`：跳过清理阶段，**须显式记录"cleanup_temp 已关闭，临时文件残留"**，残留由用户或后续人工处理（不阻断流程收尾）；关闭时"最后阶段禁止跳过"自动解除
- `find_similar=false`：跳过阶段7 查找相似需求，delta_spec 无相似需求参考
- `version_check=false`：跳过 Step 0 版本检查（不推荐关闭）

**ref_file 策略**：

| 配置键 | 单仓 ref_file | 多仓 ref_file.multi | 承载类型 |
|--------|--------------|--------------------|---------|
| version_check | references/version-check.md | 同单仓 | 内容型（单文档承载） |
| req_refine | references/req-refine.md | references/req-refine-multi.md | 通道型（双文件，多仓全局一份） |
| knowledge_precheck | references/knowledge-precheck.md | 同单仓 | 内容型（单文档承载，B 档） |
| brainstorming | references/requirement-clarification.md | 同单仓 | 内容型（单文档承载，B 档） |
| find_similar | references/find-similar.md | 同单仓 | 内容型（单文档承载） |
| l1_review | references/l1-review.md | references/l1-review-multi.md | 通道型（双文件） |
| explore_review | references/explore-review.md | references/explore-review-multi.md | 通道型（双文件） |
| cleanup_temp | references/cleanup-temp.md | references/cleanup-temp-multi.md | 通道型（双文件） |

**依赖链豁免**：

- `req_refine=true` → step-4 自动降级（`dependency_downgraded`），无需用户手动关闭 step-4（step-4 是固定步骤，无 config_key，由互斥规则自动管理）
- `req_refine` 关闭 → 不影响其他键；`knowledge_precheck`/`brainstorming` 不追加 `req_refine` 联动豁免条件，按原检查点执行

### 4.4 core-design

**内置步骤**：

| 配置键 | 对应步骤 | 默认 | 依赖 |
|--------|---------|------|------|
| version_check | Phase 1 版本检查 | true | — |
| fetch_rules | Phase 2 code-rule 拉取（Step 1~3，**B 档双层语义**：GATE 不受控） | true | — |
| read_similar | Phase 5 读取相似需求参考归档 | true | — |
| expert_experience | Phase 7 准备已有设计经验 | true | — |
| design_traceability | Phase 9 设计追溯验证（cross-doc-checker L2/L3，subagent 强制） | true | — |
| design_review | Phase 10 design-doc-reviewer 文档审查（subagent 强制） | true | — |
| cleanup | Phase 11 清理临时文件 | true | — |

**编排点**（core-design 的 SKILL.md 预置插槽）：

| 编排点 | 粒度 | 位置 |
|--------|------|------|
| post-rule-fetch | change | Phase 2 规范拉取后 |
| post-gather-context | change | Phase 3 上下文收集后（M-1 完成后） |
| post-code-understanding | change | Phase 4 代码理解后 |
| pre-generate | change | Phase 8 生成前（M-2 启动前） |
| post-generate | change | Phase 8 生成后（M-2 全部仓完成后） |
| post-traceability | change | Phase 9 追溯验证后（M-3a 全部仓完成后） |
| post-design-review | change | Phase 10 审查后（M-3b 全部仓完成后） |
| post-cleanup | change | Phase 11 清理后 |

**关闭语义**：

- **双层语义（fetch_rules）**：`fetch_rules` 关闭仅跳过 code-rule 拉取（Step 1~3），**Phase 2.2 的 GATE（design-principles.md / design-views.md）不受开关控制**，仍无条件加载——即关闭 `fetch_rules` 后设计文档生成仍受原则/视图约束保护，但语言级规范集合为空
- **design_traceability / design_review**：单仓承载 Phase 9/10，多仓承载 M-3a/M-3b（ref_file.multi 指向独立 `*-multi.md`）。关闭时对应阶段/关卡豁免（含"必经关卡"、"禁止主会话直接执行"、转换门控等强制位），指令文件不被 Read
  - `design_traceability=false` 但 `design_review=true`：M-2 完成后直接进入 M-3b，"M-3a 全过后才执行 M-3b"依赖随 `design_traceability` 关闭豁免
- `cleanup=false`：跳过清理阶段，**须显式记录"cleanup 已关闭，临时文件残留"**，残留由用户或后续人工处理（不阻断流程收尾）；关闭时"最后阶段禁止跳过"自动解除
- `read_similar=false`：跳过 Phase 5 相似需求参考读取，delta_design 无历史设计参考
- `expert_experience=false`：跳过 Phase 7 已有设计经验准备，不加载对应指令文件；直接进入 Phase 8。
- `version_check=false`：跳过 Phase 1 版本检查（不推荐关闭）

### 4.5 core-archive

**内置步骤**：

| 配置键 | 对应步骤 | 默认 | 依赖 |
|--------|---------|------|------|
| version_check | Step 1 版本检查 | true | — |
| core_verify | Step 4 core-verify 归档前验证（单仓单会话 / 多仓 M-0 子代理并行，UNDER_IMPL 阻塞 / DOC_STALE 交反刷） | true | — |
| check_artifacts | Step 5 检查 artifact 完成状态 | true | — |
| check_tasks | Step 6 检查 task 完成状态 + 消费 skipped-core-apply.json | true | — |
| backfill | Step 9 代码反刷（backfill-from-code，单文档承载单/多仓） | true | — |
| spec_sync | Step 10 delta 合并到全量文档（单仓单会话 / 多仓 M-2 子代理并行） | true | — |
| show_summary | Step 12 展示归档摘要 | true | — |
| push_mr | Step 13 core-auto-git 推送 + 建 MR（多仓 M-4 逐仓替代） | true | — |

> **不可关闭步骤**：Step 7（get-versions 获取版本号）、Step 8（detect-multi-repo 多仓检测）、Step 11（execute-archive 执行归档 + 生成归档索引条目）——核心归档动作，无 `config_key` 映射，强制位永远生效。

**编排点**（core-archive 的 SKILL.md 预置插槽）：

| 编排点 | 粒度 | 位置 |
|--------|------|------|
| pre-verify | change | Step 4 core-verify 前（多仓 M-0 启动前） |
| post-verify | change | Step 4 core-verify 后（多仓 M-0 完成后） |
| pre-backfill | change | Step 9 反刷前（多仓 M-1 启动前） |
| post-backfill | change | Step 9 反刷后（多仓 M-1 完成后） |
| pre-spec-sync | change | Step 10 spec-sync 前（多仓 M-2 启动前） |
| post-spec-sync | change | Step 10 spec-sync 后（多仓 M-2 完成后） |
| pre-archive | change | Step 11 归档前（多仓 M-3 启动前） |
| post-archive | change | Step 11 归档后（多仓 M-3 完成后） |
| pre-push | change | Step 13 push 前（多仓 M-4 启动前） |
| post-push | change | Step 13 push 后（多仓 M-4 完成后） |

**关闭语义**：

- **core_verify=false**：跳过 Step 4 归档前验证（单仓单会话 / 多仓 M-0 子代理并行均豁免），subagent 强制 / 并发规则 / 汇总逻辑全部豁免，直接进入 Step 5（check_artifacts）。**DOC_STALE 差异线索为空**，backfill（M-1）以 git diff 独立发现 gap
- **backfill=false**：跳过 Step 9 代码反刷（含单仓单会话 / 多仓 M-1 子代理并行），subagent 强制 / 并发规则 / 汇总逻辑全部豁免，直接进入 Step 10（spec_sync）。归档前文档与代码差异不反刷
- **spec_sync=false**：跳过 Step 10 delta→全量文档合并（含单仓单会话 / 多仓 M-2 子代理并行），subagent 强制 / 并发规则 / 汇总逻辑全部豁免，直接进入 Step 11（归档执行）。全量 spec.md / design.md 不更新，delta 变更仅保留在归档中
- **push_mr=false**：跳过 Step 13 推送 + MR（含单仓单会话 / 多仓 M-4 逐仓），代码留在本地分支。摘要展示"代码将留在本地分支，未推送"
- **check_artifacts=false**：跳过 Step 5 artifact 完成状态检查
- **check_tasks=false**：跳过 Step 6 task 完成状态检查
- **show_summary=false**：跳过 Step 12 归档摘要展示
- **version_check=false**：跳过 Step 1 版本检查（不推荐关闭）
- **依赖链豁免**：`core_verify` 关闭但 `backfill` 开启 → M-0→M-1 依赖随 `core_verify` 关闭豁免；`backfill` 关闭但 `spec_sync` 开启 → M-1→M-2 依赖随 `backfill` 关闭豁免；`spec_sync` 关闭但 M-3 不可关 → M-2→M-3 依赖随 `spec_sync` 关闭豁免
- **M-3 不可关闭**：多仓归档执行（Step 11 / M-3）是核心归档动作，无 `config_key` 映射，subagent 强制 / 并发规则 / 汇总逻辑永远生效

**ref_file 策略**：

| 配置键 | 单仓 ref_file | 多仓 ref_file.multi | 承载类型 |
|--------|--------------|--------------------|---------|
| version_check | references/version-check.md | 同单仓 | 内容型（单文档承载） |
| core_verify | references/verify-result-handling.md | references/verify-multi.md | 通道型（双文件） |
| check_artifacts | references/check-artifacts.md | 同单仓 | 内容型（单文档承载） |
| check_tasks | references/check-tasks.md | 同单仓 | 内容型（单文档承载） |
| backfill | references/backfill-from-code.md | 同单仓 | 内容型（单文档承载标杆） |
| spec_sync | references/spec-sync.md | references/spec-sync-multi.md | 通道型（双文件） |
| show_summary | references/completion-report.md | 同单仓 | 内容型（单文档承载） |
| push_mr | references/push-mr.md | 同单仓 | 内容型（单文档承载） |

### 4.6 其他 core-* 技能

接入 flow-config 框架后在此追加分节（内置步骤键 + 编排点）。接入前该技能全默认，无需配置。

## 5. 字段说明

| 字段 | 适用类型 | 必填 | 说明 |
|------|---------|------|------|
| type | reference/skill | 是 | "reference" 或 "skill" |
| file | reference | 是 | reference 文件路径（绝对 > 用户 skill 目录 references/ > 对应技能安装目录 references/） |
| skill | skill | 是 | 用户提供的 skill 名称（agent 通过 Skill tool 调用） |
| at | reference/skill | 是 | 编排点名称（见对应 skill 分节） |
| order | reference/skill | 否 | 同一编排点内执行顺序，默认 0，升序串行 |
| depends_on | reference/skill | 否 | 依赖的内置步骤键名数组 |
| dependency_type | reference/skill | 否 | "hard"（默认，依赖关闭则本步骤跳过）/ "soft"（标注 WARNING 继续） |
| run_mode | skill | 否 | "direct"（默认，当前会话）/ "subagent"（独立子代理）。reference 型不适用 |
| args | — | — | 已移除：业务输入请在 skill 内自包含配置承载 |

## 6. 执行计划与确认场景（构建执行计划行为）

构建执行计划时调用 `main.py flow-config --json --skill <name>` 读取配置 → 校验 → 计算配置指纹 → 构建执行计划 → 持久化，并按场景决定是否需用户确认：

| 场景 | 条件 | 行为 |
|------|------|------|
| A 首次·全默认 | 配置文件存在，但命名空间不存在 / 计划=全默认 | 命名空间已配置且解析全默认 → 跳过确认，零接触；**命名空间缺失（`ns_missing=true`）→ 不跳过确认**（见下"命名空间缺失"说明） |
| C 续跑·一致 | 计划存在且配置指纹匹配 | 直接续跑 |
| E 配置变更 | 指纹不匹配 | 需用户确认 |
| D 计划缺失 | 计划文件缺失但命名空间存在 | 需用户确认 |

> 优先级：A > D > C > E（修复后）。全默认计划恒为场景 A。

> **首次运行·配置文件不存在**：`~/.corespec/flow-config.json` 不存在时，场景判定仍为 A，但**不跳过确认**——构建执行计划时会向用户提供"生成配置模板 / 继续默认"选择（`config_missing=true`）。这是用户唯一一次接触 flow-config 框架的机会：选择生成模板（`main.py flow-config --init`）后可启停步骤、插入自定义步骤；选择继续默认则直接使用全默认计划。配置文件存在且全默认才真正零接触。

> **命名空间缺失·配置文件已存在**：`~/.corespec/flow-config.json` 已存在（可能由其他 skill 的首次运行 `--init` 生成）但**当前 skill 的命名空间不存在**时，场景判定为 A，但同样**不跳过确认**（`ns_missing=true`）——该 skill 的用户从未见过自己的可配置项，与首次运行同权：必须提供"生成模板 / 继续默认"选择。选择生成模板时执行 `--init --skill <name>` 追加缺失命名空间（见 §7），重建计划后 `ns_missing=false` 进入正常场景流。零接触仅当**命名空间已配置且解析为全默认**（`ns_missing=false`）时成立。

## 7. 辅助命令

- `main.py flow-config --json --skill <name>`：构建执行计划时调用，输出执行计划（唯一权威）
- `main.py flow-config --describe --json --skill <name>`：输出该 skill 可用配置键/schema/默认值/示例
- `main.py flow-config --init`：生成带注释的 JSONC 模板 + 同步本指南到用户级目录。**`--init --skill <name>` 追加缺失命名空间**：文件不存在 → 生成完整模板（顶层仅 core-apply 活动块，其他 skill 为注释示例）；文件已存在且缺 `<skill>` 分区 → 从模板提取该 skill 示例块（去注释）追加到顶层闭合前（自动补尾逗号），已存在的分区/键不被覆盖；分区已存在 → 幂等不重复追加
- `main.py flow-config --guide`：输出本指南全文
- `main.py flow-config --apply --skill <name> <changes>`：应用确认调整，**同步写回配置文件**并重同步 skipped 标记。`<changes>` 语法：
  - `key=true` / `key=false`：启用/关闭内置步骤开关
  - 裸 `key`：取消内置步骤（等效 `key=false`）
  - 自定义步骤 `key=`：**注释软删除**（声明整块注释保留在配置源，随时可恢复）；`key=true`：**取消注释恢复启用**（仅当存在被注释的声明；无声明数据无法创建）
  - 自定义步骤的任意值更新不支持（请直接编辑配置文件修改声明）
  - **多变更**：每个变更用独立 `<changes>` 参数（如 `--changes code_review=false --changes unit_test=false`）；**逗号拼接成单个参数也兼容**（如 `--changes code_review=false,unit_test=false`，内部按逗号拆分逐个应用）——两种写法均可（2026-09-21 修复：`--changes` 改用 `action='append'`，重复参数不再折叠）
  - **幂等**：变更的目标值已是配置源当前值时视为成功（不误报"配置中不存在键"）；自定义步骤的**启用/关闭**对已处于目标状态（已启用/已注释）的键同样幂等成功，不中断 apply

  写回后下次构建执行计划重建会因指纹变化进入场景 E 需再次确认——这是预期行为（调整已固化到配置）。`run_build` 输出 `active_orchestration_entries` 字段列出当前**启用的编排点条目**（供 Adjust 生成"关闭 <key>"选项）与 `commented_custom_steps` 字段列出当前被注释（可恢复启用）的自定义步骤（供 Adjust 生成"启用 <key>"选项）。

## 8. 用户心智模型（只需记三条）

> - **想配置哪个 skill？** → 把它的键包在 `"<skill 名>": {...}` 对象里（如 `"core-apply": {...}`）
> - **想关掉某步？** → 在对应 skill 对象内写 `"<内置步骤键>": false`（如 `"l4_review": false`）
> - **想加一步知识注入？** → 在对应 skill 对象内填 `type: "reference"` + `file` + `at`
> - **想加一步能力执行？** → 在对应 skill 对象内填 `type: "skill"` + `skill` + `at`；想让它在独立子代理里跑？再加 `run_mode: "subagent"`

同一位置想加多步？用 `order` 排序。文件不存在、键缺失、或该 skill 顶层对象不存在？自动用默认值——未配置的 skill 完全不受影响。

## 9. 默认安全：什么都不配 = 当前行为完全兼容

配置文件不存在时，内置步骤按出厂默认启停（core-apply 默认开启：version_check/l4_review/code_review/unit_test/l5_coverage/completion_report、**默认关闭：show_progress**；core-init 默认开启：version_check/multi_analysis/check_sync/execute_sync、**默认关闭：okf_knowledge_fetch**；core-explore 默认开启：version_check/knowledge_precheck/brainstorming/find_similar/l1_review/explore_review/cleanup_temp、**默认关闭：req_refine**；core-design 默认全开：version_check/fetch_rules/read_similar/expert_experience/design_traceability/design_review/cleanup；core-archive 默认全开：version_check/core_verify/check_artifacts/check_tasks/backfill/spec_sync/show_summary/push_mr）、无自定义步骤——等价于今天的全量行为（首次构建执行计划时会先提供一次"生成模板 / 继续默认"的配置机会，选择继续默认后即与今天完全一致）。即使配置文件存在，未配置的 skill 顶层对象同样全默认，各 skill 配置互不干扰。**向后兼容是零成本的。**

## 10. 配置示例（core-apply 命名空间）

```jsonc
{
  "core-apply": {
    // ---- 内置步骤开关（true/false）----
    "version_check": true,
    "show_progress": false,  // Step 8 展示当前进度（默认关闭）
    "l4_review": true,
    "code_review": true,
    "unit_test": true,
    "l5_coverage": true,
    "completion_report": true,

    // ---- 自定义步骤 1：知识注入型（给 agent 看资料）----
    "judgment_ladder": {
      "type": "reference",
      "file": "references/judgment-ladder.md",
      "at": "pre-codegen"
    },

    // ---- 自定义步骤 2：能力执行型（让 agent 干活）----
    "compile": {
      "type": "skill",
      "skill": "my-compile-skill",
      "at": "post-codegen",
      "order": 1
    },

    // ---- 自定义步骤 3：能力执行型 + 独立子代理执行 ----
    "codebase_scan": {
      "type": "skill",
      "skill": "my-scan-skill",
      "at": "post-review",
      "run_mode": "subagent"
    }
  }
}
```

> **自定义步骤启停（注释软删除/恢复）**：通过 `main.py flow-config --apply` 关闭自定义步骤（`<key>=`）时，声明**整块注释保留**在配置中（如下），不删除——下次用 `<key>=true` 即可恢复启用，无需重新手写声明。被注释的声明不参与配置指纹与执行计划，可随时安全注释/取消注释。Adjust 勾选时，**当前启用的自定义步骤也会生成"关闭 <key>"选项**（与内置步骤的关闭选项一致，无需手动输入自定义答案）：

```jsonc
{
  "core-apply": {
    "l4_review": true,
    // "judgment_ladder": {
    //   "type": "reference",
    //   "file": "references/judgment-ladder.md",
    //   "at": "pre-codegen"
    // }
  }
}
```

## 11. 常见问题

| 问题 | 说明 |
|------|------|
| 关闭的步骤还会执行吗？ | 不会。关闭步骤的指令文件不加载，内容不进 agent 上下文（结构阻断） |
| 首次运行（没有配置文件）会发生什么？ | 构建执行计划时会询问是否生成配置模板（`main.py flow-config --init`）或继续默认。选择继续默认后与旧行为完全一致；之后任何时候都可以用 `--init` 生成模板再修改 |
| 修改配置后需要做什么？ | 无需手动操作。下次构建执行计划检测到指纹变化（场景 E）会自动重建计划并请确认 |
| 关闭 l5_coverage 会怎样？ | 仅关闭 L5。关闭 unit_test 会导致 l5_coverage 自动降级（依赖规则） |
| 自定义步骤文件找不到怎么办？ | 按"绝对路径 > 用户 skill 目录 references/ > 对应技能安装目录 references/"依次解析 |
| 配置文件损坏会怎样？ | 解析失败时框架先尝试自愈（剥除最后一个有效键的尾逗号——旧版 `--apply` 写回可能遗留），成功后正常加载；无法自愈则构建执行计划时显式报错（`ok: false` + 解析失败原因）并**保留既有执行计划**，绝不静默降级为全默认。修复前可回退 `flow-config.json.bak-*` 备份 |
| 其他 core-* 技能怎么配？ | 看第 4 节"已接入 skill 一览"对应分节；未接入的技能无需配置（全默认）。或用 `--describe --skill <name>` 查该技能可用键 |
