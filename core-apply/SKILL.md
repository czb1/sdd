---
name: core-apply
description: Implement tasks from an CoreSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks.
license: MIT
compatibility: Works without npm - uses Python scripts directly
metadata:
  author: corespec
  version: "1.0"
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

**Step 1: Version Check (MANDATORY - Must be the FIRST phase in your execution plan)**

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
4. 按 references/multi-repo.md 执行 M-1~M-6（**跳过Step 4~9 + 门控检查**，M-2内部子代理按拓扑分批并行读取context files和执行代码生成）
   - M-1: 多仓检测（读取repo_assignments.json，involved_repos>1 = 多仓）
   - M-2: 按仓拓扑分批 + 子代理并行代码生成（替代Step 4~9）
   - M-3: 各仓L4实现追溯验证（subagent并行，替代门控1 L4）
   - M-4: 各仓Code Review（subagent并行，替代Code Review环节）
   - M-5: 各仓单元测试（subagent并行，替代UT环节）
   - M-6: 各仓L5 UT覆盖度验证（subagent并行，替代门控2 L5）

**【重要】多仓模式下tasks.md路径**：多仓环境中，tasks.md位于各仓目录下（如`cm/docs/changes/<change>/tasks.md`），**不是**项目根目录（`docs/changes/<name>/tasks.md`在多仓模式下不存在）。M-2子代理从各仓目录读取tasks.md。

**多仓模式下Step 4~9 + 门控检查全部由M-1~M-6替代**：
- Step 4 (Check status) → Step 3多仓change状态检查（Agent直接Glob+Read）
- Step 5 (Get apply instructions) → M-2子代理内部执行
- Step 6 (Read context files) → M-2子代理内部读取（从`{repo}/docs/changes/<change>/`路径）
- Step 7 (Load code-gen-principles) → M-2子代理内部读取（作为输入文件注入）
- Step 8 (Show progress) → M-2子代理内部展示
- Step 9 (Implement tasks) → M-2子代理按拓扑分批并行代码生成
- Step 10 (Gate-1 L4) → M-3
- Step 11 (Code Review) → M-4
- Step 12 (Unit Test) → M-5
- Step 13 (Gate-2 L5) → M-6

**单仓模式**：继续Step 4

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
- `references/code-gen-principles.md`：在 Step 9 执行每个代码生成任务时，对照每条原则（C-1~C-15），确保生成的代码符合增量开发、代码复用、质量硬约束要求
- Step 9.4 原则自检环节：每执行一个代码生成任务前，必须根据原则进行自检

**多仓场景注意**：主会话 GATE 加载的内容**不传递给子代理**。多仓模式下，主会话必须在 M-2 Step 6 构造子代理 prompt 时，将该文件作为输入文件表显式列出（含绝对路径和消费用途），确保子代理自行读取。详见 `references/multi-repo.md` M-2。

### 8. Show current progress

Display:
- Schema being used
- Progress: "N/M tasks complete"
- Remaining tasks overview
- Dynamic instruction from output

### 9. Implement tasks (loop until done or blocked)

For each pending task:
1. **针对当前任务进行代码理解**（详见下方 9.1）
2. **解析设计锚点**（详见下方 9.2）
   - 仅对 1.x 代码生成任务，按 9.2 中的任务级 Skill 规则加载附加上下文
3. **分阶段展示设计信息**（P0 → P1 → P2，详见下方 9.3）
4. **代码生成原则自检**（对照 code-gen-principles.md C-1~C-15，详见下方 9.4）
5. 执行代码生成（详见下方 9.5）
6. 标记任务完成: `- [ ]` → `- [x]`
7. Continue to next task

#### 9.1 代码理解

针对当前任务，有指向性地理解相关代码。不同于统一查看，任务级代码理解：
- 结合具体任务需求，只查看当前任务相关的代码
- 在不了解任务的情况下盲目查看全部代码效率低下
- 看完即用，记忆更清晰，减少上下文浪费

