---
name: core-design
description: Design document generation - reads delta_spec.md from explore phase from docs, fetch rule lists and request for relevant rules, generates design artifacts based on schema definitions with expert experience integration
license: MIT
compatibility: Works without npm - uses Python scripts with schema-driven generation
metadata:
  author: corespec
  version: "4.3"
  generatedBy: "manual"
---

Design document generation for a change.

**Note**: This skill generates ONLY design-phase artifacts. The proposal and delta_spec are generated in the explore phase.

## Input

- Change name (kebab-case)
- `docs/relationship.md` - 多仓库依赖关系，理解设计涉及的跨仓库调用链
- Optional: `--step` for step mode, `--quick` for quick mode
- Optional: `--query` for expert experience keywords

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

**Step 0: Version Check (MANDATORY - Must be the FIRST phase in your execution plan)**

When creating your execution plan, you MUST include version check as the first phase (before all other phases). Do NOT execute it separately before planning — include it IN the plan. Execute the command below as the first action of the first phase.

```bash
python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'check','--json'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
```

**If the JSON output shows `"upgrade_available": true`**, you **MUST** use **AskUserQuestion tool** with the EXACT structure below. Do NOT modify the options, labels, or descriptions — use them exactly as specified:

```
AskUserQuestion({
  questions: [{
    question: "CoreSpec 有新版本可更新。本地版本: <local_version_update_time>, 远端最新发布: <remote_version_update_time>。请选择操作：",
    header: "版本升级",
    options: [
      { label: "Upgrade", description: "下载并安装新版本（立即在后台执行，重启后生效）" },
      { label: "Skip 24h", description: "跳过本次升级提示，24小时内不再提醒" },
      { label: "Continue", description: "忽略升级，继续执行当前流程" }
    ]
  }]
})
```

Based on user's choice:
- If Upgrade: run the command below. The installer runs in background. Then **IMMEDIATELY proceed to next step** — do NOT wait for the installer to finish, do NOT ask the user to restart now. Simply note: "升级已在后台启动，安装完成后请重启 CodeAgent。"
  ```bash
  python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'upgrade'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
  ```
- If Skip: run the command below, replacing `<REMOTE_TIME>` with the `remote_version_update_time` value from the check output, then proceed to next step:
  ```bash
  python -c "import sys,subprocess;from pathlib import Path;d=Path.home()/'.config/opencode/skills/core-shared/scripts';d2=Path.home()/'.cac/skills/core-shared/scripts';s=d if d.exists() else d2;r=subprocess.run([sys.executable,str(s/'version_check.py'),'skip','--hours','24','--create-time','<REMOTE_TIME>'],encoding='utf-8',capture_output=True,text=True);print(r.stdout.strip());sys.exit(r.returncode)"
  ```
- If Continue: proceed to next step directly

**If the JSON output shows `"upgrade_available": false`**, or the command fails, proceed to next step directly.

**IMPORTANT**: The workflow ALWAYS continues to next step after this step, regardless of which option the user chose. Do NOT stop or wait for restart.

## Artifact Scope

| Phase | Artifacts Generated | Input Required |
|-------|---------------------|----------------|
| **Explore** (`/core-explore`) | proposal.md, delta_spec.md | Requirement ID |
| **Design** (`/core-design`) | delta_design.md, delta_test_design.md, tasks.md | delta_spec.md (from explore) |

## Multi-Language Rule Fetching

### Step 1: 获取各语言相关规范目录树

**【强制要求】**：不许自作主张合并多种语言目录，必须保持多语言独立文件

首先调用 `code-rule-tree` skill 生成规范目录树：
 ```
 python skills/code-rule-tree/scripts/get_tree.py
 ```

该脚本会将结果保存到 `docs/rule_index.md`。读取该文件，按语言分隔解析出规范目录树。例如 `docs/rule_index.md` 内容为：
 ```json
 {
     "python": [
       "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
       "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程",
       "华为 CleanCode Python 核心原则/规则级别",
       "云核心网产品工程与IT装备部Python规范"
       ],
   "cpp": [],
   ...
 }
 ```

### Step 2: 挑选 Design 相关的目录名称
根据 Step 1 从 `docs/rule_index.md` 读取的规范目录树，识别 **业务实现规范** 目录条目：

**筛选过程分为两步**：
1. 根据当前需求涉及的编程语言，只处理对应语言下的目录条目。 
2. 从对应语言的目录中，挑选与`业务实现规范`相关的目录。


**优先级规则**
第一优先级：`业务实现规范`
- 只要有 `业务实现规范` 相关目录（如：`业务实现规范/项目结构/父项目结构`），全量拉取 该类别下的所有目录。
- 业务实现规范涵盖需求落地、业务功能实现、业务流程设计等与业务直接相关的规范。

第二优先级：Design 通用规范（仅当没有业务实现规范时）
- 如果对应语言下 没有 `业务实现规范` 目录，则参考 Design 通用规范目录名拉取 design 相关规范：
  - 核心设计原则 
  - 架构与模块设计 
  - 职责划分与边界设计 
  - 接口与依赖设计 
  - 数据模型与数据结构设计 
  - 异常处理策略 
  - 安全性与防御式设计 
  - 并发、性能与资源管理设计 
  - 可读性、可维护性与可扩展性 
  - 兼容性与演进设计

**【强制要求】**
- 不得选择当前需求未涉及语言的规范目录。 
- 不得将不同语言的目录合并到同一列表中。 
- 必须保持以语言为维度的独立目录列表。
- 不选择仅适用于具体代码实现、语法细节、编码格式、代码生成或局部实现检查的目录。 
- 必须从 Step 1 返回的原始目录条目中选择，不得自行编造、改写或补充目录名称。 
- 目录名称必须完整保留，不得只传递末级目录名称。 
- 若某种相关语言下没有合适的 Design 规范目录（既无业务实现规范，也无上述 Design 通用规范），则该语言对应的目录列表返回空数组。

