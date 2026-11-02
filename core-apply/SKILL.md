---
name: core-apply
description: Implement tasks from an CoreSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks; optionally consume task-linked Skills and experiences when enabled in the execution plan (disabled by default)
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
- `"ok": true` → 执行计划已持久化到 `docs/.flow_context/execution-plan-core-apply.json`，skipped 标记到 `docs/.flow_context/skipped-core-apply.json`。按 `config_missing` 与 `scenario` 决定确认动作：
  - **`"template_initialized": true`**（首次自动初始化模板）→ 在执行总结中添加一行提示："已初始化可编辑的产物模板（如需自定义章节，编辑 `~/.corespec/` 下的模板文件，执行 `python -m core_templates --guide` 查看使用指南）。"——**仅首次出现时告知，`false` 时静默跳过**

**首次运行（`config_missing: true`）——必须给用户配置机会**：

配置文件 `~/.corespec/flow-config.json` 不存在时，这是用户**唯一一次**接触 flow-config 框架的机会（后续修改需手动编辑配置文件，且仅在场景 E 触发重建）。**不得静默跳过**——必须用 **AskUserQuestion** 向用户提供"生成模板 / 继续默认"选择：

```
AskUserQuestion({
  questions: [{
    question: "未检测到 flow-config 配置文件（~/.corespec/flow-config.json）。\n当前将以全默认计划执行（内置步骤按出厂默认启停：version_check/l4_review/code_review/unit_test/l5_coverage/completion_report 开启，show_progress/skill_consumption 关闭，无自定义步骤）。\n是否生成配置模板以便启停步骤或插入自定义步骤？\n<summary>",
    header: "首次配置",
    options: [
      { label: "生成模板", description: "生成 ~/.corespec/flow-config.json 模板（含全部可配置项说明），用户修改后重建计划" },
      { label: "继续默认", description: "直接使用全默认计划执行，本次不再配置" }
    ]
  }])
```

- 用户选择 **生成模板**：运行以下命令生成带注释的 JSONC 模板（含全部可配置键说明）并同步配置指南到 `~/.corespec/flow-config-guide.md`：

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run(
    [sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'flow-config', '--init', '--skill', 'core-apply'],
    encoding='utf-8', capture_output=True, text=True)
