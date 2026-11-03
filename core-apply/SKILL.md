---
name: core-apply
description: Implement tasks from an CoreSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks.
license: MIT
compatibility: Works without npm - uses Python scripts directly
metadata:
  author: corespec
  version: 1.3.2
  generatedBy: "1.1.4"
---

Implement tasks from an CoreSpec change.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Execution Method**

The skill uses Python scripts in `scripts/` directory. Execute using:
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
    config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py',
    '<command>', '<options>'
])
sys.exit(result.returncode)
"
```

Or directly (auto-detect config directory):
```bash
# OpenCode: ~/.config/opencode/skills/core-apply/scripts/main.py
# ClaudeCode: ~/.cac/skills/core-apply/scripts/main.py
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
ref_path = config_dir / 'skills' / 'core-apply' / 'references' / 'multi-repo.md'
# 然后用 Read 工具读取 ref_path
```

**备选路径**（动态解析失败时依次尝试）：
1. `~/.config/opencode/skills/core-apply/references/multi-repo.md`
2. `~/.cac/skills/core-apply/references/multi-repo.md`

**【禁止】在项目工作目录下搜索 references/ 路径**——该目录不存在于项目中。

**Step 0: Build execution plan (MANDATORY - Must be the FIRST action of the FIRST phase, before Step 1)**

**Step 0 必须先于 Step 1（version check）执行**：它是执行计划的第一阶段、第一个动作。执行以下命令构建执行计划（唯一权威）：

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run(
    [sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'flow-config', '--json', '--skill', 'core-apply'],
    encoding='utf-8', capture_output=True, text=True)
print(result.stdout)
sys.exit(result.returncode)
"
```

**输出 JSON 内容判断**（非零 exit code 不意味着失败，必须以 JSON 内容为准）：

- `"ok": false` → 配置校验/解析失败（`error` 或 `errors` 说明原因）→ **MUST STOP**，告知用户修正 `~/.corespec/flow-config.json` 后重试，禁止继续执行。`error` 含"解析失败"时是配置源损坏（如旧版写回遗留尾逗号）——框架已尝试自愈，若仍失败说明文件严重损坏，需用户手工修复（`flow-config.json.bak-*` 备份可回退）
- `"ok": true` → 执行计划已按配置构建并持久化到 `docs/.flow_context/execution-plan-core-apply.json`，skipped 标记到 `docs/.flow_context/skipped-core-apply.json`，**直接按计划执行，无需流程配置确认**：
  - **`"config_initialized": true`**（首次自动生成配置文件）→ 在执行总结中添加一行提示（仅首次，`false` 时静默跳过）："已生成流程编排配置文件 `~/.corespec/flow-config.json`（如需启停步骤或添加自定义步骤，直接编辑该文件，下次运行自动生效；说明见 `~/.corespec/flow-config-guide.md`）。"
  - **`"template_initialized": true`**（首次自动初始化模板）→ 在执行总结中添加一行提示："已初始化可编辑的产物模板（如需自定义章节，编辑 `~/.corespec/` 下的模板文件，执行 `python -m core_templates --guide` 查看使用指南）。"——**仅首次出现时告知，`false` 时静默跳过**
- 用户想调整步骤（启停内置步骤 / 添加自定义步骤）→ 直接编辑 `~/.corespec/flow-config.json`，下次运行自动生效（无需任何命令或确认）

**计划解析成功后必须创建 task 任务（MANDATORY）**：进入主流程前，必须使用 **TaskCreate 工具**创建 task 任务清单：
- **先创建当前阶段即可确定的任务**：
  - 固定主流程步骤：Step 0（构建执行计划）→ Step 1（版本检查）→ Step 2（选择 change）→ Step 3（多仓检测与路由）→ Step 15（完成展示）各建一个 task
  - 单仓模式：按执行计划 `steps` 数组，为每个启用的可配置内置步骤（`config_key` = `version_check`/`show_progress`/`skill_consumption`/`l4_review`/`code_review`/`unit_test`/`l5_coverage`/`completion_report`）创建 task；关闭的步骤不创建
  - 多仓模式：为启用的 M-1a（任务 Skill 准备）创建 task，再按执行计划对应 M 阶段（M-3 l4_review / M-4 code_review / M-5 unit_test / M-6 l5_coverage）创建 task；关闭的 M 不创建
  - 每个启用的编排点插槽条目（`orchestration_points` 中的 reference/skill 步骤）同样创建 task
