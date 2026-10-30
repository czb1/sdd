# CoreSpec 模板自定义使用指南

> 本指南是**全局共享指南**（模板层）：描述 CoreSpec 模板系统的三层架构、双通道解析、端到端使用流程，以及新增 artifact 的声明链路。
>
> **获取本指南**：`python -m core_templates --guide` 输出全文；首次运行任何 core-* skill 时会自动同步到 `~/.corespec/template-guide.md`。

目录：§1 使用场景 → §2 三层架构 → §3 双通道解析 → §4 使用流程 → §5 验证方法 → §6 新增 artifact → §7 常见问题 → §8 相关文档。

---

## 1. 为什么需要模板自定义

CoreSpec 内置 5 个必需 artifact 的模板（proposal / delta_spec / delta_design / tasks / delta_test_design），覆盖通用场景。当团队需要：

- 新增章节（如"风险与对策"、"安全合规评审"）且希望全局或项目级生效
- 调整章节顺序或替换章节骨架
- 声明全新的 artifact（如"架构决策记录"）并接入 SDD 流程编排

就需要模板自定义能力。CoreSpec 提供**三层模板架构** + **双通道解析** + **命令行工具**覆盖上述需求。

## 2. 三层模板架构

模板按优先级从低到高分三层，高层覆盖低层（整文件替换，非章节级合并）：

| 层级 | 位置 | 作用域 | 何时使用 |
|------|------|--------|---------|
| **L1 内置** | `coreharness-spec/core-schemas/<schema>/templates/` | 随包分发，所有项目共享 | 出厂默认，**禁止直接修改** |
| **L2 用户** | `~/.corespec/core-schemas/<schema>/templates/` | 当前用户的所有项目 | 全局自定义（本机所有 CoreSpec 项目共享） |
| **L3 项目** | `<project_root>/docs/core-schemas/<schema>/templates/` | 仅当前项目 | 项目级自定义（团队共享，随 git 提交） |

**覆盖规则**：同一 artifact 文件名在多层存在时，最高层胜出（整文件替换）。例如 L3 有 `proposal.md` 则使用 L3 的，忽略 L2 和 L1。

**路径解析**：

- 仅返回**实际存在**的层目录
- 解析顺序固定 L1 → L2 → L3，高层后写入覆盖低层

## 3. 双通道解析

CoreSpec 有两个独立的解析通道，分别管"模板内容"和"schema 声明"：

### 3.1 模板通道（L1 → L2 → L3 叠加）

**用途**：解析某个 artifact 的有效模板内容（章节骨架）。

- 按层级顺序 L1 → L2 → L3 叠加，高层文件覆盖低层
- 从最终内容提取 H2 章节名（去重、规范化），供 reviewer 做完整性比对

### 3.2 Schema 通道（L3 → L2 → L1 首层命中替换）

**用途**：解析有效 schema（artifact 声明列表、requires 依赖、instruction 等）。

- schema.yaml 按层级首层命中即返回（整文件替换，非叠加）
- `init()` 会将内置 schema.yaml 复制到 L2（`~/.corespec/core-schemas/<schema>/schema.yaml`），用户可直接编辑 L2 schema.yaml 声明新增 artifact

**两通道独立**：模板通道决定"章节骨架长什么样"，schema 通道决定"有哪些 artifact、依赖关系是什么"。修改模板内容走模板通道，新增 artifact 声明编辑 L2 schema.yaml 的 artifacts 列表。

## 4. 端到端使用流程

### 4.0 自动初始化（无需手动执行 init）

**默认行为**：任何 core-* skill（core-init / core-explore / core-design / core-apply / core-archive）首次运行时，会自动检测用户层模板目录 `~/.corespec/core-schemas/spec-driven/templates/` 是否存在：

- **不存在** → 静默复制内置模板到 L2 + 同步使用指南到 `~/.corespec/template-guide.md`（无用户交互，无需确认）
- **已存在** → 跳过（用户已初始化或已自定义）