以下类型通常不属于本步骤的筛选范围：
- 具体语法规则 
- 命名格式细则 
- 缩进、空格、换行等代码风格 
- 单条 API 的具体调用方式 
- 某个函数或代码片段的实现规则 
- 代码生成、代码补全或代码改写细节 
- 仅在 Coding 阶段才能判断的局部代码问题

例如，`docs/rule_index.md` 内容包含：
```markdown

{
  "python": [
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程",
    "华为 CleanCode Python 核心原则/规则级别",
    "云核心网产品工程与IT装备部Python规范/编码风格/命名规则"
  ],
  "cpp": [
    "华为 CleanCode C++ 核心原则/架构与模块设计",
    "华为 CleanCode C++ 编码规范/格式与排版"
  ]
}
```

假设当前需求仅涉及 Python，则筛选结果可以是：
```json
{
  "python": [
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程"
  ]
}
```
不得选择：

```
华为 CleanCode Python 核心原则/规则级别
云核心网产品工程与IT装备部Python规范/编码风格/命名规则
```

因为这些目录与当前 Design 阶段的方案设计关联较弱，或更适合后续 Coding、Code Review 阶段。

### Step 3: 整合多语言 规范
将 Step 2 筛选出的目录，以json格式，按照语言分别传递给 `code-rule-content` skill，获取对应规范内容。

Invoke `code-rule-content` skill:

输入必须保持多语言独立，例如：
```json
{
  "python": [
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程"
  ],
  "cpp": [
    "华为 CleanCode C++ 核心原则/架构与模块设计"
  ]
}
```

**【强制要求】**

- 每种语言只传递该语言对应的目录。
- 不得将 Python、Java、C++ 等不同语言目录混合传递。
- 不得传递空目录、缩写目录或自行推测的目录。
- 必须使用 Step 2 返回的目录名称。

`code-rule-content` 返回结果统一按语言组织，例如：
```json
{
  "python": "### 可读性与可维护性\n- 使用具有明确含义的标识符\n- 公共函数必须编写 Docstring\n",
  "cpp": "### 特殊成员函数\n- 类成员变量必须显式初始化\n- 单参数构造函数声明为 explicit\n # Cpp规范"
}
```
Agent 必须统一理解为：
> 当前需求的**语言级 Design 规范集合（`language-specific design specifications`）**。


### Step 3 Output

Step 3 完成后，将得到当前需求唯一使用的 Design 规范集合，例如：

```json
{
  "python": "...markdown...",
  "cpp": "......."
}
```

后续所有设计阶段均直接使用该结果。

**【强制要求】**

后续流程：
- 不再重新调用 `code-rule-tree`
- 不再重新调用 `code-rule-content`
- 不再重新读取任何 `*-rule.md`
- 不再重新筛选规范目录

Step 3 返回的规范集合是 Design 阶段唯一的语言规范来源（Single Source of Truth）。

During design artifact generation, the system:
1. Reads `delta_spec.md`
2. Reads the `language-specific design specifications` resolved in **Step 3**
3. Reads global design/spec documents
4. Reads similar change references
5. Reads expert experience (if available)
6. Injects the relevant specification constraints into:
   - `delta_design.md`
   - `tasks.md`
   - `delta_test_design.md`

**【强制要求】**

- 仅使用当前需求涉及语言的规范。
- 不得跨语言应用规范。
- 规范必须结合当前需求进行应用，不得机械复制全文。
- Design 阶段只应用与设计相关的规范；Coding、Code Review 等阶段规则不得提前注入设计文档。


## Execution Flow

> **编号规则**：Phase 1~12 连续编号，与 steps.md 序号一一对应。无 0/0.5/1.5 等非整数编号。

### Phase 1: Version Check (MANDATORY — 必须为第一个 Phase 的第一个动作)

详见本文档 **Step 0: Version Check** 章节。在 plan 的第一个 Phase 中执行。

### Phase 2: Fetch Design Rules + 加载设计原则与视图约束

#### 2.1 多语言规范获取

即本文档 **Multi-Language Rule Fetching** 章节（Step 1~3）。完成后得到 `language-specific design specifications`。

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

Before generating design documents, SKILL layer must gather context:

1. **Read `docs/changes/<change-name>/delta_spec.md`** - Requirement delta (MUST)
   - This is the frozen specification from explore phase
   - Contains ADDED/MODIFIED/REMOVED requirements

2. **Read `language-specific design specifications` resolved in Step 3** - Design stage specification constraints (multi-language)
   - Company, product_line, pdu, department, team specs
   - Must ensure design complies with these rules
   - If `language-specific design specifications` contain skill usage descriptions (e.g., "Use /huawei-cleancode-java to query CleanCode rules"), include them in delta_design.md