print(result.stdout)
sys.exit(result.returncode)
"
```

  告知用户修改 `~/.corespec/flow-config.json` 后**重新运行本 Step 0 命令**（此时 `config_missing` 变为 false，按 `scenario` 正常流程确认）。用户选择"继续默认"或确认修改后 → 进入 Step 1
- 用户选择 **继续默认**：直接使用已持久化的全默认计划，进入 Step 1

**命名空间缺失（`config_missing: false` 且 `ns_missing: true`）——也必须给用户配置机会**：

配置文件 `~/.corespec/flow-config.json` 已存在（可能是其他 skill 首次运行 `--init` 生成的），但**本 skill（core-apply）的命名空间不存在**——你从未见过 core-apply 的可配置项。这与首次运行（`config_missing: true`）同权：**不得静默跳过**（场景 A 的零接触仅适用于命名空间已配置且解析为全默认的情况）——必须用 **AskUserQuestion** 向用户提供"生成模板 / 继续默认"选择（结构与上方"首次运行"分支相同，question 文案改为"flow-config 配置文件已存在，但未包含 core-apply 命名空间"）。用户选择 **生成模板** 时运行 `flow-config --init --skill core-apply`（从模板提取 core-apply 示例块追加到已存在文件，已存在的分区/键不被覆盖；若 core-apply 分区已存在则幂等不重复追加）；选择 **继续默认** 则直接使用已持久化的全默认计划。

**非首次运行（`config_missing: false`）**，按 `scenario` 决定确认动作：

| scenario | 含义 | 动作 |
|----------|------|------|
| `A` | 命名空间未配置/解析后全默认（配置文件存在） | 命名空间已配置且解析全默认 → **跳过确认**（零接触）；**命名空间缺失（`ns_missing: true`）→ 同首次运行，必须用 AskUserQuestion 提供"生成模板 / 继续默认"**（见上"命名空间缺失"分支） |
| `B` | 首次·非默认 | 用 **AskUserQuestion**（`multiSelect: true`）展示完整勾选列表（可关闭的内置步骤 + 自定义步骤） |
| `C` | 续跑·一致（指纹匹配） | 轻量确认：展示计划摘要，用户确认/跳过 |
| `D` | 计划缺失·命名空间存在 | 用 **AskUserQuestion** 确认：配置非默认 → `multiSelect: true` 完整勾选列表；配置全默认 → 轻量确认（等价旧"首次·非默认"） |
| `E` | 配置变更（指纹不匹配） | 用 **AskUserQuestion** 展示变更后计划，确认后继续 |

**任何多选提问（场景 B/D 的完整勾选、Adjust 的调整项）的空应答处理**：用户提交但未选中任何选项时，**禁止静默按"不调整/保持默认"继续**——先确认"未选中任何选项"事实，再按"不调整"处理并明确声明；若 UI 异常无法确认，重新发起一次相同多选提问。

**多选提问的操作键提示（场景 B/D 完整勾选、Adjust 调整项均适用）**：所有 `multiSelect: true` 提问的 question 文本**必须内嵌操作键说明**——`↑↓ 移动高亮 / 空格（Space）勾选或取消 / 回车（Enter）提交`。多选 checkbox 与单选交互不同（单选是方向键高亮 + 回车即选中；多选必须空格勾选、回车才提交），用户按单选直觉操作会提交空选择（2026-09-20 三次真实失败均因此返回空应答）。操作键说明是 question 文本的固定组成部分，**禁止删除、禁止只写在对话文本里**（对话文本会被 agent 省略，用户看不到）。

**AskUserQuestion 结构化参数（Do NOT modify）**：

```
AskUserQuestion({
  questions: [{
    question: "执行计划已构建（scenario: <scenario>）。\n<summary>。\n请选择操作：",
    header: "执行计划",
    options: [
      { label: "Confirm", description: "确认当前执行计划，按计划执行" },
      { label: "Adjust", description: "调整计划（告知要启停的步骤或插入的自定义步骤）" }
    ]
  }])
```

`<summary>` 取 run_build 输出的 `summary` 字段（分节清爽文本：【主流程步骤】全 16 步按执行顺序带启停状态 /【编排点子环节】仅非空插槽 /【已关闭】关闭原因）。禁止自行拼接步骤清单。

**用户选择 `Adjust` 时，必须用 AskUserQuestion 的多选（multiSelect）结构化选项让用户勾选，禁止用自由文本提问**。选项与 `run_build` 输出的计划状态同步生成（当前关闭的步骤 → 启用选项；当前启用的内置步骤 → 关闭选项；当前启用的编排点条目（自定义步骤）→ 关闭选项；`commented_custom_steps` 中被注释的自定义步骤 → 启用选项），并固定包含一个"不调整"选项。**Do NOT modify 结构**（`<操作键说明>` 固定为"↑↓ 移动高亮，空格（Space）勾选/取消，回车（Enter）提交"）：

```
AskUserQuestion({
  questions: [{
    question: "请选择要调整的步骤（可多选；↑↓ 移动高亮，空格（Space）勾选/取消，回车（Enter）提交；不选任何项直接提交 = 不调整，继续执行）：\n<当前状态摘要，取自 run_build 输出 summary 的【已关闭】与【编排点子环节】>",
    header: "调整计划",
    multiSelect: true,
    options: [
      { label: "启用版本检查", description: "启用 Step 1 版本检查（version_check=true）" },
      { label: "启用进度展示", description: "启用 Step 8 展示当前进度（show_progress=true，默认关闭）" },
      { label: "启用任务 Skill 消费", description: "启用 Step 9 与每任务消费（skill_consumption=true，默认关闭；已启用时改为关闭选项）" },
      { label: "启用 L4", description: "启用 Step 11 Gate-1 L4 实现追溯验证（l4_review=true）" },
      { label: "启用 Code Review", description: "启用 Step 12 Code Review（code_review=true）" },
      { label: "启用单元测试", description: "启用 Step 13 单元测试（unit_test=true，自动恢复 L5）" },
      { label: "启用 L5", description: "启用 Step 14 Gate-2 L5 UT 覆盖度验证（l5_coverage=true，依赖 UT 开启）" },
      { label: "启用完成展示", description: "启用 Step 15 完成或暂停时展示状态（completion_report=true）" },
      // ↑ 当前关闭的内置步骤生成"启用"选项；当前启用的内置步骤生成"关闭 <步骤>"选项（如 { label: "关闭 L4", description: "关闭 Step 11 L4（l4_review=false）" }）
      // ↑ 当前启用的编排点条目（run_build 输出 `active_orchestration_entries`，即执行计划 orchestration_points 各区非空条目）生成"关闭 <key>"选项（如 { label: "关闭 compile", description: "关闭编排点 compile（post-codegen，compile=）" }）
      // ↑ 配置中的自定义步骤生成"删除 <key>"选项（如 { label: "删除 judgment_ladder", description: "删除自定义步骤 judgment_ladder（judgment_ladder=）" }）；run_build 输出 `commented_custom_steps` 中被注释的自定义步骤生成"启用 <key>"选项（如 { label: "启用 judgment_ladder", description: "恢复被注释的自定义步骤 judgment_ladder（judgment_ladder=true）" }）
      { label: "不调整", description: "保持当前计划不变，继续执行" }
    ]
  }])
})
```

**空应答处理（重要）**：若用户提交时返回空（未选中任何选项），**禁止静默按"不调整/保持默认"继续**——这会把用户的勾选意图当作取消。必须先确认"未选中任何选项"这一事实，再按"不调整"处理，并在输出中明确声明："未选中任何调整项 → 按当前计划继续（如需调整请重新发起）"。若 agent 因 UI 异常无法确认选择内容，重新发起一次相同的多选提问，不得自行解读。

用户按勾选结果应用调整：记录调整内容，执行以下命令应用调整并重同步 skipped 标记（`<changes>` 为 `key=false` / `key=true` / `key`（取消）列表；**多变更用多个独立 `--changes` 参数**（如 `'--changes', 'code_review=false', 'unit_test=false'`）或**单参数逗号拼接**（如 `'--changes', 'code_review=false,unit_test=false'`）——两种写法都兼容（`--apply` 内部按逗号拆分 + 追加归一化，2026-09-21 修复：argparse 重复参数折叠 bug 已改为 `action='append'`）；**关闭自定义步骤用 `key=`（注释软删除，声明保留在配置源可恢复）**；**启用被注释的自定义步骤用 `key=true`（取消注释恢复）**；**启停幂等**：重复勾选已处于目标状态的步骤（如再次"关闭"已关闭步骤、"启用"已启用步骤）视为成功，不中断 apply；自定义步骤的任意值更新不支持）：

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run(
    [sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'flow-config', '--apply', '--json', '--skill', 'core-apply', '--changes', '<key>=<value>', '--project-root', '<project_root>'],
    encoding='utf-8', capture_output=True, text=True)
print(result.stdout)
sys.exit(result.returncode)
"
```

