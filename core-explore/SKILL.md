---
name: core-explore
description: Core Explore需求探索SKILL - 从CoreAlm获取需求、解析设计文档、检索云见知识、生成proposal和delta_spec
license: MIT
compatibility: Works without npm - uses Python scripts directly
metadata:
  author: corespec
  version: "2.0"
  generatedBy: "manual"
---

# Core Explore - 需求探索与规格生成助手

## 1. 功能定位

该SKILL用于探索需求、获取需求信息、解析设计文档、检索相关知识，并生成符合Spec工程规范的proposal.md和delta_spec.md文档。

## 2. 输入要求

用户需要提供以下信息之一：
- US号 (如 US20251017596178)
- Story号 (如 ST20251017596178)
- SR号 (如 SR20260110000656)
- IR号 (如 IR20250831000227)
- 需求澄清信息（如 当前需求需要做什么什么）
- `docs/relationship.md` - 多仓库描述，理解需求涉及的跨仓库调用链


## 3. 执行模式

**重要说明**：本SKILL采用**AI自主判断**的执行模式，不是自动化的脚本流水线。每个阶段执行后，AI需要根据当前状态判断下一步操作：
- 可使用Bash工具调用脚本
- 可直接使用Read/Write/Edit等工具
- **【禁止】跳过任何强制阶段** — 仅条件分支允许跳过（如阶段3仅执行3.1或3.2、5.5仅多仓执行、阶段7无相似需求时快速通过）

**连续执行规则**：
- 除brainstorming交互和用户确认门控外，各阶段**自动连续执行**，禁止等待用户"继续"输入
- 仅在遇到阻塞错误时才暂停等待用户指示
- **【禁止】输出"等待CMS推进"后停止** — 每个阶段完成后必须立即开始下一阶段执行，不要等待CMS或用户触发
- **【强制】阶段9（L1验证）、阶段10（explore-doc-reviewer审查）、阶段11（清理临时文件）为不可跳过的强制阶段** — 禁止在阶段8后宣布流程完毕
- **【强制】阶段9和阶段10是两个不同阶段**：阶段9使用cross-doc-checker（L1需求追溯），阶段10使用explore-doc-reviewer（文档质量审查）。**禁止合并或混淆这两个阶段，禁止用explore-doc-reviewer替代cross-doc-checker**
- **【强制】阶段9和阶段10必须通过Agent tool启动子代理执行** — 禁止主会话直接调用Skill tool。子代理失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行（详见阶段9/10"降级策略"）
- 多仓模式连续执行规则（M-1~M-8各阶段的用户交互节点和自动继续要求）详见 references/multi-repo.md M-1章节

## 4. 脚本调用方式

**注意**：由于本SKILL采用分阶段脚本调用，请使用以下动态路径解析方式：

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
    config_dir / 'skills' / 'core-explore' / 'scripts' / '<script_name>.py',
    '<script_args>'
])
sys.exit(result.returncode)
"

# Or directly (auto-detect config directory):
# OpenCode: ~/.config/opencode/skills/core-explore/scripts/<script_name>.py
# ClaudeCode: ~/.cac/skills/core-explore/scripts/<script_name>.py
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
ref_path = config_dir / 'skills' / 'core-explore' / 'references' / 'multi-repo.md'
# 然后用 Read 工具读取 ref_path
```

**备选路径**（动态解析失败时依次尝试）：
1. `~/.config/opencode/skills/core-explore/references/multi-repo.md`
2. `~/.cac/skills/core-explore/references/multi-repo.md`

**【禁止】在项目工作目录下搜索 references/ 路径**——该目录不存在于项目中。

### Windows环境注意事项

1. **编码**：所有Python subprocess调用必须指定 `encoding='utf-8', errors='replace'`。Windows默认GBK编码会导致中文输出解码失败。
2. **Shell语法**：当前环境可能是PowerShell而非Bash。避免使用 `&&`、`||` 连接命令；改用分步执行或 `bash -c "..."`。
3. **目录创建**：`mkdir -p` 在PowerShell中不可用，改用 `New-Item -ItemType Directory -Force` 或分步 `mkdir`。
4. **命令失败恢复**：如Shell命令因语法错误失败，必须使用替代语法重试，**不得跳过当前步骤**。

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

**常用脚本**：
| 脚本 | 用途 |
|------|------|
| `corealm_api.py` | 获取需求信息 |
| `single_file_downloader.py` | 下载CoreAlm文档 |
| `docx_tools_gpt.py` | 解析Word文档 |
| `proposal_generator.py` | 生成proposal.md模板 |
| `delta_spec_generator.py` | 生成delta_spec.md模板 |
| `dbox_download.py` | DBox文档下载 |

**【重要】L1验证（阶段9）不使用Python脚本**：cross-doc-checker 是Agent审查技能，通过 Skill tool 在子代理中调用（详见阶段9）。**禁止**调用 trace_validator.py、cross_doc_checker.py 等脚本文件执行L1验证 — 这些脚本不存在或已废弃，调用将导致验证步骤被跳过。

## 5. 工作流程与判断节点

> **阶段执行规则**：
> - 阶段1~11 连续编号，与 steps.md 序号一一对应
> - **【强制】所有阶段必须按顺序执行，禁止跳过任何阶段**（条件分支除外，如阶段3仅执行3.1或3.2、5.5仅多仓执行）
> - **【强制】阶段5内5.1~5.5必须依次执行，禁止跳过任何子步骤** — 5.1→5.2→5.3→5.4→5.5 为强制顺序，每个子步骤完成后必须进入下一个子步骤
> - **【强制】阶段9（L1验证）、阶段10（explore-doc-reviewer审查）、阶段11（清理临时文件）为不可跳过的强制阶段**
> - **【禁止】在阶段8后宣布流程完毕** — 必须继续执行阶段9→10→11
> - **【强制】阶段9使用cross-doc-checker，阶段10使用explore-doc-reviewer** — 禁止合并或混淆，禁止用explore-doc-reviewer替代cross-doc-checker
> - **【强制】阶段9和阶段10必须通过Agent tool启动子代理执行** — 禁止主会话直接调用Skill tool。子代理失败时先告知用户再降级

### 阶段1: 检查用户输入
**动作**：验证是否提供了US号/Story号/IR号
**判断**：
- 如果未提供 → 进入阶段5
- 如果已提供 → 进入阶段2

### 阶段2: 获取需求信息
**动作**：调用CoreAlm接口获取需求信息
**调用方式**：通过Bash工具调用：
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'corealm_api.py', '--id', '<ID>', '--user', '<用户工号>'])
sys.exit(result.returncode)
"
```
或直接使用requests调用API
**接口信息**：
- URI: https://coreinsight.rnd.huawei.com/chat/search/corealm/e2e_info
- Method: POST
- 输入: {"e2e_id": "<ID>", "ir_id": "<ID>", "sr_id": "<ID>", "us_id": "<ID>", "user_id": "<用户工号>", "doc_open": true, "desc_open": true}
- 返回: 包含e2e_id、ir_id、sr_id、sr_e2e_id、us_id、description、IR_doc_info等字段

**判断**：
- 如果获取不到用户工号 → 提示用户提供工号
- 如果接口调用失败 → 提示用户检查网络或ID是否正确
- 如果获取成功 → 进入阶段3

### 阶段3: 下载相关附件
**动作**：根据阶段2接口返回值中 IR_doc_info中 docType字段的值，判断是进入3.1，还是3.2

**判断**：
- 如果`docType`为 `IDP` → 进入3.1
- 如果`docType`为 `DBOX` → 进入3.2
- 如果IR_doc_info为空 → 进入阶段4

#### 3.1 IDP文档下载
**动作**：根据US_ID，使用single_file_downloader.py工具，下载CoreAlm文档，并在目录下查看下载的文件名
**重要说明**：不能直接使用CoreAlm API返回的doc_url（该URL是HTML只读页面），需要使用专门的文档下载脚本通过doc_id获取并下载原始Word文档
**调用方式**：通过Bash调用
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'single_file_downloader.py', '<doc_id>', '<output_dir>', '<us_num>'])
sys.exit(result.returncode)
"
```
**参数说明**：
- `doc_id`: 从CoreAlm API获取的文档ID（IR_doc_info中的docId字段）
- `output_dir`: 输出目录，如 `docs/changes/{需求id}-<name>/downloads/` <name>为基于需求信息总结出来的名字，为英文名。**附件必须保存到downloads/子目录**，不得直接保存到changes根目录。下载前须先创建该目录。
- `us_num`: 需求编号，如 US20260108586349

**判断**：
- 如果没有附件 → 跳过此阶段，直接进入阶段4
- 如果有附件 → 下载后进入阶段4

#### 3.2 DBOX文档下载
**动作**：根据docId，使用dbox_download.py工具，下载DBox文档，并在目录下查看下载的文件名
**重要说明**：不能直接使用CoreAlm API返回的doc_url（该URL是HTML只读页面），需要使用专门的文档下载脚本通过doc_id获取并下载原始Word文档
**调用方式**：通过Bash调用
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'dbox_download.py', '<doc_id>', '<output_dir>', '<us_num>'])
sys.exit(result.returncode)
"
```
**参数说明**：
- `doc_id`: 从CoreAlm API获取的文档ID（IR_doc_info中的docId字段）
- `output_dir`: 输出目录，如 `docs/changes/{需求id}-<name>/downloads/` <name>为基于需求信息总结出来的名字，为英文名。**附件必须保存到downloads/子目录**，不得直接保存到changes根目录。下载前须先创建该目录。
- `us_num`: 需求编号，如 US20260108586349

