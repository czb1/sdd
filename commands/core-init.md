---
description: Initialize or update a CoreSpec project (core-init)
---

# /core-init

Initialize or update a CoreSpec project with specs from remote repositories.

## Overview

`/core-init` sets up a new CoreSpec project or refreshes existing specs. It handles
**配置文件生成 + 排除目录确认**、project initialization、layered spec fetching、
and module design generation.

**你不需要自己写配置文件。** `/core-init` 第一步会自动扫描工作区并生成
`codegraph.json`，然后**停下来问你有没有要排除的目录**，你可以三选一：

| 选项 | 你要做的事 | Agent 要做的事 |
|------|-----------|----------------|
| 1️⃣ 自然语言 | 直接说"排除 static 和所有 vendor 目录" | 翻译成 gitignore 模式写进 `codegraph.json`，回读给你确认 |
| 2️⃣ 自己改 | 打开 Agent 生成好的 `codegraph.json` 改，改完说"继续" | 输出文件路径 + 当前内容 + 字段说明，然后**暂停等你** |
| 3️⃣ 不排除 | 说"不用排除" | 保持空配置，直接继续 |

**防爆**：如果启动目录下的仓库数超过阈值（默认 5），这一步是**强制**的 ——
必须先选定纳入哪些仓库（选项 3 不可用），选择结果写入 `codegraph.json`，
后续所有步骤都只处理这些仓库。

## Usage

```bash
/core-init [project-root] [options]
```

## Options

| Option | Description |
|--------|-------------|
| `--update` | Update existing specs instead of fresh init |
| `--max-repos N` | 仓库数阈值，超过则暂停询问（默认 5，也可写进 `codegraph.json` 的 `corespec.maxRepos`） |
| `--force` | 跳过仓库数守卫（确认要处理全部仓库时才用） |
| `--skip-scope-prompt` | 跳过"排除目录"提问，沿用现有 `codegraph.json`（自动化 / CI 场景） |
| `--apply-suggestions` | 生成配置时直接采纳自动检测出的候选排除项 |
| `--no-index` | 跳过 `codegraph index`（只建结构，稍后再索引） |
| `--json` | JSON output |

## Repo scope 配置（自动生成）

配置文件：`<project-root>/codegraph.json`（与 CodeGraph 共用，一份配置两处生效）

**首次运行时由 `/core-init` 自动创建**，初始内容是一份空骨架：

```json
{
  "exclude": [],
  "include": [],
  "extensions": {},
  "corespec": { "maxRepos": 5 }
}
```

Agent 会同时把**候选排除项**（扫描到的 `vendor/`、`static/`、已提交进仓库的三方目录等）
列给你看，但**不会自动写入** —— 除非你说要，或者你用了 `--apply-suggestions`。

确认后的配置大致长这样：

```json
{
  "exclude": ["legacy-repo/", "static/", "**/vendor/**"],
  "include": ["Tools/"],
  "includeIgnored": ["packages/"],
  "extensions": { ".tpl": "php" },
  "corespec": { "maxRepos": 8 }
}
```

- `exclude` 对**已被 git 跟踪**的目录也生效 —— 排除提交进仓库的 vendor 主题 / SDK 就用它
- 显式 `exclude` 优先于 `include`
- `node_modules`、`dist`、`.git` 等内置跳过项永远不会被重新纳入
- 改完配置需要重新索引：`codegraph index`（`/core-init` 默认自动执行）

### 自然语言 → 排除模式对照

告诉 Agent 时不用写模式，说人话就行，Agent 按下表翻译：

| 你说 | 写入 `codegraph.json` |
|------|----------------------|
| "排除 static 目录" | `"exclude": ["static/"]` |
| "所有 vendor 目录都不要" | `"exclude": ["**/vendor/**"]` |
| "第三方 SDK 在 libs/sdk 下，跳过" | `"exclude": ["libs/sdk/"]` |
| "只保留 repo_a 和 repo_b" | 其余仓库自动写入 `exclude` |
| "Tools 被 gitignore 了但要扫" | `"include": ["Tools/"]` |

### 手动 / 脚本方式

```bash
# 只生成配置文件并预览会纳入哪些仓（不修改任何东西）
main.py init-config --project-root . --json

# 只保留这几个仓，其余自动写入 exclude
main.py set-repo-scope --project-root . --repos repo_a,repo_b --exclude "static/,**/vendor/**"

# 预览当前会纳入哪些仓
main.py scan-repos --project-root . --json
```

## Examples

```bash
# Initialize new project（会生成 codegraph.json 并询问排除目录）
/core-init

# Initialize in specific directory
/core-init /path/to/project

# 工作区里有 8 个仓，全都要
/core-init --max-repos 10

# 直接采纳自动检测出的候选排除项，少一轮问答
/core-init --apply-suggestions

# CI / 自动化：沿用已有配置，不提问
/core-init --skip-scope-prompt

# Update existing specs
/core-init --update
```

## Invokes

`skills/core-init` skill which:
1. Detects project state (init/update mode)
2. **生成 `codegraph.json` 并确认排除目录（强制交互 + 防爆）**：自动创建配置文件，
   向用户提问是否需要排除目录；仓库过多时必须先选定仓库范围
3. Creates project structure（并执行 `codegraph init` + `codegraph index`）
4. Generates `docs/language.json`（只针对 scope 内的仓库）
5. Invokes multi-code-analysis skill to scan multi-repo dependencies and generate relationship.md
6. Invokes code-rule-skills skill to fetch layered specs
7. After code-rule-skills completes: invoke codewiki-sync skill
8. codewiki-sync fetches from CodeWiki or generates full spec.md and design.md

## Exit codes

| Code | 含义 | 处理方式 |
|------|------|----------|
| 0 | 成功 | 继续 |
| 1 | 错误 | 报告用户 |
| 3 | `needs_repo_selection` | **不是失败**，向用户展示仓库列表并让其选择，不要重试 |

## Output

```
📁 位置: <path>/docs

### 仓库范围:
- 纳入: repo_a, repo_b   （已排除: repo_c, repo_d — codegraph.json）
- 配置文件: <path>/codegraph.json  （本次自动生成 / 沿用已有）

### 生成的文件:
- codegraph.json        # 仓库范围 / 索引配置（由 /core-init 自动生成，用户可手改）
- docs/rule.md          # 由 code-rule-skills 自动生成
- docs/language.json    # 由 core-init scan_language.py 自动生成（仓库语言和URL）
- docs/relationship.md  # 由 multi-code-analysis + Agent 自动生成（多仓库依赖关系逻辑视图）
- docs/graph.json       # 由 multi-code-analysis 自动生成（依赖图数据）

### 多仓场景额外生成:
- 各仓内部 `docs/specs/` # 由 codewiki-sync 从 CodeWiki 拉取（仅拉取，不本地生成）

✅ 项目初始化完成

📁 位置: <path>/docs
📋 下一步: 运行 `/core-explore` 开始需求探索
```

## Related Commands

| Command | Description |
|---------|-------------|
| `/core-explore` | Explore requirements |
| `/core-design` | Design documents |
| `/core-apply` | Implement changes |
| `/core-verify` | Verify implementation |
| `/core-archive` | Archive completed changes |