3. **【必须】Read Global Spec and Design Documents** - 全局视角上下文

   **判断环境类型（第一步）**：
   - 读取 `docs/relationship.md` 检查是否为多仓环境
   - 如果是**单仓环境**：继续读取根目录全局文档
   - 如果是**多仓环境**：详见 references/multi-repo.md M-1/M-2

   **【单仓环境】全局文档读取**：
    | 优先级 | 文档 | 路径 | 用途 |
    |--------|------|------|------|
    | P0 | 项目级 spec.md | `docs/specs/spec.md` | 了解全局规格，全局功能划分，与其他模块的关系 |
    | P0 | 项目级 design.md | `docs/specs/design.md` | 了解全局架构、技术选型、模块依赖关系 |
    | P0 | 多仓库依赖关系 | `docs/relationship.md` | 了解各子仓库间的依赖关系和调用链（由 core-init 生成） |
    | P0 | 多仓环境说明 | `proposal.md` 第6节 | 校验 explore 阶段确认的仓库范围、实现顺序、接口契约 |
    | P1 | 相关模块级 design.md | `docs/specs/<module-name>/design.md` | 了解受影响模块的设计细节 |
    | P1 | 相关模块级 spec.md | `docs/specs/<module-name>/spec.md` | 了解受影响模块的接口和约束 |

   **【多仓环境】子仓文档读取和校验**：详见 references/multi-repo.md M-2（各仓按仓生成中的文档读取与校验）

   **读取策略**：
   - 如果 `docs/specs/` 目录不存在或全局文档为空，则跳过
   - 如果全局文档存在，**必须**读取后再进行设计
   - 根据 delta_spec.md 中识别的"受影响模块"，选择性读取对应模块的文档

   **全局文档的作用**：
   - **设计一致性**：确保 delta_design.md 与全局架构保持一致
   - **技术选型参考**：参照项目级 design.md 的技术栈进行选型
   - **避免重复设计**：了解现有模块能力，避免重复造轮子
   - **接口兼容性**：确保新设计与现有模块接口兼容
   - **术语约束**：delta_design.md 中所有术语必须与 spec.md "领域术语"保持一致；如需引入新术语，必须同时更新 spec.md "领域术语"章节
   - **决策约束**：设计必须遵守 design.md "设计决策"中已有记录；如设计需要推翻已有决策，必须在 delta_design.md 的"设计决策"章节显式标注推翻理由

### Phase 4: 代码理解（Agent 决策）

**重要说明**：
- CodeBase 工具是 Agent 内置能力，具体可用性需尝试调用判断
- 目标代码需要提前在 CodeBase 平台构建才有数据
- 具体调用方式由 Agent 自行判断，SKILL.md 只提供建议
- **统一尝试调用**：无论 OpenCode 还是 ClaudeCode，都应先尝试调用
- **回退策略**：CodeBase 不可用或无结果时，必须回退到 read/grep/glob

**Agent 执行逻辑**：

#### 4.1 尝试调用 CodeBase 工具

**统一尝试调用策略**：
- 无论 OpenCode 还是 ClaudeCode，都**先尝试调用** CodeBase 工具
- 根据调用结果判断是否可用：**能获取到有效数据视为可用，否则视为不可用**
- 这样可以兼容后续 ClaudeCode 可能支持 CodeBase 的情况

**调用示例**（具体调用方式由 Agent 自行判断）：
- 尝试调用 `CodeSemanticSearch` 进行语义搜索
- 尝试调用 `GetFeatureTree` 获取项目结构
- 如果返回有效结果 → 继续使用
- 如果返回空结果或报错 → 回退到 read/grep/glob

#### 4.2 尝试使用 CodeBase 工具（如果可用）

**建议优先级**：

1. **GetFeatureTree** — 获取项目功能结构
   - 参数：label_detailed=true, description_detailed=true
   - 目的：了解项目的模块划分和接口层级

2. **CodeSemanticSearch** — 语义搜索核心功能
   - 参数：query="需求核心功能描述（英文）"
   - 目的：快速定位核心实现文件

3. **ComprehensiveSearch** — 理解业务调用链
   - 参数：codeQuery="功能锚点", chainQuery="业务主流程"
   - 目的：获取完整的业务调用路径

4. **GetRemoteCallChain** — 追溯关键方法调用链
   - 参数：file_path="关键文件", method_name="核心方法", depth=2
   - 目的：理解设计决策的上下游影响

**三状态判断**：
| 状态 | 条件 | 动作 |
|------|------|------|
| present | CodeBase 可用且有数据 | 使用 CodeBase 结果 |
| missing | CodeBase 可用但无数据 | 回退到 read/grep/glob |
| not_installed | CodeBase 工具不可用 | 直接使用 read/grep/glob |

#### 4.3 回退到传统工具（必须）

**当 CodeBase 不可用或无结果时，使用以下替代**：

| CodeBase 工具 | 降级替代工具 | 使用方式 |
|---------------|--------------|----------|
| GetFeatureTree | glob + grep | `glob "**/*.{py,java,ts}"` + 分析模块结构 |
| CodeSemanticSearch | grep | `grep -r "关键词" --include="*.py"` |
| ComprehensiveSearch | grep + read | grep 定位 + read 理解调用链 |
| GetRemoteCallChain | grep + read | 多轮 grep 追溯调用关系 |

#### 4.4 必须通过 read 验证

**验证要求**：
- 无论使用哪种工具，**最终必须通过 read 实际读取代码进行验证**
- CodeBase 只是辅助定位，不能替代实际代码阅读
- 验证 CodeBase 定位的文件是否确实与设计相关
- 补充 CodeBase 可能遗漏的边界情况

---

### Phase 5: Read Similar Changes Reference

**IMPORTANT**: This phase references similar changes from the same requirements area to learn from past designs.

1. Read `docs/changes/<change-name>/delta_spec.md`
2. Check for "Similar Requirements Reference" section
3. If exists: Read referenced similar changes' files:
   - **归档目录下的引用**（由 core-explore 打分筛选后写入）：读取归档路径下的 `delta_design.md`（技术方案参考）和 `delta_spec.md`（需求变更参考）

**Similar Changes Reference Format**:
```markdown
## Similar Requirements Reference

- [版本/日期-需求名](归档路径): 简要说明相似点
- [Change-Name-1]: Description of similarity
```

**归档引用解析规则**：
- 引用中包含路径（如 `docs/archive/...`）→ 按路径读取归档目录下的 `delta_design.md` 和 `delta_spec.md`
- **单仓环境**：路径直接指向当前项目 `docs/archive/`
- **多仓环境**：详见 references/multi-repo.md M-2（各仓归档引用解析规则）

### Phase 6: 读取 brainstorming 生成的 design.md