**判断**：
- 如果没有附件 → 跳过此阶段，直接进入阶段4
- 如果有附件 → 下载后进入阶段4

### 阶段4: 解析设计文档
**动作**：获取附件目录树，先获取"简介"和"功能实现设计"章节的内容，只需要关注与 sr_e2e_id 相关的功能，获取该章节内容

**【重要】DOCX文件名处理**：
下载脚本已修复：文件下载后会自动重命名为需求编号（如 `SR20260128001211.docx`），脚本输出的"文件路径"即为实际文件路径。
但如果重命名失败（脚本输出"重命名失败"），实际文件名可能仍为通用名（如 `downloadPublishFileFromUrl.docx`）。
在解析前：
1. 检查下载脚本输出的"文件路径"是否包含实际存在的文件
2. 如果脚本报告重命名成功 → 直接使用脚本输出的文件路径
3. 如果脚本报告重命名失败 → 使用Glob工具查找 `docs/changes/<change>/downloads/*.docx` 获取实际文件名
4. **禁止硬编码或猜测DOCX文件名** — 必须使用脚本输出或Glob确认的实际文件名

**调用方式**：
1. 获取目录树:
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'docx_tools_gpt.py', 'tree', '<实际DOCX文件名>'])
sys.exit(result.returncode)
"
```
2. 调用工具把DOCX简介转换为md文件:
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'docx_tools_gpt.py', 'content', '<实际DOCX文件名>', '--keyword', '简介', '--output', 'docs/changes/<change>/downloads/简介.md'])
sys.exit(result.returncode)
"
```
3. 调用工具把DOCX对应章节转换为md文件:
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'docx_tools_gpt.py', 'content', '<实际DOCX文件名>', '--keyword', '功能实现设计', '--output', 'docs/changes/<change>/downloads/功能实现设计.md'])
sys.exit(result.returncode)
"
```

**输出路径**（必须遵守）：
- `简介.md` → `docs/changes/<change>/downloads/简介.md`
- `功能实现设计.md` → `docs/changes/<change>/downloads/功能实现设计.md`
- `--output` 参数必须指向 `docs/changes/<change>/downloads/` 目录

4. 读取md文件，获取章节内容
**判断**：
- 如果没有下载的文档 → 跳过此阶段
- 如果文档解析失败 → 记录错误，继续进入阶段5
- 如果解析成功 → 进入阶段5

### 阶段5: 上下文补全与需求澄清
**重要说明**：该阶段非常重要，5.1~5.5都要依次执行，确保需求澄清清楚，多仓环境下需求分析正确。
**动作**：本阶段是可迭代的过渡阶段，在生成proposal和delta_spec之前，确保上下文完整且需求清晰；在5.3步骤中，在明确需要澄清的问题后，对于知识性问题一定要使用`skills/core-knowledge-skill`去做预解答；在多仓环境下时，按5.5进入多仓流程。

#### 5.1 多仓环境检测确认

**动作**：确认plan阶段的多仓检测结果。多仓检测已在plan阶段完成（见阶段1），此处仅需确认`is_multi_repo`标志。

**【强制】如果plan阶段未执行多仓检测**（plan.json使用的是单仓阶段列表但当前项目可能为多仓），必须在此处补充执行检测脚本：
```bash
python -c "
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
sys.path.insert(0, str(config_dir / 'skills' / 'core-explore' / 'scripts'))
from multi_repo_utils import detect_multi_repo
result = detect_multi_repo(Path.cwd())
print(json.dumps(result, ensure_ascii=False))
"
```

**判断结果**：
- `is_multi_repo = True` → 记录此标志，后续5.2~5.4按多仓模式适配执行，**必须进入5.5多仓分支**
- `is_multi_repo = False` → 记录此标志，后续按单仓模式执行，**5.5检查点通过后直接进入阶段6**

**【强制】此步骤不可跳过**。未确认检测前，Agent不得假设单仓或多仓。

#### 5.2 补全上下文（强制 — 5.1完成后必须执行）
**【禁止跳过】**：即使项目中docs/specs/目录不存在，也必须逐项检查并记录结果。本步骤为5.3知识预澄清和5.4需求澄清提供上下文基础。
**动作**：查找本项目下的所有信息，如代码文件、md文件等，补全上下文
**多仓模式适配**：多仓环境下本步骤仅执行历史归档打分，全局文档和子仓文档读取由M-2子代理完成；单仓环境下执行完整的上下文补全。

**【强制】以下操作必须逐项执行，不得整体跳过**：
1. 检查 `docs/specs/` 目录 → 不存在则记录"无全局规格文档"，继续下一项
2. 检查 `docs/archive/` 目录 → 不存在则记录"无历史归档"，继续下一项
3. 读取 `docs/relationship.md` → 不存在则记录"无多仓依赖文档"，继续下一项
4. 多仓模式：仅执行历史归档打分（5.2中步骤3）
5. 单仓模式：执行完整上下文补全

**【禁止】因某个目录不存在而跳过整个阶段**——每项检查独立执行，缺失项记录后继续。

**可用操作**：
- 使用Glob工具查找相关代码文件、配置文件、MD文档等
- 使用Grep/Read工具查看具体文件内容

**【重要】读取全局文档（必须执行）**：
在补全上下文时，**必须**按以下优先级读取全局文档，以确保对需求有全局视角的理解：

| 优先级 | 文档 | 路径 | 用途 |
|--------|------|------|------|
| P0 | 项目级 spec.md | `docs/specs/spec.md` | 了解全局规格说明，掌握项目整体功能划分 |
| P0 | 项目级 design.md | `docs/specs/design.md` | 了解全局架构设计、技术选型、模块关系 |
| P0 | 多仓库依赖关系 | `docs/relationship.md` | 了解各子仓库间的依赖关系和调用链（由 core-init 生成） |
| P0 | 归档索引 | `docs/archive/archive-index.md` | 快速扫描历史变更概要，查找相关需求，便于寻找相关文档总结 |
| P1 | 相关模块级 design.md | `docs/specs/<module-name>/design.md` | 了解相关模块的设计细节（根据需求影响的模块选择） |
| P1 | 相关模块级 spec.md | `docs/specs/<module-name>/spec.md` | 了解相关模块的规格说明 |

**【多仓环境】全局文档读取**：多仓环境下子仓文档读取由 references/multi-repo.md M-2 并行子仓探索完成，本步骤不读取子仓文档。

**读取时机**：
- 在阶段5刚开始时**必须**先读取全局文档
- 如果 `docs/specs/` 目录不存在或为空，则跳过此步骤
- 如果全局文档存在但与当前需求无关，可以简化阅读

**全局文档的作用**：
1. **理解需求背景**：了解需求在整体架构中的位置
2. **识别受影响模块**：根据项目级 design.md 的模块划分，准确定位受影响模块
3. **保持一致性**：确保 proposal.md 中的"影响分析"与全局设计保持一致
4. **避免冲突**：发现需求与现有设计可能冲突的地方，提前在5.3中澄清

**历史文档读取流程（必须执行）**：

在读取全局文档后，**必须**按以下流程读取历史归档文档：

1. 检查当前目录下的 `docs/archive/` 目录是否存在
2. 如果存在，读取 `docs/archive/archive-index.md`
3. AI 根据下方"相关性打分标准"，对每条历史记录打分（0-10分）
4. 根据得分执行不同操作：
   - **≥4分**（相关）：**必须**在阶段8生成delta_spec.md时写入"Similar Requirements Reference"章节，标注该归档路径供core-design读取。**本阶段不读取归档文件**
   - **≤3分**（弱相关）：跳过

**【强制检查点】**：打分后**必须**在对话中输出打分结果，格式：
```
历史归档打分结果：
- [需求名]：模块重叠+X | 需求目标相似+X | 技术手段相似+X | 变更类型重叠+X = 总分X → 写入引用/跳过
```
如果`docs/archive/`不存在或archive-index.md为空，输出"无历史归档记录，跳过"。**禁止无声跳过此步骤**。

**相关性打分标准（0-10分）**：

AI 对每条历史记录按以下维度打分，各项累加后得出总分：

| 维度 | 条件 | 得分 | 说明 |
|------|------|------|------|
| 模块重叠 | 与当前需求修改同一模块 | +4 | 同模块意味着代码和接口直接相关 |
| 模块相邻 | 与当前需求修改的模块有依赖或调用关系 | +2 | 相邻模块的接口变更可能互相影响 |
| 需求目标相似 | 解决同类问题（如都是"归档优化"、"认证改造"） | +3 | 同类问题的实现方案可直接参考 |
| 技术手段相似 | 采用相同技术手段（如都是"模板驱动"、"中间件模式"） | +1 | 技术方案的复用价值 |
| 变更类型重叠 | 属于同类变更（如都是SKILL修改、都是接口新增） | +1 | 相同变更类型意味着流程和规范可参考 |

**打分示例**：

- 当前需求："归档时增加代码统计信息"，历史记录"归档时生成结构化索引条目"
  - 模块重叠（都改 core-archive）：+4
  - 需求目标相似（都是归档功能增强）：+3
  - 变更类型重叠（都是SKILL修改）：+1
  - 总分：8 → 高度相关，写入引用

- 当前需求："部署流水线优化"，历史记录"归档时生成结构化索引条目"
  - 无模块重叠：0
  - 无需求目标相似：0
  - 总分：0 → 弱相关，跳过

- 当前需求："认证模块缓存优化"，历史记录"认证模块审计日志增强"
  - 模块重叠（都改 auth-core）：+4
  - 需求目标不完全相同但都是认证域增强：+1
  - 总分：5 → 可能相关，只看详细描述

**单仓环境**：读取当前项目目录下的 `docs/archive/archive-index.md`，打分后对≥4分的记录在delta_spec.md中写入Similar Requirements Reference。

**多仓环境**：多仓子仓归档索引遍历由 references/multi-repo.md M-2 并行子仓探索完成。

**读取策略**：
- 优先读 archive-index.md（P0，快速扫描），读取索引中的"详细描述"字段获取历史变更概要
- 按打分标准量化相关性，避免主观随意判断
- core-explore只打分和写引用，不读取归档文件（读取由core-design Phase 1完成）
- 如果 `docs/archive/` 目录不存在 → 跳过，继续正常流程

#### 5.3 领域知识预澄清（强制 — 5.2完成后必须执行）
**【禁止跳过】**：即使需求描述看似清晰，也必须执行本步骤。领域知识预澄清是brainstorming的前提，跳过将导致需求澄清不完整。
**动作**：识别需求中的模糊点和冲突点，向云见知识助手提问并确认
**参考文件**：`core-explore/领域知识预澄清指南.md`

**【强制执行步骤 — 必须逐步完成，禁止整体跳过】**：
1. **步骤1（必须执行）**：通过Read工具读取`core-explore/领域知识预澄清指南.md`，识别出知识性问题并铭记提问规则。本环节只处理知识性问题，流程性问题在5.4章节澄清
2. **步骤2（必须执行）**：识别至少5个知识性问题 — 即使需求看起来清晰，也必须从设计文档中提取至少5个技术概念/术语/架构决策相关的知识性问题。**【禁止】以"需求已清晰"为由跳过此步骤**
3. **步骤3（必须执行）**：云见知识性问题预澄清 — 对于知识性问题，遵循提问规则地使用云见知识助手对该问题进行预解答，知识助手将返回问题的答案与答案的置信度，知识助手通过以下方式调用：

a. 通过以下指令调用云见知识助手
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
import subprocess
result = subprocess.run([
    sys.executable,
    config_dir / 'skills' / 'core-knowledge-skill' / 'scripts' / 'knowledge_query.py',
    '--content',
    '用户问题'
])
sys.exit(result.returncode)
"
```

