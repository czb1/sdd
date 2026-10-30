# 模板自定义命令（T3.1 / T3.2 / T3.3 / T3.4）

> 唯一真相源文件位于 core-shared（框架共享）目录：`coreharness-spec/skills/core-shared/references/template-commands.md`，随 coreharness-spec 包分发。
> core-init / core-design / core-explore 等消费 skill 的 SKILL.md 通过 GATE:REF 引用本文件，不在骨架中内嵌命令细节。
>
> **首次使用？** 请先阅读 [模板自定义使用指南](template-guide.md)（同目录），了解三层模板架构、双通道解析、端到端使用流程和验证方法。本文件为命令参考，侧重参数和产出。
> 也可以执行 `python -m core_templates --guide` 输出使用指南全文；`init` 命令执行后会自动同步指南到 `~/.corespec/template-guide.md`。

CoreSpec 支持用户层模板自定义。`core_templates.py`（位于 `core-shared/scripts/core_templates.py`）提供五个子命令（init / resolve / validate / remove / rename），覆盖用户层模板的初始化复制、产物物化、完整性校验、增量维护全生命周期。

目录：T3.1 init → T3.2 resolve / materialize → T3.3 validate → T3.4 remove / rename。

## T3.1 `init` 子命令（用户层模板复制）

**用途**：将内置模板复制到用户层 `~/.corespec/core-schemas/<schema>/templates/`，用户可在不修改内置 `templates/` 的前提下按需修改章节、增加字段。

**归属环节**：core-init 主流程完成（Step 6b execute_sync 后）后的可选维护操作。非 init/update 6 Step 主流程的一部分，用户主动需要时才执行。

**使用场景**：

- 项目有自定义章节需求（如新增"风险与对策"章节），且希望全局生效（所有使用本机的 CoreSpec 项目共享）
- 需要在 `proposal.md`/`delta_spec.md` 等产物的章节顺序中插入产品特定章节
- 需要为某 schema（如 `spec-driven`）整体替换章节骨架，而非逐文件 patch

```bash
python -m core_templates init --skill spec-driven
# 或显式指定 schema（等价）：
python -m core_templates init --schema spec-driven
# 指定目标目录（默认 ~/.corespec/core-schemas/spec-driven/templates/）：
python -m core_templates init --skill spec-driven --project ~/.corespec/core-schemas/spec-driven
```

**参数说明**：

- `--skill <schema>`：`--schema` 的别名（模板自定义以 schema 为作用域，与 skill 一一对应）。二者任选其一，同时给出时 `--skill` 优先。
- `--project <dir>`：目标根目录。省略时默认 `~/.corespec/core-schemas/<schema>/`。

**预期产出**（已存在则跳过，不覆盖用户修改）：

```text
~/.corespec/core-schemas/spec-driven/templates/
├── manifest.json          # 模板清单（artifact id + requires 依赖）
├── version.json           # 版本号（与内置版本同步）
├── proposal.md            # proposal 模板骨架
├── delta_spec.md          # delta_spec 模板骨架
├── delta_design.md        # delta_design 模板骨架
├── tasks.md               # tasks 模板骨架
└── delta_test_design.md   # delta_test_design 模板骨架
```

**注意事项**：

- **版本同步**：`init` 时写入的 `version.json` 与内置 `templates/version.json` 字节级一致；后续内置模板升级时，用户需手动重新 `init` 或手动 merge
- **L3 项目模板优先**：若项目 `docs/core-schemas/<schema>/templates/` 存在（L3 层），解析器优先使用 L3；用户层（L2）次之；内置（L1）兜底

## T3.2 `resolve` 子命令（含 `--materialize`）

**用途**：解析指定 artifact 的有效模板（L1 内置 → L2 用户 → L3 项目逐层叠加），输出章节骨架。

```bash
# 仅输出到 stdout（不物化）：
python -m core_templates resolve <artifact_id> [--schema spec-driven]
# 物化到磁盘（GATE:REF 强制 Read 的物化文件）：
python -m core_templates resolve <artifact_id> --materialize <change_dir> [--schema spec-driven]
```

