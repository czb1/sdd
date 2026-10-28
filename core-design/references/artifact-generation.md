# Phase 8: 生成设计文档（单仓模式指令文件）

> 本文件为 Phase 8 单仓生成流程的指令文件（GATE:REF 无条件加载）。多仓模式由 M-2 替代（见 references/multi-repo.md M-2）。

**动作**：Python 脚本生成模板后，Agent 必须执行内容填充。

## 测试策略读取（生成 tasks.md 前）

读取配置确定测试策略（**零交互**，不弹 AskUserQuestion）：
1. 项目级：`<项目根>/docs/config.yaml` 的测试策略字段（**优先**；用户改这里即覆盖全局默认）
2. 全局级：`~/.corespec/flow-config.json` 的顶层 `test_strategy`（**默认值来源**；core-init 生成项目 config.yaml 时参考此值，无项目级字段时生效）
3. 缺省：`test-after`

测试策略为 `tdd` 时：
1. **生成顺序约束**：delta_test_design.md 必须先于 tasks.md 完成：
   - 先生成 delta_test_design.md（测试设计，TC 全量）
   - **确认其 TC 完整、格式正确**（含测试用例章节、每个 TC 有前置/步骤/预期）
   - 再生成 tasks.md（此时每任务"覆盖用例"字段的来源已就绪）
   - 注：不改变制品 DAG 依赖关系（schema.yaml 的 requires 不变），仅调整 core-design 阶段内的执行顺序
2. 用现有 tasks.md 模板生成 tasks.md
3. 调用派生脚本 `python scripts/tasks_tdd_deriver.py --change <change-name> --project-root <项目根>` 应用 tdd 差异
   （头部测试策略字段 / 每任务覆盖用例+测试文件路径+测试命令字段 / 依赖图节点标注）
4. 每任务"覆盖用例"字段引用 delta_test_design.md 对应 TC 编号——
   **必须保证全部 TC 被覆盖**（自检项，派生脚本会校验）

测试策略为 `test-after` / 无字段（缺省）时：**不执行上述生成顺序约束**，
按基线流程生成 delta_test_design.md 与 tasks.md（顺序与改造前一致）。

## 8.1 读取参考文档

生成模板后，Agent 必须读取以下参考文档进行填充：

| 优先级 | 文档 | 路径 | 用途 |
|--------|------|------|------|
| P0 | delta_spec.md | `docs/changes/<change-name>/delta_spec.md` | 提取需求内容 (ADDED/MODIFIED/REMOVED) |
| P0 | 项目级 design.md | `docs/specs/design.md` | 提取全局架构设计和技术选型 |
| P0 | 相关模块级 design.md | `docs/specs/<module-name>/design.md` | 提取受影响模块的设计细节 |
| P1 | 项目级 spec.md | `docs/specs/spec.md` | 提取全局规格说明和模块关系 |
| P2 | expert_experience.md | `docs/changes/<change-name>/expert_experience.md` | 仅在存在且适用时复用已有经验，不要求生成此文件 |

## 8.2 填充模板占位符

根据参考文档内容，替换模板中的占位符：

**语言一致性要求**：
- **必须使用与 delta_spec.md 相同的语言填充**
- 如果 delta_spec.md 是中文，则 tasks.md 中的任务描述、验收标准等**必须使用中文**
- 不要自行翻译或转换为英文

| 占位符 | 填充来源 | 必须对照的 reference | 示例 |
|--------|---------|---------------------|------|
| `<变更名称>` | delta_spec.md 概述/背景 | — | FST支持按namespace粒度部署HisecAgent框架 |
| `<设计目标>` | delta_spec.md 核心能力 | — | 新增custom_selector部署模式 |
| `<受影响模块>` | delta_spec.md 影响分析 | design-principles.md P-1 | paas-om, pcm, 前端 |
| `<原则1><原则2>` | delta_spec 约束 + design-principles.md P-1~P-10 选取与当前需求相关的原则 | design-principles.md | 架构一致性、入口出口明确 |
| `<技术选型>` | Phase 7 专家经验 | design-principles.md P-7 | 优先使用项目现有技术栈 |
| `## 设计决策` 章节 | 注入 step3返回的规范集合： `language-specific design specifications` + Phase 7 专家经验 | design-principles.md P-3, P-4 | — |
| 3.1 核心模块设计 | delta_spec + 代码理解 + design-principles.md | design-principles.md P-1, P-2, P-6; design-views.md §1 | 类图必须产出 |
| 6.1 核心流程设计 | delta_spec + 代码理解 | design-views.md §1 | 时序图必须产出（含异常路径） |
| 2.1 整体架构 | 全局 design.md | design-principles.md P-1; design-views.md §1 | 架构图必须产出 |
| 2.2 模块划分 | 全局 design.md | design-principles.md P-1, P-7; design-views.md §1 | 模块依赖图必须产出 |

## 8.3 填充注意事项

以下要点在填充时应注意遵循，减少后续审核（Phase 9 cross-doc-checker + Phase 10 design-doc-reviewer）的修复轮次：

1. 不保留未填充的占位符 `<...>` — Phase 10 CHECK-R7.3 会检测截断/占位符
2. 需求引用应包含 delta_spec.md 的具体需求内容 — Phase 9 CHECK-R11-L2 会验证 spec→design 追溯
3. 规范约束应包含 step3 返回的 `language-specific design specifications` — Phase 10 CHECK-R7.1 会检查章节完整性
4. tasks.md 使用 checkbox 格式 `- [ ]` — Phase 10 CHECK-R7.5c 会验证 tasks-delta_design 一致性
5. 每个代码生成任务应包含 `设计锚点` 字段 — Phase 9 CHECK-R11-L3 会验证 design→tasks 追溯
6. 1.2 设计原则章节应包含 design-principles.md 中与当前需求相关的原则 — Phase 10 CHECK-R12.1 会验证视图完整性
7. design-views.md §1 必须视图应全部产出，§2 条件视图按触发条件产出 — Phase 10 CHECK-R12.1 会验证视图完整性

## 8.4 tasks.md 结构 + 8.5 设计锚点提取

必须读取 **references/tasks-md-guidance.md**（tasks.md 结构指导、任务形成后的云见 CLI 能力查找与关联、锚点格式规范及提取示例），在生成任务后先准备候选并按任务组批量确认，再去重下载、原子替换项目级 Skill 并回写 tasks.md 的 Skill 字段。此动作不受 expert_experience 开关控制。

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

# --query 如有提供，由 Agent 用作任务形成后的云见 CLI 查找关键词参考。
# 不通过旧生成脚本触发独立经验获取。
```

The scripts:
1. Read from schema.yaml to get artifact templates
2. Inject expert knowledge into generated artifacts

After context is prepared, invoke the design generation:

```
For each artifact to generate:
- Read context files (delta_spec.md, `language-specific design specifications`, similar changes, Phase 7 expert experience context)
- Generate artifact with references to context
- Ensure `language-specific design specifications` skill usage instructions are included in delta_design.md
- When applicable, integrate actually available experience into design decisions; after tasks are formed, follow this Skill’s consumption rules for CLI discovery and task associations
- **CRITICAL: Fill template placeholders with actual content before writing**
```
