# sdd

CoreSpec 的 core-design / core-apply 指令文件及 core-shared 共享文档。

任务 Skill 消费通过现有编排点的 `skill_consumption` reference 步骤按需开启，**默认关闭**。配置和执行位置见 [flow-config 配置指南 §10.1](core-shared/references/flow-config-guide.md#skill-consumption)，可合并的配置样例见 [flow-config.skill-consumption.jsonc](examples/flow-config.skill-consumption.jsonc)。

core-shared 保留原有 SKILL.md 骨架、[模板自定义命令](core-shared/references/template-commands.md)与[模板使用指南](core-shared/references/template-guide.md)；Skill 消费细节放在专属指令中。

本仓库不包含完整 CoreSpec 运行时；这些指令配合已有框架使用。