**参数**：

- `<artifact_id>`：artifact 标识（如 `proposal` / `delta_spec` / `delta_design` / `tasks` / `delta_test_design`）
- `--materialize <dir>`：物化到 `<dir>/.templates/resolved/<artifact>.md`（单仓和多仓共用同一物化路径，所有子仓共享同一物化文件）
- `--schema <schema>`：schema 名（默认 `spec-driven`）

**使用场景**：

- **生成产物前物化**：在 GATE:REF 强制 Read 物化文件前，由主会话执行 `resolve --materialize <change_dir>`，子代理仅 Read 物化文件获取章节骨架（禁止子代理各自解析模板层）
- **校验章节顺序**：单独执行 `resolve <artifact_id>` 查看当前有效模板章节顺序

**输出**：

- 无 `--materialize`：输出解析后的模板内容到 stdout（含 `<!-- template-v...` 头）
- 含 `--materialize`：输出 `Materialized: <path>` 提示，物化文件写入磁盘

### core-explore 阶段常用调用

core-explore 阶段主要用于 proposal / delta_spec 物化：

```bash
python -m core_templates resolve proposal --materialize <change_dir> [--schema spec-driven]
python -m core_templates resolve delta_spec --materialize <change_dir> [--schema spec-driven]
```

### core-design 阶段常用调用

core-design 阶段用于 delta_design / tasks / delta_test_design 物化：

```bash
python -m core_templates resolve delta_design --materialize <change_dir> [--schema spec-driven]
python -m core_templates resolve tasks --materialize <change_dir> [--schema spec-driven]
python -m core_templates resolve delta_test_design --materialize <change_dir> [--schema spec-driven]
```

## T3.3 `validate` 子命令（双缺口检测）

**用途**：校验用户层模板完整性，检测四类缺口。

```bash
python -m core_templates validate [--schema spec-driven]
```

**检测的 3 类缺口**：

1. **有模板无声明**：`templates/` 目录下存在 `.md` 文件，但 schema.yaml 未声明该 artifact
2. **有声明无模板**：schema.yaml 声明了 artifact，但 `templates/` 目录下找不到对应 `.md` 文件
3. **requires 引用不存在**：schema.yaml 中 `requires` 字段引用的 artifact_id 在当前清单中不存在

**输出**：

- 缺口为空：返回 rc=0，输出 "All templates valid"
- 检测到缺口：返回 rc=1，输出缺口报告（按 4 类分组列出）

**与内置模板比对**：`validate` 额外比对用户层模板与内置模板的差异，提示用户哪些 artifact 已被用户层覆盖、哪些内置 artifact 在用户层缺失（必需 artifact 缺失会报 ERROR）。

## T3.4 `remove` / `rename` 子命令（LIFO 清理三件套）

**用途**：维护用户层 `~/.corespec/core-schemas/<schema>/templates/` 下的 artifact 声明。

### `remove`（LIFO 清理）

```bash
python -m core_templates remove <artifact_id>
```

**LIFO 清理顺序**（两件套）：

1. **再删模板载体**：删除 `~/.corespec/core-schemas/<schema>/templates/<artifact>.md`
2. **再删 schema.yaml 声明**：从 L2 `schema.yaml` 的 artifacts 列表中移除该 artifact 条目

**约束**：

- `REQUIRED_BUILTIN_ARTIFACTS`（proposal / delta_spec / delta_design / tasks / delta_test_design）拒绝删除，返回 rc=1
- 仅允许删除用户层扩展的非必需 artifact

### `rename`（同步 requires 引用）

```bash
python -m core_templates rename <old_id> <new_id>
```

**同步动作**：

1. 重命名 `templates/<old_id>.md` → `templates/<new_id>.md`
2. 更新 L2 `schema.yaml` 中该 artifact 的 `id` 字段
3. **同步 requires 引用**：扫描 `schema.yaml` 中其他 artifact 的 `requires` 数组，将 `old_id` 替换为 `new_id`
4. 返回 rc=0；若 L2 `schema.yaml` 不存在返回 rc=1