**IMPORTANT**: 当brainstorming技能在core-explore阶段执行后，会生成design.md并通过`.brainstorming_output`元数据文件记录路径

1. **检查brainstorming输出**：
   - 读取 `docs/changes/<change-name>/.brainstorming_output` 元数据文件
   - 如果文件存在，解析其中的 `design_doc_path` 字段获取design.md路径

2. **读取design.md内容**：
   - 如果`.brainstorming_output`存在，读取对应的design.md文件
   - 将design.md内容用于生成delta_design.md的参考

3. **元数据文件格式**：
   ```json
   {
     "version": "1.0",
     "requirement_id": "<ID>",
     "design_doc_path": "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md",
     "generated_at": "<ISO时间>",
     "source": "brainstorming-skill"
   }
   ```

4. **读取后的处理**：
   - design.md内容读取后暂存于内存，供后续阶段使用
   - design.md的实际清理在Phase 11执行

5. **确认延迟的实现层面问题**（仅多仓）：
   - **单仓** → 跳过（单仓无impl_questions_for_design.json）
   - **多仓** → 按references/multi-repo.md M-2步骤3执行（读取impl_questions_for_design.json，逐条让用户确认实现层面延迟问题的设计方向）

### Phase 7: Fetch Expert Experience

**IMPORTANT**: This phase fetches expert knowledge to assist with design decisions.

**脚本路径获取方式**（与 core_paths.py 路径解析一致）：
- 优先使用 `OPENCODE_CONFIG` 环境变量
- 回退到 `~/.config/opencode` (OpenCode) 或 `~/.cac` (ClaudeCode)

调用 paradigm-exp-use skill 获取专家知识：

```bash
# Dynamic path resolution (supports both OpenCode and ClaudeCode)
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([
    sys.executable,
    config_dir / 'skills' / 'paradigm-exp-use' / 'scripts' / 'fetch_experiences.py',
    '<query>', 'expert_experience.md'
])
sys.exit(result.returncode)
"
```

**Save Location**: `docs/changes/<change-name>/expert_experience.md`

**Query Strategy**:
- If `--query` provided: use user-specified keywords
- If no `--query`: derive keywords from:
  - "Similar Requirements Reference" in delta_spec.md
  - Core requirements from delta_spec.md
  - Use those changes' design patterns as search queries

**Expert Experience Integration**:
- Expert knowledge saved to `expert_experience.md`
- Read and inject into `delta_design.md` design decisions section
- Used for technical approach and technology selection guidance

**After using expert experience** (Phase 8 完成后):
1. Delete `expert_experience.md` to keep the change directory clean
2. Clean up workflow directory if it exists:
   ```python
   import shutil
   from pathlib import Path
   workflow_dir = Path(project_root) / 'workflow'
   if workflow_dir.exists():
       shutil.rmtree(workflow_dir)
   ```

### Phase 8: Generate Artifacts (必须填充)

**【多仓分支】**：
- **单仓** → 继续本 Phase 的单仓生成流程
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

---

**单仓生成流程**：

Python 脚本生成模板后，**Agent 必须执行内容填充**：

#### 8.1 读取参考文档
生成模板后，Agent 必须读取以下参考文档进行填充：

| 优先级 | 文档 | 路径 | 用途 |
|--------|------|------|------|
| P0 | delta_spec.md | `docs/changes/<change-name>/delta_spec.md` | 提取需求内容 (ADDED/MODIFIED/REMOVED) |
| P0 | 项目级 design.md | `docs/specs/design.md` | 提取全局架构设计和技术选型 |
| P0 | 相关模块级 design.md | `docs/specs/<module-name>/design.md` | 提取受影响模块的设计细节 |
| P1 | 项目级 spec.md | `docs/specs/spec.md` | 提取全局规格说明和模块关系 |
| P2 | expert_experience.md | `docs/changes/<change-name>/expert_experience.md` | 提取专家经验 |

#### 8.2 填充模板占位符
根据参考文档内容，替换模板中的占位符：

**语言一致性要求**：
- **必须使用与 delta_spec.md 相同的语言填充**
- 如果 delta_spec.md 是中文，则 tasks.md 中的任务描述、验收标准等**必须使用中文**
- 不要自行翻译或转换为英文

| 占位符 | 填充来源                                                                    | 必须对照的 reference | 示例 |
|--------|-------------------------------------------------------------------------|---------------------|------|
| `<变更名称>` | delta_spec.md 概述/背景                                                     | — | FST支持按namespace粒度部署HisecAgent框架 |
| `<设计目标>` | delta_spec.md 核心能力                                                      | — | 新增custom_selector部署模式 |
| `<受影响模块>` | delta_spec.md 影响分析                                                      | design-principles.md P-1 | paas-om, pcm, 前端 |
| `<原则1><原则2>` | delta_spec 约束 + design-principles.md P-1~P-10 选取与当前需求相关的原则 | design-principles.md | 架构一致性、入口出口明确 |
| `<技术选型>` | Phase 7 专家经验                                                            | design-principles.md P-7 | 优先使用项目现有技术栈 |
| `## 设计决策` 章节 | 注入 step3返回的规范集合： `language-specific design specifications` + Phase 7 专家经验 | design-principles.md P-3, P-4 | — |
| 3.1 核心模块设计 | delta_spec + 代码理解 + design-principles.md | design-principles.md P-1, P-2, P-6; design-views.md §1 | 类图必须产出 |
| 6.1 核心流程设计 | delta_spec + 代码理解 | design-views.md §1 | 时序图必须产出（含异常路径） |
| 2.1 整体架构 | 全局 design.md | design-principles.md P-1; design-views.md §1 | 架构图必须产出 |
| 2.2 模块划分 | 全局 design.md | design-principles.md P-1, P-7; design-views.md §1 | 模块依赖图必须产出 |

#### 8.3 填充注意事项

