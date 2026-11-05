# sdd

CoreSpec 的 core-design / core-apply 指令文件、core-shared 共享文档及流程编排模块。

本仓已整合 master 的配置驱动流程与 main 的任务 Skill 消费能力：首次运行自动初始化配置，每次运行按配置重建执行计划，不再要求流程配置确认。调整步骤直接编辑 `~/.corespec/flow-config.json`，下次运行自动生效。

同时补齐 master2 的增量复审（`--recheck`）、多仓审查目录约束与 Linux/Windows 版本升级结果反馈。审查指令沿用 Skill 消费插入后的步骤编号；单仓/多仓即使关闭追溯验证或文档审查，也须先完成或按配置跳过 Phase 9 的 Skill 关联。

## 任务 Skill 消费

任务 Skill 消费是**内置可启停步骤**：design / apply 各自通过 `skill_consumption: true/false` 控制，均默认 `false`。仅启用时加载对应阶段的消费指令；关闭时不检索、下载、消费关联内容或回写字段，已有字段和文件保留。

- Skill 按当前 Agent 的约定或项目已有配置安装到项目级 Skill 目录；多仓分别安装到任务所属仓，`tasks.md` 的 Skill 字段记录实际安装路径。
- core-design：Phase 8 生成任务后，Phase 9 完成查找、候选确认、安装与关联；多仓由主会话在 M-2 全部完成后聚合执行一次。
- core-apply：单仓 Step 9 一次完成关联检查、必要的补齐与批量确认，Step 10 使用准备好的任务上下文；多仓由独立的 M-1a 准备，M-2 子代理只读本仓片段的 `built_in_steps.skill_consumption`，无需读取根计划或单仓 Step 9。
- `expert_experience` 与消费开关独立；通用自定义插槽继续按自己的配置执行。流程配置自动生效不替代候选选择、安装冲突等业务确认。

配置和迁移见 [任务 Skill 消费配置](core-shared/references/skill-consumption-config.md)，开关示例见 [flow-config.skill-consumption.jsonc](examples/flow-config.skill-consumption.jsonc)。

## 源码与集成

[core-shared/scripts/flow_config.py](core-shared/scripts/flow_config.py) 是完整、可独立运行的单文件模块，已将原先上传的 `flow_config.py` / `flow_config2.py` 按顺序合并。无需自行拼接，也不要再叠加第二段文件。

同步到完整 CoreHarness 时，保持 `core-shared/scripts/flow_config.py` 路径，并一并同步本仓的 design / apply 骨架、步骤表与引用文件。以该完整源码为准；[模板常量](patches/flow_config_template.py) 仅供核对，不能覆盖完整模块。

需要在与本次 master 相同的基线（`8eb0857`）上按差异合入时，先合并原来的两段文件，再使用 [消费兼容补丁](patches/skill-consumption-template.patch)。该补丁调整消费注册、步骤编号和模板，并在 core-apply 的多仓片段中增加 M-1a 消费控制；其他技能的片段格式保持不变。旧的 builtin-upgrade / metadata 补丁只保留作历史迁移参考，不用于当前基线。

通用配置见 [flow-config 用户指南](core-shared/references/flow-config-guide.md)，实现约定见 [开发者指导](开发者指导.md)。保留 [共享 SKILL 骨架](core-shared/SKILL.md)、[模板自定义命令](core-shared/references/template-commands.md)及[模板使用指南](core-shared/references/template-guide.md)。

## 验证

```bash
python -m py_compile core-shared/scripts/flow_config.py
python -m unittest discover -s tests -v
python core-shared/scripts/flow_config.py --describe --json --skill core-design
```

回归覆盖默认关闭、四种启停组合、直接编辑配置后的重建、静默初始化、非法配置保留旧计划、步骤顺序、独立自定义插槽、多仓片段独立门控、跨仓片段与默认关闭状态，以及注册表/骨架/步骤表/指令标题一致性和关闭审查时的 Skill 关联衔接。也可通过 `python tests/test_skill_consumption_flow.py --flow-config /path/to/flow_config.py -v` 验证目标模块。

本仓仍不包含完整 CoreHarness（各 Skill 的 main.py、core_paths、模板包等）及内网服务环境；完整 Agent 多仓执行、真实 CLI 检索和下载需在目标环境验收。
