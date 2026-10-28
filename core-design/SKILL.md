---
name: core-design
description: Design document generation - reads delta_spec.md from explore phase from docs, fetch rule lists and request for relevant rules, generates design artifacts based on schema definitions with expert experience integration and task-level Skill discovery through 云见 CLI
license: MIT
compatibility: Works without npm - uses Python scripts with schema-driven generation
metadata:
  author: corespec
  version: 1.3.2
  generatedBy: "manual"
---

Design document generation for a change.

**Note**: This skill generates ONLY design-phase artifacts. The proposal and delta_spec are generated in the explore phase.

## Skill 与经验消费规则

### 能力判断与候选查找

以当前任务目标、代码仓和上下文为输入，由 Agent 自主判断需要业务相关能力还是通用能力；需要两类能力时分别选择对应路径。SDD 只针对 tasks.md 的 1.x 代码生成任务，结合任务描述和「编程语言」匹配候选。

| 能力类型 | 查找与选择 |
|---|---|
| 业务相关 | 结合 git remote、仓库根目录名、.codeagent/product.json 解析产品名 → 通过云见 CLI 获取产品场景 → 按任务描述与编程语言语义匹配场景（可多选）→ 获取命中场景的 Skill 名称及描述 |
| 业务路径未命中 | 产品无法定位、场景无法匹配或场景无合适 Skill 时，通过云见 CLI 分别检索最多 **3 个 Skill 候选**和经验引擎中最多 **3 条经验候选**，综合判断 Skill、经验或两者组合 |
| 通用能力 | 跳过产品和场景链路，直接通过云见 CLI 检索通用 Skill |

产品名无法可靠解析或来源有冲突时，向用户询问产品名，允许跳过；跳过后按业务未命中路径处理，不反复追问。为每个任务预判最多 Top3 Skill，给出一句话匹配理由及 Agent 首选；不足时按实际数量处理，不强行凑数。场景已有合适 Skill 或当前只需要通用能力时，不自动追加业务兜底的经验检索。一侧检索失败时仍可判断另一侧已返回的候选，但服务错误不能报告为确定无结果。

### 批量确认（候选准备后、下载前）

- 按任务组聚合候选，一次 AskUserQuestion（或当前环境等价交互工具）批量展示，不逐任务弹窗。展示任务编号、编程语言、候选名称 / 描述、匹配理由，并对每个首选标注 **✓ 推荐**；有经验候选时一起展示拟采用内容。
- 支持用户在同一次回答中按任务或任务组指定 Skill / 不使用；固定附加 **全部由 Agent 决定** 和 **本次不使用外部 Skill** 两个选项。
- 同一次回答的优先级为：全局「本次不使用外部 Skill」最高，其次逐任务指定，再次任务组指定，最后默认首选。某任务明确选择不使用时不得回退成推荐项，也不得通过新获取经验绕过。选择「全部由 Agent 决定」时采用首选；选择「本次不使用外部 Skill」时，本轮展示范围内的任务均不下载或使用外部 Skill，也不通过经验兜底绕过该选择。
- 用户跳过、提交但未选，或交互工具明确结束并返回无答案时，静默采用仍有合适候选任务的 Agent 首选；部分任务未指定时仅对这些任务采用首选。正在等待的提问不能仅凭时间流逝判为无响应；工具故障不能冒充用户跳过。
- 用户指定名称或明确确认推荐项记为「用户指定」；选择「全部由 Agent 决定」、跳过 / 未选或交互返回无答案后采用首选，记为「Agent 自选」。最终输出列明哪些任务由用户指定、哪些是 **Agent 自选**，以及哪些不使用或获取失败。无合适候选时继续原任务，不虚构首选。
- 以上默认规则只用于能力候选选择，不覆盖执行计划确认本身的空应答规则。单仓由主会话统一确认；多仓子代理只准备候选，由主会话汇总各仓任务组后统一提问并分发锁定结果，禁止子代理各自弹窗。

