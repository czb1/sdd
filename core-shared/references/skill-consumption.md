# Skill 与经验消费规则（共享指令）

> 仅由已启用的 `skill_consumption` 内置步骤加载。本文件不是自动执行入口，不能因 tasks.md 已有 Skill 字段、项目存在 .codeagent/skills、提供 --query 或启用了 expert_experience 而自动启用。

目录：配置边界 → 能力判断与候选查找 → CLI 命令与字段传递 → 批量确认 → 去重与项目级落地 → tasks.md 回写。

## 配置边界

- 执行计划是唯一权威；由阶段专属指令检查 `steps` 中 `config_key=skill_consumption`、`type=built_in`、`enabled=true` 的条目，不重读或改写配置源。
- 内置开关为 `false`、未配置（默认 `false`）或计划无启用条目时关闭。关闭时跳过新增的检索、候选确认、下载、关联内容读取及字段回写；保留已有字段与本地文件，继续原设计 / 代码生成流程。
- 关闭不影响原有设计经验准备、普通任务文件读取、checkbox 更新和其他编排条目；持久关联内容须按下方安装边界保存。
- 步骤开启只决定是否执行消费流程；用户对候选的“不使用”决定仍按下方规则优先处理。候选空答案规则不能反向开启该步骤。

## 能力判断与候选查找

以当前任务目标、代码仓和上下文为输入，由 Agent 自主判断需要业务相关能力还是通用能力；需要两类能力时分别选择对应路径。SDD 只针对 tasks.md 的 1.x 代码生成任务，结合任务描述和「编程语言」匹配候选。

| 能力类型 | 查找与选择 |
|---|---|
| 业务相关 | 代码仓 → `skill offering` 获取产品 ID 与名称 → `skill product-scenes --dim_code <offering_id>` 获取场景 → 按任务描述与编程语言匹配场景（可多选）→ `skill scene-skills` 获取命中场景的 Skill；本地仓可用 `skill scenes --repo <目录>` 合并前两次查询 |
| 业务路径未命中 | 产品无法定位、场景无法匹配或场景无合适 Skill 时，通过云见 CLI 分别检索最多 **3 个 Skill 候选**和经验引擎中最多 **3 条经验候选**，综合判断 Skill、经验或两者组合 |
| 通用能力 | 跳过产品和场景链路，直接通过云见 CLI 检索通用 Skill |

产品以 CLI 实际返回的 ID 与名称映射为准；仓库根目录名、.codeagent/product.json 或用户提供的产品名只作为选择线索，不能据此编造 `offering_id`。返回多个产品时保留各自的 ID、名称与场景归属，按任务上下文选择相关产品；无法可靠判断或来源冲突时一次询问用户，允许跳过，不静默取第一项。只有产品名而无法取得对应 ID 时，允许用户补充可验证的产品信息；仍无法定位或用户跳过后按业务未命中路径处理，不反复追问。为每个任务预判最多 Top3 Skill，给出一句话匹配理由及 Agent 首选；不足时按实际数量处理，不强行凑数。场景已有合适 Skill 或当前只需要通用能力时，不自动追加业务兜底的经验检索。一侧检索失败时仍可判断另一侧已返回的候选，但服务错误不能报告为确定无结果。

## CLI 命令与字段传递