**9.1.1 尝试调用 CodeBase 工具**

**统一尝试调用策略**：
- 无论 OpenCode 还是 ClaudeCode，都**先尝试调用** CodeBase 工具
- 根据调用结果判断是否可用：**能获取到有效数据视为可用，否则视为不可用**
- 这样可以兼容后续 ClaudeCode 可能支持 CodeBase 的情况

**调用示例**（具体调用方式由 Agent 自行判断）：
- 尝试调用 `GetRemoteCallChain` 追溯当前任务涉及代码的调用链
- 尝试调用 `CodeSemanticSearch` 语义搜索当前任务相关实现
- 如果返回有效结果 → 继续使用
- 如果返回空结果或报错 → 回退到 read/grep/glob

**建议优先级**：

1. **GetRemoteCallChain** — 追溯任务代码的调用链
   - 参数：file_path="任务相关文件", method_name="核心方法", depth=2
   - 目的：理解任务代码的上下游依赖

2. **CodeSemanticSearch** — 语义搜索相关实现
   - 参数：query="任务功能描述（英文）"
   - 目的：定位相关代码文件

3. **GetFeatureTree** — 理解任务所属模块结构
   - 参数：label_detailed=true
   - 目的：了解模块的整体结构

**三状态判断**：
| 状态 | 条件 | 动作 |
|------|------|------|
| present | CodeBase 可用且有数据 | 使用 CodeBase 结果 |
| missing | CodeBase 可用但无数据 | 回退到 read/grep/glob |
| not_installed | CodeBase 工具不可用 | 直接使用 read/grep/glob |

**9.1.2 回退到传统工具（必须）**

**当 CodeBase 不可用或无结果时，使用以下替代**：

| CodeBase 工具 | 降级替代工具 | 使用方式 |
|---------------|--------------|----------|
| GetRemoteCallChain | grep + read | 多轮 grep 追溯调用关系 |
| CodeSemanticSearch | grep | `grep -r "关键词"` 定位文件 |
| GetFeatureTree | glob + grep | `glob "**/module/**/*.py"` + 分析 |

**9.1.3 必须通过 read 验证**

**验证要求**：
- 无论使用哪种工具，**最终必须通过 read 实际读取代码进行验证**
- CodeBase 结果只是参考，必须实际读取代码确认实现细节
- 确保理解与实际代码一致后再进行实现

#### 9.2 锚点解析

**任务级领域 Skill（可选）**：从当前仓的原始 `tasks.md` 读取当前 1.x 任务的元数据（脚本返回的任务列表仅为标题/状态概览）。任务没有 `Skill` 字段时按原流程执行；存在时，读取本技能的 [references/task-skills.md](references/task-skills.md)，按其中规则解析 `Skill路径` 并 Read 对应 `SKILL.md`。领域 Skill 的优先级低于 `delta_design.md` 的设计锚点和项目约束。引用文件或领域 Skill 不可读时记录 WARNING，按无 Skill 执行，不阻断任务。不将本规则应用于 2.x / 3.x / 4.x 及以后任务。

```markdown
# 从任务的"设计锚点"字段解析锚点
设计锚点: #3.1 #2.2 #1.1:约束 #1.2:证据驱动 #5.x:审查流程

# 解析结果分类
- 章节锚点: #3.1, #2.2
- 关键词锚点: #1.1:约束, #1.2:证据驱动
- 通配符锚点: #5.x:审查流程 → 展开为 #5.1, #5.2, #5.3 等
```

#### 9.3 分阶段展示设计信息

**P0 必须参考**（第一阶段展示）：

```
Working on task 1.1: explore-doc-reviewer Skill

【P0 必须参考 - 设计锚点解析结果】

📌 详细设计章节：
   #3.1 → 3.1 explore-doc-reviewer Skill 设计

📌 架构模块划分：
   #2.2 → 2.2 模块划分

请基于以上设计信息实现当前任务。
```

**P1 应当参考**（第二阶段展示）：

