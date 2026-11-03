# CoreSpec flow-config 用户指南

> 一句话定位：**core-* 技能的流程编排配置**——想"关掉某一步"或"加一步"时编辑 `~/.corespec/flow-config.json` 即可。
> 获取方式：`main.py flow-config --guide` 输出本文；首次运行任意 core-* 技能会自动把本指南同步到 `~/.corespec/flow-config-guide.md`（与配置文件同目录）。

---

## 1. 这是什么，什么时候需要它

**不修改配置时使用各步骤的出厂默认值。** 任务 Skill 消费在 design / apply 中均默认关闭；其他默认值见第 5 节。 配置文件首次运行 core-* 时已自动生成，你无需任何操作。

只有两种时刻需要它：

- 想**关掉**某个内置步骤（如关掉单元测试、跳过版本检查）
- 想**加一步**（注入一份参考资料，或在固定位置调用你的自定义 skill）

**改完即生效**：下次运行 core-* 自动按新配置构建执行计划执行，无需流程配置确认、额外命令或重启。配置写错会在启动时明确报错（唯一拦截点），修复前不会继续。

## 2. 配置文件在哪

- `~/.corespec/flow-config.json` —— 配置文件（JSONC：支持 `//` 行注释），首次运行自动生成
- `~/.corespec/flow-config-guide.md` —— 本指南（与配置文件同目录）

执行期派生文件（自动维护，无需关心）：`docs/.flow_context/execution-plan-<skill>.json`（执行计划）、`docs/.flow_context/skipped-<skill>.json`（关闭步骤标记）。

## 3. 三条心智模型

- **想配置哪个 skill** → 把它的键包在 `"<skill名>": {...}` 对象里（如 `"core-apply": {...}`）；某 skill 对象不存在 = 该 skill 全默认
- **想关掉某步** → 在对应 skill 对象内写 `"<内置步骤键>": false`
- **想加一步** → 填 `{ "type": ... }` 声明 + `"at"` 编排点：

| 字段 | 适用类型 | 必填 | 说明 |
|------|---------|------|------|
| type | reference/skill | 是 | "reference"（给 agent 看资料）或 "skill"（让 agent 干活） |
| file | reference | 是 | 资料文件路径（绝对 > 用户 skill 目录 references/ > 对应技能安装目录 references/） |
| skill | skill | 是 | 你的 skill 名称（agent 通过 Skill tool 调用） |
| at | reference/skill | 是 | 编排点名称（见 §5 各技能速查） |
| order | reference/skill | 否 | 同一编排点内执行顺序，默认 0，升序串行 |
| depends_on | reference/skill | 否 | 依赖的内置步骤键名数组 |
| dependency_type | reference/skill | 否 | "hard"（默认，依赖关闭则本步骤跳过）/ "soft"（标注 WARNING 继续） |
| run_mode | skill | 否 | "direct"（默认，当前会话）/ "subagent"（独立子代理） |

## 4. 场景化操作

### 4.1 关闭某个内置步骤

1. 打开 `~/.corespec/flow-config.json`，找到对应 skill 对象（没有就加上，见 §6 示例）
2. 把目标键改为 `false`（如 `"unit_test": false`）
3. 保存。下次运行该技能时此步骤直接跳过：指令文件不加载、内容不进 agent 上下文，总结中会列出被关闭的步骤

### 4.2 添加自定义步骤

在对应 skill 对象内追加一个声明块（完整示例见 §6）：

- **知识注入型**（给 agent 看资料）：`{ "type": "reference", "file": "references/my-notes.md", "at": "pre-codegen" }`
- **能力执行型**（让 agent 干活）：`{ "type": "skill", "skill": "my-compile-skill", "at": "post-codegen", "order": 1 }`；想让它跑在独立子代理里，加 `"run_mode": "subagent"`

`at` 必须是该技能的合法编排点（§5 速查中列出）；同一编排点加多步用 `order` 排序。自定义步骤不用了可整块注释保留（JSONC 支持 `//`），想恢复取消注释即可。

### 4.3 改完之后：什么都不用做

下次运行该 core-* 技能，第一步会自动读取配置 → 校验 → 重建执行计划 → 按新计划执行。无需流程配置确认或额外命令。启用 Skill 消费后的候选选择等业务确认仍保留。

### 4.4 出错了怎么办

| 症状 | 处理 |
|------|------|
| 启动时报 `ok: false` + 解析/校验失败原因 | 配置写错了（拼写错的键、非法编排点、损坏的 JSON）。按报错修文件；修复前既有执行计划不会被覆盖 |
| 想确认自己配了什么 | `main.py flow-config --describe --json --skill <name>` 查看该技能可用键、默认值与示例 |
| 改坏了想回退 | 配置目录下有 `flow-config.json.bak-*` 自动备份，或整段注释掉自定义配置回到默认 |
| 自定义步骤的资料文件找不到 | 按"绝对路径 > 用户 skill 目录 references/ > 对应技能安装目录 references/"依次解析，把文件放到其中一处 |

