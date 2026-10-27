# SDD Skills

| Skill | 职责 |
|---|---|
| [core-design](core-design/SKILL.md) | 生成 SDD 设计及任务；任务形成后查找 Skill / 经验并同步 tasks.md |
| [core-apply](core-apply/SKILL.md) | 从 tasks.md 加载任务关联的项目级能力，缺失时按需获取并执行任务 |
| [yunjian-skill-use](yunjian-skill-use/SKILL.md) | SDD / 其他场景的统一云见 CLI 能力查找与使用入口 |
| [yunjian-skill-evolve](yunjian-skill-evolve/SKILL.md) | 建议与 Skill → 候选版本及说明 → 广场审核 → 正式变更与结果核验 |

安装 core-design / core-apply 时同时提供 yunjian-skill-use，使运行时可按技能名或同级目录读取。其他场景先安装并读取实际的云见 CLI Skill，再使用 yunjian-skill-use；本仓不提供云见 CLI 本体或其命令契约。进化入口需要实际可用的 Skill 广场提交、审核及正式变更能力。

业务能力优先沿代码仓 → 产品 → 场景匹配 Skill；未命中时分别检索最多 3 个 Skill 与 3 条经验，再按需选择。通用能力直接检索 Skill。所有查找获取统一通过云见 CLI，选用内容下载到项目级目录；SDD 同步 tasks.md，其他场景不修改 tasks.md。没有合适结果或查找失败时继续原任务。

tasks.md 是 SDD 任务及其能力关联的唯一数据源，不另建索引。单仓和多仓遵循同一流程，多仓仅关联各仓自身任务。既有 expert_experience 配置键保留为设计前已有经验准备开关，不关闭任务形成后的能力查找。

查找使用可以独立结束。评测和建议生成是外部前置能力；拿到建议后才进入独立进化流程，经验不属于本次审核变更对象。用户审核通过后，由 Skill 广场变更正式 Skill，并核验生效内容与获批内容一致；审核后再修改需重新审核。广场更新不自动覆盖已有项目的本地内容。

本仓维护 Agent 操作指引，不实现云见 CLI、广场后端、前置评测、接口、目录布局、tasks.md 字段协议或版本管理机制。core-design / core-apply 原有脚本与 schema 依赖仍由运行环境提供。