该指令返回的结果格式如下：

```json
{
    "code": 200,
    "msg": "success",
    "data": {
        "retrieved_text": [],
        "Result": "模型回答内容"
    },
    "meta_data": null
}
```

其中 `data.Result` 和 `data.retrieved_text` 分别为回答结果与检索片段结果，回答结果中包含置信度。如果返回空或报错，告知用户具体错误原因。

b. 多次调用云见知识助手，直到你认为所有的知识性问题都已经被解答。

c. 最终确认：将所有云见知识助手的回答结果与置信度返回给用户，让用户确认最终的回答的结果是否正确。
    <br> 注意事项1：对于所有使用知识助手回答的问题，请将【回答结果、置信度、答案采纳与否】展示给用户，答案采纳的标准是置信度高于75%
    <br> 注意事项2：初步接纳的知识性问题，也需要给予用户修改答案的权限

**【重要提醒】**： 在完成5.3领域知识预澄清之前，**禁止进入5.4需求澄清提问（brainstorming环节）**。

**【强制检查点】5.3完成标志** — 进入5.4前必须确认以下条件全部满足：
1. 已向云见知识助手提问至少5次（即已执行步骤3）
2. 已将知识助手的回答结果和置信度展示给用户
3. 用户已确认知识性问题的答案
**【禁止】在以上条件未满足时进入5.4** — 缺少任一条件视为5.3未完成。


#### 5.4 需求澄清提问（强制 — 5.3完成后必须执行）
**多仓模式**：跳过（由 references/multi-repo.md M-3 统一brainstorming澄清替代）
**单仓模式**：执行以下流程

多仓模式M-3澄清规则详见 references/multi-repo.md M-3章节。

**【强制前提】**：在brainstorming调用完成且后处理执行完毕之前，**禁止进入阶段6**。违反此约束将导致需求澄清不完整。

**【强制检查点】5.4完成标志** — 进入5.5前必须确认以下条件全部满足：
1. brainstorming已通过Skill tool在主会话中调用
2. 已完成至少3轮问答交互（用户实际回答了问题，而非Agent自行判断"需求已清晰"跳过）
3. 已向用户呈现设计方案并获得确认
4. clarification_summary.json已生成到变更目录
5. design.md已生成到docs/superpowers/specs/目录（或已通过Glob确认存在）
6. 术语对齐后处理已执行（必须展示扫描结果，或显式声明"未发现术语冲突"）
7. 决策记录后处理已执行（必须展示每个决策的三条件检查结果；满足三条件的决策已写入docs/specs/design.md"设计决策"章节）
**【禁止】在以上条件未满足时进入5.5** — 缺少任一条件视为5.4未完成。
**【禁止】以"需求已清晰"为由跳过brainstorming交互** — brainstorming的核心价值是让用户参与决策，即使Agent认为需求清晰也必须与用户确认。
**动作**：识别需求中的模糊点和冲突点，通过brainstorming技能进行苏格拉底式需求澄清
**参考文件**：`core-explore/需求澄清指南.md`

**【重要】brainstorming集成说明**：
brainstorming技能提供逐题提问、多选优先、方案对比、用户确认门控、Spec Self-Review的完整苏格拉底式需求澄清流程。**当brainstorming技能可用时，优先使用它进行需求澄清**。

**【关键】brainstorming的交互特性**：
- brainstorming **就是设计为与用户进行交互式对话的**，这不是缺陷而是设计意图
- 调用 brainstorming 时，**用户会直接与brainstorming对话**（逐题提问、多选确认），AI Agent变为旁观者
- **禁止因为"不适合自动化流程"而回退**——brainstorming返回后仍需执行后处理生成clarification_summary.json
- 即使brainstorming在和用户对话，后处理步骤在brainstorming返回后执行

**brainstorming调用逻辑**：

**【强制执行】步骤1：检测brainstorming技能可用性**
**【关键】必须按以下优先级使用检测路径**：

**优先级1（Windows首选）**：
```
if (Test-Path "$env:USERPROFILE\.config\opencode\skills\brainstorming\SKILL.md") { Write-Output "brainstorming_available" } elseif (Test-Path "$env:USERPROFILE\.cac\skills\brainstorming\SKILL.md") { Write-Output "brainstorming_available" } else { Write-Output "brainstorming_unavailable" }
```

**优先级2（Linux/Mac）**：
```
(test -f ~/.config/opencode/skills/brainstorming/SKILL.md || test -f ~/.cac/skills/brainstorming/SKILL.md) && echo "brainstorming_available" || echo "brainstorming_unavailable"
```

**优先级3（仅当优先级1/2失败时备选）**：仅当 `$env:USERPROFILE` 不可用时才使用 `$env:OPENCODE_CONFIG`：
```
if (Test-Path "$env:OPENCODE_CONFIG\skills\brainstorming\SKILL.md") { Write-Output "brainstorming_available" } else { Write-Output "brainstorming_unavailable" }
```

**优先级4**：检查.brainstorming_output元数据文件是否已存在（表示brainstorming已执行）

**【重要】**：`OPENCODE_CONFIG` 环境变量在Windows上可能未设置，**不要优先使用**，必须先尝试 `$env:USERPROFILE` 路径。

**【强制执行】步骤2：根据检测结果分支**
- 如果输出包含"brainstorming_available"或.brainstorming_output存在：
  **必须调用**skill(name="brainstorming", requirement_id="<ID>", requirement_desc="<需求描述>", context_files=["docs/specs/spec.md", "docs/specs/design.md", "docs/relationship.md"], design_doc_content="<从阶段4获取的设计文档内容>", knowledge_results="<从阶段5获取的云见知识>")
   - **【绝对禁止】使用Agent tool启动brainstorming** — brainstorming必须通过Skill tool在主会话中直接调用，禁止通过Agent tool以任何subagent_type启动。原因：Agent tool会将brainstorming放入子代理上下文，用户无法直接与brainstorming交互对话，导致苏格拉底式澄清失败
   - **【绝对禁止】将brainstorming折叠到SubAgent中执行** — brainstorming必须在主会话中与用户直接对话
   - **【绝对禁止】因"brainstorming需要用户交互不适合自动化"而跳过brainstorming调用** — brainstorming的交互式对话是其核心设计，不可跳过
  - brainstorming会生成design.md到 docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
  - **【关键问题】**：如果执行过程中brainstorming被系统自动折叠到subagent执行（执行记录出现"SubAgent: brainstorming"或"general SubAgent: brainstorming"），说明用户无法与brainstorming交互，此时**必须**执行"主会话苏格拉底式澄清流程"（见步骤3a）

**【强制执行】步骤3a：主会话苏格拉底式澄清流程（brainstorming在subagent中执行时触发）**
当检测到brainstorming通过subagent执行时（执行记录包含"SubAgent"），**禁止等待subagent完成**或依赖其结果。必须立即在**主会话**中直接与用户进行苏格拉底式澄清：