```
【P1 应当参考 - 设计约束与原则】

📌 设计约束（#1.1:约束）：
   - 新增Skill必须遵循现有Skill接口规范
   - 审查规则必须支持配置化
   - design-doc-reviewer审查不影响现有命令流程兼容

📌 设计原则（#1.2:证据驱动）：
   - 任何审查结果必须附带文件路径+行号

📌 设计原则（#1.2:不信任）：
   - 任何检测结果必须可通过代码Grep验证
```

**P2 建议参考**（第三阶段展示）：

```
【P2 建议参考 - 核心流程】

📌 审查流程（#5.x:审查流程）：
   详见 delta_design.md 5.1 节完整审查流程时序图

📌 TDD强制流程（#5.x:TDD强制流程）：
   详见 delta_design.md 5.1.2 节 TDD强制流程
```

**锚点召回优先级**：

| 优先级 | 锚点类型 | 强制参考 | 展示阶段 |
|--------|---------|---------|---------|
| P0 | `#X.X` 章节锚点 | 必须参考 | 第一阶段 |
| P0 | `#2.1` `#2.2` 架构锚点 | 必须参考 | 第一阶段 |
| P1 | `#1.1:约束` 约束锚点 | 必须参考 | 第二阶段 |
| P1 | `#1.2:原则名` 原则锚点 | 必须参考 | 第二阶段 |
| P2 | `#4.x:流程名` 流程锚点 | 建议参考 | 第三阶段 |

#### 9.4 代码生成原则自检

基于 Step 7 GATE 加载的 `code-gen-principles.md`，在执行代码生成前对每个任务进行原则自检：

**必检项（每个任务）**：
- C-1: 当前任务是修改现有文件还是新增文件？如果是新增，是否已论证现有文件无法扩展？
- C-5: 是否已读取并理解现有代码的入口方法、调用链、数据流？
- C-7: 是否已确认增量代码的插入点？
- C-8: 生成代码的函数是否不超过50行、行宽不超过120字符、圈复杂度不超过3？
- C-12: 生成后是否检查冗余空行/import/变量/无用方法？

**条件检项（按触发条件）**：
- C-2: 涉及已有结构体/方法修改时——是否优先在现有结构体中增加字段/在现有方法中增加逻辑分支？
- C-3: 是否搜索项目已有同类实现，避免重复？
- C-4: 新增类/文件时——该类的职责是什么？项目中是否有类似职责的文件？
- C-9: 每个import是否已验证存在和可访问性？
- C-10: 是否新增了入口点？设计文档是否有对应描述？
- C-11: 是否使用了高危API？是否保留了原始许可证声明？
- C-13: 代码中的日期是否为当前真实日期？
- C-14: 生成的方法/函数是否可被调用方触达？是否有死循环？
- C-15: 修改现有代码时，是否先理解原有逻辑？

#### 9.5 执行代码生成

向 Agent 展示完整的召回信息并完成原则自检后，执行代码生成。

**Pause if:**
- Task is unclear → ask for clarification
- Implementation reveals a design issue → suggest updating artifacts
- Error or blocker encountered → report and wait for guidance
- User interrupts

任务按以下步骤严格顺序执行（关键步骤间有门控检查）：
1. **Step 9 — 代码生成任务**: 先执行 "## 代码生成任务" 下的所有任务
2. **Step 10 — 门控检查1 L4 实现追溯验证**: 代码生成完成后、进入 Code Review 前，**必须立即**执行
3. **Step 11 — Code Review 任务**: L4 验证通过后，所有语言执行规范检查，C/C++/Java/Python/Go 额外执行内存安全检查
4. **Step 12 — 单元测试任务**: Code Review 完成后，按环节分组执行 "## 单元测试任务" 下的所有任务
5. **Step 13 — 门控检查2 L5 UT覆盖度验证**: UT 生成完成后，**必须立即**执行UT与delta_test_design.md的覆盖度验证

