# sdd

CoreSpec 的 core-design / core-apply 指令文件及 core-shared 共享文档。

任务 Skill 消费通过现有编排点的自定义 reference 步骤按需开启，**默认关闭**。配置和执行位置见 [专属配置说明](core-shared/references/skill-consumption-config.md)；通用配置语法见 [flow-config 配置指南](core-shared/references/flow-config-guide.md)。流程骨架和固定步骤表只保留通用调度。

core-shared 保留原有 SKILL.md 骨架、[模板自定义命令](core-shared/references/template-commands.md)与[模板使用指南](core-shared/references/template-guide.md)；Skill 消费细节放在专属指令中。

配置声明须合入完整框架 `flow_config.py` 的 `TEMPLATE_JSONC`，注释即默认关闭，取消注释后由执行计划统一调度。[注释声明片段](examples/flow-config.skill-consumption.jsonc) 用于模板合入或补充已有配置；用户现有配置按原初始化规则保留。

本仓库不包含完整 CoreSpec 运行时，目前缺少完整 `flow_config.py`，模板合入与初始化、执行计划构建及多仓片段的运行时验证仍待源文件补齐。本次指令修改不代表这些运行时变更已经完成。
