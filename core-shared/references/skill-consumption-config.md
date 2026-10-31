# 任务 Skill 消费配置

本文件承载任务 Skill 消费的配置和执行边界。通用配置语法见 [flow-config 配置指南](flow-config-guide.md)；具体业务规则不写入通用指南、固定步骤表或流程骨架。

## 步骤类型与默认值

任务 Skill 消费采用**自定义 reference 步骤**，不是内置布尔步骤。两个命名空间独立配置，均默认关闭：

| 命名空间 | 自定义键 | 编排点 | file（相对所属 Skill 安装目录） |
|----------|----------|--------|--------------------------------|
| core-design | skill_consumption | post-generate | references/skill-consumption.md |
| core-apply | skill_consumption | pre-codegen | references/skill-consumption.md |

声明应放在完整框架 `core-shared/scripts/flow_config.py` 的 `TEMPLATE_JSONC` 中，经现有 `--init` 流程写入用户配置。模板内整块注释表示默认关闭，取消整块注释表示开启；不能把自定义对象改成 `true/false`，也不向内置步骤注册表添加同名键。`expert_experience` 继续作为独立内置可启停步骤，仅通过自己的 `steps` 条目和 `ref_file` 加载。

## 配置来源

配置声明应合入完整框架 `core-shared/scripts/flow_config.py` 的 `TEMPLATE_JSONC`；[注释声明片段](../../examples/flow-config.skill-consumption.jsonc) 供合入该模板及已有配置补充缺失声明时参考，不是第二个运行时配置源。分发时同时更新共享配置模块、阶段指令及共享指令，保留其他内置开关、编排点和用户自定义步骤。

本仓当前未包含完整 `flow_config.py`，因此模板合入尚待该源文件；不能把本文或示例片段当作已完成的 `--init` 改造。

若整个命名空间也是模板中的注释示例，步骤声明保留两层注释：`--init --skill` 提取命名空间并去掉外层注释后，步骤仍默认关闭。已有命名空间不覆盖，只在用户明确选择时补入缺少的声明。

## 开启、关闭与生效

1. 完整框架合入模板声明后，用 `main.py flow-config --init --skill core-design` / `--skill core-apply` 初始化所需命名空间。已有命名空间按原框架规则不覆盖；需要时仅补入缺少的注释声明，保留其他键与注释。
2. 在 `~/.corespec/flow-config.json` 中取消所需声明整块注释以开启；重新注释整块以关闭。`reference` 对象不填写 `run_mode` / `args`。相邻字段的逗号须符合 JSONC 对象语法。
3. 已有声明时也可用 `main.py flow-config --apply --skill <name> --changes skill_consumption=` 关闭，用 `--changes skill_consumption=true` 恢复。后者是恢复声明的命令参数，不是配置源的布尔值；没有声明时不能凭它创建步骤。
4. 重新运行对应 Skill 的 Step 0 构建并确认执行计划。仅计划对应插槽中存在 `key=skill_consumption`、`type=reference`、`file` 指向阶段指令且未禁用的条目时执行；不要直接编辑执行计划或 skipped 文件，也不从配置源推断旧计划已经更新。

## 执行位置与关闭语义

- **design / 单仓**：Phase 8 全部产物生成后，在通用 `post-generate` 调度中执行一次。
- **design / 多仓**：M-2 全部仓完成后，由主会话聚合调度一次；生成代理不提前执行。任务候选统一确认，再按仓安装与回写。
- **apply / 单仓**：通用执行期规则在任务循环前加载启用的 reference 指令，按其“主会话前置准备”完成一次批量准备；每任务在 9.3.5 消费锁定内容。
- **apply / 多仓**：主会话按根计划在 M-2 代理启动前完成前置准备；子代理按本仓片段在 task 级消费，需新增决策时返回主会话汇总。
- **关闭**：不加载阶段或共享消费指令，不检索、确认、下载、读取关联内容或回写关联。原设计、代码生成、checkbox 更新、内置设计经验准备及其他已启用编排条目继续执行；已有任务字段和本地内容保留。

`--query`、已有 Skill 字段、本地目录、`expert_experience` 或 design 的启用状态均不能隐式开启 apply。启用步骤只决定是否执行流程，不能覆盖用户在候选选择中明确指定的“不使用”。

## 专属指令

- [设计阶段指令](../../core-design/references/skill-consumption.md)：准备任务候选、统一确认、下载和关联回写。
- [执行阶段指令](../../core-apply/references/skill-consumption.md)：主会话前置准备、逐任务消费和多仓协作。
- [共享消费规则](skill-consumption.md)：CLI、候选选择、安装路径、失败处理和字段格式。

## 完整框架验收

分别验证两阶段均关闭、仅 design 开启、仅 apply 开启、两阶段均开启；确认默认注释不产生计划条目，取消注释后只出现在对应插槽，重新关闭并重建后条目消失。检查首次初始化、缺失命名空间追加及已有配置保留；多仓片段须与根计划一致，同插槽其他自定义条目保持原有顺序和行为。