这意味着用户**无需手动执行 `init`**——首次使用任何 core-* skill 时即自动获得可编辑的 L2 模板副本。之后直接编辑 `~/.corespec/core-schemas/spec-driven/templates/` 下的文件即可自定义。

> 手动 `init` 仍可用于强制覆盖 L2 模板（如内置模板升级后想重新同步）。

### 4.1 场景 A：修改现有 artifact 的章节（最常见）

**目标**：在 `proposal.md` 模板中新增"风险与对策"章节，全局生效。

```bash
# 步骤1: 编辑用户层模板，添加章节
#   文件：~/.corespec/core-schemas/spec-driven/templates/proposal.md
#   在合适位置添加：## 风险与对策
```

完成后下次执行 `core-explore` 时，流程会自动重新物化模板（含新增章节）并验证完整性——无需手动执行 `validate` 或 `resolve`。

**项目级替代**：如果只想在某个项目生效（非全局），将文件放到 `<project_root>/docs/core-schemas/spec-driven/templates/proposal.md`（L3 层）。

### 4.2 场景 B：新增 artifact 并接入 SDD 流程

**目标**：新增"架构决策记录"（`arch_decisions`）artifact，在 design 阶段生成、design-review 阶段审查。

只需两步——在 L2 schema.yaml 的 artifacts 列表追加声明 + 创建模板载体：

```bash
# 步骤1: 创建模板载体
#   位置：~/.corespec/core-schemas/spec-driven/templates/arch_decisions.md
#   内容：## 决策背景  ## 备选方案  ## 决策结论  ## 影响评估

# 步骤2: 在 L2 schema.yaml 的 artifacts 列表追加声明
#   位置：~/.corespec/core-schemas/spec-driven/schema.yaml
#   在 artifacts: 列表末尾追加：
#   - id: arch_decisions
#     generates: arch_decisions.md
#     template: arch_decisions.md
#     requires: [delta_spec]
```

完成后流程会自动处理：

- **模板完整性校验**：下次执行 SDD 流程时，`resolve --materialize` 会自动 validate（ERROR 阻断、WARNING 打印）
- **审查覆盖**：新 artifact 自动纳入对应环节 reviewer 审查范围（explore-doc-reviewer / design-doc-reviewer 在 Stage 1 通过 `load_schema` 动态发现并按 DAG 分层过滤，无需额外配置）

### 4.3 场景 C：仅项目级自定义（不影响全局）

**目标**：仅在某项目调整 `tasks.md` 模板，不污染全局。

```bash
# 步骤1: 创建项目级模板目录
mkdir -p <project_root>/docs/core-schemas/spec-driven/templates/

# 步骤2: 从用户层模板复制并编辑
cp ~/.corespec/core-schemas/spec-driven/templates/tasks.md \
   <project_root>/docs/core-schemas/spec-driven/templates/tasks.md
#   编辑文件，调整章节

# 步骤3: 提交到 git（团队共享）
git add docs/core-schemas/
git commit -m "chore: customize tasks template for this project"
```

完成后下次执行 SDD 流程时会自动使用 L3 项目层模板（L3 优先于 L2/L1）——无需手动验证。

## 5. 验证方法总览（可选自验证）

SDD 流程执行时会自动验证模板完整性（`resolve --materialize` 嵌入 validate），以下命令供用户在流程外主动确认：

| 验证目的 | 命令 | 预期输出 |
|---------|------|---------|
| 模板完整性（4类缺口） | `python -m core_templates validate` | `OK: all artifacts have templates...` |
| 查看有效模板章节 | `python -m core_templates resolve <artifact>` | 模板全文含 `<!-- template-v... -->` 头 |
| 物化到变更目录 | `python -m core_templates resolve <artifact> --materialize <change_dir>` | `Materialized to <path>`（含自动 validate） |

> **resolve --materialize 自动 validate**：`resolve` 带 `--materialize` 参数时会自动嵌入 validate 校验——ERROR 级缺口（必需内置缺失 / requires 引用断裂 / 声明的 artifact 无模板文件）会阻断物化并抛出 ValueError，WARNING 级缺口（孤儿模板）打印但不阻断。