## 验证流程

**说明**：需求完整性验证（core-explore）和设计追溯验证（core-design）已在文档生成环节执行，core-apply 只需关注实现追溯验证。

### 10. Gate-1: L4 实现追溯验证（强制 — 不可跳过）

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

**【强制】进入此门控检查时，必须向用户输出：**
"## Step 10: L4 实现追溯验证 — 代码生成已完成，正在执行tasks→code追溯验证..."

**【强制】此门控检查是 Step 9（代码生成）和 Step 11（Code Review）之间的必经关卡。禁止跳过此步骤直接进入Code Review。**

**【强制】禁止以环境限制为由跳过L4验证** — L4验证是**代码审查**（通过Grep/Read/Glob验证代码是否存在、函数签名是否一致、是否有桩代码等），不是编译验证。Windows/Linux环境差异不影响Grep/Read/Glob工具的可用性。禁止以"Windows环境无法编译"、"需要Linux环境"等理由跳过或推迟L4验证。

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L4：
```
Skill tool: cross-doc-checker <change-name> --layer L4
```

**【强制】必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用。Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑。
- **验证内容**：tasks 中引用的文件是否存在、函数/类是否正确定义、函数签名是否与设计一致
- **失败处理**：实现追溯验证失败 → 阻塞整个流程，**必须自动修复**后重新执行L4验证，通过后方可继续
  - **自动修复循环（最多3轮）**：
    1. 读取cross-doc-checker输出的findings列表
    2. 按finding类型执行修复：
       - 【代码质量类】（桩代码/空壳实现）→ 补充实现逻辑
       - 【实现一致性类-Code>Doc】（实现超范围）→ 删除超出文档范围的代码
       - 【实现一致性类-Code<Doc】（实现不足）→ 补充文档要求的代码
       - 【文档保真类】（设计文档与实现不一致）→ 以实际代码为准更新设计文档
    3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L4
    4. 如果3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
  - **禁止**：发现FAIL后仅报告问题不修复，或跳过修复直接标记完成
- **强制要求**：不得跳过此步骤直接进入 Code Review，不得用自编 Python 脚本替代 Skill tool 调用，**不得自行执行Grep/Read绕过Skill tool做L4验证** — 必须且只能通过 Skill tool 调用 cross-doc-checker
- **结果校验**：Skill tool 执行完成后，必须检查输出中是否包含所有L4 CHECK-ID（CHECK-R5-STUB, CHECK-R5-FRAMEWORK-*, CHECK-R5-ORPHAN, CHECK-R5-HOLLOW, CHECK-R12.1, CHECK-R12.2, CHECK-R12.3, CHECK-R5-SHELL, CHECK-R5-DECORATIVE, CHECK-R5-DOWNGRADE, CHECK-R6-CODEDOC-1~5, CHECK-R6-DISQUALIFY）。缺少任何CHECK-ID的输出表示 cross-doc-checker 未完整执行，必须重新调用
- **通过后**：L4 验证结果为 PASS → 进入 Code Review 环节；L4 验证结果为 FAIL → 修复问题后重新调用 cross-doc-checker，直到通过

**主会话后处理**（子代理返回后执行）：
- 子代理返回L4验证通过 → 进入 Code Review
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败 → 主会话直接调用 cross-doc-checker Skill 执行（降级策略）

### 11. Code Review（所有语言）

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["codecheck-for-cleancode", "cwd-audit"]
**同步/异步**: sync

根据编程语言选择对应的代码检视技能：

| 编程语言 | 规范检查 | 内存安全检查 |
|----------|---------|-------------|
| cpp/c/c++/java/python/go | `codecheck-for-cleancode` | `cwd-audit`（检测+修复） |
| javascript/typescript/other | `codecheck-for-cleancode` | 跳过 |

#### 11.1 规范加载 -- 筛选当前实现相关的规范内容

3.0.1 **筛选规范目录**
从 `docs/rule_index.md` 读取的规范目录树，识别适合当前阶段生成的代码的目录条目：