**核心原则**：
- **逐题提问**：每次只问一个问题，等待用户回复后再问下一个
- **多选优先**：优先提供A/B/C/D选项，降低用户回答门槛
- **方案对比**：提供2-3个方案让用户选择
- **用户确认门控**：每个关键决策需要用户明确确认

**执行步骤**：
1. **开场**：向用户说明将进行需求澄清，需要澄清几个关键问题
2. **澄清问题1**（如需求范围）：提供多选选项，如"过流不计费场景具体包括哪些？A)穿透流量 B)去重流量 C)协议过滤 D)全部 E)其他"
3. **等待用户回复**后，进入问题2
4. **澄清问题2**（如话统vs命令）：提供多选选项
5. **等待用户回复**后，进入问题3
6. **继续直到所有关键模糊点澄清完毕**
7. **方案推荐**：基于用户选择，推荐一个方案并说明理由
8. **【关键】呈现设计方案**：将推荐的方案以结构化方式呈现给用户，包含：
   - **核心思路**：一句话概括
   - **方案细节**：API变更、数据流、接口设计等
   - **兼容性说明**：如涉及版本兼容
9. **【关键】用户确认门控**：询问用户：
   ```
   请确认：
   1. 以上设计是否符合预期？
   2. 需要调整或补充的内容？
   3. 是否有其他需要澄清的模糊点？
   ```
10. **等待用户回复**：
    - 如果用户确认"符合预期"或"可以" → 进入后处理步骤
    - 如果用户有调整意见 → 记录意见，基于意见更新方案，重新呈现设计方案，直到用户确认
    - 如果用户提出新模糊点 → 继续逐题澄清（返回步骤2），澄清完毕后再呈现方案（返回步骤8）
11. **【强制】用户确认后才执行后处理**：生成clarification_summary.json和design.md