**多变更写法（每个变更一个独立 `--changes` 参数，禁止逗号拼接成单参数）**：

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run(
    [sys.executable, config_dir / 'skills' / 'core-apply' / 'scripts' / 'main.py', 'flow-config', '--apply', '--json', '--skill', 'core-apply', '--changes', 'code_review=false', '--changes', 'unit_test=false', '--changes', 'judgment_ladder=', '--project-root', '<project_root>'],
    encoding='utf-8', capture_output=True, text=True)
print(result.stdout)
sys.exit(result.returncode)
"
```

应用结果同样按 JSON 内容判断：`"ok": false` → 调整失败（`errors` 说明原因）；`"ok": true` → 调整已应用，`skipped_path` 为重同步后的关闭标记（后续执行期以调整后的执行计划为准）。

**调整持久化语义（重要）**：`--apply` 的调整会**同步写回配置源** `~/.corespec/flow-config.json`（内置步骤开关 / 自定义步骤启停），因此 **Step 0 重建计划时调整依然生效**，不会被配置源覆盖。**自定义步骤的"关闭"是注释软删除**（声明整块注释保留在配置源，随时可恢复）；"启用"是取消注释恢复声明。若调整后再次运行 Step 0，scenario 变为 `E`（配置变更，指纹变化）——这是预期行为，需按场景表再次确认。

**计划确认后必须创建 task 任务（MANDATORY）**：计划确认完成（Confirm 或 Adjust 应用完成）后，进入主流程前，必须使用 **TaskCreate 工具**创建 task 任务清单：
- **先创建当前阶段即可确定的任务**：
  - 固定主流程步骤：Step 0（构建执行计划）→ Step 1（版本检查）→ Step 2（选择 change）→ Step 3（多仓检测与路由）→ Step 15（完成展示）各建一个 task
  - 单仓模式：按执行计划 `steps` 数组，为每个启用的可配置内置步骤（`config_key` = `version_check`/`show_progress`/`skill_consumption`/`l4_review`/`code_review`/`unit_test`/`l5_coverage`/`completion_report`）创建 task；关闭的步骤不创建
  - 多仓模式：为启用的 Step 9 准备步骤创建 task，再按执行计划对应 M 阶段（M-3 l4_review / M-4 code_review / M-5 unit_test / M-6 l5_coverage）创建 task；关闭的 M 不创建
  - 每个启用的编排点插槽条目（`orchestration_points` 中的 reference/skill 步骤）同样创建 task
- **Step 3 路由判定后必须补充创建分支 task（MANDATORY）**：执行计划在 Step 0 构建时尚未运行 Step 3 多仓检测，单仓/多仓分支无法在确认时预知，因此 **Step 3 输出路由结果后、进入主流程主体前，必须立即用 TaskCreate 补齐分支任务**：单仓 → Step 4（检查 change 状态）→ Step 5（获取执行指令）→ Step 6（读取上下文文件）→ Step 7（加载代码生成原则）→ Step 8（展示进度）→ Step 9（任务 Skill 准备，执行计划含启用条目才创建）→ Step 10（代码生成任务）各建一个 task；多仓 → 按 references/multi-repo.md 的 M-1~M-6 各建一个 task，并为启用的 Step 9 主会话准备补建 task（M 阶段与执行计划启停对应：关闭的 M 不创建）。**禁止跳过 Step 3 后的分支补建**——否则任务清单缺失主体执行环节，用户看不到后续要执行什么
- task 描述注明对应步骤/config_key/M 阶段与启停状态；Step 10 任务循环与后续可配置步骤执行时，以这些 task 跟踪进度
- 补建时复用已存在的同一步骤 task，只创建缺失项，禁止重复创建。
- **禁止跳过 TaskCreate**（用户可直观看到哪些步骤要执行、哪些已关闭）

**执行期规则**：

下文“执行计划含条目”指存在启用条目：内置步骤须 `enabled=true`，自定义条目不得为 `enabled=false`。`steps` 是完整步骤视图，可能保留 `enabled=false` 的关闭项；不能仅凭键存在就执行。
- 执行计划是**唯一权威**：后续每个编排点/可配置步骤，查 `execution-plan-core-apply.json` 的 `steps` 数组（主流程步骤，含 `config_key` 的可配置内置步骤）与 `orchestration_points` 对象（5 个插槽子环节）——**有条目则执行，无条目则直接进入下一步**
- 计划 `orchestration_points` 含 `pre-codegen` 插槽条目 → 每个 task 在 10.3 与 10.4 之间执行该条目指令；不含 → 跳过（指令文件不加载，内容不进上下文）
- 计划 `orchestration_points` 含 `post-codegen`/`post-l4`/`post-review`/`post-ut` 插槽条目 → 对应 change 级编排点执行；不含 → 跳过
- 计划 `steps` 数组含 `config_key=version_check`/`show_progress`/`skill_consumption`/`l4_review`/`code_review`/`unit_test`/`l5_coverage`/`completion_report`（`type=built_in`，`enabled=true`）条目 → 执行对应 Step 的指令文件（`ref_file.single` 单仓 / `ref_file.multi` 多仓）；不含 → 该步骤跳过，**不 Read 指令文件**
- 自定义步骤只由 `orchestration_points` 调度，按计划顺序（`order` 升序）串行执行：`reference` 从条目的 `file` 读取指令，`skill` 调用条目的 `skill`（`run_mode=subagent` 时启动独立子代理）。显式 `enabled=false` 的条目跳过；骨架不指定自定义步骤名称或指令文件。
- 自定义声明由 `flow_config.py` 的 `TEMPLATE_JSONC` 承载。配置中整块注释表示关闭，取消整块注释表示开启，重建并确认执行计划后生效；已有产物或其他条目不能隐式开启步骤。
- 有待办 1.x 任务且 `skill_consumption` 内置步骤启用时，主会话在单仓 Step 9 / 多仓 M-2 代码生成代理启动前，读取其 `ref_file.single` / `ref_file.multi`，完成一次准备；任务级动作在 10.3.4 执行。子代理从根计划读取同一内置条目的启用状态并加载指令，准备结果随任务上下文传入，新增用户决策事项返回主会话汇总。
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
4. **路由判定后必须补充创建分支 task（MANDATORY）**：执行计划在 Step 0 构建时尚未运行本步多仓检测，单仓/多仓分支任务无法在计划确认时创建。因此**路由结果输出后、进入主流程主体前，必须立即用 TaskCreate 补齐分支任务**（单仓 → Step 4~10 各一个 task；多仓 → M-1~M-6 各一个 task，关闭的 M 不创建）。禁止跳过。
5. 按 references/multi-repo.md 执行 M-1~M-6（**跳过Step 4~10 + 门控检查**，M-2内部子代理按拓扑分批并行读取context files和执行代码生成；M-3~M-6 为**可配置步骤**，执行与否以执行计划为准——含对应 `key` 条目则按 `ref_file.multi` 指令文件执行，不含则跳过，详见 multi-repo.md 头部"可配置步骤与编排点"）
   - M-1: 多仓检测（读取repo_assignments.json，involved_repos>1 = 多仓）
   - M-2: 按仓拓扑分批 + 子代理并行代码生成（替代Step 4~10）
   - M-3: 各仓L4实现追溯验证（subagent并行，替代门控1 L4）**[可配置: l4_review]**
   - M-4: 各仓Code Review（subagent并行，替代Code Review环节）**[可配置: code_review]**
   - M-5: 各仓单元测试（subagent并行，替代UT环节）**[可配置: unit_test]**
   - M-6: 各仓L5 UT覆盖度验证（subagent并行，替代门控2 L5）**[可配置: l5_coverage]**

**【多仓可配置步骤执行规则】**（与单仓 Step 11-14 同一权威，执行计划是唯一数据源）：
- 可配置步骤（M-3~M-6）：查 `execution-plan-core-apply.json` 的 `steps` 数组。含 `config_key=l4_review`/`code_review`/`unit_test`/`l5_coverage`（type=built_in）条目 → 从条目 `ref_file.multi` 取指令文件并 Read 执行；不含 → 跳过，**不 Read 指令文件**（内容不进上下文），直接进入下一 M 阶段
- 主会话执行的可配置步骤（不映射 M 阶段，与单仓同一机制、同一执行计划条目）：`version_check`（Step 1，M-1 之前）/ `show_progress`（Step 8，M-2 之前）/ `skill_consumption`（Step 9，M-2 之前主会话准备、M-2 内每任务消费，默认关闭）/ `completion_report`（Step 15，M-6 之后 on-completion）。这些步骤的 `ref_file.multi` 为单多仓通用文件，存在性判断同单仓
- 编排点插槽（多仓下同样查执行计划 `orchestration_points` 对象）：`pre-codegen`（M-2 子代理内 task 级，10.3 与 10.4 之间）/ `post-codegen`（M-2 后）/ `post-l4`（M-3 后）/ `post-review`（M-4 后）/ `post-ut`（M-5 后）。对应插槽数组含条目 → 按条目 `type` 执行（reference 型 Read `file` 指令文件 / skill 型调用 skill，`run_mode=subagent` 时 spawn 独立子代理）；不含 → 跳过，指令文件不加载
- **多仓子代理的计划输入**：Step 0 生成 `execution-plan-fragment-core-apply-<repo>.json` 片段文件（`main.py flow-config --fragment --repo <repo> --repo-cwd <路径> --project-root <根项目绝对路径>`，内容为 `repo`/`repo_cwd`/`plan_path`/`orchestration_points` 五插槽；**必须显式传 `--project-root`**，否则以 cwd 解析根项目，多仓子代理 cwd 是各仓目录时片段会写到错误位置；`--fragment` 无论是否带 `--json` 都落盘片段文件，`--json` 仅额外在 stdout 输出一份），M-2 子代理通过输入文件接收本仓片段，按片段中插槽条目执行（pre-codegen 任务级、post-codegen 生成完成后），不在插槽的编排点不执行；所有仓共享同一根执行计划。子代理同时读取片段 `plan_path` 指向的根计划，仅从其 `steps` 判断内置步骤启停；片段不含 `steps`，不得用插槽条目推断内置步骤状态
- `l5_coverage` 依赖 `unit_test`：UT 关闭 → L5 自动降级（disabled 区 `dependency_downgraded`），两指令文件均不 Read
- `skipped-core-apply.json` 只读：Step 15 on-completion 展示可配置步骤状态时读取，agent 全程不写

**【重要】多仓模式下tasks.md路径**：多仓环境中，tasks.md位于各仓目录下（如`cm/docs/changes/<change>/tasks.md`），**不是**项目根目录（`docs/changes/<name>/tasks.md`在多仓模式下不存在）。M-2子代理从各仓目录读取tasks.md。

**多仓模式下Step 4~10 + 门控检查全部由M-1~M-6替代**：
- Step 4 (Check status) → Step 3多仓change状态检查（Agent直接Glob+Read）
- Step 5 (Get apply instructions) → M-2子代理内部执行
- Step 6 (Read context files) → M-2子代理内部读取（从`{repo}/docs/changes/<change>/`路径）
- **M-2 子代理代码生成循环对象仅限各仓 tasks.md `## 代码生成任务` 章节（1.x）**；`## Code Review 任务`（2.x）属 M-4（`code_review`）、`## 单元测试任务`（3.x）属 M-5（`unit_test`），对应 M 阶段关闭时整章节跳过，**禁止**在 M-2 代码生成循环中执行（与单仓 Step 10 同一边界约束）
- Step 7 (Load code-gen-principles) → M-2子代理内部读取（作为输入文件注入）
- Step 8 (Show progress) → M-2 之前主会话执行（show_progress 默认关闭，执行计划含条目才执行）
- Step 9 (任务 Skill 准备与消费) → M-2 之前主会话准备一次、M-2 子代理内每任务执行（仅启用时）
- Step 10 (Implement tasks) → M-2子代理按拓扑分批并行代码生成
- Step 11 (Gate-1 L4) → M-3
- Step 12 (Code Review) → M-4
- Step 13 (Unit Test) → M-5
- Step 14 (Gate-2 L5) → M-6