**筛选过程分为两步**：
1. 根据当前需求涉及的编程语言，只处理对应语言下的目录条目。 
2. 从对应语言的目录中，挑选与代码实现细节、语法规则、编码格式相关的目录。

**【强制要求】**
- 不得选择当前需求未涉及语言的规范目录。 
- 不得将不同语言的目录合并到同一列表中。 
- 必须保持以语言为维度的独立目录列表。 
- 只选择与 apply 阶段相关的目录：适用于具体代码实现、语法细节、编码格式、代码生成或局部实现检查的目录。 
- 必须从`docs/rule_index.md`原始目录条目中选择，不得自行编造、改写或补充目录名称。 
- 目录名称必须完整保留，不得只传递末级目录名称。 
- 若某种相关语言下没有合适的 Apply 编码规范目录，则该语言对应的目录列表返回空数组。

Apply 阶段 通常可关注以下类型的规范：
- 具体语法规则与语言特性使用 
- 命名格式、缩进、空格等代码风格 
- API 具体调用方式 
- 函数/方法的实现规范 
- 异常捕获与处理的具体写法 
- 注释规范与文档字符串 
- 代码组织结构（文件/包/模块） 
- 变量声明与作用域规则 
- 类/接口的具体实现方式 
- 代码生成、模板使用

不属于 Apply 阶段筛选范围：
- 架构层面的模块划分（Design 阶段已完成） 
- 高层设计原则（如设计模式选择、架构决策） 
- 整体职责划分（Apply 阶段主要执行具体实现）

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
    "云核心网产品工程与IT装备部Python规范/编码风格/命名规则"
  ]
}
```
不得选择：

```
    "华为 CleanCode Python 核心原则/核心设计原则/可读性与可维护性",
    "华为 CleanCode Python 核心原则/核心设计原则/安全性与防御式编程",
```

因为这些目录与当前 Apply 阶段的代码实现检查相关性底。

3.0.2 **获取具体规范内容**
将 3.0.1 步骤筛选出的目录，以json格式，按照语言分别传递给 `code-rule-content` skill，获取对应规范内容。

Invoke `code-rule-content` skill:

输入必须保持多语言独立，例如：
```json
{
  "python": [
    "云核心网产品工程与IT装备部Python规范/编码风格/命名规则"
  ],
  "cpp": [
      "华为 CleanCode C++ 编码规范/格式与排版"
  ]
}
```

**【强制要求】**

- 每种语言只传递该语言对应的目录。
- 不得将 Python、Java、C++ 等不同语言目录混合传递。
- 不得传递空目录、缩写目录或自行推测的目录。
- 必须使用 3.0.1 返回的目录名称。

`code-rule-content` 返回结果统一按语言组织，例如：
```json
{
  "python": "### 可读性与可维护性\n- 使用具有明确含义的标识符\n- 公共函数必须编写 Docstring\n",
  "cpp": "### 特殊成员函数\n- 类成员变量必须显式初始化\n- 单参数构造函数声明为 explicit\n # Cpp规范"
}
```
Agent 必须统一理解为：
> 当前需求的**语言级 Apply 规范集合（`language-specific Apply specifications`）**。

后续代码规范检查过程中以这里的输出作为检视标准。


#### 11.2 规范检查（所有语言）

调用 `codecheck-for-cleancode` 技能进行编码规范检查与修复。

**必须先检查 CodeCheckCLI 是否已安装**：在执行任何规范检查操作之前，**必须**先执行 `codecheck --version` 验证安装状态。如果命令执行失败（返回非0或提示"不是内部或外部命令"），**必须立即按照 `codecheck-for-cleancode` 技能的"兜底策略（自动安装）"章节执行安装**，包括：检测 Node.js → 配置 npm 仓库 → 安装 CodeCheckCLI → 验证安装。**严禁在未安装 CodeCheckCLI 的情况下跳过规范检查**，安装失败则分析安装失败的原因（如网络问题、Node.js 版本不兼容、npm 仓库不可达等）并反馈用户。

**检查范围**：使用代码生成任务中涉及的变更文件，通过 `--files` 参数传入。

**规范检查流程**:
1. **规范内容加载与预处理** (`#### 3.0 规范加载`)
- 从 `docs/rule_index.md` 读取规范目录树 
- 根据当前需求的编程语言，筛选 Apply 阶段相关的规范目录
- 调用 `code-rule-content` skill 获取具体规范内容
- 将获取的规范内容作为 检视标准 传递给后续检查流程