### CLI 接入、去重与项目级落地

- 所有产品、场景、Skill 与经验的查找和获取统一通过云见 CLI 完成。读取实际可用的云见 CLI Skill / 操作指引及帮助信息，不编造命令、参数、接口或标识。scenes(product)、skills(scene)、download(skill_name) 是 Registry 的逻辑能力，经 CLI 调用，不另建绕开 CLI 的 HTTP 获取路径。
- 云见 CLI Skill 提供操作指引，业务 / 通用 Skill 提供任务实际使用的能力，二者不要混淆。其他场景先安装并读取云见 CLI Skill；已安装时直接读取。
- CLI、操作指引、身份、安装入口或服务不可用时，说明本次未获取到能力，继续原任务。交互工具故障时说明无法完成候选确认，本轮不新增下载；已有明确锁定的关联仍可使用。
- 确认或默认选择锁定后，扫描已选集合，**按 skill name 去重**；同一名称下载一次，多个任务共同引用。多仓可复用下载包，但分别安装到所属仓项目目录；候选及确认结果仅暂存在主会话上下文，不另建索引。
- Skill 包先解压到临时目录，校验名称、内容可读性及解压路径未越界，再原子替换项目级 **.codeagent/skills/<name>/**。本轮明确获取的同名 Skill 可以替换；只替换该名称目录，不改动其他 Skill 或相邻目录。
- 下载、校验或原子替换失败时保留原同名目录，不将半成品当作成功结果；只有验证旧内容仍适用时才继续使用旧内容并如实说明。经验按项目已有约定保存到项目级目录；单项失败不阻断其余成功内容或原任务。

### tasks.md 回写与后续消费

- **SDD 场景**：落地成功后回写对应任务的 **Skill 字段**，记录实际锁定名称、可读本地路径及选择来源（用户指定 / Agent 自选）；经验按任务已有描述约定关联。保留任务编号、checkbox、设计锚点及测试策略。
- 用户明确不使用时，将 Skill 字段写为「不使用（用户选择）」；无候选或获取失败时如实注明，不能将未成功落地的内容写成可用关联。明确不使用是有效决策，不能被当成缺少关联而自动重新检索。
- **其他场景**：直接用于当前任务，不修改 tasks.md，即使项目中已有该文件。
- tasks.md 是 SDD 任务及其能力关联的唯一数据源；下载文件只承载能力内容，不新增任务能力索引。
- 执行已有 SDD 任务时先读 Skill 字段及本地实际内容，复用已锁定的内容，不重复确认。只有确需新增 / 改选 Skill 时，才在任务循环前汇总受影响任务，执行一次批量确认；单纯补下已锁定的同名 Skill 无须再次选型。循环中才发现新增 / 改选需求时，先收集并预检其余待办任务，返回主会话的批量准备阶段统一处理，不逐任务临时弹窗；已有可用关联的任务可以继续。用户明确不使用的任务保持该决定，除非用户更改。
- 多仓以任务所属代码仓定位产品，内容落到该仓 .codeagent/skills，关联写入该仓 tasks.md；各仓执行者自行读取上下文，不在根项目另建汇总索引或修改其他仓任务。
- 没有本轮明确获取或更新决定时不自动覆盖项目本地内容；清理时保留任务仍引用的 Skill 与经验。
- 最终简要报告查找、选择来源、安装及 tasks.md 同步结果。获取失败不阻断原任务，同步未成功时不得宣称完成。

## Input

- Change name (kebab-case)
- `docs/relationship.md` - 多仓库依赖关系，理解设计涉及的跨仓库调用链
- Optional: `--step` for step mode, `--quick` for quick mode
- Optional: `--query` for task capability search keywords

## Execution Method

The skill uses Python scripts in `scripts/` directory that read from schema definitions:

```bash
# Dynamic path resolution using core_paths.py (supports both OpenCode and ClaudeCode)
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([
    sys.executable,
    config_dir / 'skills' / 'core-design' / 'scripts' / 'main.py',
    '<command>', '<options>'
])
sys.exit(result.returncode)
"
```

Or directly (auto-detect config directory):
```bash
# OpenCode: ~/.config/opencode/skills/core-design/scripts/main.py
# ClaudeCode: ~/.cac/skills/core-design/scripts/main.py
```

### Reference文件路径解析

本SKILL中的 `references/` 路径**相对于本SKILL.md所在目录**（即skill安装目录），**不是相对于项目工作目录**。

**解析方式**：使用与脚本调用相同的动态路径解析：
```python
# 构建 reference 文件绝对路径
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
ref_path = config_dir / 'skills' / 'core-design' / 'references' / 'multi-repo.md'
# 然后用 Read 工具读取 ref_path
```

**备选路径**（动态解析失败时依次尝试）：
1. `~/.config/opencode/skills/core-design/references/multi-repo.md`
2. `~/.cac/skills/core-design/references/multi-repo.md`

**【禁止】在项目工作目录下搜索 references/ 路径**——该目录不存在于项目中。

**第 0 步（前置）：构建执行计划（MANDATORY - 必须为第一个动作，先于 Phase 1 版本检查）**

**必须先于 Phase 1（version check）执行**：它是执行计划的第一阶段、第一个动作。执行以下命令构建执行计划（唯一权威）：

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run(
    [sys.executable, config_dir / 'skills' / 'core-design' / 'scripts' / 'main.py', 'flow-config', '--json', '--skill', 'core-design'],
    encoding='utf-8', capture_output=True, text=True)
print(result.stdout)
sys.exit(result.returncode)
"
```

**输出 JSON 内容判断**（非零 exit code 不意味着失败，必须以 JSON 内容为准）：

- `"ok": false` → 配置校验/解析失败（`error` 或 `errors` 说明原因）→ **MUST STOP**，告知用户修正 `~/.corespec/flow-config.json` 后重试，禁止继续执行。
- `"ok": true` → 执行计划已持久化到 `docs/.flow_context/execution-plan-core-design.json`，skipped 标记到 `docs/.flow_context/skipped-core-design.json`。按 `config_missing` 与 `scenario` 决定确认动作：

**首次运行（`config_missing: true`）——必须给用户配置机会**：

配置文件 `~/.corespec/flow-config.json` 不存在时，这是用户**唯一一次**接触 flow-config 框架的机会。**不得静默跳过**——必须用 **AskUserQuestion** 向用户提供"生成模板 / 继续默认"选择：

```
AskUserQuestion({
  questions: [{
    question: "未检测到 flow-config 配置文件（~/.corespec/flow-config.json）。\n当前将以全默认计划执行（内置步骤按出厂默认启停：version_check/fetch_rules/read_similar/expert_experience/design_traceability/design_review/cleanup 全部开启，无自定义步骤）。\n是否生成配置模板以便启停步骤或插入自定义步骤？\n<summary>",
    header: "首次配置",
    options: [
      { label: "生成模板", description: "生成 ~/.corespec/flow-config.json 模板（含全部可配置项说明），用户修改后重建计划" },
      { label: "继续默认", description: "直接使用全默认计划执行，本次不再配置" }
    ]
  }])
```

- 用户选择 **生成模板**：运行以下命令生成带注释的 JSONC 模板并同步配置指南到 `~/.corespec/flow-config-guide.md`：

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run(
    [sys.executable, config_dir / 'skills' / 'core-design' / 'scripts' / 'main.py', 'flow-config', '--init', '--skill', 'core-design'],
    encoding='utf-8', capture_output=True, text=True)
print(result.stdout)
sys.exit(result.returncode)
"
```

  告知用户修改 `~/.corespec/flow-config.json` 后**重新运行本构建命令**。用户选择"继续默认"或确认修改后 → 进入 Phase 1（版本检查）
- 用户选择 **继续默认**：直接使用已持久化的全默认计划，进入 Phase 1（版本检查）

**命名空间缺失（`config_missing: false` 且 `ns_missing: true`）——也必须给用户配置机会**：

配置文件 `~/.corespec/flow-config.json` 已存在但**本 skill 的命名空间不存在**——必须用 **AskUserQuestion** 向用户提供"生成模板 / 继续默认"选择：

```
AskUserQuestion({
  questions: [{
    question: "flow-config 配置文件已存在，但未包含 core-design 命名空间（首次接触本 skill 的配置项）。\n当前将以全默认计划执行（内置步骤按出厂默认启停：version_check/fetch_rules/read_similar/expert_experience/design_traceability/design_review/cleanup 全部开启，无自定义步骤）。\n是否生成配置模板以便启停步骤或插入自定义步骤？\n<summary>",
    header: "首次配置",
    options: [
      { label: "生成模板", description: "生成 ~/.corespec/flow-config.json 的 core-design 分区模板（含全部可配置项说明），用户修改后重建计划" },
      { label: "继续默认", description: "直接使用全默认计划执行，本次不再配置" }
    ]
  }])
```

- 用户选择 **生成模板**：运行上方 `--init` 命令（文件不存在时生成完整模板；已存在时从模板提取 core-design 示例块追加到顶层闭合前），告知用户确认后**重新运行本构建命令** → 进入 Phase 1（版本检查）
- 用户选择 **继续默认**：直接使用已持久化的全默认计划，进入 Phase 1（版本检查）

**非首次运行（`config_missing: false`）**，按 `scenario` 决定确认动作：

| scenario | 含义 | 动作 |
|----------|------|------|
| `A` | 命名空间未配置/解析后全默认（配置文件存在） | 命名空间已配置且解析全默认 → **跳过确认**（零接触）；**命名空间缺失（`ns_missing: true`）→ 同首次运行，必须用 AskUserQuestion 提供"生成模板 / 继续默认"** |
| `B` | 首次·非默认 | 用 **AskUserQuestion**（`multiSelect: true`）展示完整勾选列表（可关闭的内置步骤 + 自定义步骤） |
| `C` | 续跑·一致（指纹匹配） | 轻量确认：展示计划摘要，用户确认/跳过 |
| `D` | 计划缺失·命名空间存在 | 用 **AskUserQuestion** 确认：配置非默认 → `multiSelect: true` 完整勾选列表；配置全默认 → 轻量确认 |
| `E` | 配置变更（指纹不匹配） | 用 **AskUserQuestion** 展示变更后计划，确认后继续 |

**计划确认后必须创建 task 任务（MANDATORY）**：计划确认完成后，进入主流程前，必须使用 **TaskCreate 工具**创建 task 任务清单：
- **先创建当前阶段即可确定的任务**：
  - 固定主流程步骤：构建执行计划 → Phase 1（版本检查，`version_check` 关闭时跳过）→ Phase 2（获取规范，`fetch_rules` 关闭时跳过 GATE 仍执行）→ Phase 3（收集上下文）→ Phase 4（代码理解）→ Phase 8（生成设计文档）各建一个 task
  - 按执行计划 `steps` 数组，为每个启用的可配置内置步骤（`config_key` = `version_check`/`fetch_rules`/`read_similar`/`expert_experience`/`design_traceability`/`design_review`/`cleanup`）创建 task；关闭的步骤不创建
  - 每个启用的编排点插槽条目（`orchestration_points` 中的 reference/skill 步骤）同样创建 task
- **多仓检测后必须补充创建分支 task（MANDATORY）**：执行计划在构建时尚未运行多仓检测，单仓/多仓分支无法在确认时预知。Phase 3 多仓检测输出路由结果后，必须立即用 TaskCreate 补齐分支任务：单仓 → Phase 5（`read_similar` 关闭时跳过）→ Phase 6 → Phase 7（`expert_experience` 关闭时跳过）→ Phase 8 → Phase 9（`design_traceability` 关闭时跳过）→ Phase 10（`design_review` 关闭时跳过）→ Phase 11（`cleanup` 关闭时跳过）各建一个 task；多仓 → 按 references/multi-repo.md 的 M-1/M-2/M-3a/M-3b/cleanup 各建一个 task（M-3a 对应 `design_traceability`、M-3b 对应 `design_review`、cleanup 对应 `cleanup`，关闭的 M 不创建；M-2 不可关，始终创建）
- task 描述注明对应步骤/config_key/M 阶段与启停状态
- **禁止跳过 TaskCreate**（用户可直观看到哪些步骤要执行、哪些已关闭）

## Artifact Scope

| Phase | Artifacts Generated | Input Required |
|-------|---------------------|----------------|
| **Explore** (`/core-explore`) | proposal.md, delta_spec.md | Requirement ID |
| **Design** (`/core-design`) | delta_design.md, delta_test_design.md, tasks.md | delta_spec.md (from explore) |

## Execution Flow

> **编号规则**：Phase 1~12 连续编号，与 steps.md 序号一一对应。无 0/0.5/1.5 等非整数编号。

### Phase 1: Version Check [可配置: version_check]

> 本步骤为可配置步骤。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=version_check`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入 Phase 2（指令文件不加载，内容不进上下文）

### Phase 2: Fetch Design Rules + 加载设计原则与视图约束

> #### 2.1 多语言规范获取 [可配置: fetch_rules]
>
> 本步骤为可配置步骤（B 档双层语义）。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=fetch_rules`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行 Step 1~3（多语言规范获取：code-rule-tree → 筛选 → code-rule-content），完成后得到 `language-specific design specifications`。
> - **执行计划不含本步骤** → 跳过 Step 1~3 的 code-rule 拉取流程，`language-specific design specifications` 视为空集合，直接进入 2.2（指令文件不加载，内容不进上下文）
>
> **【B 档双层语义】**：`fetch_rules` 开关**仅控制** 2.1 的 code-rule 拉取流程（Step 1~3）。下方 2.2 的 GATE（design-principles.md / design-views.md）为**无条件加载**，与 `fetch_rules` 开关**正交**——即 `fetch_rules` 关闭时 2.1 跳过，但 2.2 的两个 GATE 仍必须执行。

#### 2.2 加载设计原则与视图约束（GATE）

<!-- GATE:REF references/design-principles.md -->
**MANDATORY GATE**: 生成设计文档前必须 Read 本 SKILL 所在目录下的 `references/design-principles.md`。
绝对路径 = config_dir / 'skills/core-design/references/design-principles.md'（动态路径解析参见本 SKILL Reference 文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/design-principles.md loaded"。
<!-- /GATE:REF -->

<!-- GATE:REF references/design-views.md -->
**MANDATORY GATE**: 生成设计文档前必须 Read 本 SKILL 所在目录下的 `references/design-views.md`。
绝对路径 = config_dir / 'skills/core-design/references/design-views.md'（动态路径解析参见本 SKILL Reference 文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/design-views.md loaded"。
<!-- /GATE:REF -->

**使用方式**：
- `references/design-principles.md`：在 Phase 8 填充每个 delta_design 章节时，对照"与 delta_design 章节的映射"表，确保对应原则在章节中体现
- `references/design-views.md`：在 Phase 8 填充包含视图的章节时，对照"必须视图"和"条件视图"表，确保产出对应 PlantUML 图

**多仓场景注意**：主会话 GATE 加载的内容**不传递给子代理**。多仓模式下，主会话必须在 M-2 Step 4 构造子代理 prompt 时，将这两个文件作为输入文件表第9/10行显式列出（含绝对路径和消费用途），确保子代理自行读取。详见 `references/multi-repo.md` M-2 Step 4。

### Phase 3: Gather Context

<!-- GATE:REF references/gather-context.md -->
**MANDATORY GATE**: 收集上下文前必须先 Read 本SKILL所在目录下的 `references/gather-context.md`（Phase 3 完整执行指令：delta_spec.md 读取、language-specific design specifications 读取、全局文档读取优先级表、单仓/多仓环境判断、读取策略、全局文档作用）。
绝对路径 = config_dir / 'skills/core-design/references/gather-context.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/gather-context.md loaded"。
<!-- /GATE:REF -->

### Phase 4: 代码理解（Agent 决策）

<!-- GATE:REF references/code-understanding.md -->
**MANDATORY GATE**: 代码理解前必须先 Read 本SKILL所在目录下的 `references/code-understanding.md`（Phase 4 完整执行指令：CodeBase 工具调用策略、建议优先级、三状态判断、回退工具表、read 验证要求）。
绝对路径 = config_dir / 'skills/core-design/references/code-understanding.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/code-understanding.md loaded"。
<!-- /GATE:REF -->

### Phase 5: Read Similar Changes Reference [可配置: read_similar]

> 本步骤为可配置步骤。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=read_similar`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行（读取相似需求参考归档）
> - **执行计划不含本步骤** → 直接进入 Phase 6（指令文件不加载，内容不进上下文）
>
> **执行位置**：Phase 4（代码理解）之后、Phase 6（读取 brainstorming design.md）之前执行。。

### Phase 6: 读取 brainstorming 生成的 design.md

**动作**：读取 `docs/changes/<change-name>/.brainstorming_output` 元数据文件，解析 `design_doc_path` 字段获取 design.md 路径并读取内容，供 Phase 8 生成 delta_design.md 参考。元数据文件不存在说明 brainstorming 未执行，跳过本步骤。design.md 实际清理在 Phase 11 执行。

**确认延迟的实现层面问题**（仅多仓）：
- **单仓** → 跳过（单仓无 impl_questions_for_design.json）
- **多仓** → 按 references/multi-repo.md M-2 步骤3执行（读取 impl_questions_for_design.json，逐条让用户确认实现层面延迟问题的设计方向）

### Phase 7: Prepare Existing Experience Context [可配置: expert_experience]

> 本步骤为可配置步骤。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=expert_experience`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行（准备已有的项目级设计经验与后续云见 CLI 查找上下文）
> - **执行计划不含本步骤** → 直接进入 Phase 8（指令文件不加载，内容不进上下文）
>
> **执行位置**：Phase 6（读取 brainstorming design.md）之后、Phase 8（生成设计文档）之前执行。

### Phase 8: Generate Artifacts (必须填充)

**【多仓分支】**：
- **单仓** → 继续本 Phase 的单仓生成流程（下方 GATE:REF）
<!-- GATE:REF references/artifact-generation.md -->
**MANDATORY GATE**: 单仓生成设计文档前必须先 Read 本SKILL所在目录下的 `references/artifact-generation.md`（Phase 8 完整执行指令：测试策略读取、参考文档读取、模板占位符填充、填充注意事项、生成脚本命令）。
绝对路径 = config_dir / 'skills/core-design/references/artifact-generation.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/artifact-generation.md loaded"。
<!-- /GATE:REF -->

- **多仓** → 先执行 GATE 加载 multi-repo.md，再按 references/multi-repo.md M-2 执行（替代本 Phase 的单仓生成）
<!-- GATE:REF references/multi-repo.md -->
**MANDATORY GATE (仅多仓)**: 多仓环境必须先 Read 本SKILL所在目录下的 `references/multi-repo.md`。
绝对路径 = config_dir / 'skills/core-design/references/multi-repo.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止降级为单仓执行。
**【强制】如果Read工具返回文件不存在**：
1. 立即停止当前执行
2. 告知用户："GATE文件 references/multi-repo.md 未找到。多仓环境无法继续。请确认skill已正确安装。"
3. 等待用户指示，**禁止自行决定继续执行**
读取后输出: "GATE PASSED: references/multi-repo.md loaded"。
<!-- /GATE:REF -->

**多仓模式**：本 Phase 的单仓文档生成由 M-2 替代；Phase 9~11 仍正常执行。

### 任务形成后：查找与关联 Skill / 经验（单仓和多仓均执行）

在 Phase 8 或多仓 M-2 中先形成任务，再按本 Skill 的「Skill 与经验消费规则」执行 SDD 路径：Agent 按任务判断业务 / 通用能力，通过云见 CLI 准备候选，按任务组批量请用户确认，再按名称去重下载、原子替换 .codeagent/skills/<name>/，最后回写该任务的 Skill 字段。根据实际选用内容完善相关设计，再进入 Phase 9 / M-3a。

本动作属于任务生成流程，不受 `expert_experience` 或自定义编排点开关控制；该开关仅控制 Phase 7 的已有设计经验准备。完整确认、去重及回写步骤见 references/tasks-md-guidance.md。多仓执行者读取本 Skill 的消费规则并返回候选，由主会话汇总确认后按锁定结果更新本仓；未匹配或获取失败时说明并继续原任务。

### Phase 9: 设计追溯验证（强制）[可配置: design_traceability]

> 本步骤为可配置步骤。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=design_traceability`（type=built_in）条目** → 本步骤强制不可跳过，按以下模式执行（单仓读取 `ref_file.single` 指令文件 / 多仓读取 `ref_file.multi` 指令文件并执行 M-3a）
> - **执行计划不含本步骤** → 本步骤整体跳过，**Phase 9→10 衔接豁免**（不检查"已通过 Agent tool 启动子代理"），直接进入 Phase 10
> - 多仓模式：`design_traceability` 关闭 → M-3a 整体跳过，M-3a 的必经关卡/禁止主会话/ERROR 禁止推迟强制位同步豁免（见 references/multi-repo.md）

### Phase 10: design-doc-reviewer 审查 [可配置: design_review]

> 本步骤为可配置步骤。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=design_review`（type=built_in）条目** → 本步骤强制不可跳过，按以下模式执行（单仓读取 `ref_file.single` 指令文件 / 多仓读取 `ref_file.multi` 指令文件并执行 M-3b）
> - **执行计划不含本步骤** → 本步骤整体跳过，**Phase 10→11 衔接豁免**（不检查"已通过 Agent tool 启动子代理"），直接进入 Phase 11
> - 多仓模式：`design_review` 关闭 → M-3b 整体跳过，M-3b 的必经关卡/禁止主会话/ERROR 禁止推迟强制位同步豁免（见 references/multi-repo.md）
> - **`design_traceability` 关闭但 `design_review` 开启时**：M-2 完成后直接进入 M-3b，"M-3a 全过后才执行 M-3b"依赖随 `design_traceability` 关闭豁免

### Phase 11: 清理临时文件 [可配置: cleanup]

> 本步骤为可配置步骤。执行与否以构建执行计划持久化的 execution-plan-core-design.json 为准：
> - **执行计划 steps 数组含 `config_key=cleanup`（type=built_in）条目** → 本步骤强制不可跳过（core-design 流程最后一步），按以下模式执行（单仓读取 `ref_file.single` 指令文件 / 多仓读取 `ref_file.multi` 指令文件并执行多仓清理）
> - **执行计划不含本步骤** → 本步骤整体跳过，**必须显式记录"cleanup 已关闭，临时文件残留"后输出执行总结并宣布"core-design 流程执行完毕"** — 关闭时残留文件由用户或后续人工处理，不阻断流程收尾
> - 多仓模式：`cleanup` 关闭 → 跳过双层清理（项目级 + 各仓级），临时文件残留

## Schema Reference

The design-phase artifacts are defined in `core-schemas/spec-driven/schema.yaml`:

| Artifact ID | generates | Description | Requires |
|-------------|-----------|-------------|----------|
| delta_design | delta_design.md | Technical design | proposal, delta_spec |
| tasks | tasks.md | Implementation tasks | delta_spec, delta_design |
| delta_test_design | delta_test_design.md | Test design | proposal, delta_spec, delta_design |

## `language-specific design specifications` resolved in Step 3 Structure

```
{
  "python": "### 可读性与可维护性\n- 使用具有明确含义的标识符\n- 公共函数必须编写 Docstring\n",
  "cpp": "### 特殊成员函数\n- 类成员变量必须显式初始化\n- 单参数构造函数声明为 explicit\n # Cpp规范"
}
```

## Modes

| Mode | Behavior |
|------|----------|
| `--step` | Create one artifact at a time, pause after each |
| `--quick` | Create all design artifacts without pausing |

## Output On Success

```
## Design Artifacts Generated

**Change:** <change-name>
**Schema:** spec-driven
**Artifacts (Design Phase only):**
  ✓ delta_design.md (已填充 - 包含 `language-specific design specifications` 约束；经验按实际可用情况使用)
  ✓ delta_test_design.md (已填充)
  ✓ tasks.md (已填充，checkbox格式 verified)

### Prerequisites Met
- proposal.md: ✓ (from explore)
- delta_spec.md: ✓ (from explore)

### Phase Execution Results
- Phase 3 (Gather Context): ✓
- Phase 4 (Code Understanding): ✓
- Phase 5 (Similar Changes): ✓ (if references exist)
- Phase 6 (Brainstorming Output): ✓ (if exists)
- Phase 7 (Existing Experience Context): <已准备 / 无可复用经验 / 已关闭>
- Phase 8 (Task Capabilities): <批量确认结果；用户指定 / Agent 自选 / 不使用；安装及 Skill 字段回写结果>
- Phase 8 (Generate Artifacts): ✓ (已执行内容填充，已对照 design-principles.md + design-views.md)
- Phase 9 (设计追溯验证): ✓ (cross-doc-checker L2/L3)
- Phase 10 (design-doc-reviewer 审查): ✓

### `language-specific design specifications` Rule Integration
- Rule content fetched in Step 3: ✓
- Skill instructions extracted: ✓
- Injected into delta_design.md: ✓

### Task Capability Integration
- Capability query derived from tasks: <实际结果>
- Skill / experience fetched via 云见 CLI: <实际结果，允许未选用或失败>
- tasks.md associations and design integration: <实际结果>

### Content Filling Status
- delta_spec.md content referenced: ✓
- `language-specific design specifications` constraints included: ✓
- Template placeholders filled: ✓ (无未填充占位符)

Ready for implementation. Run /core-apply <change-name>
```

## Important Notes

- **Design phase only**: core-design does NOT generate proposal.md or delta_spec.md
- **Schema-driven**: All artifact filenames and formats are defined in schema.yaml
- **`language-specific design specifications` integration**: Automatically reads and injects these constraints fetched in step 3.
- **Skill 与经验**: 任务形成后通过云见 CLI 查找候选，按任务组批量确认后获取并回写 tasks.md 的 Skill 字段；已有项目经验可辅助设计
- **Similar Changes**: Reads referenced similar changes for design patterns
- **tasks.md NOT task.md**: The schema defines artifact ID `tasks` which generates `tasks.md` (plural)
- **Checkbox format**: The schema requires checkbox format (`- [ ]`) for tasks
- **Verification required**: Always verify generated artifacts match schema expectations
- **Design anchors**: Use `anchor_extractor.py` to automatically extract design anchors for tasks from delta_design.md metadata
