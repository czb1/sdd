# Phase 8: 生成设计文档（单仓模式指令文件）

> 本文件为 Phase 8 单仓生成流程的指令文件（GATE:REF 无条件加载）。多仓模式由 M-2 替代（见 references/multi-repo.md M-2）。

**动作**：Python 脚本生成模板后，Agent 必须执行内容填充。

## 规则0：resolved 模板强制契约

`.templates/resolved/<artifact_id>.md`（用户裁剪/新增后的物化模板）是最高优先级基准：
- 产物 H2 + resolved 模板已有 H3 必须与物化模板**完全一致**，不得增删、不得重编号、不得从归档版本或兄弟仓恢复被删章节
- 用户裁剪掉的章节禁止恢复（如模板无"跨仓接口"章节，产物不得新增此 H2/H3；多仓场景按 m2-multi.md 规则2 处理）
- 用户自定义新增的章节必须保留（落入 resolved 模板已有 H3）
- **物化模板内声明的条件章节不得删除**——若条件不满足，章节填写"无"，章节本体保留
- 多仓场景下 shared_context 注入按 m2-multi.md 规则2 处理（条件追加独立 H2），单仓场景不追加
- **【禁止篡改物化模板】物化模板文件 `.templates/resolved/<artifact_id>.md` 是只读基准，禁止使用 Edit/Write 工具修改其内容**——包括但不限于：
  - 禁止将物化模板 H2 编号重编号为连续
  - 禁止删除物化模板中的章节
  - 禁止修改物化模板 H2/H3 标题文本
  - 物化模板编号跳跃是用户裁剪后的合法状态，**产物必须按物化模板的原始编号生成**
  - **违反此禁令即物化模板篡改**，审查器将通过 re-resolve 物化到临时目录后 diff 检测，发现篡改即 ERROR 并以临时物化文件为基准重新校验

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

**章节结构存在性校验（T2.5）**：
- 生成产物的章节顺序与编号按 `core_templates.resolve_template_channel('<artifact_id>')` 解析后有效模板的章节骨架（存在性校验），不固定章节号
- 下表"占位符"列中的章节名为解析后骨架的章节名（实际生成以物化模板为准）

| 占位符 | 填充来源 | 必须对照的 reference | 示例 |
|--------|---------|---------------------|------|
| `<变更名称>` | delta_spec.md 概述/背景 | — | FST支持按namespace粒度部署HisecAgent框架 |
| `<设计目标>` | delta_spec.md 核心能力 | — | 新增custom_selector部署模式 |
| `<受影响模块>` | delta_spec.md 影响分析 | design-principles.md P-1 | paas-om, pcm, 前端 |
| `<原则1><原则2>` | delta_spec 约束 + design-principles.md P-1~P-10 选取与当前需求相关的原则 | design-principles.md | 架构一致性、入口出口明确 |
| `<技术选型>` | Phase 7 专家经验 | design-principles.md P-7 | 优先使用项目现有技术栈 |
| `## 设计决策` 章节 | 注入 step3返回的规范集合： `language-specific design specifications` + Phase 7 专家经验 | design-principles.md P-3, P-4 | — |
| 核心模块设计章节 | delta_spec + 代码理解 + design-principles.md | design-principles.md P-1, P-2, P-6; design-views.md §1 | 类图必须产出 |
| 核心流程设计章节 | delta_spec + 代码理解 | design-views.md §1 | 时序图必须产出（含异常路径） |
| 整体架构章节 | 全局 design.md | design-principles.md P-1; design-views.md §1 | 架构图必须产出 |
| 模块划分章节 | 全局 design.md | design-principles.md P-1, P-7; design-views.md §1 | 模块依赖图必须产出 |

## 8.3 填充注意事项

以下要点在填充时应注意遵循：

1. 不保留未填充的占位符 `<...>`
2. 需求引用应包含 delta_spec.md 的具体需求内容
3. 规范约束应包含 step3 返回的 `language-specific design specifications`
4. tasks.md 使用 checkbox 格式 `- [ ]`
5. 每个代码生成任务应包含 `设计锚点` 字段
6. 1.2 设计原则章节应包含 design-principles.md 中与当前需求相关的原则
7. design-views.md §1 必须视图应全部产出，§2 条件视图按触发条件产出

**校验委托**：本步骤不在生成阶段执行骨架/规范一致性校验，全部校验由 `design-doc-reviewer` SKILL 在审查阶段统一执行（CHECK-R7.1 T1.10a 规则1 + T1.10b 规则2 + 其他 CHECK-ID）。生成后仅需确认产物已 Write 成功（存在性自检）。

## 8.4 tasks.md 结构 + 8.5 设计锚点提取

必须读取 **references/tasks-md-guidance.md**（tasks.md 结构指导、锚点格式规范及提取示例）。本阶段只生成任务；Skill 消费由 Phase 8 全部完成后的 `post-generate` 编排点按执行计划调度，`skill_consumption` 默认关闭，不能因读取结构指导而触发。

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