以下要点在填充时应注意遵循，减少后续审核（Phase 9 cross-doc-checker + Phase 10 design-doc-reviewer）的修复轮次：

1. 不保留未填充的占位符 `<...>` — Phase 10 CHECK-R7.3 会检测截断/占位符
2. 需求引用应包含 delta_spec.md 的具体需求内容 — Phase 9 CHECK-R11-L2 会验证 spec→design 追溯
3. 规范约束应包含 step3 返回的 `language-specific design specifications` — Phase 10 CHECK-R7.1 会检查章节完整性
4. tasks.md 使用 checkbox 格式 `- [ ]` — Phase 10 CHECK-R7.5c 会验证 tasks-delta_design 一致性
5. 每个代码生成任务应包含 `设计锚点` 字段 — Phase 9 CHECK-R11-L3 会验证 design→tasks 追溯
6. 1.2 设计原则章节应包含 design-principles.md 中与当前需求相关的原则 — Phase 10 CHECK-R12.1 会验证视图完整性
7. design-views.md §1 必须视图应全部产出，§2 条件视图按触发条件产出 — Phase 10 CHECK-R12.1 会验证视图完整性

#### 8.4 tasks.md 填充特别指导

**重要**：tasks.md 必须按照以下结构组织：

**【多仓模式】tasks.md 仅包含"代码生成任务"章节（即下方 1.x 任务），不包含"Code Review 任务"和"单元测试任务"章节。原因：多仓模式下Code Review和UT由core-apply M-4/M-5子代理按仓独立执行，不由tasks.md驱动。包含这些任务会导致：status脚本误判blocked、完成率虚低、M-2子代理执行越界。**

```markdown
## 代码生成任务

- [ ] 1.1 <任务描述>
  - **编程语言**: <java/cpp/go/python/javascript/typescript/other>
  - **关联需求**: <需求ID>
  - **验收标准**: <完成标准>
  - **设计锚点**: <#3.1 #2.2 #1.1:约束 #1.2:证据驱动>  # 自动提取/手动填写

## Code Review 任务

> 代码生成完成后进行规范检查（所有语言）和内存安全检查（C/C++、Java、Python、Go）。

### 3.1 规范检查（所有语言）

> 调用 codecheck-for-cleancode 技能进行编码规范检查与修复。**执行前必须先验证 CodeCheckCLI 是否已安装，未安装则按 skill 兜底策略自动安装，安装失败则分析失败原因并反馈用户，严禁跳过。**

- [ ] 2.1 代码规范检查与修复
  - **编程语言**: <java/cpp/go/python/javascript/typescript/other>
  - **检视技能**: codecheck-for-cleancode
  - **依赖任务**: 1.1
  - **验收标准**: 规范检查完成，告警已全部修复，所有中间文件（含 `.codecheckcli/` 目录）已删除

### 3.2 内存安全检查（C/C++、Java、Python、Go）

> 调用 cwd-audit 技能检测内存安全和资源管理问题，检测出问题后直接修复（所有语言）

- [ ] 2.2 代码内存安全检查与修复
  - **编程语言**: <cpp/c/java/python/go>
  - **检视技能**: cwd-audit
  - **依赖任务**: 2.1
  - **验收标准**: 内存安全检查完成，问题已修复或标记 blocked

## 单元测试任务

> 所有 UT 生成任务按环节分组，每个环节内的任务可以并行执行，环节之间必须按顺序执行。
> **重要**: UT生成前必须先读取 `delta_test_design.md`，根据其中定义的测试用例（TCxxx）生成对应的UT代码。
> **注意**: C/C++/Java/Python/Go 语言在规范检查后有内存安全检查+修复环节（任务 2.2），检测到问题后直接修复；其他语言规范检查（2.1）完成后直接进入 UT 生成。

### 4.1 UT生成

- [ ] 3.1 为 1.1 生成UT
  - **编程语言**: <java/cpp/go/python/javascript/typescript/other>
  - **UT生成技能**: <generate-java-ut/c-cpp-dt/go-ut/test-driven-development>
  - **依赖任务**: 1.1, 2.1 (C/C++/Java/Python/Go 需 2.2 完成)
  - **覆盖用例**: <TC001, TC002, ...（来自delta_test_design.md）>
  - **验收标准**: 生成的UT必须覆盖delta_test_design.md中定义的所有测试用例

### 4.2 UT修复

| 编程语言 | UT生成技能链路 |
|----------|----------------|
| java | `fix-java-ut` |
| cpp/c/c++ | `c-cpp-dt-autofix` |
| go | `go-ut-compilation-execution-fixing` |
| python/javascript/typescript/other | 无此环节（跳过） |

- [ ] 4.1 修复 3.1 的UT
  - **编程语言**: <java/cpp/go>
  - **UT生成技能**: <fix-java-ut/c-cpp-dt-autofix/go-ut-compilation-execution-fixing>
  - **依赖任务**: 3.1
  - **验收标准**: UT 编译通过，运行无错误

### 4.3 覆盖率提升 (仅Java)

- [ ] 5.1 提升 4.1 的覆盖率
  - **编程语言**: java
  - **UT生成技能**: improve-java-ut-coverage
  - **依赖任务**: 4.1
  - **验收标准**: 行覆盖率 ≥80%

### 4.4 断言审查 (仅Java)

- [ ] 6.1 审查 5.1 的断言有效性
  - **编程语言**: java
  - **UT生成技能**: java-assertion-validity-review
  - **依赖任务**: 5.1
  - **验收标准**: 断言符合规范

### 4.5 测试报告 (仅Java)

- [ ] 7.1 生成 6.1 的测试报告
  - **编程语言**: java
  - **UT生成技能**: java-test-report
  - **依赖任务**: 6.1
  - **验收标准**: 测试报告生成完成
```

