# 任务 Skill 消费配置

任务 Skill 消费统一使用**内置可启停步骤**。通用配置语法见 [flow-config 配置指南](flow-config-guide.md)；业务操作细节仅在专属指令中展开。

## 配置与执行位置

| 命名空间 | 内置键 | 默认 | 执行位置 |
|----------|--------|------|----------|
| core-design | skill_consumption | false | Phase 9：Phase 8 及其通用插槽完成后；多仓 M-2 全部完成后由主会话聚合执行 |
| core-apply | skill_consumption | false | Step 9 / 多仓 M-2 启动前准备一次；Step 10 的 10.3.4 / 多仓每任务独立检查点消费 |

```jsonc
{
  "core-design": { "skill_consumption": false },
  "core-apply": { "skill_consumption": false }
}
```

`true` 开启、`false` 关闭；未配置时使用注册表默认值 `false`。两阶段独立，`expert_experience` 也独立；已有任务关联、本地文件和输入参数不能隐式开启步骤。将示例键合并到现有命名空间，保留其他配置。

## flow_config.py 修改范围

1. `BUILT_IN_STEPS_BY_SKILL`：在 design / apply 中各注册 `skill_consumption`，`default=False`、`depends_on=[]`，`ref_file.single` / `ref_file.multi` 均为 `references/skill-consumption.md`（相对所属 Skill 安装目录）。design 的 `at=step-8` 对应 Phase 9；apply 的 `at=step-9` 对应 Step 9。
2. `FIXED_STEPS` / `FIXED_STEPS_BY_SKILL`：插入对应步骤位，后续编号顺延，并同步注册项的位置与步骤标签。design 共 12 步，apply 共 16 步；计划中的步骤位保持连续。
3. `TEMPLATE_JSONC`：两个命名空间的内置开关区增加 `"skill_consumption": false`，删除上一版同名自定义 reference 对象。design 命名空间仍保留原有一层示例注释；提取该命名空间后，布尔键为有效的 `false` 配置。
4. 保留上一版 `_fix_restored_entry_separators` 的首项逗号修复：`if not code.endswith(("{", ",")):`。这是通用自定义步骤恢复修复，与本内置开关独立。

[模板常量](../../patches/flow_config_template.py) 仅供核对，不能替代注册表和步骤顺序修改，也不能覆盖整个模块。分发时同时同步本仓的阶段骨架、步骤表和引用文件，避免旧编号与新计划混用。

## 应用补丁

两份补丁择一使用：最初提供的源码使用 [完整补丁](../../patches/skill-consumption-template.patch)；已经应用上一版自定义步骤补丁的源码使用 [升级补丁](../../patches/skill-consumption-builtin-upgrade.patch)。后者将原自定义声明移除并完成内置注册。

在完整 CoreHarness 仓库根目录执行（将 `/path/to/sdd` 替换为本仓位置；升级时替换补丁文件名）：

```bash
git apply --check --directory=coreharness-spec/skills /path/to/sdd/patches/skill-consumption-template.patch
git apply --directory=coreharness-spec/skills /path/to/sdd/patches/skill-consumption-template.patch
python /path/to/sdd/tests/test_skill_consumption_flow.py --flow-config coreharness-spec/skills/core-shared/scripts/flow_config.py -v
```

若目标仓根目录直接包含 `core-shared/`，去掉 `--directory=coreharness-spec/skills`，并相应调整测试路径。补丁按代码上下文匹配；检查不通过时对照当前实现合并，不能用片段覆盖完整文件。

## 已有配置迁移与生效

- 若 `~/.corespec/flow-config.json` 已含上一版 `"skill_consumption": { "type": "reference", ... }`，将**整个同名对象**（包括其注释示例）替换成一个布尔键；原来启用且仍要启用时设为 `true`，原来关闭则设为 `false`。不能同时保留同名对象和布尔键，也不把它改名后继续挂在通用插槽中。
- 新版注册表会拒绝同名自定义对象及其他非布尔值，不静默迁移或隐式开启。
- 已有命名空间按原初始化规则保留，修改模板不会覆盖它；只补入缺失的布尔键即可。缺少命名空间时可用对应 `main.py flow-config --init --skill <name>` 初始化。
- 以后使用 `main.py flow-config --apply --skill <name> --changes skill_consumption=true` 或 `skill_consumption=false` 调整；内置步骤关闭使用 `false`。
- 修改后重新执行两个 Skill 的 Step 0，重建并确认执行计划和 skipped 标记。步骤编号已更新，不能沿用旧执行计划或旧片段；这些产物由框架生成，禁止手工修改。

## 执行期规则

唯一门控是当前 Skill 根计划 `steps` 中 `config_key=skill_consumption`、`type=built_in`、`enabled=true` 的条目。骨架从其 `ref_file.single` / `ref_file.multi` 动态加载指令。关闭态仅保留 `enabled=false` 的步骤位，不含 `config_key` / `ref_file`；不加载指令文件、不检索、确认、下载、读取关联内容或回写字段。已有字段和本地内容保留。

多仓 apply 的通用插槽仍从本仓片段 `orchestration_points` 读取；内置步骤从片段 `plan_path` 指向的根计划 `steps` 读取。片段没有 `steps`，不能以片段无条目为由关闭或开启内置步骤。主会话准备一次、子代理按任务消费，新增用户决策交回主会话汇总。根计划/片段无效或路径不一致时停止并报告。

## 专属指令与验证

- [设计阶段指令](../../core-design/references/skill-consumption.md)
- [执行阶段指令](../../core-apply/references/skill-consumption.md)
- [共享消费规则](skill-consumption.md)

回归覆盖两阶段四种启停组合、默认关闭、布尔开关持久化与指纹、旧对象拒绝、连续步骤顺序、ref_file 条件加载、expert_experience 与通用自定义插槽独立性。由于本仓缺少完整 main.py 与运行时，完整初始化、确认调整和多仓执行端到端验收仍需在目标框架完成。
