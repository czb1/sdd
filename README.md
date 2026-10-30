# sdd

CoreSpec 的 core-design / core-apply 指令文件。

任务 Skill 消费通过现有编排点的 `skill_consumption` reference 步骤按需开启，**默认关闭**。配置和执行位置见 [消费配置说明](core-shared/references/skill-consumption-config.md)，可合并的配置样例见 [flow-config.skill-consumption.jsonc](examples/flow-config.skill-consumption.jsonc)。

本仓库不包含完整 CoreSpec 运行时；这些指令配合已有框架使用。
