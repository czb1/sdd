# sdd

CoreSpec 的 core-design / core-apply 指令文件及 core-shared 共享文档。

任务 Skill 消费统一为**内置可启停步骤**：design / apply 各自通过 `skill_consumption: true/false` 控制，均默认 `false`。执行计划只在 `steps` 中生成启用的 `built_in` 条目，骨架从其 `ref_file.single` / `ref_file.multi` 加载指令。`expert_experience` 保持独立的内置步骤。配置、迁移和执行位置见 [专属配置说明](core-shared/references/skill-consumption-config.md)。

core-design 在 Phase 8 生成任务后，由新增 Phase 9 完成查找、确认、安装与关联；core-apply 在新增 Step 9 准备一次，Step 10 按任务消费。后续步骤编号及单/多仓引用同步顺延，通用自定义插槽保持独立。

本仓不含完整 CoreSpec 运行时。已完成内置注册和步骤编号迁移的版本（本次提供的源码）使用以下修复：

- [修复工具](patches/apply_flow_config_fixes.py)：按 Python AST 定位并替换 `update_config_value`，补齐 JSONC 辅助函数，同步注册表描述、模板注释和一致性检查提示。与函数在文件中的顺序无关，保留其他函数的执行逻辑、已有步骤的默认值与编号。
- [可复制的写入函数](patches/flow_config_update.py)：仅包含四个辅助函数和 `update_config_value`；不能用它覆盖完整模块。
- [源码差异](patches/flow-config-runtime-fixes.patch)：依据本次提供的源码片段生成，便于检视；完整文件中的函数顺序未知，实际合入推荐使用上面的 AST 工具。
- [模板常量](patches/flow_config_template.py)：用于核对 `TEMPLATE_JSONC`。其中 `judgment_ladder` 保持未注释、默认启用；生成模板后的 core-apply 计划因此不属于“无自定义步骤”的全默认计划。

在本仓根目录运行（将占位路径换成完整运行时文件路径）：

```bash
# 先显示具体 diff；不写文件
python patches/apply_flow_config_fixes.py /path/to/core-shared/scripts/flow_config.py
# 应用修复；保留 flow_config.py.before-flow-config-fixes.bak，重复应用不改文件
python patches/apply_flow_config_fixes.py /path/to/core-shared/scripts/flow_config.py --apply
# 验证实际运行时的配置写入与执行计划
python tests/test_flow_config_update.py --flow-config /path/to/core-shared/scripts/flow_config.py
python tests/test_skill_consumption_flow.py --flow-config /path/to/core-shared/scripts/flow_config.py
```

尚未完成内置步骤迁移的旧版本，先按来源选择下面一份历史补丁，完成内置注册、步骤顺序和模板迁移，再使用上述修复工具：

- 从最初提供的源码合入：[完整补丁](patches/skill-consumption-template.patch)。
- 已应用上一版自定义步骤补丁：[升级补丁](patches/skill-consumption-builtin-upgrade.patch)。两份补丁择一使用。
- [布尔配置示例](examples/flow-config.skill-consumption.jsonc) 用于补充已有配置；旧的同名自定义对象须整体替换为布尔值。

保留原有 [共享 SKILL 骨架](core-shared/SKILL.md)、[模板自定义命令](core-shared/references/template-commands.md)和[模板使用指南](core-shared/references/template-guide.md)。通用流程编排仍见 [flow-config 配置指南](core-shared/references/flow-config-guide.md)，业务操作细节集中于专属消费指令。

本仓可直接运行 `python -m unittest discover -s tests -p 'test_flow_config*.py' -v`：覆盖空对象、行尾注释、单行/多行配置、嵌套同名键、字符串内注释符、幂等、写入失败保留原文件，以及修复工具的备份和重复应用。

[执行计划集成测试](tests/test_skill_consumption_flow.py)需要通过 `--flow-config` 提供完整运行时，覆盖默认关闭、四种启停组合、保存后重建、旧对象拒绝、步骤顺序和自定义步骤独立性。本次未获得完整运行时，未将片段测试视为完整 CLI 初始化或多仓执行的端到端验证。