- **Step 3 路由判定后必须补充创建分支 task（MANDATORY）**：执行计划在 Step 0 构建时尚未运行 Step 3 多仓检测，单仓/多仓分支无法在计划构建时预知，因此 **Step 3 输出路由结果后、进入主流程主体前，必须立即用 TaskCreate 补齐分支任务**：单仓 → Step 4（检查 change 状态）→ Step 5（获取执行指令）→ Step 6（读取上下文文件）→ Step 7（加载代码生成原则）→ Step 8（展示进度）→ Step 9（任务 Skill 准备，执行计划含启用条目才创建）→ Step 10（代码生成任务）各建一个 task；多仓 → 按 references/multi-repo.md 的 M-1、M-1a、M-2~M-6 各建一个 task（M 阶段与执行计划启停对应：关闭的 M 不创建）。**禁止跳过 Step 3 后的分支补建**——否则任务清单缺失主体执行环节，用户看不到后续要执行什么
- task 描述注明对应步骤/config_key/M 阶段与启停状态；Step 10 任务循环与后续可配置步骤执行时，以这些 task 跟踪进度
- 补建时复用已存在的同一步骤 task，只创建缺失项，禁止重复创建。
- **禁止跳过 TaskCreate**（用户可直观看到哪些步骤要执行、哪些已关闭）

**执行期规则**：

下文“执行计划含条目”指存在启用条目：内置步骤须 `enabled=true`，自定义条目不得为 `enabled=false`。`steps` 是完整步骤视图，可能保留 `enabled=false` 的关闭项；不能仅凭键存在就执行。
- 执行计划是**唯一权威**：后续每个编排点/可配置步骤，查 `execution-plan-core-apply.json` 的 `steps` 数组（主流程步骤，含 `config_key` 的可配置内置步骤）与 `orchestration_points` 对象（5 个插槽子环节）；多仓任务消费按 M-1a 的片段控制——**有条目则执行，无条目则直接进入下一步**
- 计划 `orchestration_points` 含 `pre-codegen` 插槽条目 → 每个 task 在 10.3 与 10.4 之间执行该条目指令；不含 → 跳过（指令文件不加载，内容不进上下文）
- 计划 `orchestration_points` 含 `post-codegen`/`post-l4`/`post-review`/`post-ut` 插槽条目 → 对应 change 级编排点执行；不含 → 跳过
- 计划 `steps` 数组含 `config_key=version_check`/`show_progress`/`skill_consumption`/`l4_review`/`code_review`/`unit_test`/`l5_coverage`/`completion_report`（`type=built_in`，`enabled=true`）条目 → 执行对应 Step 的指令文件（`ref_file.single` 单仓 / `ref_file.multi` 多仓，任务消费的多仓入口见 M-1a）；不含 → 该步骤跳过，**不 Read 指令文件**
- 内置步骤关闭不等于关闭其后插槽，仍按计划调度有效条目；计划 / 片段无效或已启用条目的指令文件缺失时停止并报告，不自行重建、猜测启用或静默跳过。
- `skipped-core-apply.json` 只读：Step 15 完成展示与下游 core-* 读取，agent 全程不写

**Step 1: Version Check [可配置: version_check]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=version_check`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入下一步（指令文件不加载，内容不进上下文）
>
> **执行位置**：第一阶段 Step 0（构建执行计划）之后立即执行，作为第一阶段的第二个动作。

## 主流程

### 2. Select the change

If a name is provided, use it. Otherwise:
- Infer from conversation context if the user mentioned a change
- Auto-select if only one active change exists
- If ambiguous, run the following to get available changes and use the **AskUserQuestion tool** to let the user select:
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'list', '--json'])
print(result.stdout)
sys.exit(result.returncode)
"
```

Always announce: "Using change: <name>" and how to override (e.g., `/core-apply <other>`).

### 3. 多仓检测与路由

**判断逻辑**：读取 `docs/changes/<name>/repo_assignments.json`，检查 `involved_repos` 数量。
- 文件不存在 → 单仓模式，继续Step 4
- 文件存在但 `involved_repos` < 1 → 降级为单仓模式，继续Step 4
- `involved_repos` >= 1 → **多仓模式**

**多仓模式**：
1. 输出: "检测到多仓环境（involved_repos: {repos}），进入多仓模式"
2. 多仓change状态检查（跳过Step 4的status脚本，脚本基于根目录路径，多仓模式下tasks.md不在根目录）：
   - schema: Read `docs/changes/<change>/.docs.yaml`
   - artifacts存在性: Glob各仓 `{repo}/docs/changes/<change>/` 下文件
   - tasks存在性: Glob各仓 `{repo}/docs/changes/<change>/tasks.md`
   - tasks完成进度: Read各仓tasks.md统计 `- [x]` vs `- [ ]`