**【强制】禁止行为**：
- 禁止一次性抛出多个问题
- 禁止在用户未回复时继续提问
- 禁止跳过任何澄清问题直接进入下一阶段
- 禁止在用户未确认设计方案的情况下执行后处理
- 禁止调用writing-plans skill（该skill不存在）
    
   b. 传递参数说明：
      - requirement_id: 需求标识（US/ST/IR号）
      - requirement_desc: 从CoreAlm获取的需求描述
      - context_files: 全局文档路径列表（spec.md, design.md, relationship.md）
      - design_doc_content: 从阶段4解析的设计文档内容
      - knowledge_results: 从阶段5获取的云见知识检索结果
   
    c. **【强制后续步骤】brainstorming执行完毕后（无论是否真正进行了澄清对话）**：
       **禁止等待brainstorming调用writing-plans skill**（writing-plans不存在）
       **【强制】 brainstorming技能调用返回后，必须立即执行以下后处理步骤，不允许跳过或提前进入其他阶段**：
       
        **后处理步骤**：
        1. **检查brainstorming是否执行了交互式对话**
           - **【关键】brainstorming必须与用户进行多轮问答对话**，如：
             - "请选择A/B/C/D"
             - "是否同意..."
             - 用户回答："A"、"B"等
           - **【强制检测】**如果没有检测到至少3轮问答，视为brainstorming未正常执行
             - 原因：brainstorming被调用但对话被跳过（agent自行判断"需求已清晰"）
           - 如果brainstorming未正常执行，**必须重新调用brainstorming**并明确传递需求信息
        2. **【强制门控】确保design.md已生成**
           - 在 `docs/superpowers/specs/` 目录下使用Glob查找 `*-design.md` 文件
           - 如果brainstorming已生成design.md → 记录其路径，继续步骤3
           - **如果brainstorming未生成design.md** → **必须立即基于clarification_summary.json和brainstorming对话历史生成design.md**到 `docs/superpowers/specs/` 目录，禁止跳过：
             - design.md内容必须包含：架构设计、组件设计、数据流、接口设计等章节
             - 从clarification_summary.json提取purpose、approaches、recommended_approach填入设计文档
             - **【禁止】**：禁止因"brainstorming已澄清完毕"而跳过design.md生成 — design.md是core-design Phase 1.5的必要输入，缺失将导致delta_design.md设计深度不足
           - **【强制验证】**：生成后必须用Read工具回读design.md，确认文件非空且包含上述章节标题
        3. **【强制】读取 references/clarify-enhance-rules.md** — 术语对齐/决策记录的后处理规则（采纳 domain-modeling 理念，不调用外部技能）。**禁止在未读取此规则文件的情况下执行步骤4/5**
        4. **【强制】术语对齐后处理**（规则来源：references/clarify-enhance-rules.md）
           - 读取 spec.md "领域术语"章节，了解已有术语定义（如不存在则跳过写入）
           - 扫描 brainstorming 对话历史中的术语冲突（同一概念使用不同词、与已有定义冲突的用法）
           - 扫描 brainstorming 对话历史中的模糊术语（无冲突但定义不清的词，需精确定义）
           - 术语确定后写入 spec.md "领域术语"章节，格式：术语 / 英文 / 定义 / 避免使用（四列）
           - 可选：与代码交叉验证，记录冲突供后续阶段参考
           - **【强制执行证据】**：即使无术语冲突且无模糊术语，也**必须显式声明**"扫描brainstorming对话历史，未发现术语冲突或模糊术语" — 禁止跳过本步骤而不留任何执行痕迹
        5. **【强制】决策记录后处理**（规则来源：references/clarify-enhance-rules.md）
           - 扫描 brainstorming 对话历史中的决策确认（用户对方案选择的回答）
           - 三条件检查（三个必须同时满足）：Hard to reverse / Surprising without context / Real trade-off
           - 三条件全满足 → 写入 **docs/specs/design.md**（项目级设计规格文档）"设计决策"章节（追加，不覆盖已有内容）
           - **【关键】决策记录写入的是 `docs/specs/design.md`**（项目级设计规格，与步骤3中术语对齐写入的spec.md同级），**不是** brainstorming后处理步骤2生成的 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`（该文件是brainstorming生成的架构设计参考，不用于决策记录）
           - 任一条件不满足 → 不写入（正常情况，仅记录到 clarification_summary.json）
           - 如 docs/specs/design.md 不存在 → 记录决策到 clarification_summary.json，不创建文件
           - **【强制执行证据】**：对于每个用户确认的设计方案，**必须显式列出三条件检查结果**（如："决策X: hard_to_reverse=true, surprising_without_context=false, real_trade_off=true → 不满足全部三条件，仅记录到clarification_summary.json"）— 禁止仅声明"决策记录后处理已执行"而不展示检查过程
        6. **生成clarification_summary.json** 到变更目录
           - **输入来源**：**必须从brainstorming的对话历史中提取**，禁止从requirement_desc等参数直接生成
             - 从brainstorming对话中的问答内容 → purpose、constraints、success_criteria
             - 从brainstorming对话中的用户选择 → scope、approaches、recommended_approach
             - 从brainstorming对话中的澄清内容 → ambiguities_resolved、contradictions_resolved
           - **【禁止】**：禁止跳过brainstorming对话，直接从参数生成clarification_summary.json
           - 文件必须包含：purpose、constraints、success_criteria、scope、approaches、ambiguities_resolved、**terms_resolved**、**design_decisions**等字段
        7. **【强制】生成.brainstorming_output元数据文件** 记录design.md路径 — 前提：步骤2必须已确认design.md存在；design_doc_path必须指向真实存在的文件；生成后必须验证design_doc_path有效
        8. **读取clarification_summary.json和design.md**，将clarification信息整合到后续proposal.md中
        9. **【强制】执行完毕后直接进入阶段6**，不允许在brainstorming环节停留等待用户确认或调用其他技能
   
   d. clarification_summary.json格式：
      ```json
      {
        "version": "1.0",
        "requirement_id": "<ID>",
        "source": "brainstorming-skill",
        "generated_at": "<ISO时间>",
        "clarification": {
          "purpose": {...},
          "constraints": [],
          "success_criteria": [],
          "scope": {"included": [], "excluded": []},
          "approaches": [...],
          "recommended_approach": "",
          "ambiguities_resolved": [...],
          "contradictions_resolved": [...],
          "terms_resolved": [
            {
              "term": "<规范术语>",
              "term_en": "<英文>",
              "definition": "<定义>",
              "avoid": ["<避免使用词1>", "<避免使用词2>"],
              "conflict_detected": true,
              "conflict_description": "<冲突描述>",
              "written_to": "<写入位置，如docs/specs/spec.md#领域术语>"
            }
          ],
          "design_decisions": [
            {
              "decision": "<决策结论>",
              "background": "<背景>",
              "alternatives": ["<替代方案>"],
              "rationale": "<理由>",
              "three_gate_check": {
                "hard_to_reverse": true,
                "surprising_without_context": true,
                "real_trade_off": true
              },
              "written_to": "<写入位置，如docs/specs/design.md#设计决策>"
            }
          ]
        },
        "user_approval": {...},
        "self_review": {...}
      }
      ```
   
   e. .brainstorming_output元数据文件格式：
      ```json
      {
        "version": "1.0",
        "requirement_id": "<ID>",
        "design_doc_path": "docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md",
        "generated_at": "<ISO时间>",
        "source": "brainstorming-skill"
      }
      ```

3. brainstorming不可用时（回退机制）：
   - 回退到使用需求澄清指南.md进行需求澄清
   - 通过Read工具读取该文件获取提问原则和常见示例
   - 基于需求澄清指南生成clarification_summary.json（包含模糊点、冲突点、解决方案）
   - 正常继续后续流程，进入阶段6

**重点关注**：
- **模糊点识别**：信息不完整、描述不明确、需要补充说明的地方
- **冲突点识别**：需求内部矛盾、与现有设计冲突、多方需求相互矛盾、优先级冲突等
- **知识性问题预解答**：不要直接将所有问题返回给用户，一定要先用云见知识助手对知识性问题做预解答

#### 5.5 多仓环境分支（5.4完成后执行）

**【强制检查点】进入阶段6前必须满足**：
1. clarification_summary.json 已存在于变更目录
2. design.md 已存在于 docs/superpowers/specs/ 目录
3. .brainstorming_output 已存在于变更目录
**缺少任一文件 → 返回5.4执行brainstorming及后处理，禁止跳过。**

**单仓模式**（`is_multi_repo = False`）→ 检查点通过后直接进入阶段6，无需执行多仓相关步骤

**多仓模式**（`is_multi_repo = True`）→
<!-- GATE:REF references/multi-repo.md -->
**MANDATORY GATE**: 多仓环境必须先 Read 本SKILL所在目录下的 `references/multi-repo.md`。
绝对路径 = config_dir / 'skills/core-explore/references/multi-repo.md'（参见Section 4 Reference文件路径解析）。
文件不存在时 MUST STOP，禁止降级为单仓执行。
**【强制】如果Read工具返回文件不存在**：
1. 立即停止当前执行
2. 告知用户："GATE文件 references/multi-repo.md 未找到。多仓环境无法继续。请确认skill已正确安装。"
3. 等待用户指示，**禁止自行决定继续执行**
读取后输出: "GATE PASSED: references/multi-repo.md loaded"。
<!-- /GATE:REF -->
按 references/multi-repo.md 执行 M-1~M-8。各M-*阶段的替换关系、执行顺序和门控检查详见multi-repo.md对应章节。**关键路径摘要（Agent必须按此顺序执行，禁止跳过任何M-*阶段）**：

| 顺序 | M编号 | 功能 | 替换单仓步骤 | 执行模式 | 前置门控 |
|------|-------|------|-------------|----------|----------|
| 1 | M-1 | 多仓检测+涉及仓确认 | 阶段5.1~5.2 | 主会话 | repo_assignments.json不存在 |
| 2 | M-2 | 并行子仓探索 | 阶段5.2子仓文档读取 | **subagent并行**（≤3并发） | M-1通过 |
| 3 | M-3 | 统一brainstorming澄清 | 阶段5.4 | 主会话Skill tool | M-2通过 |
| 4 | **M-4** | **shared_context生成+hash一致性校验** | **无（多仓专属新增）** | 主会话 | **M-3通过** |
| 5 | M-5 | 各仓proposal生成 | 阶段6 | **subagent并行**（≤3并发） | **M-4通过（shared_context.md必须存在）** |
| 6 | — | find-similar-changes | 阶段7 | 主会话 | M-5通过 |
| 7 | M-6 | 各仓delta_spec生成 | 阶段8 | **subagent并行**（≤3并发） | find-similar完成 |
| 8 | M-7 | 各仓L1验证 | 阶段9 | **subagent并行**（≤3并发，每仓一个子代理） | M-6通过 |
| 9 | M-8 | 各仓explore-doc-reviewer审查 | 阶段10 | **subagent并行**（≤3并发，每仓一个子代理） | M-7通过 |
| 10 | — | cleanup-temp | 阶段11 | 主会话 | M-8通过 |

**【强制】M-4是M-5的必要前置** — shared_context.md不存在时，禁止进入M-5生成proposal。缺少M-4将导致各仓proposal缺少共享章节、跨仓一致性无法保证。
**【强制】M-5/M-6/M-7/M-8必须使用subagent并行** — 禁止主会话直接Write各仓文档，禁止将多个仓合并为一个子代理执行。

### 阶段6: 生成proposal.md

**【强制前提 — 必须读取以下文件后再生成proposal.md】**：
1. **clarification_summary.json** — 从5.4后处理生成，包含purpose/constraints/approaches/ambiguities_resolved/design_decisions等信息。**【禁止】在不读取此文件的情况下生成proposal.md** — 即使文件不存在，也必须显式检查并记录原因
2. **design.md**（docs/superpowers/specs/）— 从5.4后处理生成，包含架构设计/组件设计/数据流/接口设计。**【禁止】在不读取此文件的情况下生成proposal.md** — 即使文件不存在，也必须显式检查并记录原因
3. **spec.md**（docs/specs/spec.md）— 全局规格文档，用于术语对齐
4. **需求信息** — 从阶段2获取的CoreAlm需求描述
5. **设计文档** — 从阶段4解析的简介和功能实现设计内容

**检查顺序**：先Glob检查clarification_summary.json和design.md是否存在 → 存在则Read → 不存在则记录"5.4后处理未生成，需返回5.4执行brainstorming"并返回5.4

**【多仓模式条件分支】**：
- **多仓模式**（`is_multi_repo = True`）：**执行M-4→M-5流程**（而非直接生成proposal）。详细规则见references/multi-repo.md M-4和M-5章节。以下为SKILL.md本地结构性约束：

  <!-- GATE:M4 M-4 shared_context前置门控 -->
  **MANDATORY GATE**: 进入M-5前必须验证M-4已完成。
  **检查项**：
  1. `shared_context.md` 存在于 `docs/changes/<change>/` 目录
  2. `cross_repo_contracts.json` 存在于 `docs/changes/<change>/clarifications/` 目录
  **【强制】如果检查不通过**：
  1. 立即停止，不生成任何仓的proposal.md
  2. 告知用户："M-4 shared_context未生成。缺失必要输出文件。请先完成M-4。"
  3. 返回执行M-4（shared_context生成 + hash一致性校验），**禁止降级为直接生成proposal**
  <!-- /GATE:M4 -->

  **M-5子代理并行结构性约束**（对齐references/multi-repo.md M-5）：
  - **【强制】执行模式**：subagent（并行）— 每仓一个子代理，**禁止主会话直接Write proposal.md**
  - **【禁止】以下行为**：
    - 主会话直接使用Write工具写入各仓proposal.md（最常见绕过方式）
    - 主会话自行用Write逐仓生成（绕过子代理并行）
    - 将多个仓合并为一个子代理执行（每仓必须独立子代理）
    - 对5个仓中仅2-3个生成就声明全部完成
  - **并发上限**：3个子代理（≤3仓一次性启动，>3仓分批启动每批3个）
  - **子代理类型**：`subagent_type="general"`
  - **子代理启动验证**（必须输出，否则M-5执行失败）：
    ```
    M-5 子代理启动确认：
    - {repo1}: 子代理M5-proposal-{repo1}已启动
    - {repo2}: 子代理M5-proposal-{repo2}已启动
    - ...
    ```
  - **【强制验证】**：所有子代理完成后，执行hash验证（shared_context共享章节与各仓proposal对应章节比对）+ 内容抽查（Read每个仓proposal的"1. 背景与动机"章节确认非引用占位符）

  **输出路径**：各仓proposal.md生成到 `<project_root>/{repo}/docs/changes/<change>/proposal.md`（**禁止** `docs/changes/<change>/{repo}/proposal.md`）

- **单仓模式**（`is_multi_repo = False`）：继续正常流程（完整proposal生成）。

**动作**：按照spec工程规范.md 1.5.1要求生成proposal.md
**注意要点**：你需要整合前面获取的所有内容，并按要求输出，而对于"功能实现设计"章节，你仅需注意与用户同SR下的部分内容即可，其他部分忽略
**输出路径**：`docs/changes/{需求id}-<name>/proposal.md`

**【brainstorming集成】读取design.md和clarification_summary.json**：
1. 如果brainstorming已执行（.brainstorming_output存在），读取clarification_summary.json
2. 从clarification_summary.json中提取ambiguities_resolved、contradictions_resolved、recommended_approach等信息
3. 读取brainstorming生成的design.md（通过.brainstorming_output中的design_doc_path获取）
4. 将以上信息整合到proposal.md的对应章节中
5. **【术语对齐】**：如 spec.md "领域术语"章节有内容，proposal.md "变更内容"章节的措辞必须使用领域术语中的规范词
6. **【决策约束关联】**：如 clarification_summary.json 含 design_decisions 字段，在 proposal.md "影响分析"章节增加"决策约束关联"子章节，列出关键决策与本次变更的关系

#### proposal.md 编写规范（1.5.1节要求）

**必须包含的章节**：
1. 背景与动机（现状痛点 + 业务驱动）
2. 变更内容（功能清单 + 用户STORY + 不在范围内）
3. 影响分析（受影响的规格/设计章节、破坏性变更、依赖关系）
4. DFX约束（本次新增的非功能性约束）
5. 里程碑

**编写规则**：
- **规则1.5.1**：`proposal.md`必须明确列出"不在范围内"的事项，避免范围蔓延
- **规则1.5.2**：功能清单必须使用P0 / P1 / P2三级优先级标注，禁止省略优先级或自定义其他等级
- **规则1.5.3**：`proposal.md`中如存在破坏性变更，必须显式声明并描述迁移方案

**生成方式**（单仓模式）：
- 可通过Bash调用:
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'proposal_generator.py', '--id', '<ID>', '--output', '<DIR>', '--desc', '<描述>'])
sys.exit(result.returncode)
"
```
- 也可AI根据获取的信息直接生成符合规范的proposal.md

