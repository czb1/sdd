# sdd

CoreSpec 的 core-design / core-apply 指令文件及 core-shared 共享文档。

任务 Skill 消费通过现有编排点的自定义 reference 步骤按需开启，**默认关闭**。配置和执行位置见 [专属配置说明](core-shared/references/skill-consumption-config.md)；通用配置语法见 [flow-config 配置指南](core-shared/references/flow-config-guide.md)。流程骨架和固定步骤表只保留通用调度。

core-shared 保留原有 SKILL.md 骨架、[模板自定义命令](core-shared/references/template-commands.md)与[模板使用指南](core-shared/references/template-guide.md)；Skill 消费细节放在专属指令中。

配置声明放在完整框架 `flow_config.py` 的 `TEMPLATE_JSONC`，注释即默认关闭，取消注释后由执行计划统一调度。根据提供的原模板，已准备 [原文件补丁](patches/skill-consumption-template.patch) 和 [完整 TEMPLATE_JSONC 替换片段](patches/flow_config_template.py)；两个命名空间独立启停，保留已有内置开关、`judgment_ladder` 和全局测试策略。[注释声明示例](examples/flow-config.skill-consumption.jsonc) 用于已有配置补充缺失声明。

本仓库不包含完整 CoreSpec 运行时；请按 [专属配置说明](core-shared/references/skill-consumption-config.md) 将补丁应用到完整框架。替换片段仅含常量，不能覆盖整个 `flow_config.py`。补丁同时修复启用首个自定义声明时误补逗号的问题。

已使用此前提供的真实配置函数验证模板解析、命名空间提取、四种启停组合、关闭/恢复、配置指纹与计划构建；完整 `main.py --init` 和多仓片段端到端流程仍需在完整框架验证。回归脚本见 [test_skill_consumption_flow.py](tests/test_skill_consumption_flow.py)，通过 `--flow-config` 指定应用补丁后的原文件。