**Code Review 技能 映射**：
| 编程语言 | 规范检查 | 内存安全检查 |
|----------|---------|-------------|
| cpp/c/c++/java/python/go | codecheck-for-cleancode | cwd-audit（检测+修复） |
| javascript/typescript/other | codecheck-for-cleancode | 跳过 |

**UT生成技能 映射**：
| 编程语言 | 环节1-UT生成 | 环节2-UT修复 | 环节3-覆盖率提升 | 环节4-断言审查 | 环节5-测试报告 |
|----------|-------------|-------------|-----------------|---------------|---------------|
| java | generate-java-ut | fix-java-ut | improve-java-ut-coverage | java-assertion-validity-review | java-test-report |
| cpp/c/c++ | c-cpp-dt | c-cpp-dt-autofix | - | - | - |
| go | go-ut | go-ut-compilation-execution-fixing | - | - | - |
| python/js/ts/other | test-driven-development | - | - | - | - |

**关键规则**：
- **必须先定义所有代码生成任务，再定义单元测试任务**
- **单元测试任务按环节分组：UT生成 → UT修复 → 覆盖率提升 → 断言审查 → 测试报告**
- **同一环节内的任务可以并行执行，环节之间必须按顺序执行**
- **每个环节的任务必须依赖上一环节对应的任务**

#### 8.5 设计锚点自动提取（推荐）

生成 tasks.md 时，**强烈推荐**自动提取设计锚点：

**锚点提取流程**：
1. 读取 `delta_design.md` 内容
2. 对于每个代码生成任务（1.1, 1.2, 2.1 等）：
   - 解析 delta_design.md 中的元数据注释 `<!-- tasks: [1.1, 2.1] -->`
   - 查找任务关联的章节锚点
   - 提取该章节的关联关键词（如约束、原则等）
3. 自动生成锚点字符串：`#3.1 #2.2 #1.1:约束 #1.2:证据驱动`

**锚点格式规范**：
| 锚点类型 | 格式 | 示例 |
|---------|------|------|
| 章节锚点 | `#X.X` | `#3.1` → 第3.1章详细设计 |
| 关键词锚点 | `#X.X:关键词` | `#1.1:约束` → 1.1节中"约束"相关内容 |
| 通配符锚点 | `#4.x:*` | `#4.x:审查` → 4.x节所有子章节中含"审查"的内容 |

**锚点优先级**：
| 优先级 | 锚点类型 | 说明 |
|--------|---------|------|
| P0 | `#3.x` 详细设计章节 | 必须参考，直接决定代码实现 |
| P0 | `#2.1` `#2.2` 架构锚点 | 必须参考，影响代码组织结构 |
| P1 | `#1.1:约束` 约束锚点 | 必须参考，避免违反非目标 |
| P1 | `#1.2:原则名` 原则锚点 | 必须参考，影响实现质量标准 |
| P2 | `#4.x:流程名` 流程锚点 | 建议参考，影响业务逻辑走向 |

**自动提取示例**：
```python
# 使用 anchor_extractor.py 自动提取
from anchor_extractor import extract_anchors_by_task

delta_design_path = "docs/changes/<change>/delta_design.md"
task_1_1_anchors = extract_anchors_by_task(delta_design_path, "1.1")
# 返回: ['#3.1', '#2.2', '#1.1:约束', '#1.2:证据驱动', '#1.2:不信任']

# 在 tasks.md 中填入
- [ ] 1.1 开发 explore-doc-reviewer Skill
  - **设计锚点**: #3.1 #2.2 #1.1:约束 #1.2:证据驱动 #1.2:不信任
```

After context is prepared, invoke the design generation:

```
For each artifact to generate:
- Read context files (delta_spec.md, `language-specific design specifications`, similar changes, Phase 7 expert experience context)
- Generate artifact with references to context
- Ensure `language-specific design specifications` skill usage instructions are included in delta_design.md
- Ensure expert experience is injected into design decisions
- **CRITICAL: Fill template placeholders with actual content before writing**
```

## Artifact Generation Scripts

The scripts in `scripts/` directory handle the actual generation:
With language-specific design specifications (from Step 3)

1. 先将 `language-specific design specifications` from step 3 生成临时json 文件 `temp_rule.json`
2. 将临时文件`temp_rule.json`的路径作为传参 `--design-rules {temp_rule.json}`

```bash
# Dynamic path resolution (supports both OpenCode and ClaudeCode)
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-design' / 'scripts' / 'main.py', 'continue', '--change', '<name>', '--step', '--design-rules', 'temp_rules.json'])
sys.exit(result.returncode)
"
```

**Example commands**:
```bash
# Quick mode: create all remaining artifacts
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-design' / 'scripts' / 'main.py', 'ff', '--change', '<name>', '--quick', '--design-rules', 'temp_rules.json'])
sys.exit(result.returncode)
"

# With expert experience query
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-design' / 'scripts' / 'main.py', 'ff', '--change', '<name>', '--query', '<keywords>', '--design-rules', '<temp_rule.json>'])
sys.exit(result.returncode)
"
```

The scripts:
1. Read from schema.yaml to get artifact templates
2. Inject expert knowledge into generated artifacts

### Phase 9: 设计追溯验证（强制）

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

生成 delta_design.md 和 tasks.md 后，**必须**通过子代理调用 `cross-doc-checker` 验证追溯链：

**【强制】必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用。Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑。

**设计追溯验证**：delta_spec → delta_design

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L2：
```
Skill tool: cross-doc-checker <change-name> --layer L2
```
- **验证内容**：delta_spec.md中的需求是否都有对应的delta_design.md设计
- **失败处理**：标记问题，上报用户具体失败原因