**判断**：
- 生成后检查是否符合规范 → 如不符合，手动调整
- 确认无误后进入阶段7

### 阶段7: 查找相似需求
**动作**：在`docs/changes/`目录下查找是否有相似需求的delta_spec.md
**调用方式**：直接使用Glob/Read工具查找

**【brainstorming集成】参考clarification_summary.json**：
1. 如果brainstorming已执行，读取clarification_summary.json中的clarification信息
2. 从clarification_summary.json中获取clarified scope和resolved approaches，作为相似需求查找的参考
3. 确保本需求的scope与历史需求的scope不重叠，避免重复开发

**判断**：
- 如果找到相似需求 → 读取其delta_spec.md内容作为参考，进入阶段8
- 如果未找到 → 直接进入阶段8

### 阶段8: 生成delta_spec.md

**【多仓模式条件分支】**：
- **多仓模式**（`is_multi_repo = True`）：**执行M-6流程**（而非直接生成delta_spec）。详细规则见references/multi-repo.md M-6章节。以下为SKILL.md本地结构性约束：

  **M-6子代理并行结构性约束**（对齐references/multi-repo.md M-6）：
  - **【强制】执行模式**：subagent（并行）— 每仓一个子代理，**禁止主会话直接Write delta_spec.md**
  - **【禁止】以下行为**：
    - 主会话直接使用Write工具写入各仓delta_spec.md（最常见绕过方式）
    - 主会话自行用Write逐仓生成（绕过子代理并行）
    - 将多个仓合并为一个子代理执行（每仓必须独立子代理）
    - 对5个仓中仅2-3个生成就声明全部完成
  - **并发上限**：3个子代理（≤3仓一次性启动，>3仓分批启动每批3个）
  - **子代理类型**：`subagent_type="general"`
  - **子代理启动验证**（必须输出，否则M-6执行失败）：
    ```
    M-6 子代理启动确认：
    - {repo1}: 子代理M6-deltaspec-{repo1}已启动
    - {repo2}: 子代理M6-deltaspec-{repo2}已启动
    - ...
    ```
  - **【强制验证】**：所有子代理完成后，执行ADDED/MODIFIED/REMOVED格式验证 + shared_context内容一致性验证

  **输出路径**：各仓delta_spec.md生成到 `<project_root>/{repo}/docs/changes/<change>/delta_spec.md`（**禁止** `docs/changes/<change>/{repo}/delta_spec.md`）

- **单仓模式**（`is_multi_repo = False`）：继续正常流程（完整delta_spec生成）。

**动作**：按照spec工程规范.md 1.5.2要求生成delta_spec.md
**输出路径**：`docs/changes/{需求id}-<name>/delta_spec.md`

#### delta_spec.md 编写规范（1.5.2节要求）

**必须包含的章节**：
1. ADDED Requirements（新增的业务规则）
2. MODIFIED Requirements（修改的业务规则）
3. REMOVED Requirements（删除的业务规则）
4. 数据约束变更（按ADDED / MODIFIED / REMOVED分类）
5. 术语变更（按ADDED / MODIFIED分类）
6. 合并检查清单
7. Similar Requirements Reference（如果5.2打分有≥4分的记录，**必须**包含此章节，格式如下）

**Similar Requirements Reference 格式**：
```markdown
## Similar Requirements Reference

- [版本/日期-需求名](归档路径): 简要说明相似点
```
示例：
```markdown
## Similar Requirements Reference

- [CoreTool_27.0.0/2026-07-07-IR20260701000019](docs/archive/CoreTool_27.0.0/2026-07-07-IR20260701000019): 同为归档功能增强，实现方案可参考
```

**编写规则**：
- **规则1.5.4**：`delta_spec.md`的所有变更必须使用ADDED / MODIFIED / REMOVED三种标记之一进行分类，禁止自由文本描述变更
- **规则1.5.5**：MODIFIED类型的变更必须写出**完整的修改后内容**，并在末尾用`← (原为: [原描述])`标注原始内容
- **【术语对齐】**：所有规则描述必须使用 spec.md "领域术语"中的规范词；术语变更章节消费 clarification_summary.json 的 terms_resolved 字段，ADDED 行增加"避免使用"和"来源"列
  - 说明：MODIFIED不是"diff描述"，而是"修改后的全量描述 + 原始描述备注"，便于直接合并到SPEC.md时替换
- **规则1.5.6**：REMOVED类型的变更必须显式说明删除原因；若涉及外部使用者，必须提供迁移路径
- **规则1.5.7**：`delta_spec.md`中新增或修改的每条规则必须附带验收条件，遵循1.2.3的编写规范

**验收条件编写规范（1.2.3节）**：
- **规则1.2.7**：验收条件必须可判定，禁止使用"合理"、"适当"、"正确"等不可量化的描述
- **规则1.2.8**：验收条件描述规格层面的预期行为，禁止涉及测试代码实现细节（如Mock设置、断言语法）
- **建议1.2.4**：每条业务规则的验收条件应当至少覆盖一个**正向场景**和一个**负向场景**，确保边界行为被显式定义

**验收条件格式示例**：
```markdown
1. **金额非负**：订单金额必须大于零。
   - 验收条件：输入金额 -1 → 系统返回错误码 E4001。
   - 验收条件：输入金额 0 → 系统返回错误码 E4001。
2. **状态流转**：订单状态只能按 CREATED → PAID → CLOSED 顺序流转。
   - 验收条件：当前状态为 CREATED，接收"支付成功"事件 → 状态变更为 PAID。
   - 验收条件：当前状态为 CLOSED，接收任意事件 → 状态保持 CLOSED 不变。
```

**生成方式**：
- 可通过Bash调用:
```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / '.config' / 'opencode' / 'skills' / 'core-shared' / 'scripts'))
from core_paths import get_opencode_config_dir
config_dir = get_opencode_config_dir()
import subprocess
result = subprocess.run([sys.executable, config_dir / 'skills' / 'core-explore' / 'scripts' / 'delta_spec_generator.py', '--id', '<ID>', '--output', '<DIR>'])
sys.exit(result.returncode)
"
```
- 也可AI根据proposal.md内容和获取的知识直接生成符合规范的delta_spec.md
- 应参考阶段7获取的相似需求

**判断**：
- 生成后检查是否符合规范 → 如不符合，手动调整
- 完成生成

### 阶段9: 需求完整性验证（强制）

**【多仓模式条件分支】**：
- **多仓模式**（`is_multi_repo = True`）：**正常执行**L1验证 — 对各仓的proposal.md↔delta_spec.md追溯完整性进行验证（按references/multi-repo.md M-7执行）。
- **单仓模式**（`is_multi_repo = False`）：正常执行L1验证 - 按如下模式执行。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**【禁止】主会话直接调用cross-doc-checker Skill tool** — 主会话必须通过Agent tool启动子代理，由子代理调用Skill tool
**【禁止】通过Bash调用Python脚本执行L1验证** — cross-doc-checker是Agent审查技能（使用Read/Grep/Glob），不是Python脚本。禁止调用trace_validator.py/cross_doc_checker.py
**加载技能**: ["cross-doc-checker"]
**同步/异步**: sync

**【强制执行证据】**：
- **必须**使用 Agent tool（subagent_type="general"）启动子代理执行L1验证 — 禁止直接调用 Skill tool: cross-doc-checker
- **必须**显式声明"已通过Agent tool启动子代理执行阶段9 L1验证" — 禁止仅声明"L1验证已执行"而不说明执行方式
- **必须**展示子代理的返回结果（PASS/FAIL及findings数量） — 禁止省略子代理返回结果
- **自检**：如果执行记录中出现"SkillToolcross-doc-checker"而非"Agent tool"启动子代理，说明违反了subagent强制执行要求，**必须**重新通过Agent tool启动子代理执行

**子代理启动方式**：
```
Agent tool: subagent_type="general", prompt="执行core-explore阶段9 L1需求完整性验证。调用 Skill tool: cross-doc-checker <change-name> --layer L1。按cross-doc-checker的CHECK-ID集合执行完整性验证。验证完成后报告结果。"
```

**验证内容**：
- proposal.md中的需求是否都体现在delta_spec.md中
- delta_spec.md中的变更是否都有对应的proposal描述

**【强制】子代理必须使用Skill tool调用cross-doc-checker** — 禁止Agent自行用Grep/Read替代skill调用。Agent自行Grep比对无法覆盖cross-doc-checker的完整CHECK-ID集合和语义判断逻辑。

**失败处理**：
- 验证的是文档之间的追溯关系，需要人工判断和修复
- 标记问题，上报用户具体失败原因
- 用户确认后继续执行

**自动修复循环（最多3轮）**：
1. 读取cross-doc-checker输出的findings列表
2. 按finding类型执行修复：
   - 【文档保真类】proposal有但delta_spec缺需求ID → 在delta_spec.md中补充缺失需求
   - 【文档保真类】delta_spec有但proposal缺需求ID → 在proposal.md中补充或从delta_spec中删除
   - 【文档保真类】需求ID名称不匹配 → 统一两份文档中同一需求ID的名称
   - 【文档保真类】截断/占位符 → 替换为具体内容