### 5.1 validate 的 3 类缺口

| 缺口类型 | 严重级别 | 说明 |
|---------|---------|------|
| 有模板无声明 | WARNING | `templates/` 下有 `.md` 但 schema.yaml 未声明 |
| 有声明无模板 | ERROR | schema.yaml 声明了 artifact 但任何层都找不到模板文件 |
| requires 引用不存在 | ERROR | schema.yaml 中 `requires` 字段引用的 artifact_id 在当前清单中不存在 |

### 5.2 端到端验证检查点

在 SDD 流程执行中，模板自定义的效果会在以下检查点体现：

| SDD 阶段 | 检查点 | 验证方法 |
|---------|--------|---------|
| core-explore | proposal / delta_spec 物化 GATE | 确认 `.templates/resolved/` 下对应文件含自定义章节 |
| core-explore | explore-doc-reviewer | reviewer 按物化模板章节做完整性比对 |
| core-design | artifact 生成 | 按物化模板填充章节 |
| core-design | design-doc-reviewer | reviewer 按有效模板章节审查 |

## 6. 新增 artifact 声明链路（两步 + 自动化）

新增 artifact 用户只需两步，后续环节自动处理：

| 步骤 | 文件 | 作用 | 缺失后果 |
|------|------|------|---------|
| 1 模板载体 | `~/.corespec/core-schemas/spec-driven/templates/<artifact>.md` | 章节骨架 | resolve 报错（找不到模板文件） |
| 2 schema.yaml | `~/.corespec/core-schemas/spec-driven/schema.yaml` | artifact 声明（id / generates / template / requires） | 流程不知道该 artifact 存在 |

**自动化环节（无需用户参与）**：

- **完整性校验**：下次执行 SDD 流程时，`resolve --materialize` 自动 validate（ERROR 阻断、WARNING 打印）
- **审查覆盖**：新 artifact 自动纳入对应环节 reviewer 审查范围（DAG 分层过滤一次性覆盖，无需额外配置）

## 7. 常见问题

| 问题 | 说明 |
|------|------|
| 用户层模板什么时候被创建？ | 任何 core-* skill 首次运行时自动复制内置模板到 `~/.corespec/core-schemas/spec-driven/templates/`（无需手动 `init`）。已存在则跳过 |
| `init` 后内置模板升级了怎么办？ | 用户层模板不会自动同步。需手动 `init` 重新复制（会覆盖），或手动 merge 新章节。`version.json` 可比对版本 |
| L2 和 L3 都有同名模板，哪个生效？ | L3（项目级）优先。模板通道按 L1→L2→L3 叠加，高层覆盖低层 |
| 新增 artifact 后 `validate` 报 ERROR？ | 检查：1) 模板文件是否在 `~/.corespec/core-schemas/spec-driven/templates/` 目录 2) L2 `schema.yaml` 的 artifacts 列表是否声明了对应条目 3) `requires` 引用的 id 是否存在 |
| `resolve --materialize` 报模板完整性错误？ | 物化前会自动 validate，ERROR 级缺口会阻断物化。按报错修复后重试，或先手动 `validate` 确认 |
| 物化文件在哪？ | `docs/changes/<change>/.templates/resolved/<artifact>.md`（单仓和多仓共用同一路径，所有子仓共享同一物化文件） |
| reviewer 用的章节列表从哪来？ | 从物化模板的 H2 标题提取（去重、规范化），非 instruction 文本 |
| `requiredSections: auto` 是什么？ | schema.yaml 中 artifact 的字段，表示必需章节从解析后的有效模板自动派生。reviewers 消费该结果 |
| 新增 artifact 如何被 SDD 流程生成？ | 在 L2 `schema.yaml` 的 artifacts 列表声明 + 模板载体存在即可。流程按 requires 依赖顺序生成 |

## 8. 相关文档

| 文档 | 位置 | 内容 |
|------|------|------|
| flow-config 配置指南 | `~/.corespec/flow-config-guide.md` | 编排点插槽配置 |