3. <!-- GATE:REF references/multi-repo.md -->
   **MANDATORY GATE**: 多仓环境必须先 Read 本SKILL所在目录下的 `references/multi-repo.md`。
   绝对路径 = config_dir / 'skills/core-apply/references/multi-repo.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
   文件不存在时 MUST STOP，禁止降级为单仓执行。
   **【强制】如果Read工具返回文件不存在**：
   1. 立即停止当前执行
   2. 告知用户："GATE文件 references/multi-repo.md 未找到。多仓环境无法继续。请确认skill已正确安装。"
   3. 等待用户指示，**禁止自行决定继续执行**
   读取后输出: "GATE PASSED: references/multi-repo.md loaded"。
   <!-- /GATE:REF -->
4. **路由判定后必须补充创建分支 task（MANDATORY）**：执行计划在 Step 0 构建时尚未运行本步多仓检测，单仓/多仓分支任务无法在计划构建时创建。因此**路由结果输出后、进入主流程主体前，必须立即用 TaskCreate 补齐分支任务**（单仓 → Step 4~10 各一个 task；多仓 → M-1、M-1a、M-2~M-6 各一个 task，关闭的 M 不创建）。禁止跳过。
5. 按 references/multi-repo.md 执行 M-1 → M-1a → M-2~M-6（**跳过Step 4~10 + 门控检查**，M-2内部子代理按拓扑分批并行读取context files和执行代码生成；M-3~M-6 为**可配置步骤**，执行与否以执行计划为准——含对应 `key` 条目则按 `ref_file.multi` 指令文件执行，不含则跳过，详见 multi-repo.md 头部"可配置步骤与编排点"）
   - M-1: 多仓检测（读取repo_assignments.json，involved_repos>1 = 多仓）
   - M-1a: 任务 Skill 准备（主会话汇总各仓待办）**[可配置: skill_consumption]**
   - M-2: 按仓拓扑分批 + 子代理并行代码生成（替代Step 4~8及Step 10）
   - M-3: 各仓L4实现追溯验证（subagent并行，替代门控1 L4）**[可配置: l4_review]**
   - M-4: 各仓Code Review（subagent并行，替代Code Review环节）**[可配置: code_review]**
   - M-5: 各仓单元测试（subagent并行，替代UT环节）**[可配置: unit_test]**
   - M-6: 各仓L5 UT覆盖度验证（subagent并行，替代门控2 L5）**[可配置: l5_coverage]**

**【多仓可配置步骤执行规则】**（与单仓 Step 11-14 同一权威，执行计划是唯一数据源）：
- 可配置步骤（M-3~M-6）：查 `execution-plan-core-apply.json` 的 `steps` 数组。含 `config_key=l4_review`/`code_review`/`unit_test`/`l5_coverage`（type=built_in）条目 → 从条目 `ref_file.multi` 取指令文件并 Read 执行；不含 → 跳过，**不 Read 指令文件**（内容不进上下文），直接进入下一 M 阶段
- 主会话执行的可配置步骤（不映射 M 阶段，与单仓同一机制、同一执行计划条目）：`version_check`（Step 1，M-1 之前）/ `show_progress`（Step 8，M-2 之前）/ `completion_report`（Step 15，M-6 之后 on-completion）。这些步骤的 `ref_file.multi` 为单多仓通用文件，存在性判断同单仓
- 编排点插槽（多仓下同样查执行计划 `orchestration_points` 对象）：`pre-codegen`（M-2 子代理内 task 级，10.3 与 10.4 之间）/ `post-codegen`（M-2 后）/ `post-l4`（M-3 后）/ `post-review`（M-4 后）/ `post-ut`（M-5 后）。对应插槽数组含条目 → 按条目 `type` 执行（reference 型 Read `file` 指令文件 / skill 型调用 skill，`run_mode=subagent` 时 spawn 独立子代理）；不含 → 跳过，指令文件不加载
- **多仓子代理的计划输入**：M-1 确定仓列表后，主会话用 `main.py flow-config --fragment --skill core-apply --repo <repo> --repo-cwd <仓绝对路径> --project-root <根项目绝对路径>` 生成各仓片段（加 `--json` 可同时查看 JSON 输出）。M-1a 与 M-2 从本仓片段的 `built_in_steps.skill_consumption` 判断消费环节启停；通用插槽从 `orchestration_points` 读取。子代理不读取根计划，`plan_path` 仅记录片段来源。
- `l5_coverage` 依赖 `unit_test`：UT 关闭 → L5 自动降级（disabled 区 `dependency_downgraded`），两指令文件均不 Read
- `skipped-core-apply.json` 只读：Step 15 on-completion 展示可配置步骤状态时读取，agent 全程不写

