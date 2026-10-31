# sdd

CoreSpec 的 core-design / core-apply 指令文件及 core-shared 共享文档。

任务 Skill 消费统一为**内置可启停步骤**：design / apply 各自通过 `skill_consumption: true/false` 控制，均默认 `false`。执行计划只在 `steps` 中生成启用的 `built_in` 条目，骨架从其 `ref_file.single` / `ref_file.multi` 加载指令。`expert_experience` 保持独立的内置步骤。配置、迁移和执行位置见 [专属配置说明](core-shared/references/skill-consumption-config.md)。

core-design 在 Phase 8 生成任务后，由新增 Phase 9 完成查找、确认、安装与关联；core-apply 在新增 Step 9 准备一次，Step 10 按任务消费。后续步骤编号及单/多仓引用同步顺延，通用自定义插槽保持独立。

本仓不含完整 CoreSpec 运行时，`flow_config.py` 的修改以补丁交付，覆盖内置注册表、完整步骤顺序和 `TEMPLATE_JSONC`：

- 从最初提供的源码合入：[完整补丁](patches/skill-consumption-template.patch)。
- 已应用上一版自定义步骤补丁：[升级补丁](patches/skill-consumption-builtin-upgrade.patch)。两份补丁择一使用。
- [模板常量](patches/flow_config_template.py) 仅供核对；只替换模板不能完成内置化，也不能用它覆盖完整模块。
- [布尔配置示例](examples/flow-config.skill-consumption.jsonc) 用于补充已有配置；旧的同名自定义对象须整体替换为布尔值。

保留原有 [共享 SKILL 骨架](core-shared/SKILL.md)、[模板自定义命令](core-shared/references/template-commands.md)和[模板使用指南](core-shared/references/template-guide.md)。通用流程编排仍见 [flow-config 配置指南](core-shared/references/flow-config-guide.md)，业务操作细节集中于专属消费指令。

回归脚本：[test_skill_consumption_flow.py](tests/test_skill_consumption_flow.py)，通过 `--flow-config` 指定应用补丁后的完整文件。已使用此前提供的真实配置函数验证默认关闭、四种启停组合、布尔开关持久化、旧对象拒绝、步骤顺序及其他步骤独立性；完整 CLI 初始化和多仓执行端到端验证仍需在目标框架完成。