**单仓模式**：路由判定后必须用 TaskCreate 补充创建分支 task（MANDATORY）：Step 4（检查 change 状态）→ Step 5（获取执行指令）→ Step 6（读取上下文文件）→ Step 7（加载代码生成原则 GATE）→ Step 8（展示当前进度，执行计划含 show_progress 条目才创建）→ Step 9（任务 Skill 准备，执行计划含启用条目才创建）→ Step 10（代码生成任务）各一个 task（Step 0~3 与 Step 15、可配置内置步骤、编排点条目已在计划确认时创建，见"计划确认后必须创建 task 任务"段）。然后继续Step 4

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

### 9. 任务 Skill 准备与消费 [可配置: skill_consumption]

> 本步骤默认关闭。仅当根执行计划 `steps` 含 `config_key=skill_consumption`、`type=built_in`、`enabled=true` 条目时，Read 该条目的 `ref_file.single`，完成主会话准备；每任务动作按 Step 10 的独立内置检查点执行。
> 没有启用条目 → 跳过，不加载指令文件，继续 Step 10。无待办 1.x 任务时无需准备。
> 多仓由 M-2 启动前的主会话读取 `ref_file.multi` 执行一次准备，子代理按根计划执行每任务动作。

### 10. Implement code-generation tasks (loop until done or blocked, tasks.md `## 代码生成任务` section only)