# --query 仅在执行计划启用 skill_consumption 时作为查找关键词参考，不会自动开启该步骤。
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
- Integrate existing design experience when applicable; additional task capability discovery and associations run only through the enabled post-generate skill_consumption entry.
- **CRITICAL: Fill template placeholders with actual content before writing**
```

## 8.6 模板物化 GATE（T2.9）

生成 delta_design.md / delta_test_design.md / tasks.md 前必须先执行物化并 Read 物化的解析后有效模板 `docs/changes/<change>/.templates/resolved/<artifact_id>.md`。

- **每次生成都必须重新执行** `python -m core_templates resolve <artifact_id> --materialize <change_dir>`——物化是覆盖式写入，确保物化文件反映用户层模板的最新修改（用户可能在上次生成后编辑了 `~/.corespec/core-schemas/spec-driven/templates/` 下的模板）。**禁止因物化文件已存在而跳过物化**
- 物化完成后 Read 物化文件，按物化骨架的 H2 章节顺序生成产物
- **物化失败（如 ValueError 模板完整性校验失败）时 MUST STOP**，按报错修复模板后重试
- 读取后输出: "GATE PASSED: .templates/resolved/<artifact_id>.md loaded"

## 8.7 剩余 artifact 循环（T5.2）

> **M5b T5.2 新增**：生成完内置 5 artifact 后，**必须**遍历有效 schema.yaml 的剩余 artifact（非内置），依次生成。**本子步骤为强制执行，禁止跳过**——即使"预期无非内置 artifact"，也必须先调 `load_schema()` 获取清单确认后才能跳过。

**【强制执行流程】**（内置 5 artifact 生成完成后立即执行）：
1. **【强制】调 `load_schema('spec-driven')` 获取有效 schema.yaml 的 artifacts 清单**（读取 L1+L2 overlay 合并后的有效 schema，含用户层 `~/.corespec/core-schemas/spec-driven/schema.yaml` 声明的新增 artifact）
2. 从清单中筛除内置 5 artifact（`proposal` / `delta_spec` / `delta_design` / `delta_test_design` / `tasks`），剩余即为非内置 artifact
3. **【DAG 分层过滤】** 只生成 `requires` 字段含 `delta_design` 或更下游 artifact 的非内置 artifact（即依赖设计阶段产物的 artifact，由 core-design 生成）。`requires: []` 或 `requires` 仅含 proposal/delta_spec 的非内置 artifact（如 `proposal-data`）属 core-explore 环节，**core-design 跳过不生成**（已在 core-explore T5.2 生成）
4. **存在符合 DAG 分层的非内置 artifact 时**：对每个 artifact，依次执行：
   - 调 `python -m core_templates resolve <artifact_id> --materialize <change_dir>` 物化模板到 `<change>/.templates/resolved/<artifact>.md`（**禁止篡改物化模板**，规则同规则0）
   - Read 物化模板，按骨架填充内容（参考本文件 8.2 填充规范）
   - Write 产物到 `<change_dir>/<artifact_id>.md`
   - 确认 Write 成功（存在性自检）
5. **无符合 DAG 分层的非内置 artifact 时**：记录"无剩余 artifact（core-design 分层），T5.2 跳过"并继续
6. **【禁止】**：禁止不调 `load_schema()` 就声称"无非内置 artifact"；禁止跳过本子步骤直接进入下一阶段；禁止生成属 core-explore 环节的 artifact（requires ⊆ {proposal, delta_spec}）

**触发条件**（信息性说明，非豁免理由）：
- L2 schema.yaml 声明了非内置 artifact（M5b 开放后）
- `load_schema()` 返回的 artifacts 列表中存在 `REQUIRED_BUILTIN_ARTIFACTS` 之外的 artifact id，且其 `requires` 含 `delta_design` 或更下游 artifact

## 8.8 用户层模板维护操作（可选，非主流程）

模板自定义命令（T3.1 init / T3.2 resolve / T3.3 validate / T3.4 remove+rename）属于用户层维护操作，非 Phase 8 主流程步骤。用户主动需要时才执行：

- **首次使用请先阅读使用指南**：`core-shared/references/template-guide.md`（模板自定义使用指南 — 三层模板架构、双通道解析、端到端使用流程、验证方法；也可执行 `python -m core_templates --guide` 输出全文；用户层模板在首次运行任意 core-* skill 时已自动初始化到 `~/.corespec/core-schemas/spec-driven/templates/`）
- **命令参考**：`core-shared/references/template-commands.md`（T3.1~T3.4 子命令的参数、产出、约束，用户主动需要时 Read 该文件执行）
- **T3.2 `resolve --materialize`**：已在 §8.6 物化 GATE 中执行（本文件），多仓见 `references/m2-multi.md` 步骤 4
- **T3.1 `init` / T3.3 `validate` / T3.4 `remove` / `rename`**：用户主动调用时 Read `core-shared/references/template-commands.md` 执行