2. **pre-ai-fix 阶段** (`### 3.1 规范检查`)
   - 收集代码生成任务中变更的文件列表
   - 调用 `codecheck-for-cleancode` 技能的增量检查+修复流程（参考 `assets/increcheck-fix.md`）
   - 执行 pre-ai-fix：
     ```bash
     python scripts/increcheck_and_fix_workflow.py --working-dir <project_root> --files <变更文件列表> --phase pre --check-type incre
     ```
   - 读取 `.codecheckcli/codecheck-result.json` 判断是否有告警：
     - **无告警**: 标记 2.1 完成，进入下一环节（C/C++/Java/Python/Go 进入 3.2 内存安全检查，其他语言完成Code Review进入单元测试环节）
     - **有告警**: 进入 AI 修复

3. **AI 修复**（基于规范内容检视 + 修改)
   - 参考 `codecheck-for-cleancode` 技能的 `assets/ai-fix.md` 执行 AI 修复
   - 主要步骤：黑名单过滤 → 报告拆分 → 并行 AI 修复子 Agent → 验证

   - 检视阶段： 
     - 将 3.0 加载的规范内容作为检视依据 
     - 逐条对照规范内容，检查变更文件中的代码是否符合规范 
     - 识别不符合规范的代码位置和具体问题 
     - 生成问题清单（包括：违规位置、违反的规范条目、建议修改方案） 
   - 修改阶段:
     - 参考 `codecheck-for-cleancode` 技能的 `assets/ai-fix.md` 执行 AI 修复
     - 主要步骤：黑名单过滤 → 报告拆分 → 并行 AI 修复子 Agent → 验证
     
4. **post-ai-fix 阶段**（AI 修复后执行）
   - 执行 post-ai-fix：
     ```bash
     python scripts/increcheck_and_fix_workflow.py --working-dir <project_root> --files <变更文件列表> --phase post --check-type incre
     ```
   - 生成最终 HTML 报告
   - 对照 3.0 的规范内容进行最终复核，确保所有规范条目已落实

**规范检查结果处理**：
- **无告警**: 删除中间文件（`.codecheckcli/` 目录等），标记 2.1 完成
- **有告警**: 进入 AI 修复，修复后重新检查，循环直到告警清零。完成后删除所有中间文件，标记 2.1 完成

#### 11.3 内存安全检查（C/C++、Java、Python、Go）

> 调用 `cwd-audit` 技能检测内存安全和资源管理问题，检测出问题后直接修复（所有语言）

1. **检测** (`### 3.2 内存安全检查`)
   - 调用 `cwd-audit` 技能检测代码
   - 读取检测结果判断是否有问题：
     - **无问题**: 删除中间检测报告，标记 2.2 完成，进入单元测试环节
     - **有问题**: 根据检测报告直接修复代码，修复后重新调用 `cwd-audit` 检测验证，循环直到无问题或达到最大次数（3次）。全部修复则标记完成，3次后仍有问题则标记 blocked 返回主会话由主会话上报用户
   - **必须删除中间过程产生的检测报告**

**主会话后处理**（子代理返回后执行）：
- 子代理返回 Code Review 完成 → 进入单元测试环节
- 子代理返回 blocked → 主会话上报用户处理
- 子代理执行失败 → 主会话直接执行 Code Review（降级策略）