3. 修复完成后，**必须重新调用** Skill tool: cross-doc-checker <change-name> --layer L1
4. 3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现FAIL后仅报告问题不修复

**判断**：
- 验证通过 → 进入阶段10
- 验证失败 → 修复文档问题后重新验证（循环最多3次）

**主会话后处理**（子代理返回后执行）：
- 子代理返回验证通过 → 进入阶段10
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败或无法调起 → **【强制】先向用户明确告知**："子代理L1验证执行失败（原因：{具体错误}），将降级为主会话直接执行cross-doc-checker"，**然后**主会话降级直接调用 cross-doc-checker Skill 执行

**【降级策略】**：子代理执行失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行。**禁止跳过告知直接降级**（这会掩盖subagent执行失败的事实）。告知内容必须包含：1) 失败的具体原因 2) 即将执行的降级操作。

**多仓模式**：阶段9按references/multi-repo.md M-7执行。以下为SKILL.md本地结构性约束：

  **M-7子代理并行结构性约束**（对齐references/multi-repo.md M-7）：
  - **【强制】执行模式**：subagent（并行）— **每仓一个子代理**，禁止主会话直接调用cross-doc-checker
  - **【禁止】以下行为**：
    - 主会话直接调用 `Skill tool: cross-doc-checker` 后自行用Grep/Read验证（最常见绕过方式 — agent加载skill内容后自行执行，不启动子代理）
    - 将多个仓合并为一次cross-doc-checker调用（5仓必须5个独立子代理）
    - 对5个仓中仅2个做"抽样检查"就声明全部通过
    - 通过Bash调用Python脚本执行cross-doc-checker
  - **并发上限**：3个子代理（≤3仓一次性启动，>3仓分批启动每批3个）
  - **子代理类型**：`subagent_type="general"`
  - **子代理启动验证**（必须输出，否则M-7执行失败）：
    ```
    M-7 子代理启动确认：
    - {repo1}: 子代理M7-L1-{repo1}已启动
    - {repo2}: 子代理M7-L1-{repo2}已启动
    - ...
    ```
  - **【强制验证】**：每个子代理必须通过Skill tool调用cross-doc-checker --layer L1；子代理内部3轮自动修复循环详见references/multi-repo.md M-7
  - 子代理需要用户决策时升级到主会话

  **主会话兜底修复**（所有M-7子代理返回后，对未修复的ERROR执行）：
  - **【强制】禁止将M-7发现的ERROR级问题推迟到core-design阶段修复** — "L1验证发现的问题建议在core-design阶段修复"是**禁止行为**。L1验证发现的问题必须在explore阶段内修复完成
  - 修复路径（按优先级）：
    1. 子代理返回FAIL但未执行3轮修复（fix_rounds<3） → **重新启动该仓子代理**执行修复循环（子代理修复为第一优先）
    2. 子代理返回ESCALATE（fix_rounds=3，子代理3轮修复失败） → **主会话兜底修复**：主会话直接使用Edit/Write工具修改该仓的proposal.md/delta_spec.md，修复后重新调用cross-doc-checker验证
    3. 主会话兜底修复仍无法解决 → AskUserQuestion让用户决策
  - 子代理执行失败（非ESCALATE，子代理无法调起） → 先向用户明确告知失败原因，然后主会话降级直接调用cross-doc-checker执行该仓L1验证 + 修复
  - **【强制】禁止主会话将子代理返回的问题"记录后继续"** — 不能将子代理发现的ERROR静默记录后标记PASS并继续。每个仓的结果只能是PASSED/FIXED/ESCALATE之一

**【阶段9→10 转换门控】**：进入阶段10前，**必须**验证以下条件（任一不满足则禁止进入阶段10）：
1. 阶段9通过 **Agent tool启动子代理** 执行（执行记录中包含Agent tool调用，而非直接调用SkillToolcross-doc-checker）
2. 子代理返回验证通过结果（PASSED/FIXED）
3. **【禁止】**：如果阶段9未通过子代理执行，**禁止**进入阶段10 — 必须重新通过Agent tool启动子代理执行阶段9

### 阶段10: explore-doc-reviewer 审查（强制 — 不可跳过）

**【与阶段9的区别】**：阶段9使用 **cross-doc-checker**（L1需求追溯验证），阶段10使用 **explore-doc-reviewer**（文档质量审查）。这是两个不同的Skill，**禁止混淆或合并**。**禁止用explore-doc-reviewer替代cross-doc-checker执行阶段9**。

**【执行模式】**: subagent（强制）— 此步骤必须通过子代理执行，禁止主会话直接执行
**【禁止】主会话直接调用explore-doc-reviewer Skill tool** — 主会话必须通过Agent tool启动子代理，由子代理调用Skill tool
**【禁止】通过Bash调用Python脚本执行explore-doc-reviewer** — explore-doc-reviewer是Agent审查技能（使用Read/Grep/Glob按Stage 1→2→3→4顺序执行），不是Python脚本
**加载技能**: ["explore-doc-reviewer"]
**同步/异步**: sync

**【强制执行证据】**：
- **必须**使用 Agent tool（subagent_type="general"）启动子代理执行explore-doc-reviewer审查 — 禁止直接调用 Skill tool: explore-doc-reviewer
- **必须**显式声明"已通过Agent tool启动子代理执行阶段10 explore-doc-reviewer审查" — 禁止仅声明"审查已执行"而不说明执行方式
- **必须**展示子代理的返回结果（PASS/FAIL及findings数量） — 禁止省略子代理返回结果
- **自检**：如果执行记录中出现"SkillToolexplore-doc-reviewer"而非"Agent tool"启动子代理，说明违反了subagent强制执行要求，**必须**重新通过Agent tool启动子代理执行

**子代理启动方式**：
```
Agent tool: subagent_type="general", prompt="执行core-explore阶段10 explore-doc-reviewer审查。调用 Skill tool: explore-doc-reviewer <change-name>。按explore-doc-reviewer的Stage 1→2→3→4顺序执行审查。审查完成后报告结果。"
```

**动作**：生成文档后**必须**通过子代理调用 `explore-doc-reviewer` Skill 进行审查，确保文档质量
**调用方式**：子代理使用 Skill tool 调用 `explore-doc-reviewer`：
```
Skill tool: explore-doc-reviewer <change-name>
```

**审查维度**：
| 维度 | 检测内容 | 阈值 |
|------|----------|------|
| 完整性 | 检查所有必需章节是否存在 | 100%覆盖 |
| 清晰度 | 检测模糊词（可能、大致、若干） | 零容忍 |
| 一致性 | proposal ↔ delta_spec 一致性 | 100%匹配 |
| 可验证性 | 每条需求是否有验收条件 | 100%必需 |
| 截断检测 | 检测截断内容（"..."、"待补充"） | 零容忍 |

**判断**：
- 审查通过 → **【强制】必须进入阶段11（清理临时文件），禁止在阶段10后停止或宣布流程完毕**
- 审查失败 → **必须自动修复**后重新审查（循环最多3次）

**自动修复循环（最多3轮）**：
1. 读取explore-doc-reviewer输出的findings列表
2. 按finding类型执行修复：
   - 【文档保真类】必需章节缺失 → 补充缺失章节
   - 【文档保真类】截断/占位符 → 替换为具体内容
   - 【文档保真类】验收条件缺失 → 补充可判定的验收条件
   - 【文档保真类】模糊词 → 替换为具体表述
   - 【文档保真类】未授权决策/隐式越权 → 删除越权内容，返回主会话由主会话与用户确认
   - 【用户意图类】NEEDS CLARIFICATION超标 → 返回主会话，由主会话与用户澄清
   - 【用户意图类】→ **禁止**自行修改文档掩盖问题，必须返回主会话由主会话与用户更新决策记录
3. 修复完成后，**必须重新调用** Skill tool: explore-doc-reviewer <change-name>
4. 3轮后仍有FAIL → 暂停流程，返回主会话由主会话上报用户处理
5. **禁止**：发现FAIL后仅报告问题不修复

**主会话后处理**（子代理返回后执行）：
- 子代理返回审查通过 → 进入阶段11
- 子代理返回【用户意图类】finding → 主会话与用户交互澄清，完成后再次派发子代理执行审查
- 子代理返回3轮FAIL → 主会话上报用户处理
- 子代理执行失败或无法调起 → **【强制】先向用户明确告知**："子代理explore-doc-reviewer审查执行失败（原因：{具体错误}），将降级为主会话直接执行explore-doc-reviewer"，**然后**主会话降级直接调用 explore-doc-reviewer Skill 执行

**【降级策略】**：子代理执行失败或无法调起时，**必须先向用户明确告知失败原因**，然后按主会话降级执行。**禁止跳过告知直接降级**（这会掩盖subagent执行失败的事实）。告知内容必须包含：1) 失败的具体原因 2) 即将执行的降级操作。