**L2自动修复循环（最多3轮）**：
1. 读取cross-doc-checker输出的findings列表
2. 按finding类型执行修复：
   - 【文档保真类】delta_spec需求未在delta_design中映射 → 在delta_design.md中补充该需求的设计章节和"对应需求"字段
   - 【文档保真类】截断/占位符 → 替换为具体内容
3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L2
4. 3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现FAIL后仅报告问题不修复

**任务覆盖验证**：tasks → delta_design + delta_test_design

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L3：
```
Skill tool: cross-doc-checker <change-name> --layer L3
```
- **验证内容**：delta_design.md中的设计模块是否都有对应的tasks.md任务
- **失败处理**：标记问题，上报用户具体失败原因

**L3自动修复循环（最多3轮）**：
1. 读取cross-doc-checker输出的findings列表
2. 按finding类型执行修复：
   - 【文档保真类】设计需求未在tasks中覆盖 → 在tasks.md中补充对应任务，填写"关联需求"字段
   - 【文档保真类】截断/占位符 → 替换为具体内容
3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L3
4. 3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现FAIL后仅报告问题不修复

**判断**：
- 验证通过 → 进入 Phase 10
- 验证失败 → 修复文档问题后重新验证（循环最多3次）

**主会话后处理**（子代理返回后执行）：
- 子代理返回验证通过 → 进入 Phase 10
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败 → 主会话直接调用 cross-doc-checker Skill 执行（降级策略）

**多仓模式**：Phase 9 按references/multi-repo.md M-3a使用subagent并行执行各仓L2/L3验证。**【强制】Phase 9必须调用cross-doc-checker，禁止调用design-doc-reviewer替代**。

### Phase 10: design-doc-reviewer 审查

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["design-doc-reviewer"]
**同步/异步**: sync

生成 delta_design.md、delta_test_design.md、tasks.md 后，**必须**通过子代理调用 `design-doc-reviewer` Skill 进行审查：

子代理使用 Skill tool 调用 `design-doc-reviewer`：
```
Skill tool: design-doc-reviewer <change-name>
```

**审查维度**：
| 维度 | 检测内容 | 严重级别 |
|------|----------|----------|
| 六维检测 | 可测试性/可维护性/可扩展性/安全性/可监控性/容错性 | ERROR |
| 九条宪法 | 简洁性/抽象性/单一职责/清晰结构/一致性/可读性/可验证性/最小依赖/增量更新 | WARNING |
| NEEDS CLARIFICATION限流 | 单文档标记不超过3个 | ERROR |

**判断**：审查通过 → 设计完成，可进入 /core-apply | 审查失败 → **必须自动修复**后重新审查（循环最多3次）

**自动修复循环（最多3轮）**：
1. 读取design-doc-reviewer输出的findings列表
2. 按finding类型执行修复：
   - 【文档保真类】必需章节缺失 → 补充缺失章节
   - 【文档保真类】截断/占位符 → 替换为具体内容
   - 【文档保真类】验收条件缺失 → 补充可判定的验收条件
   - 【文档保真类】越权决策/隐式越权 → 删除越权内容，返回主会话由主会话与用户确认
   - 【文档保真类】Q&A捏造 → 删除无交互记录对应的Q&A
   - 【实现一致性类】设计引用spec外模块 → 删除多余模块或在spec中补充需求
   - 【实现一致性类】设计模块无对应任务 → 在tasks.md中补充遗漏任务
   - 【实现一致性类】任务缺少必需字段 → 补充编程语言/关联需求/验收标准
   - 【用户意图类】NEEDS CLARIFICATION超标 → 返回主会话，由主会话与用户澄清
   - 【用户意图类】→ **禁止**自行修改文档掩盖问题，必须返回主会话由主会话与用户更新决策记录
3. 修复完成后，**必须重新调用** Skill tool: design-doc-reviewer <change-name>
4. 3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现FAIL后仅报告问题不修复

**主会话后处理**（子代理返回后执行）：
- 子代理返回审查通过 → 进入 Phase 11
- 子代理返回【用户意图类】finding → 主会话与用户交互澄清，完成后再次派发子代理执行审查
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败 → 主会话直接调用 design-doc-reviewer Skill 执行（降级策略）

**多仓模式**：Phase 10 按references/multi-repo.md M-3b使用subagent并行执行各仓design-doc-reviewer审查。**【强制】Phase 10必须调用design-doc-reviewer，禁止调用cross-doc-checker替代。M-3a(cross-doc-checker)必须全部通过后才能执行M-3b(design-doc-reviewer)**。

### Phase 11: 清理临时文件

**IMPORTANT**: 清理core-explore阶段保留的跨阶段引用文件和brainstorming临时文件
**【强制】Phase 11是core-design流程的最后一步，禁止跳过** — 禁止在Phase 10后宣布流程完毕而不执行清理。

1. **检查元数据文件**：
   - 读取 `docs/changes/<change-name>/.brainstorming_output` 元数据文件
   - 如果文件不存在，说明brainstorming未执行，跳过design.md清理（但仍需清理clarification_summary.json）

2. **清理design.md**：
   - 如果元数据文件存在，解析获取 `design_doc_path`
   - 删除design.md文件和元数据文件本身
   - 使用Python脚本清理：
     ```python
     import json
     from pathlib import Path

     change_dir = Path("docs/changes/<change-name>")
     output_meta = change_dir / ".brainstorming_output"

     if output_meta.exists():
         with open(output_meta) as f:
             meta = json.load(f)
         design_path = Path(meta["design_doc_path"])
         if design_path.exists():
             design_path.unlink()
             print(f"Deleted: {design_path}")
         output_meta.unlink()
         print(f"Deleted: {output_meta}")
     ```