<!-- GATE:REF references/code-generation-procedure.md -->
**MANDATORY GATE**: Step 10 执行前必须先 Read 本SKILL所在目录下的 `references/code-generation-procedure.md`。
绝对路径 = config_dir / 'skills/core-apply/references/code-generation-procedure.md'（动态路径解析参见本SKILL Reference文件路径解析章节）。
文件不存在时 MUST STOP，禁止跳过。
读取后输出: "GATE PASSED: references/code-generation-procedure.md loaded"。
<!-- /GATE:REF -->

**执行方式**：按 `references/code-generation-procedure.md` 的主循环执行每个待办任务——每个 task 依次执行 10.1 代码理解 → 10.2 锚点解析 → 10.3 分阶段展示 → 10.3.4 内置每任务检查点 → 10.3.5 通用插槽 → 10.4 原则自检 → 10.5 代码生成，标记任务完成 `- [ ]` → `- [x]` 后进入下一任务。10.5 按测试策略分 test-after/tdd 两个互斥分支（读取 tasks.md 头部 `测试策略` 字段，缺省 test-after）。编排点 pre-codegen（10.3 与 10.4 之间）与 post-codegen（Step 10 之后）的判断逻辑见指令文件。

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
> **依赖规则**：`l5_coverage` 依赖 `unit_test`。若 `unit_test` 关闭（配置或确认时取消），`l5_coverage` 自动降级（reason=`dependency_downgraded`），执行计划不含本步骤。

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