以下映射依据 [coreinsight-cli 实现](https://github.com/czb1/coreinsight-cli/blob/a5aa6d3338cc70a4b1896ae56c07e3328d6f7ed9/internal/cli/skill.go)。仅在消费步骤已启用时检查实际安装版本的帮助与登录状态：`coreinsight-cli skill --help`、`coreinsight-cli auth status`；未登录时用 `coreinsight-cli auth login` 完成当前版本的浏览器授权后再继续。命令不可用或返回错误时报告真实失败，不编造替代命令或绕过 CLI 请求接口。

### 业务链路：代码仓 → 产品 → 场景 → Skill

| 步骤 | 命令 | 返回值及下一步 |
|---|---|---|
| 1. 仓库 URL 查产品 | `coreinsight-cli skill offering --http_url "<仓库 HTTP URL>"` | 读取 `result.products[]` 的 `offering_id`、`offering_cn_name`，保留同一产品的 ID / 名称映射 |
| 1. 本地目录查产品（替代上一行） | `coreinsight-cli skill offering --repo "<本地仓库目录>"` | CLI 读取该目录的 origin 后查询，返回字段同上 |
| 2. 产品 ID 查场景 | `coreinsight-cli skill product-scenes --dim_code "<offering_id>"` | 读取 `result.scenes[]` 的 `firstScene`、`secondScene`，再按 1.x 任务描述与语言语义匹配 |
| 3. 命中场景查 Skill | `coreinsight-cli skill scene-skills --first_scene "<firstScene>" --second_scene "<secondScene>" --dim_type "产品级" --dim_name "<offering_cn_name>"` | 读取 `result.skills` 中实际返回的名称、描述及标识，每个命中场景分别查询，再为每任务筛选 Top3 |

`--dim_code` 使用产品 **ID**，`--dim_name` 使用对应产品 **名称**；`--dim_type "产品级"` 用于本消费流程的产品维度。一级、二级场景使用返回的原始值，不能用任务文本代替，也不能将产品 ID 填进 `--dim_name`。

本地仓也可以使用组合入口：

```text
coreinsight-cli skill scenes --repo "D:\projects\uscdb"
```

组合入口已经在 CLI 内部依次查询产品与场景，返回 `result.products[]` 中的 `offering_id`、`product`（对应产品名）和 `scenes`。复用已返回的场景后直接进入 `scene-skills`，不再重复执行 `offering` / `product-scenes`；成功返回空场景时按未命中处理。`--repo` 必须是本地目录；只有仓库 URL 时使用 `offering --http_url`，不得把 URL 当作本地路径。

已知映射的完整示例（示例值来自 UPCF 仓库，其他任务须替换为其真实返回值）：

```text
coreinsight-cli skill offering --http_url "https://codehub-y.huawei.com/pcc_db_tools/uscdb"
coreinsight-cli skill product-scenes --dim_code "22633567"
coreinsight-cli skill scene-skills --first_scene "需求开发" --second_scene "MML开发" --dim_type "产品级" --dim_name "UPCF"
```

`skill scene-search` 仍是把产品 / 场景拼成关键词的智能搜索；本业务链路使用 `scene-skills` 取得场景关联列表，不能把 `scene-search` 的结果冒充场景关联。分步路径不得省略 `offering_id → product-scenes`，也不要先按产品名猜场景。

### 通用检索、业务兜底与下载

| 用途 | 命令 |
|---|---|
| 通用能力或业务未命中时检索最多 3 个 Skill | `coreinsight-cli skill search --query "<任务描述、语言与关键词>" --page 1 --page_size 3` |
| 仅业务未命中时检索最多 3 条经验 | `coreinsight-cli experience search --query "<任务相关关键词>" --caller_id "<调用方工号>" --page 1 --page_size 3 --scene ALL` |
| 锁定选择后下载 ZIP | `coreinsight-cli skill download --skill_id "<真实 Skill ID>" --user_id "<调用方工号>" --output "<临时下载目录>"` |

当前浏览器登录不保存工号，经验检索的 `--caller_id` 和下载的 `--user_id` 使用已知的真实调用方工号；缺失时获取该信息或报告该项无法执行，不假设 CLI 可从登录推导。经验检索的 `--user_id` 是贡献者过滤，本流程默认不传。下载可在版本已知时追加 `--version "<真实版本>"`。

按名称去重不等于按名称下载：下载前保留已选结果的真实 Skill ID / 版本。场景结果只有名称与描述、缺少 ID 时，用 `coreinsight-cli skill search --query "<已选 Skill 名称>" --page 1 --page_size 3` 定位并核对同一个 Skill；不得猜 ID、直接取首条或静默改选。无法唯一定位时报告或交由主会话确认。CLI 仅下载 ZIP，校验、解压、安装与 tasks.md 回写按下文执行。

## 批量确认（候选准备后、下载前）

- 按任务组聚合候选，一次 AskUserQuestion（或当前环境等价交互工具）批量展示，不逐任务弹窗。展示任务编号、编程语言、候选名称 / 描述、匹配理由，并对每个首选标注 **✓ 推荐**；有经验候选时一起展示拟采用内容。
- 支持用户在同一次回答中按任务或任务组指定 Skill / 不使用；固定附加 **全部由 Agent 决定** 和 **本次不使用外部 Skill** 两个选项。
- 同一次回答的优先级为：全局「本次不使用外部 Skill」最高，其次逐任务指定，再次任务组指定，最后默认首选。某任务明确选择不使用时不得回退成推荐项，也不得通过新获取经验绕过。选择「全部由 Agent 决定」时采用首选；选择「本次不使用外部 Skill」时，本轮展示范围内的任务均不下载或使用外部 Skill，也不通过经验兜底绕过该选择。
- 用户跳过、提交但未选，或交互工具明确结束并返回无答案时，静默采用仍有合适候选任务的 Agent 首选；部分任务未指定时仅对这些任务采用首选。正在等待的提问不能仅凭时间流逝判为无响应；工具故障不能冒充用户跳过。
- 用户指定名称或明确确认推荐项记为「用户指定」；选择「全部由 Agent 决定」、跳过 / 未选或交互返回无答案后采用首选，记为「Agent 自选」。最终输出列明哪些任务由用户指定、哪些是 **Agent 自选**，以及哪些不使用或获取失败。无合适候选时继续原任务，不虚构首选。
- 以上默认规则只用于能力候选选择，不覆盖执行计划确认本身的空应答规则。单仓由主会话统一确认；多仓子代理只准备候选，由主会话汇总各仓任务组后统一提问并分发锁定结果，禁止子代理各自弹窗。

## CLI 接入、去重与项目级落地

- 所有产品、场景、Skill 与经验的查找和获取统一通过云见 CLI 完成，使用上方命令与字段映射。读取实际可用的云见 CLI Skill / 操作指引及帮助信息，以当前安装版本的帮助和实现核对参数，不编造命令、接口或标识，不另建绕开 CLI 的 HTTP 获取路径。
- 云见 CLI Skill 提供操作指引，业务 / 通用 Skill 提供任务实际使用的能力，二者不要混淆。其他场景先安装并读取云见 CLI Skill；已安装时直接读取。
- CLI、操作指引、身份、安装入口或服务不可用时，说明本次未获取到能力，继续原任务。交互工具故障时说明无法完成候选确认，本轮不新增下载；已有明确锁定的关联仍可使用。
- 确认或默认选择锁定后，扫描已选集合，**按 skill name 去重**；同一名称下载一次，多个任务共同引用。多仓可复用下载包，但分别安装到所属仓项目目录；候选及确认结果仅暂存在主会话上下文，不另建索引。
- Skill 包先解压到临时目录，校验名称、内容可读性及解压路径未越界，再原子替换项目级 **.codeagent/skills/<name>/**。本轮明确获取的同名 Skill 可以替换；只替换该名称目录，不改动其他 Skill 或相邻目录。
- 持久经验优先沿用项目的非临时目录；无既有约定时保存到 `.codeagent/experiences/`。回写前确认被引用内容不在 `docs/changes/<change>/downloads/`、`workflow/` 或阶段临时经验文件等清理目标中；历史关联位于临时路径时先复制到持久目录、校验并成功回写，再继续后续阶段，迁移或回写失败时暂停并报告。临时下载包可按原清理流程删除，清理步骤不承担消费配置或安装职责。
- 下载、校验或原子替换失败时保留原同名目录，不将半成品当作成功结果；只有验证旧内容仍适用时才继续使用旧内容并如实说明。经验按项目已有约定保存到项目级目录；单项失败不阻断其余成功内容或原任务。

## tasks.md 回写与后续消费

- **SDD 场景**：落地成功后回写对应任务的 **Skill 字段**，记录实际锁定名称、可读本地路径及选择来源（用户指定 / Agent 自选）；经验按任务已有描述约定关联。保留任务编号、checkbox、设计锚点及测试策略。
- 用户明确不使用时，将 Skill 字段写为「不使用（用户选择）」；无候选或获取失败时如实注明，不能将未成功落地的内容写成可用关联。明确不使用是有效决策，不能被当成缺少关联而自动重新检索。
- **其他场景**：直接用于当前任务，不修改 tasks.md，即使项目中已有该文件。
- tasks.md 是 SDD 任务及其能力关联的唯一数据源；下载文件只承载能力内容，不新增任务能力索引。
- 执行已有 SDD 任务时先读 Skill 字段及本地实际内容，复用已锁定的内容，不重复确认。只有确需新增 / 改选 Skill 时，才在任务循环前汇总受影响任务，执行一次批量确认；单纯补下已锁定的同名 Skill 无须再次选型。循环中才发现新增 / 改选需求时，先收集并预检其余待办任务，返回主会话的批量准备阶段统一处理，不逐任务临时弹窗；已有可用关联的任务可以继续。用户明确不使用的任务保持该决定，除非用户更改。
- 多仓以任务所属代码仓定位产品，内容落到该仓 .codeagent/skills，关联写入该仓 tasks.md；各仓执行者自行读取上下文，不在根项目另建汇总索引或修改其他仓任务。
- 没有本轮明确获取或更新决定时不自动覆盖项目本地内容；清理时保留任务仍引用的 Skill 与经验。
- 最终简要报告查找、选择来源、安装及 tasks.md 同步结果。获取失败不阻断原任务，同步未成功时不得宣称完成。