3. **清理clarification_summary.json**：
   - 删除 `docs/changes/<change-name>/clarification_summary.json`（brainstorming澄清阶段生成的决策摘要文件）
   - 该文件在core-explore阶段生成，已被本阶段的design-doc-reviewer用于决策保真审查，现在可以安全清理
   - 使用Python脚本清理：
     ```python
     from pathlib import Path

     change_dir = Path("docs/changes/<change-name>")
     clarification_file = change_dir / "clarification_summary.json"

     if clarification_file.exists():
         clarification_file.unlink()
         print(f"Deleted: {clarification_file}")
     ```

4. **清理drafts目录**（多仓模式）：
   - 删除 `docs/changes/<change-name>/drafts/` 目录下的所有文件
   - drafts/{repo}.md（各仓探索蒸馏文件）和drafts/ambiguities_{repo}.md（各仓模糊点清单）在core-design M-2阶段已被读取，信息已融入delta_design.md，可以安全清理
   - 使用Python脚本清理：
     ```python
     import shutil
     from pathlib import Path

     change_dir = Path("docs/changes/<change-name>")
     drafts_dir = change_dir / "drafts"

     if drafts_dir.exists():
         shutil.rmtree(drafts_dir)
         print(f"Deleted: {drafts_dir}")
     ```

5. **清理shared_context.md**（多仓模式）：
   - 删除 `docs/changes/<change-name>/shared_context.md`
   - shared_context.md在core-design M-2各仓设计文档生成阶段已被读取，信息已融入各仓delta_design.md，可以安全清理
   - 使用Python脚本清理：
     ```python
     from pathlib import Path

     change_dir = Path("docs/changes/<change-name>")
     shared_context = change_dir / "shared_context.md"

     if shared_context.exists():
         shared_context.unlink()
         print(f"Deleted: {shared_context}")
     ```

6. **清理downloads/目录**：
   - 删除 `docs/changes/<change-name>/downloads/` 整个目录（包含IDP/DBOX附件、媒体文件等）
   - 单仓和多仓模式均需执行
   - **【强制】使用 rm -rf 删除整个downloads/目录**（禁止逐个删除文件而保留目录）
   - 使用Python脚本清理：
     ```python
     import shutil
     from pathlib import Path

     change_dir = Path("docs/changes/<change-name>")
     downloads_dir = change_dir / "downloads"

     if downloads_dir.exists():
         shutil.rmtree(downloads_dir)
         print(f"Deleted: {downloads_dir}")
     ```

7. **清理impl_questions_for_design.json**：
   - 删除 `docs/changes/<change-name>/impl_questions_for_design.json`（core-explore阶段生成、本阶段M-2步骤3消费的实现层面延迟问题文件）
   - 该文件在M-2步骤3已被逐条确认，确认结果已融入各仓delta_design.md，可以安全清理
   - 【注意】用户选择"延后处理"的条目不再保留到该文件——延后的实现层面问题由core-apply根据delta_design.md中的设计约束自行处理，无需此中间文件
   - 使用Python脚本清理：
     ```python
     from pathlib import Path

     change_dir = Path("docs/changes/<change-name>")
     impl_questions_file = change_dir / "impl_questions_for_design.json"

     if impl_questions_file.exists():
         impl_questions_file.unlink()
         print(f"Deleted: {impl_questions_file}")
     ```

8. **多仓模式额外清理**：除上述项目级变更目录外，还需清理各仓变更目录：
   - 对每个涉及仓 `{repo}/docs/changes/<change>/`：
     - 必须保留：`proposal.md`、`delta_spec.md`、`delta_design.md`、`tasks.md`、`delta_test_design.md`
   - **【禁止】删除以下跨阶段引用文件**（core-apply仍需消费）：
     - `repo_assignments.json` — core-apply M-1多仓检测依赖此文件
     - `clarifications/cross_repo_contracts.json` — core-apply拓扑排序各仓执行顺序依赖此文件

9. **清理验证（必须执行）**：
   - Glob列出项目级变更目录文件清单，确认无downloads/目录、无impl_questions_for_design.json
   - 多仓模式下Glob列出各仓变更目录文件清单，确认无downloads/子目录
   - Glob验证 `**/downloads/*` 返回空
   - 确认保留文件存在：proposal.md、delta_spec.md、delta_design.md、tasks.md、delta_test_design.md、repo_assignments.json、cross_repo_contracts.json

9. **执行时机**：
   - 在Phase 10完成后执行
   - 确保design.md被用于生成delta_design.md后再清理
   - 确保clarification_summary.json已被design-doc-reviewer读取后再清理
   - 确保drafts目录已被M-2各仓按仓生成阶段读取后再清理
   - 确保shared_context.md已被M-2各仓按仓生成阶段读取后再清理

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
  ✓ delta_design.md (已填充 - 包含 `language-specific design specifications` 约束 + 专家经验)
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
- Phase 7 (Expert Experience): ✓ (已注入到 delta_design.md)
- Phase 8 (Generate Artifacts): ✓ (已执行内容填充，已对照 design-principles.md + design-views.md)
- Phase 9 (设计追溯验证): ✓ (cross-doc-checker L2/L3)
- Phase 10 (design-doc-reviewer 审查): ✓

### `language-specific design specifications` Rule Integration
- Rule content fetched in Step 3: ✓
- Skill instructions extracted: ✓
- Injected into delta_design.md: ✓

### Expert Experience Integration
- Query derived from requirements: ✓
- Expert knowledge fetched: ✓
- Injected into delta_design.md design decisions: ✓

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
- **Expert Experience**: Invokes paradigm-exp-use to get relevant knowledge
- **Similar Changes**: Reads referenced similar changes for design patterns
- **tasks.md NOT task.md**: The schema defines artifact ID `tasks` which generates `tasks.md` (plural)
- **Checkbox format**: The schema requires checkbox format (`- [ ]`) for tasks
- **Verification required**: Always verify generated artifacts match schema expectations
- **Design anchors**: Use `anchor_extractor.py` to automatically extract design anchors for tasks from delta_design.md metadata