**【重要】多仓模式下tasks.md路径**：多仓环境中，tasks.md位于各仓目录下（如`cm/docs/changes/<change>/tasks.md`），**不是**项目根目录（`docs/changes/<name>/tasks.md`在多仓模式下不存在）。M-2子代理从各仓目录读取tasks.md。

**多仓模式下Step 4~10 + 门控检查由 M-1、M-1a、M-2~M-6 替代**：
- Step 4 (Check status) → Step 3多仓change状态检查（Agent直接Glob+Read）
- Step 5 (Get apply instructions) → M-2子代理内部执行
- Step 6 (Read context files) → M-2子代理内部读取（从`{repo}/docs/changes/<change>/`路径）
- **M-2 子代理代码生成循环对象仅限各仓 tasks.md `## 代码生成任务` 章节（1.x）**；`## Code Review 任务`（2.x）属 M-4（`code_review`）、`## 单元测试任务`（3.x）属 M-5（`unit_test`），对应 M 阶段关闭时整章节跳过，**禁止**在 M-2 代码生成循环中执行（与单仓 Step 10 同一边界约束）
- Step 7 (Load code-gen-principles) → M-2子代理内部读取（作为输入文件注入）
- Step 8 (Show progress) → M-2 之前主会话执行（show_progress 默认关闭，执行计划含条目才执行）
- Step 9 (任务 Skill 准备) → 多仓独立环节 M-1a；M-2 按本仓片段使用已准备的任务上下文
- Step 10 (Implement tasks) → M-2子代理按拓扑分批并行代码生成
- Step 11 (Gate-1 L4) → M-3
- Step 12 (Code Review) → M-4
- Step 13 (Unit Test) → M-5
- Step 14 (Gate-2 L5) → M-6

**单仓模式**：路由判定后必须用 TaskCreate 补充创建分支 task（MANDATORY）：Step 4（检查 change 状态）→ Step 5（获取执行指令）→ Step 6（读取上下文文件）→ Step 7（加载代码生成原则 GATE）→ Step 8（展示当前进度，执行计划含 show_progress 条目才创建）→ Step 9（任务 Skill 准备，执行计划含启用条目才创建）→ Step 10（代码生成任务）各一个 task（Step 0~3 与 Step 15、可配置内置步骤、编排点条目已在计划构建时创建，见"计划解析成功后必须创建 task 任务"段）。然后继续Step 4

### 4. Check status to understand the schema

**注意**：此步骤仅适用于单仓模式。多仓模式下的change状态检查已在Step 3中完成。

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'status', '--change', '<name>', '--json'])
print(result.stdout)
sys.exit(result.returncode)
"
```
Parse the JSON to understand:
- `schemaName`: The workflow being used (e.g., "spec-driven")
- Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

### 5. Get apply instructions

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'apply', '--change', '<name>', '--json'])
print(result.stdout)
sys.exit(result.returncode)
"
```

This returns:
- Context file paths (varies by schema)
- Progress (total, complete, remaining)
- Task list with status
- Dynamic instruction based on current state

**Handle states:**
- If `state: "blocked"` (missing artifacts): show message, suggest using core-continue
- If `state: "all_done"`: congratulate, suggest archive
- Otherwise: proceed to implementation

> **注意 progress 统计范围**：apply 输出的 `complete/total` 统计 tasks.md **全部** checkbox（含 `## Code Review 任务`/`## 单元测试任务` 章节）。Step 10 的循环对象**仅限 `## 代码生成任务` 章节（1.x）**——即使 total 显示未完成，只要 1.x 全部 `- [x]`，Step 10 即无待办（2.x/3.x 待办属 Step 12/13 可配置步骤，关闭时整章节跳过，见 Step 10 循环对象边界）。

### 6. Read context files

Read the files listed in `contextFiles` from the apply instructions output.
The files depend on the schema being used:
- **spec-driven**: proposal, specs, design, tasks
- Other schemas: follow the contextFiles from output

### 7. Load code-gen-principles (GATE)

<!-- GATE:REF references/code-gen-principles.md -->
**MANDATORY GATE**: 生成代码前必须 Read 本 SKILL 所在目录下的 `references/code-gen-principles.md`。
绝对路径 = config_dir / 'skills/core-apply/references/code-gen-principles.md'（动态路径解析参见本 SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/code-gen-principles.md loaded"。
<!-- /GATE:REF -->

