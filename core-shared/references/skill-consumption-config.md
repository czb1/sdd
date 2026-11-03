# 任务 Skill 消费配置

任务 Skill 消费统一使用**内置可启停步骤**。通用配置语法见 [flow-config 配置指南](flow-config-guide.md)；业务操作细节仅在专属指令中展开。

## 配置与执行位置

| 命名空间 | 内置键 | 默认 | 执行位置 |
|----------|--------|------|----------|
| core-design | skill_consumption | false | Phase 9：Phase 8 产物生成后；多仓 M-2 全部完成后由主会话聚合执行 |
| core-apply | skill_consumption | false | 单仓 Step 9 / 多仓 M-1a 准备一次；Step 10 / M-2 使用已准备的当前任务上下文 |

```jsonc
{
  "core-design": { "skill_consumption": false },
  "core-apply": { "skill_consumption": false }
}
```

`true` 开启、`false` 关闭；未配置时使用注册表默认值 `false`。两阶段独立，`expert_experience` 也独立；已有任务关联、本地文件和输入参数不能隐式开启步骤。将示例键合并到现有命名空间，保留其他配置。

## flow_config.py 修改范围

1. `BUILT_IN_STEPS_BY_SKILL`：在 design / apply 中各注册 `skill_consumption`，`default=False`、`depends_on=[]`，`ref_file.single` 为 `references/skill-consumption.md`；design 的 `ref_file.multi` 与单仓共用，apply 的多仓指令为 `references/skill-consumption-multi.md`（均相对所属 Skill 安装目录）。design 的 `at=step-8` 对应 Phase 9；apply 的 `at=step-9` 对应 Step 9。
2. `FIXED_STEPS` / `FIXED_STEPS_BY_SKILL`：插入对应步骤位，后续编号顺延，并同步注册项的位置与步骤标签。design 共 12 步，apply 共 16 步；计划中的步骤位保持连续。
3. `TEMPLATE_JSONC`：两个命名空间的内置开关区增加 `"skill_consumption": false`，删除上一版同名自定义 reference 对象。design 命名空间仍保留原有一层示例注释；提取该命名空间后，布尔键为有效的 `false` 配置。
4. `run_fragment`：仅 core-apply 的片段增加 `built_in_steps.skill_consumption`，包含多仓 `phase=M-1a`、`enabled` 和启用时的 `ref_file`；不复制单仓步骤编号，保留通用插槽和来源路径。其他技能片段格式不变。
5. 同步新增步骤后的阶段数量，以及 `expert_experience` 的职责描述：它准备已有经验上下文，任务 Skill 的查找、确认、安装与关联由独立的 `skill_consumption` 步骤承担。

本仓已提供完整的 [flow_config.py](../scripts/flow_config.py)，原两段源码已合并为一个模块。保留 master 的配置解析、自动初始化、按配置重建计划、多仓片段生成与依赖处理机制，不恢复旧的交互确认或配置写回接口。

[模板常量](../../patches/flow_config_template.py) 与当前源码同步，仅供核对；只替换模板不能完成内置化。同步到目标框架时，同时同步本仓的阶段骨架、步骤表和引用文件，避免旧编号与新计划混用。

## 按差异集成

通常直接使用上面的完整源码。若目标文件来自本次 master 基线 `8eb0857`，先将原 `flow_config.py` 和 `flow_config2.py` 按顺序拼成一个文件，再应用 [消费兼容补丁](../../patches/skill-consumption-template.patch)：

```bash
git apply --check --directory=coreharness-spec/skills /path/to/sdd/patches/skill-consumption-template.patch
git apply --directory=coreharness-spec/skills /path/to/sdd/patches/skill-consumption-template.patch
python /path/to/sdd/tests/test_skill_consumption_flow.py --flow-config coreharness-spec/skills/core-shared/scripts/flow_config.py -v
```

若目标仓根目录直接包含 `core-shared/`，去掉 `--directory=coreharness-spec/skills`，并相应调整测试路径。其他基线须按当前源码对照合并；检查不通过时不能强行应用或用片段覆盖完整模块。旧的 builtin-upgrade / metadata 补丁仅保留作历史迁移参考，不叠加到本次合并源码。

## 已有配置迁移与生效

- 若 `~/.corespec/flow-config.json` 已含上一版 `"skill_consumption": { "type": "reference", ... }`，将**整个同名对象**（包括其注释示例）替换成一个布尔键；原来启用且仍要启用时设为 `true`，原来关闭则设为 `false`。不能同时保留同名对象和布尔键，也不把它改名后继续挂在通用插槽中。
- 新版注册表会拒绝同名自定义对象及其他非布尔值，不静默迁移或隐式开启。
- 已有命名空间按原初始化规则保留，修改模板不会覆盖它；只补入缺失的布尔键即可。缺少命名空间时可用对应 `main.py flow-config --init --skill <name>` 初始化。
- 以后直接编辑 `~/.corespec/flow-config.json` 中对应命名空间的 `skill_consumption`：`true` 开启，`false` 关闭。下次运行自动读取，不再使用旧的配置写回命令。
- 下次运行对应 Skill 的 Step 0 时自动重建执行计划和 skipped 标记，无需流程配置确认。候选选择、安装冲突等业务确认仍按专属指令执行。步骤编号已更新，不能沿用旧执行计划或旧片段；这些产物由框架生成，禁止手工修改。

## 执行期规则

单仓及 design 的门控是当前 Skill 执行计划 `steps` 中 `config_key=skill_consumption`、`type=built_in`、`enabled=true` 的条目。骨架从其 `ref_file.single` / `ref_file.multi` 动态加载指令。关闭态仅保留 `enabled=false` 的步骤位，不含 `config_key` / `ref_file`；不加载指令文件、不检索、确认、下载、读取关联内容或回写字段。已有字段和本地内容保留。

多仓 apply 在 M-1 后生成各仓片段，由 M-1a 根据 `built_in_steps.skill_consumption` 的 `phase=M-1a`、`enabled=true` 和 `ref_file` 聚合准备一次；M-2 子代理只读本仓片段并使用已准备的任务上下文，新增用户决策交回主会话。`plan_path` 仅记录来源，子代理不读取根计划或单仓步骤。通用插槽仍从 `orchestration_points` 读取；消费关闭不关闭插槽。旧片段缺少多仓控制字段时，由主会话重新生成，禁止回退读取单仓 Step 9。

## 专属指令与验证

- [设计阶段指令](../../core-design/references/skill-consumption.md)
- [单仓准备指令](../../core-apply/references/skill-consumption.md)
- [多仓准备与使用指令](../../core-apply/references/skill-consumption-multi.md)
- [共用准备规则](../../core-apply/references/skill-preparation.md)
- [共享消费规则](skill-consumption.md)

回归覆盖两阶段四种启停组合、默认关闭、直接编辑配置后的计划重建、首次配置和命名空间静默初始化、非法配置保留旧计划、旧对象拒绝、连续步骤顺序、ref_file 条件加载、expert_experience 与通用自定义插槽独立性，以及多仓片段独立门控及其他技能片段格式兼容性。运行 `python -m unittest discover -s tests -v`。本仓仍缺少各 Skill 的 main.py、core_paths、模板包及内网服务，完整 Agent 多仓执行和真实检索下载须在目标框架验收。