## 5. 各技能可配置项速查

> 依赖关系一句人话：关闭被依赖的键会连带处理依赖它的键（如关闭 `unit_test` 会导致 `l5_coverage` 自动降级）。每个键的"关闭后果"见表格右列。

### 5.1 core-apply

| 配置键 | 对应步骤 | 默认 | 关闭后果 |
|--------|---------|------|---------|
| version_check | Step 1 版本检查 | true | 跳过版本检查（不推荐） |
| show_progress | Step 8 展示当前进度 | **false** | 默认即关；开启则在第 8 步展示进度 |
| skill_consumption | 单仓 Step 9 / 多仓 M-1a 准备，代码生成时使用 | **false** | 不检索、确认、下载或消费关联内容；保留已有字段和文件 |
| l4_review | Step 11 L4 实现追溯验证 | true | 跳过实现追溯验证 |
| code_review | Step 12 Code Review | true | 跳过代码检视 |
| unit_test | Step 13 单元测试 | true | 跳过 UT；l5_coverage 因依赖自动降级 |
| l5_coverage | Step 14 L5 UT 覆盖度验证 | true | 仅关闭 L5 覆盖度验证 |
| completion_report | Step 15 完成或暂停时展示状态 | true | 跳过完成状态展示 |

编排点：`pre-codegen`（task，10.3/10.4 之间）、`post-codegen`、`post-l4`、`post-review`、`post-ut`。

### 5.2 core-init

| 配置键 | 对应步骤 | 默认 | 关闭后果 |
|--------|---------|------|---------|
| version_check | Step 0 版本检查 | true | 跳过版本检查（不推荐） |
| okf_knowledge_fetch | Step 4 拉取产品知识中心代码仓 | false | 默认即关；不开则 `docs/knowledge/` 不生成，需手动准备 |
| multi_analysis | Step 5 多仓依赖分析 | true | 跳过多仓依赖分析 |
| check_sync | Step 6a 同步必要性检查 | true | 跳过检查且 execute_sync 因依赖同步跳过——须确保 docs/specs/ 已有 spec.md 与 design.md |
| execute_sync | Step 6b 代码仓逆向文档获取 | true | 跳过文档拉取与生成——须确保 docs/specs/ 已有 spec.md 与 design.md |

编排点：`post-init-structure`、`post-scan-language`、`post-multi-analysis`、`pre-execute-sync`（逐仓）、`post-execute-sync`（逐仓）。

### 5.3 core-explore

| 配置键 | 对应步骤 | 默认 | 关闭后果 |
|--------|---------|------|---------|
| version_check | Step 0 版本检查 | true | 跳过版本检查（不推荐） |
| req_refine | 阶段5.1.5 需求文档细化补全（B 档） | **false** | 默认即关；开启后 step-4 因互斥规则自动降级 |
| knowledge_precheck | 阶段5.3 领域知识预澄清 | true | 指令文件不加载、检查点豁免；产物仍须保留 |
| brainstorming | 阶段5.4 需求澄清 | true | 指令文件不加载、检查点豁免；产物仍须保留 |
| find_similar | 阶段7 查找相似需求 | true | delta_spec 无相似需求参考 |
| l1_review | 阶段9 L1 需求完整性验证 | true | 对应阶段/关卡豁免，指令文件不加载 |
| explore_review | 阶段10 explore-doc-reviewer 审查 | true | 对应阶段/关卡豁免，指令文件不加载 |
| cleanup_temp | 阶段11 清理临时文件 | true | 临时文件须人工处理（不阻断收尾） |

编排点：`pre-clarification`、`post-clarification`、`pre-proposal`、`post-proposal`、`pre-delta-spec`、`post-delta-spec`、`post-l1`、`post-review`、`post-cleanup`。

req_refine 补充：开启时需求细化产物在 `docs/.explore_context/req-refine/{需求ID}/`，为通道型步骤（多仓也只产出全局一份，指令文件 references/req-refine.md / references/req-refine-multi.md）；**强制 subagent 执行**——必须通过 Agent tool 启动 subagent 完成，禁止主会话直接执行。

### 5.4 core-design

| 配置键 | 对应步骤 | 默认 | 关闭后果 |
|--------|---------|------|---------|
| version_check | Phase 1 版本检查 | true | 跳过版本检查（不推荐） |
| fetch_rules | Phase 2 code-rule 拉取 | true | 跳过语言规范拉取；Phase 2.2 的 GATE（设计原则/视图）**不受开关控制**仍生效 |
| read_similar | Phase 5 读取相似需求参考归档 | true | delta_design 无历史设计参考 |
| expert_experience | Phase 7 准备已有设计经验 | true | 不准备已有经验上下文；不影响独立的 Skill 消费开关 |
| skill_consumption | Phase 9 任务 Skill 查找、确认、安装与关联 | **false** | 不查找或关联 Skill；原任务生成及后续验证照常执行 |
| design_traceability | Phase 10 设计追溯验证 | true | 对应阶段/关卡豁免；design_review 仍开启时依赖链豁免直接进入审查 |
| design_review | Phase 11 design-doc-reviewer 审查 | true | 对应阶段/关卡豁免 |
| cleanup | Phase 12 清理临时文件 | true | 临时文件须人工处理（不阻断收尾） |