### 12. 单元测试环节

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["generate-java-ut", "fix-java-ut", "improve-java-ut-coverage", "java-assertion-validity-review", "java-test-report", "c-cpp-dt", "c-cpp-dt-autofix", "go-ut", "go-ut-compilation-execution-fixing", "test-driven-development"]
**同步/异步**: sync

**重要约束**：所有 UT 生成任务**必须**先读取 `delta_test_design.md`，根据其中定义的测试用例（TCxxx）生成对应的 UT 代码。验收标准为"生成的UT必须覆盖delta_test_design.md中定义的所有测试用例"。

**执行顺序**：

1. **环节1: UT生成** (`### 4.1 UT生成`)
   - 并行执行所有 generate-java-ut / c-cpp-dt / go-ut / test-driven-development 任务

2. **环节2: UT修复** (`### 4.2 UT修复`)
   - 仅 Java/C/C++/Go 有此环节
   - 并行执行所有 fix-java-ut / c-cpp-dt-autofix / go-ut-compilation-execution-fixing 任务

3. **环节3: 覆盖率提升** (`### 4.3 覆盖率提升`)
   - 仅 Java 有此环节
   - 执行 improve-java-ut-coverage 任务

4. **环节4: 断言审查** (`### 4.4 断言审查`)
   - 仅 Java 有此环节
   - 执行 java-assertion-validity-review 任务

5. **环节5: 测试报告** (`### 4.5 测试报告`)
   - 仅 Java 有此环节
   - 执行 java-test-report 任务

**UT生成技能映射**：

| 编程语言 | 环节1-UT生成 | 环节2-UT修复 | 环节3-覆盖率提升 | 环节4-断言审查 | 环节5-测试报告 |
|----------|-------------|-------------|-----------------|---------------|---------------|
| java | generate-java-ut | fix-java-ut | improve-java-ut-coverage | java-assertion-validity-review | java-test-report |
| cpp/c/c++ | c-cpp-dt | c-cpp-dt-autofix | - | - | - |
| go | go-ut | go-ut-compilation-execution-fixing | - | - | - |
| python/js/ts/other | test-driven-development | - | - | - | - |

**对于每个单元测试任务**:
1. 检查 **依赖任务** 字段 - 确保关联的任务已标记完成 `[x]`
2. 读取 **编程语言** 和 **UT生成技能** 字段
3. 调用对应的 UT 生成技能
4. 验证 UT 文件已生成且编译/运行正确
5. 标记任务完成: `- [ ]` → `- [x]`

**UT 任务依赖说明**:
- C/C++/Java/Python/Go 语言: UT 任务依赖代码生成任务（1.x）、规范检查任务（2.1）和内存安全检查任务（2.2）
- JavaScript/TypeScript/其他语言: UT 任务依赖代码生成任务（1.x）和规范检查任务（2.1）

**主会话后处理**（子代理返回后执行）：
- 子代理返回 UT 全部完成 → 进入 Step 13（L5门控）
- 子代理执行失败 → 主会话直接执行单元测试环节（降级策略）

### 13. Gate-2: L5 UT覆盖度验证（UT生成完成后 — 不可跳过）

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

**【强制】进入此门控检查时，必须向用户输出：**
"## Step 13: L5 UT覆盖度验证 — UT代码已生成，正在验证UT与delta_test_design.md的覆盖度..."

**【强制】此门控检查是 Step 12（单元测试）完成后的必经验证。禁止跳过此步骤直接结束流程。**

**前置条件**：如果 `delta_test_design.md` 不存在，则跳过此门控检查，直接结束流程。

**【强制】禁止以环境限制为由跳过L5验证** — L5验证是**代码审查**（通过Grep/Read验证UT代码是否覆盖TC场景、断言是否一致、是否调用业务代码），不是编译运行UT获取覆盖率。Windows/Linux环境差异、无法编译UT、无法运行UT获取覆盖率数据等均不构成跳过L5验证的理由。cross-doc-checker的L5 CHECK-ID仅依赖Grep/Read/Glob工具，这些工具在任何环境下都可用。禁止以"Windows环境无法编译"、"需要Linux环境运行UT"等理由跳过或推迟L5验证。