**多仓模式**：阶段10按references/multi-repo.md M-8执行。以下为SKILL.md本地结构性约束：

  **M-8子代理并行结构性约束**（对齐references/multi-repo.md M-8）：
  - **【强制】执行模式**：subagent（并行）— **每仓一个子代理**，禁止主会话直接调用explore-doc-reviewer
  - **【禁止】以下行为**：
    - 主会话直接调用 `Skill tool: explore-doc-reviewer` 后自行用Grep/Read审查（最常见绕过方式 — agent加载skill内容后自行执行，不启动子代理）
    - 将多个仓合并为一次explore-doc-reviewer调用（5仓必须5个独立子代理）
    - 对5个仓中仅2个做"抽样检查"就声明全部通过
    - 通过Bash调用Python脚本执行explore-doc-reviewer
  - **并发上限**：3个子代理（≤3仓一次性启动，>3仓分批启动每批3个）
  - **子代理类型**：`subagent_type="general"`
  - **子代理启动验证**（必须输出，否则M-8执行失败）：
    ```
    M-8 子代理启动确认：
    - {repo1}: 子代理M8-review-{repo1}已启动
    - {repo2}: 子代理M8-review-{repo2}已启动
    - ...
    ```
  - **【强制验证】**：每个子代理必须通过Skill tool调用explore-doc-reviewer；子代理内部3轮自动修复循环详见references/multi-repo.md M-8
  - 子代理需要用户决策时升级到主会话

  **主会话兜底修复**（所有M-8子代理返回后，对未修复的ERROR执行）：
  - **【强制】禁止将M-8发现的ERROR级问题推迟到core-design阶段修复** — "文档审查发现的问题建议在core-design阶段修复"是**禁止行为**。文档审查发现的问题必须在explore阶段内修复完成
  - 修复路径（按优先级）：
    1. 子代理返回FAIL但未执行3轮修复（fix_rounds<3） → **重新启动该仓子代理**执行修复循环（子代理修复为第一优先）
    2. 子代理返回ESCALATE（fix_rounds=3，子代理3轮修复失败） → **主会话兜底修复**：主会话直接使用Edit/Write工具修改该仓的proposal.md/delta_spec.md，修复后重新调用explore-doc-reviewer验证
    3. 主会话兜底修复仍无法解决 → AskUserQuestion让用户决策
  - 子代理执行失败（非ESCALATE，子代理无法调起） → 先向用户明确告知失败原因，然后主会话降级直接调用explore-doc-reviewer执行该仓审查 + 修复
  - **【强制】禁止主会话将子代理返回的问题"记录后继续"** — 不能将子代理发现的ERROR静默记录后标记PASS并继续。每个仓的结果只能是PASSED/FIXED/ESCALATE之一

**【阶段10→11 转换门控】**：进入阶段11前，**必须**验证以下条件（任一不满足则禁止进入阶段11）：
1. 阶段10通过 **Agent tool启动子代理** 执行（执行记录中包含Agent tool调用，而非直接调用SkillToolexplore-doc-reviewer）
2. 子代理返回审查通过结果（PASSED/FIXED）
3. **【禁止】**：如果阶段10未通过子代理执行，**禁止**进入阶段11 — 必须重新通过Agent tool启动子代理执行阶段10

### 阶段11: 清理临时文件（强制 — core-explore流程最后一步，不可跳过）
**动作**：在`docs/changes/{需求id}-<name>/`目录下清理除核心交付物和跨阶段引用文件以外的所有文件，把下载的附件，过程生成的临时文件全部删除

**【强制】禁止删除列表** — 以下文件**绝对禁止**在core-explore清理阶段删除，删除将导致后续core-design/core-apply/core-verify/core-archive阶段断裂：

| 文件 | 保留原因 | 清理责任方 |
|------|----------|-----------|
| proposal.md | 核心交付物 | core-archive |
| delta_spec.md | 核心交付物 | core-archive |
| clarification_summary.json | core-design reviewer需读取用于决策保真审查 | core-design Phase 6.5 |
| drafts/{repo}.md（多仓） | 各仓蒸馏文件（架构图/集成点/影响点/跨仓依赖），core-design设计参考 | core-design |
| impl_questions_for_design.json（多仓） | core-design Phase 1.6需读取让用户确认实现层面延迟问题 | core-design |
| repo_assignments.json（多仓） | core-design/core-apply/core-verify/core-archive的M-1多仓检测都需读取 | core-archive |
| shared_context.md（多仓） | core-design M-2各仓设计文档生成需读取 | core-design |
| cross_repo_contracts.json（多仓） | M-4/shared_context生成、core-design M-2、core-apply M-2拓扑排序均需读取 | core-archive |
| .brainstorming_output | brainstorming执行记录，core-design会读取并清理 | core-design |

**【禁止】删除整个drafts/目录** — drafts/目录中的 `{repo}.md` 文件必须保留（仅 `ambiguities_{repo}.md` 可删除）。删除整个drafts/目录会同时删除必须保留的蒸馏文件。

**【禁止】删除repo_assignments.json** — 该文件被core-design/core-apply/core-verify/core-archive四个阶段的M-1多仓检测引用，删除将导致所有后续阶段无法识别多仓环境。

**可清理文件**：
- `downloads/` 目录（下载的原始附件 docx 等）— **必须删除整个downloads/目录**
- 过程生成的临时md文件（如简介.md、功能实现设计.md）— 通常在downloads/目录中，随downloads/一起删除
- `drafts/ambiguities_{repo}.md`（多仓模式）— 已蒸馏到clarification_summary.json和impl_questions_for_design.json中，**仅删除此文件，保留drafts/{repo}.md**
- 各仓变更目录下的临时文件（如 downloads 子目录）— **必须删除**

**判断**：
- 目标目录下是否把可清理文件都清除
- **清理前必须逐项检查禁止删除列表**，确认不会误删跨阶段引用文件
- 如果不确定某个文件是否可删，**保留**而非删除
- **清理后验证**：使用Glob列出变更目录文件清单，逐项核对禁止删除列表确认所有保留文件仍然存在

**多仓模式清理**：除上述项目级变更目录外，还需清理各仓变更目录：
- 对每个涉及仓 `{repo}/docs/changes/<change>/`：
  - **必须删除**：`downloads/` 子目录（如有）— 使用 `rm -rf` 删除整个子目录
  - **必须保留**：`proposal.md`、`delta_spec.md` — 核心交付物，绝对禁止删除
- **多仓模式清理验证**（必须执行，否则阶段11未完成）：
  1. 使用Glob列出项目级变更目录 `docs/changes/<change>/` 的文件清单
  2. 使用Glob列出各仓变更目录 `{repo}/docs/changes/<change>/` 的文件清单
  3. 逐项核对禁止删除列表，确认所有保留文件仍然存在
  4. 确认所有 `downloads/` 目录已被删除 — **【强制执行证据】**：必须使用Glob验证 `**/downloads/*` 返回空
  5. 确认 `drafts/ambiguities_*.md` 已删除但 `drafts/{repo}.md` 仍存在

**【强制】阶段11是core-explore流程的最后一个阶段**。清理完成后，输出执行总结并宣布"core-explore流程执行完毕"。**禁止在阶段10或更早阶段宣布流程完毕** — 阶段10审查通过后必须继续执行阶段11。

## 6. 可用工具脚本

位于 `core-explore/scripts/` 目录下：

| 脚本 | 功能 |
|------|------|
| corealm_api.py | CoreAlm需求信息获取接口封装 |
| single_file_downloader.py | CoreAlm文档下载工具（通过doc_id下载原始Word文档） |
| single_file_downloader_wrapper.py | 文档下载包装脚本 |
| docx_tools_gpt.py | Word文档解析工具（获取目录树和章节内容） |
| proposal_generator.py | proposal.md生成器模板 |
| delta_spec_generator.py | delta_spec.md生成器模板 |

> **注意**：由于CoreAlm API返回的doc_url是HTML只读页面，无法直接下载原始Word文档。请使用`single_file_downloader.py`脚本，通过文档ID（docId）来下载完整的Word文档。

## 7. 输出文件

生成的文件存放在 `docs/changes/{需求id}-<name>/` 目录下：
- `proposal.md` - 需求澄清文档
- `delta_spec.md` - Spec增量设计文档

## 8. 接口说明汇总

### CoreAlm需求信息获取
- URI: https://coreinsight.rnd.huawei.com/chat/search/corealm/e2e_info
- Method: POST
- 输入: {"e2e_id": "US20251017596178", "user_id": "xxxxx", "doc_open": true, "desc_open": true}
- 返回示例:
```json
{
    "code": 200,
    "msg": "success",
    "data": {
        "e2e_id": "US20251017596178",
        "ir_id": "IR20250831000227",
        "description": "需求描述...",
        "IR_doc_info": [
            {
                "introduction": "文档简介...",
                "docId": "f257d2e0-4bd7-416e-b202-74f2380b365b",
                "doc_url": "https://api.idp.huawei.com/..."
            }
        ]
    }
}
```

## 9. Guardrails

- 每个阶段执行后，AI必须做出判断再决定下一步 — 但**禁止跳过任何强制阶段**
- 验证输入的ID格式是否正确（US/ST/IR开头）
- 检查输出目录是否存在，如不存在则创建
- proposal.md必须包含1.5.1规定的5个章节
- delta_spec.md必须使用ADDED/MODIFIED/REMOVED标记，且每条规则必须附带验收条件
- 验收条件格式必须为"触发场景 → 预期行为"

## Workflow After Init:
```
1. /core-design <变更名称>   # 确认需求后开始设计
2. /core-apply                # 实施变更 (同时填充 spec.md 和 design.md)
3. /core-archive              # 归档完成变更
```