编排点：`post-rule-fetch`、`post-gather-context`、`post-code-understanding`、`pre-generate`、`post-generate`、`post-traceability`、`post-design-review`、`post-cleanup`。

两个阶段分别配置，均默认关闭。在 `~/.corespec/flow-config.json` 中找到对应命名空间，添加或修改 `"skill_consumption": true` 即可开启；改为 `false` 关闭，保存后下次运行生效。保留该命名空间的其他配置项。

- `core-design` 开启后，在任务生成后查找候选，经选择确认后安装并关联到任务。
- `core-apply` 开启后，先检查待办任务关联并补齐所需内容，再在代码生成时使用；多仓由主会话统一确认，各仓使用自己的任务上下文。
- 开启设计阶段不会自动开启执行阶段。关闭后保留已有关联和本地文件，但不主动读取或使用它们。
- 如果旧配置里的 `skill_consumption` 是 `{ "type": "reference", ... }` 对象，将整个对象替换为 `true` 或 `false`，不要同时保留两种写法。

### 5.5 core-archive

| 配置键 | 对应步骤 | 默认 | 关闭后果 |
|--------|---------|------|---------|
| version_check | Step 1 版本检查 | true | 跳过版本检查（不推荐） |
| core_verify | Step 4 归档前验证 | true | 直接进入 Step 5；DOC_STALE 差异线索为空 |
| check_artifacts | Step 5 检查 artifact 完成状态 | true | 跳过 artifact 检查 |
| check_tasks | Step 6 检查 task 完成状态 | true | 跳过 task 检查 |
| backfill | Step 9 代码反刷 | true | 归档前文档与代码差异不反刷 |
| spec_sync | Step 10 delta 合并到全量文档 | true | 全量 spec.md/design.md 不更新 |
| show_summary | Step 12 展示归档摘要 | true | 跳过摘要展示 |
| push_mr | Step 13 推送 + 建 MR | true | 代码留在本地分支，未推送 |

**core-archive 默认全开。** 不可关闭步骤：获取版本号（Step 7）、多仓检测（Step 8）、归档执行（Step 11，多仓对应 M-3）——核心归档动作无配置键，强制生效。依赖链豁免：关闭 core_verify/backfill/spec_sync 时，其后开启步骤的前置依赖随关闭键豁免，链条自动续接。

编排点：`pre-verify`、`post-verify`、`pre-backfill`、`post-backfill`、`pre-spec-sync`、`post-spec-sync`、`pre-archive`、`post-archive`、`pre-push`、`post-push`。

### 5.6 其他 core-* 技能

接入 flow-config 框架后在此追加速查分节。接入前该技能全默认，无需配置。

## 6. 配置示例

```jsonc
{
  "core-apply": {
    // ---- 内置步骤开关（true/false）----
    "version_check": true,
    "show_progress": false,  // Step 8 展示当前进度（默认关闭）
    "skill_consumption": false, // Step 9 / M-1a 任务 Skill 准备（true 开启）
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

不用某自定义步骤时把声明整块注释保留即可（JSONC 支持 `//`），恢复时取消注释，无需重写：

```jsonc
{
  "core-apply": {
    "l4_review": true
    // "judgment_ladder": {
    //   "type": "reference",
    //   "file": "references/judgment-ladder.md",
    //   "at": "pre-codegen"
    // }
  }
}
```

## 7. 常见问题

| 问题 | 说明 |
|------|------|
| 为什么我没配过却出现了这个文件？ | 首次运行 core-* 时自动生成的带注释模板（总结中会提示一次），放着不动 = 全默认 |
| 修改配置后需要做什么？ | 无需手动操作。下次运行 core-* 时按修改后的配置直接生效 |
| 关闭的步骤还会执行吗？ | 不会。关闭步骤的指令文件不加载，内容不进 agent 上下文（结构阻断） |
| 关闭 l5_coverage 会怎样？ | 仅关闭 L5。关闭 unit_test 会导致 l5_coverage 自动降级（依赖规则） |
| 文件损坏会怎样？ | 解析失败时先尝试自愈（剥除尾逗号），无法自愈则启动时报 `ok: false` 并保留既有执行计划，绝不静默降级为全默认；可回退 `flow-config.json.bak-*` 备份 |
| 其他 core-* 技能怎么配？ | 看第 5 节速查表；未接入的技能无需配置（全默认）。或用 `main.py flow-config --describe --json --skill <name>` 查可用键 |