**使用方式**：
- `references/code-gen-principles.md`：在 Step 10 执行每个代码生成任务时，对照每条原则（C-1~C-15），确保生成的代码符合增量开发、代码复用、质量硬约束要求
- Step 10.4 原则自检环节：每执行一个代码生成任务前，必须根据原则进行自检

**多仓场景注意**：主会话 GATE 加载的内容**不传递给子代理**。多仓模式下，主会话必须在 M-2 Step 6 构造子代理 prompt 时，将该文件作为输入文件表显式列出（含绝对路径和消费用途），确保子代理自行读取。详见 `references/multi-repo.md` M-2。

### 8. Show current progress **[可配置: show_progress]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=show_progress`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入下一步（指令文件不加载，内容不进上下文）

### 9. 任务 Skill 准备 [可配置: skill_consumption]

> 仅当执行计划 `steps` 含 `config_key=skill_consumption`、`type=built_in`、`enabled=true` 条目时，Read 该条目的 `ref_file.single`，一次完成待办 1.x 任务的关联检查、必要的补齐与批量确认，并准备各任务上下文，供 Step 10 使用。
> 没有启用条目 → 跳过，不加载指令文件，继续 Step 10。无待办 1.x 任务时无需准备。

### 10. Implement code-generation tasks (loop until done or blocked, tasks.md `## 代码生成任务` section only)

<!-- GATE:REF references/code-generation-procedure.md -->
**MANDATORY GATE**: Step 10 执行前必须先 Read 本SKILL所在目录下的 `references/code-generation-procedure.md`。
绝对路径 = config_dir / 'skills/core-apply/references/code-generation-procedure.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/code-generation-procedure.md loaded"。
<!-- /GATE:REF -->

**执行方式**：按 `references/code-generation-procedure.md` 的主循环执行每个待办任务——每个 task 依次执行 10.1 代码理解 → 10.2 锚点解析 → 10.3 分阶段展示 → 使用本轮 Step 9 已准备的当前任务上下文 → 10.3.4 通用插槽 → 10.4 原则自检 → 10.5 代码生成，标记任务完成 `- [ ]` → `- [x]` 后进入下一任务。10.5 按测试策略分 test-after/tdd 两个互斥分支（读取 tasks.md 头部 `测试策略` 字段，缺省 test-after）。编排点 pre-codegen（10.3 与 10.4 之间）与 post-codegen（Step 10 之后）的判断逻辑见指令文件。

**【强制】Step 10 循环对象边界**：Step 10 只循环 tasks.md `## 代码生成任务` 章节（1.x）。tasks.md 的 `## Code Review 任务`（2.x）属 Step 12（`code_review`）、`## 单元测试任务`（3.x）属 Step 13（`unit_test`）——对应可配置步骤在执行计划 steps 数组中**不含** `config_key` 条目（已关闭）时，**禁止**在 Step 10 循环中执行这些章节的任何任务（指令文件不 Read，章节任务亦不执行）。Step 10 无待办且后续步骤全关闭 → 直接结束流程。

## 验证流程

**说明**：需求完整性验证（core-explore）和设计追溯验证（core-design）已在文档生成环节执行，core-apply 只需关注实现追溯验证。

### 11. Gate-1: L4 实现追溯验证 **[可配置: l4_review]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=l4_review`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入下一步（指令文件不加载，内容不进上下文）


### 12. Code Review（所有语言） **[可配置: code_review]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=code_review`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入下一步（指令文件不加载，内容不进上下文）

### 13. 单元测试环节 **[可配置: unit_test]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=unit_test`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入下一步（指令文件不加载，内容不进上下文）

### 14. Gate-2: L5 UT覆盖度验证 **[可配置: l5_coverage]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=l5_coverage`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接进入下一步（指令文件不加载，内容不进上下文）
>
> **依赖规则**：`l5_coverage` 依赖 `unit_test`。若 `unit_test` 关闭（配置关闭），`l5_coverage` 自动降级（reason=`dependency_downgraded`），执行计划不含本步骤。

### 15. On completion or pause, show status **[可配置: completion_report]**

> 本步骤为可配置步骤。执行与否以 Step 0 持久化的 execution-plan-core-apply.json 为准：
> - **执行计划 steps 数组含 `config_key=completion_report`（type=built_in）条目** → 从该条目 `ref_file.single` 字段取指令文件（动态路径解析参见本SKILL Reference文件路径解析章节）并 Read，按其中指令执行
> - **执行计划不含本步骤** → 直接结束流程（指令文件不加载，内容不进上下文）
>
> **依赖**：展示可配置步骤状态需读 `skipped-core-apply.json`（只读），详见指令文件。

## Fluid Workflow Integration

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly
