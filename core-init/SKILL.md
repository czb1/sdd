---
name: core-init
description: Initialize or update a CoreSpec project. Use when setting up a new project or refreshing existing specs from remote repositories.
license: MIT
compatibility: Works without npm - uses Python scripts directly
metadata:
   author: corespec
   version: "1.5"
   generatedBy: "1.1.4"
---

Initialize or update a CoreSpec project with specs from remote repositories.

**Input**: Optional project root path. If not provided, uses current directory.

**Execution Method**

The skill uses Python scripts in `scripts/` directory. Execute using:
```bash
# 自解析脚本路径，无外部依赖（OpenCode / ClaudeCode 两种布局自动适配）
python -c "
import sys, subprocess
from pathlib import Path
SKILL, SCRIPT = 'core-init', 'main.py'
for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
    p = base/'skills'/SKILL/'scripts'/SCRIPT
    if p.exists():
        sys.exit(subprocess.run([sys.executable, str(p), '<command>', '<options>']).returncode)
raise SystemExit(f'{SKILL} skill not found')
"
```

调用其它 skill 的脚本时，只改首行的 `SKILL, SCRIPT`，其余照抄
（例如 `SKILL, SCRIPT = 'codewiki-sync', 'main.py'`）。

**退出码会原样透传**，Step 2 / Step 3 的 `3 = needs_repo_selection` 依赖这一点。

Or directly (auto-detect config directory):
```bash
# OpenCode: ~/.config/opencode/skills/core-init/scripts/main.py
# ClaudeCode: ~/.cac/skills/core-init/scripts/main.py
```

**Steps**

1. **Determine project root**

   Use provided path or default to current working directory.

   Check if project already has a `docs/` directory:
   - If exists: Run in "update" mode (refresh specs)
   - If not exists: Run in "init" mode (create fresh)

2. **Generate `codegraph.json` and confirm exclusions (强制交互 + 防爆)** (SKILL layer executes)

   **【强制要求】这一步必须在任何扫描、索引、拉取动作之前执行。**
   **【强制要求】无论仓库数多少，都必须向用户提问一次排除目录，禁止 Agent 自行跳过。**

   **前提认知：用户不会自己创建配置文件。**
   所以这一步的职责是：**先把 `codegraph.json` 生成出来，再让用户决定排除什么**，
   而不是等用户凭空写一份配置。

   同时，用户经常在一个"工作区目录"下启动 `/core-init`，该目录可能包含几十个仓库。
   如果不加限制，后续 scan_language / multi-code-analysis / codewiki-sync
   会对每个仓库各跑一遍，直接爆掉。

   ---

   **Step 2a: 自动生成 `codegraph.json`（幂等，必须执行）**

   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'core-init', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'init-config', '--project-root', '<project_root>', '--json']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```

   行为：
   - `codegraph.json` **不存在** → 创建一份空骨架（见下方模板），`config_created: true`
   - `codegraph.json` **已存在** → **不覆盖、不改写**，只读取并回报当前内容，`config_created: false`
   - 无论哪种情况都会完成一次仓库扫描，并给出候选排除项

   自动生成的初始骨架：
   ```json
   {
     "exclude": [],
     "include": [],
     "extensions": {},
     "corespec": { "maxRepos": 5 }
   }
   ```

   Returns JSON:
   - `config_path`: 配置文件绝对路径（**必须展示给用户**）
   - `config_created`: `true` = 本次新建，`false` = 沿用已有
   - `config_content`: 当前配置内容
   - `status`: `ok` | `needs_repo_selection`
   - `scope.repos`: 发现的仓库列表（含 `name` / `path` / `language_hint`）
   - `scope.excluded_repos`: 已被 `codegraph.json` 排除的仓库
   - `scope.repo_count` / `scope.max_repos`: 仓库数与阈值（默认 5，可用 `corespec.maxRepos` 配置）
   - `scope.truncated`: 目录扫描预算耗尽（目录极大，列表不完整）
   - `suggested_exclude`: **候选**排除项 —— 扫描到的 `vendor/`、`static/`、已提交进仓库的
     三方 SDK / 前端主题等。**只是建议，脚本不会自动写入**，除非带 `--apply-suggestions`

   **Exit code 3 = `needs_repo_selection`（仓库数超阈值），必须停下来让用户选仓库，不允许继续。**

   ---

   **Step 2b: 向用户展示并提问（不可跳过）**

   把以下内容展示给用户，然后**停下来等回复**：

   ```
   已为你生成配置文件：<config_path>

   本次会纳入的仓库（<n> 个）：
   - repo_a  [java]
   - repo_b  [go]

   检测到的候选排除目录（尚未写入）：
   - **/vendor/**      (第三方依赖，已提交进仓库)
   - static/           (前端静态资源)

   请选择接下来怎么做：
   1. 直接告诉我要排除哪些目录（说人话即可，例如"排除 static 和所有 vendor 目录"），我来改配置
   2. 你自己改 <config_path>，改完告诉我一声，我继续
   3. 不需要排除，直接继续
   ```

   **禁止 Agent 替用户选择**，必须等待用户明确答复。

   ---

   **Step 2c: 按用户选择处理**

   **选项 1 —— 用户用自然语言描述（Agent 改配置）**

   把用户的描述翻译成 gitignore 风格模式，再写入配置：

   | 用户说 | 翻译成 |
      |--------|--------|
   | "排除 static 目录" | `--exclude "static/"` |
   | "所有 vendor 目录都不要" | `--exclude "**/vendor/**"` |
   | "第三方 SDK 在 libs/sdk 下" | `--exclude "libs/sdk/"` |
   | "只保留 repo_a 和 repo_b" | `--repos repo_a,repo_b`（其余自动写入 exclude） |
   | "Tools 被 gitignore 了但要扫" | `--include "Tools/"` |

   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'core-init', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'set-repo-scope', '--project-root', '<project_root>', '--repos', 'repo_a,repo_b', '--exclude', 'static/,**/vendor/**']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```

   - `--repos`：**保留**的仓库名（逗号分隔），其余仓库自动写入 `exclude`
   - `--exclude`：额外的 gitignore 风格排除模式（对已被 git 跟踪的目录同样生效）
   - `--include`：被 `.gitignore` 忽略、但确实是第一方源码的路径
   - `--max-repos`：写入 `corespec.maxRepos`，调整阈值
   - `--reset`：先清空已有 `exclude` 再写

   写完后**把最终的 `exclude` 列表和纳入的仓库回读给用户确认一遍**，含糊的描述
   （如"把没用的都去掉"）必须追问清楚，不许自行猜测。

   **选项 2 —— 用户自己改配置文件**

   - 输出 `config_path` 的**绝对路径**和当前文件内容
   - 附上可用字段说明（见下方 "Repo Scope Configuration"）和一份可直接粘贴的示例
   - 然后**暂停**，等用户说"改好了 / 继续"再执行 Step 2d
   - **禁止**在用户确认前继续，也**禁止**猜测用户改了什么

   **选项 3 —— 不需要排除**

   - 不写任何 `exclude`，配置保持空骨架，直接进入 Step 2d
   - **例外**：若 Step 2a 返回 exit code 3（仓库数超阈值），选项 3 **不可用** ——
     必须先用 `--repos` 选定仓库范围，或用户明确要求 `--force`

   ---

   **Step 2d: 复核（必须执行）**

   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'core-init', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'scan-repos', '--project-root', '<project_root>', '--json']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```

   - `status == "ok"` → 进入 Step 3
   - `status == "needs_repo_selection"`（exit 3）→ 回到 Step 2b 重新询问，**不要重试、不要 `--force`**

   ---

   **Step 2e: 例外情形**

   - 用户明确说"我知道有很多仓，全都要"时，才可以带 `--force` 跳过守卫。
     **禁止 Agent 自行决定 `--force`。**
   - `--skip-scope-prompt`（自动化 / CI）：跳过 2b 提问，沿用现有 `codegraph.json`。
     **只有用户显式传入时才生效**，Agent 不得自行添加。
   - **update 模式**（`docs/` 与 `codegraph.json` 均已存在）：仍需展示当前仓库范围，
     但提问可简化为"沿用现有配置吗？"，用户确认沿用即可进入 Step 3。

3. **Execute Python script to init project structure** (SKILL layer executes)

   Execute the Python script to initialize the project:
      ```bash
      python -c "
      import sys, subprocess
      from pathlib import Path
      SKILL, SCRIPT = 'core-init', 'main.py'
      for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
          p = base/'skills'/SKILL/'scripts'/SCRIPT
          if p.exists():
              sys.exit(subprocess.run([sys.executable, str(p), 'init', '--project-root', '<project_root>']).returncode)
      raise SystemExit(f'{SKILL} skill not found')
      "
      ```

   This init the basic docs directory structure (archive/, changes/, specs/, etc.)
   and runs `codegraph init` + `codegraph index` honouring `codegraph.json`.

   Create the following directory structure:
      ```
     <project_root>/
     ├── codegraph.json        # repo scope / index config (由 Step 2 自动生成，user owned)
     └── docs/
         ├── specs/            # [Full Docs Area] Full project specs
         ├── changes/          # [Delta Change Area] Active changes
         └── archive/          # Archived changes
      ```

   **`init` 同样带有防爆守卫**：若仓库数超阈值仍会以 exit code 3 返回
   `needs_repo_selection`，此时回到 Step 2b。

   Options:
   - `--no-index`：跳过 `codegraph index`（大仓库先只建结构时使用）
   - `--max-repos N` / `--force`：同 Step 2

4. **Detect repo environment and generate language.json** (SKILL layer executes)

   **IMPORTANT: This step is mandatory for both single-repo and multi-repo scenarios.**

   Execute language detection script (core-init own script):
     ```bash
     python -c "
     import sys, subprocess
     from pathlib import Path
     SKILL, SCRIPT = 'core-init', 'scan_language.py'
     for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
         p = base/'skills'/SKILL/'scripts'/SCRIPT
         if p.exists():
             sys.exit(subprocess.run([sys.executable, str(p), '--root', '<project_root>']).returncode)
     raise SystemExit(f'{SKILL} skill not found')
     "
     ```

   This script:
   - Discovers repos through the **same bounded scanner + `codegraph.json` filter** as Step 2
   - Scans file extensions to detect programming languages per repo
     (capped at 30000 files per repo, excluded directories are pruned)
   - Generates `docs/language.json`:
     ```json
     {
       "<repo_name>": {
         "languages": [{"name": "java", "percentage": 82.5, "role": "primary"}],
         "repo_url": "git@..."
       }
     }
     ```
   - **If no code files found**: falls back to marker files, then to `python`
   - **If too many repos**: writes nothing, exits with code 3 and
     `status: "needs_repo_selection"` → 回到 Step 2b

5. **Invoke multi-code-analysis skill** (SKILL layer executes)

   **【强制要求】**：
   - **不许调 subagent 执行** - 此步骤必须由当前 Agent 直接执行，不允许委托给子 agent
   - **严格按照 multi-code-analysis SKILL.md 执行** - 参考 `skills/multi-code-analysis/SKILL.md` 的完整流程，不得跳过任何步骤或自行发明命令
   - **只处理 `docs/language.json` 中列出的仓库**，被 `codegraph.json` 排除的仓库不得扫描

   After language detection, invoke multi-code-analysis skill to get code dependency.

   **范围已自动收敛**：multi-code-analysis v5.0 的数据源是 `codegraph.db`，
   而 Step 3 的 `codegraph index` 本身就遵守 `codegraph.json` 的 `exclude`/`include`
   —— 被排除的仓库根本不在库里，所有 SQL 查询天然限定在范围内，**无需额外传参**。
   走文件系统的 `tree-all` 由 `multi-code-analysis/scripts/repo_scope.py` 读同一份配置过滤。

   **Generated files** :
   - `docs/relationship.md` (logical view - Agent generates based on SQL query results)
   - `docs/graph.json` (dependency graph data - 仅 legacy `scan-deps` 路径产出)
   - `docs/codeCapInfo/` (directory trees and repo metadata - 仅 `tree-all` 产出，
     临时文件，relationship.md 生成后必须删除)

   **⚠️ 嵌套仓库命名**：SQL 用 `file_path` 的顶层目录代表仓库，二级仓库
   （如 `group/sub_a`）在 SQL 结果里显示为 `group`，与 `docs/language.json`
   的键 `group/sub_a` 不一致。生成 relationship.md 时以 language.json 的键为准做映射，
   否则同一父目录下的多个子仓会被合并统计。

   **退出码 3** = 仓库过多，回到 Step 2b 询问用户，禁止自行 `--force` 重试。

   See `skills/multi-code-analysis/SKILL.md` for detailed flow.

6. **Check and invoke codewiki-sync skill** (SKILL layer executes)

   After `multi-code-analysis` completes, SKILL layer must check existing spec documents before invoking codewiki-sync.

   **【强制要求】**：
   - **不许调 subagent 执行** - 此步骤必须由当前 Agent 直接执行
   - **先检查文档是否存在且有实质内容，再决定是否调用 codewiki-sync**
   - **仓库列表来自 `docs/language.json`**（已按 `codegraph.json` 过滤），不得再次全盘扫描

   **Step 6a: Check if specs need sync** (execute via script):

      ```bash
      python -c "
      import sys, subprocess
      from pathlib import Path
      SKILL, SCRIPT = 'core-init', 'main.py'
      for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
          p = base/'skills'/SKILL/'scripts'/SCRIPT
          if p.exists():
              sys.exit(subprocess.run([sys.executable, str(p), 'check-sync', '--project-root', '<project_root>', '--json']).returncode)
      raise SystemExit(f'{SKILL} skill not found')
      "
      ```

   This script returns JSON with:
   - `skip_codewiki_sync`: `true` if all repos have substantial spec content
   - `repos_needing_sync`: list of repos that need codewiki-sync
   - `repos_skipped`: list of repos that already have substantial content

   **Step 6b: Invoke codewiki-sync based on check result**:

   **【强制要求】**：
   - **每个仓库同步完成后，必须等待 module-spec 生成完成，再继续下一个仓库**
   - **禁止在 module-spec 生成完成前切换到其他仓库或报告完成**

   **Multi-repo handling**:

   a. **Multi-repo scenario**:
   - Read JSON output from step 6a
   - Only iterate through repos in `repos_needing_sync`
   - **For each sub-repo needing sync, execute in sequence** (one repo at a time):
   1. Execute codewiki-sync sync:
   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'codewiki-sync', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'sync', '--path', '<sub_repo_path>']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```
   2. **If sync succeeds and generates module-level docs** (check for `spec_prompt.md` files):
   - **Agent 必须为每个模块生成真实的 spec.md**：
   1. 执行 module-spec 生成获取模块列表和生成指引：
   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'codewiki-sync', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'generate', '--path', '<sub_repo_path>', '--step', 'module-spec', '--json']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```
   2. 读取 JSON 输出中的 `module_docs` 列表，对于每个模块（特别是 `is_placeholder=true` 的模块）：
   - 读取 `<module>/spec_prompt.md` 获取生成 prompt
   - 读取 `<module>/design.md` 了解模块设计
   - 基于 prompt 和 design 生成真实的 spec.md 内容
   - 将内容写入 `<module>/spec.md`
   3. 生成完成后删除各模块的 `spec_prompt.md` 和 `docs/specs/SYNC_MODULE_SPEC_GUIDE.md`
   - **必须等待所有模块的 spec.md 生成完成，再继续下一个仓库**
   - **【强制约束】禁止在 module-spec 生成完成前切换仓库或报告完成**
   3. **If CodeWiki pull fails for any sub-repo, prompt user for local generation**:
   - codewiki-sync 本身支持交互式询问用户是否触发本地生成
   - 参见 codewiki-sync SKILL.md 中的"交互式选择"说明
   - **由用户决定是否触发生成本地文档**
   - **【强制约束】如果用户选择本地生成，Agent 必须：**
   1. **执行完整的 6 步生成流程**，不能只生成 LOCAL_GENERATION_GUIDE.md 就跳过
   2. 6 步流程：planning → module → design → spec → compose → module-spec
   3. 在 Step 6 (module-spec) 完成后，才能删除 .generation 目录
   4. **禁止在流程中途删除 .generation 目录或切换仓库**
   5. 如果 `generate --step module-spec --json` 返回 `require_full_flow: true`，必须按指引执行完整流程
   4. **Only after module-spec generation completes, proceed to next repo**
   - Documents are written to **each sub-repo's internal `docs/specs/`** directory (e.g., `repo_a/docs/specs/spec.md`)
   - **If `skip_codewiki_sync` is `true`, skip the entire step**
   - **多仓场景下本地生成同样适用**：用户可选择拉取分支或本地生成，与单仓场景一致

   b. **Single-repo scenario**:
   - Read JSON output from step 6a
   - If `skip_codewiki_sync` is `true`, skip codewiki-sync entirely
   - Otherwise, execute codewiki-sync sync:
   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'codewiki-sync', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'sync', '--path', '<project_root>']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```
   - **If sync succeeds and generates module-level docs** (check for `spec_prompt.md` files):
   - **Agent 必须为每个模块生成真实的 spec.md**：
   1. 执行 module-spec 生成获取模块列表和生成指引：
   ```bash
   python -c "
   import sys, subprocess
   from pathlib import Path
   SKILL, SCRIPT = 'codewiki-sync', 'main.py'
   for base in (Path.home()/'.config'/'opencode', Path.home()/'.cac'):
       p = base/'skills'/SKILL/'scripts'/SCRIPT
       if p.exists():
           sys.exit(subprocess.run([sys.executable, str(p), 'generate', '--path', '<project_root>', '--step', 'module-spec', '--json']).returncode)
   raise SystemExit(f'{SKILL} skill not found')
   "
   ```
   2. 读取 JSON 输出中的 `module_docs` 列表，对于每个模块（特别是 `is_placeholder=true` 的模块）：
   - 读取 `<module>/spec_prompt.md` 获取生成 prompt
   - 读取 `<module>/design.md` 了解模块设计
   - 基于 prompt 和 design 生成真实的 spec.md 内容
   - 将内容写入 `<module>/spec.md`
   3. 生成完成后删除各模块的 `spec_prompt.md` 和 `docs/specs/SYNC_MODULE_SPEC_GUIDE.md`
   - **If CodeWiki pull fails, prompt user for local generation**:
   - codewiki-sync 本身支持交互式询问用户是否触发本地生成
   - 参见 codewiki-sync SKILL.md 中的"交互式选择"说明
   - **由用户决定是否触发生成本地文档**
   - **【强制约束】如果用户选择本地生成，Agent 必须：**
   1. **执行完整的 6 步生成流程**，不能只生成 LOCAL_GENERATION_GUIDE.md 就跳过
   2. 6 步流程：planning → module → design → spec → compose → module-spec
   3. 在 Step 6 (module-spec) 完成后，才能删除 .generation 目录
   4. **禁止在流程中途删除 .generation 目录或报告完成**
   5. 如果 `generate --step module-spec --json` 返回 `require_full_flow: true`，必须按指引执行完整流程

   The skill will handle project discovery, fetching from CodeWiki, and local generation if needed.
   See `skills/codewiki-sync/SKILL.md` for detailed flow.

   **Important**: If codewiki-sync requires user decision (e.g., project selection) and user cancels,
   **do NOT create placeholder files**. Report the error and let user decide next action.

**Repo Scope Configuration (`codegraph.json`)**

核心思路：**用 CodeGraph 自己的配置文件作为唯一事实来源**，既控制 CodeGraph 索引什么，
也控制 core-init 把哪些仓库纳入流程。参考
https://colbymchenry.github.io/codegraph/getting-started/configuration/

文件位置：`<project_root>/codegraph.json`
**由 Step 2a 自动生成**（不存在时创建空骨架，已存在时保持原样不覆盖），之后归用户所有。

自动生成的骨架：
```json
{
   "exclude": [],
   "include": [],
   "extensions": {},
   "corespec": { "maxRepos": 5 }
}
```

用户确认排除项后的典型形态：
```json
{
   "exclude": ["legacy-repo/", "static/", "**/vendor/**"],
   "include": ["Tools/"],
   "includeIgnored": ["packages/"],
   "extensions": { ".tpl": "php" },
   "corespec": { "maxRepos": 8 }
}
```

| Key | 作用 | 谁在用 |
|-----|------|--------|
| `exclude` | gitignore 风格模式，**对已被 git 跟踪的目录同样生效**（这正是排除已提交的 vendor 主题/SDK 的正确工具） | CodeGraph + core-init 仓库发现 |
| `include` | 被 `.gitignore` 忽略但确实是第一方源码的路径（如 SVN/P4 并存的目录）。**显式 `exclude` 优先级更高** | CodeGraph + core-init |
| `includeIgnored` | 被 gitignore 的目录下的嵌套 git 仓库仍要索引（super-repo 场景） | CodeGraph |
| `extensions` | 非标准后缀映射到已支持语言 | CodeGraph |
| `corespec.maxRepos` | core-init 防爆阈值（默认 5） | core-init |

模式匹配语义（core-init 侧实现的是 gitignore 的实用子集）：
- `name` → 匹配任意层级中名为 `name` 的目录
- `dir/`、`a/b` → 匹配该路径及其下所有内容
- `**/vendor/**` → 任意深度的 `vendor`
- `!keep/` → 取反，最后匹配的模式生效
- 内置跳过项（`node_modules`、`dist`、`.git` 等）永远不会被重新纳入

修改 `exclude` / `include` / `includeIgnored` / `extensions` 后需要重新索引：`codegraph index`
（`main.py init` / `update` 默认会自动执行，除非带 `--no-index`）

**Output On Success**

```
## CoreSpec Project Initialized

**Project Root:** <path>
**Mode:** init/update
**Config:** <path>/codegraph.json  (created by /core-init / reused)
**Repos in scope:** repo_a, repo_b  (excluded: repo_c, repo_d — codegraph.json)
**Excluded patterns:** static/, **/vendor/**  (由用户确认)

### Fetched Specs:
- Multi-repo Analysis: ✓ relationship.md and graph.json generated

### Generated Specs:
- Full specs: docs/specs/spec.md and docs/specs/design.md (fetched from CodeWiki or generated locally - single-repo and multi-repo)
- Multi-repo relationship: docs/relationship.md (logical view)
- Dependency graph: docs/graph.json and docs/codeCapInfo/ (dependency data)
- Multi-repo specs: Each sub-repo's internal `docs/specs/` (fetched from CodeWiki or generated locally)

### Next Steps (SKILL Layer):
1. 在实施变更时填充 spec.md 和 design.md
2. 后续想调整范围，直接改 <path>/codegraph.json 再跑 `/core-init --update`

### Workflow After Init:
```
1. /core-explore <需求描述>   # 需求澄清和探索
2. /core-design <变更名称>   # 确认需求后开始设计
3. /core-apply                # 实施变更 (同时填充 spec.md 和 design.md)
4. /core-archive              # 归档完成变更
```

### Directory Structure:
codegraph.json         # Repo scope / index config (由 /core-init 自动生成，user owned)
docs/
├── language.json      # Repo language and URL mapping (from scan_language.py)
├── relationship.md    # Multi-repo dependency logical view (Agent generated)
├── graph.json         # Dependency graph data (from multi-code-analysis)
├── codeCapInfo/       # Repo metadata and directory trees (temp, will be deleted)
├── specs/             # Full specs (via codewiki-sync, supports local generation)
│   ├── spec.md        # Full project specification
│   └── design.md      # Full project design
├── changes/           # Active changes
└── archive/           # Archived changes

### Multi-repo Directory Structure:
<multi_repo_root>/
├── codegraph.json     # Repo scope config (auto-generated)
├── repo_a/            # Sub-repo A
│   └── docs/specs/    # Sub-repo A's specs (fetched from CodeWiki or generated locally)
│       ├── spec.md
│       └── design.md
├── repo_b/            # Sub-repo B
│   └── docs/specs/    # Sub-repo B's specs (fetched from CodeWiki or generated locally)
│       ├── spec.md
│       └── design.md
└── docs/              # Root docs (shared artifacts: language.json, relationship.md, graph.json, etc.)
```

**Output On Scope Confirmation (Step 2b, 每次 init 都会出现)**

```
## CoreSpec Init - 确认仓库范围

**Config:** <path>/codegraph.json  （已自动生成）
**Discovered:** 2 repos
- repo_a  [java]
- repo_b  [go]

**候选排除目录（尚未写入）:**
- **/vendor/**   第三方依赖，已提交进仓库
- static/        前端静态资源

请选择：
1. 告诉我要排除什么（自然语言即可），我来改配置
2. 你自己改 <path>/codegraph.json，改完说一声
3. 不需要排除，直接继续
```

**Output On Repo Scope Required (exit code 3)**

```
## CoreSpec Init Paused - 仓库过多

**Project Root:** <path>
**Config:** <path>/codegraph.json  （已自动生成，等待你确认范围）
**Discovered:** 23 repos (limit 5)

请选择本次要纳入的仓库（其余会写入 codegraph.json 的 exclude）：
- repo_a  [java]
- repo_b  [go]
- ...

你可以：
1. 直接告诉我要哪几个仓 / 要排除哪些目录，我来写配置
2. 自己编辑 <path>/codegraph.json 后告诉我继续

（仓库数超阈值时不能选"不排除"，必须先收敛范围）
```

**Output On Update**

```
## CoreSpec Project Updated

**Project Root:** <path>
**Mode:** update
**Config:** <path>/codegraph.json (沿用现有配置)

### Refreshed Specs:
- Multi-repo Analysis: ✓ relationship.md and graph.json generated

Previous specs backed up to docs/backup/
```

**Guardrails**
- **`codegraph.json` 必须由 Step 2a 自动生成**，绝不要求用户凭空手写配置文件
- **已存在的 `codegraph.json` 绝不覆盖**，只读取并展示
- **每次 init 都必须问一次"有没有要排除的目录"**，禁止 Agent 自行跳过或替用户决定
- 用户选择"自己改配置"时，**必须暂停等待用户确认改完**，禁止猜测其修改内容
- 自然语言转排除模式后，**必须回读最终配置给用户确认**；描述含糊时追问，不许臆测
- **仓库数超过 `maxRepos` 时必须停下来询问用户，禁止 Agent 自行 `--force`**
- **exit code 3 = needs_repo_selection**，不是失败，不要重试，去问用户
- 只对 `docs/language.json` 中的仓库执行后续步骤
- If project already initialized, ask before overwriting
- Backup existing specs before refresh
- Show clear summary of what was fetched/merged
- Handle remote fetch failures gracefully
- Validate project.md if it exists

**Layered Spec Fetching**

The layered spec system follows this hierarchy:
```
Company Spec
    ↓
Product Line Spec
    ↓
PDU Spec
    ↓
Department Spec
    ↓
Team Spec (most specific)
```

Each level inherits from the level above it.