子代理使用 Skill tool 调用 `cross-doc-checker`，传入 layer=L5：
```
Skill tool: cross-doc-checker <change-name> --layer L5
```

**【强制】必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用。Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑。
- **验证重点**：UT是否存在空壳/恒真断言（CHECK-R5-TESTSHELL）、delta_test_design.md场景是否被UT功能覆盖（CHECK-R13-TC-SEMANTIC-COVERAGE正向+反向）、UT断言是否与预期结果一致（CHECK-R13-TC-ASSERTION）、UT是否实际调用被测业务代码（CHECK-R13-TC-CALLTARGET）、业务代码公共接口是否有测试覆盖（CHECK-R13-PUBLIC-TESTED）
- **说明**：L5执行5项UT覆盖度与代码关联性相关CHECK-ID（含TESTSHELL测试空壳检测），TC-SEMANTIC-COVERAGE采用语义匹配（非仅ID字符串匹配），功能覆盖通过但缺TC编号注释降级为WARNING不阻塞
- **强制要求**：**不得自行执行Grep/Read绕过Skill tool做L5验证** — 必须且只能通过 Skill tool 调用 cross-doc-checker。自行执行的L5验证结果无效
- **结果校验**：Skill tool 执行完成后，必须检查输出中是否包含所有L5 CHECK-ID（CHECK-R5-TESTSHELL, CHECK-R13-TC-SEMANTIC-COVERAGE, CHECK-R13-TC-ASSERTION, CHECK-R13-TC-CALLTARGET, CHECK-R13-PUBLIC-TESTED）。缺少任何CHECK-ID的输出表示 cross-doc-checker 未完整执行，必须重新调用
- **失败处理**：UT覆盖度验证失败 → **必须自动修复**后重新执行L5验证
  - **自动修复循环（最多3轮）**：
    1. 读取cross-doc-checker输出的findings列表
    2. 按finding类型执行修复：
       - 【实现一致性类】TC场景未被UT覆盖（CHECK-R13-TC-SEMANTIC-COVERAGE FAIL）→ 补充UT代码覆盖缺失场景
       - 【代码质量类】UT空壳或恒真断言（CHECK-R5-TESTSHELL WARNING）→ 补充实际测试逻辑或有效断言
       - 【代码质量类】UT仅操作mock未调用业务代码（CHECK-R13-TC-CALLTARGET FAIL）→ 修改UT使其实际调用业务代码
       - 【实现一致性类】UT断言与预期结果不一致（CHECK-R13-TC-ASSERTION FAIL）→ 修正UT断言使其与delta_test_design.md一致
       - 【实现一致性类】业务代码public函数无测试覆盖（CHECK-R13-PUBLIC-TESTED FAIL）→ 为该函数生成UT
       - 【文档保真类】设计文档中引用的函数名与实际代码不一致（如设计写validateScaleRequest但实际是doCustomSelectorScale）→ **以实际代码为准更新设计文档**
    3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L5
    4. 如果3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
  - **WARNING级finding处理**：WARNING不阻塞流程，但**应当修复**。修复后无需重新执行L5验证
  - **禁止**：发现FAIL后仅报告问题不修复，或跳过修复直接标记完成
- **通过后**：所有L5 CHECK-ID通过 → core-apply流程完成

**主会话后处理**（子代理返回后执行）：
- 子代理返回L5验证通过 → core-apply流程完成
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败 → 主会话直接调用 cross-doc-checker Skill 执行（降级策略）

### 14. On completion or pause, show status

Display:
- Tasks completed this session
- Overall progress: "N/M tasks complete"
- If all done: suggest archive
- If paused: explain why and wait for guidance

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete! Ready to archive this change. Run /core-archive <change-name>
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```

## Fluid Workflow Integration

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly
