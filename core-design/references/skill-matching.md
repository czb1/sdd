# 8.6 任务级领域 Skill 匹配

在 8.4 tasks.md 填充、8.5 设计锚点处理完成后，进入追溯验证前执行。只补充 **1.x 代码生成任务**，不修改 2.x 及以后任务或原 Code Review / UT 固定技能映射。增强能力失败只输出 WARNING，继续原设计流程。

本仓版本实际为 Phase 9 追溯验证、Phase 10 文档审查、Phase 11 清理；没有独立的 Verify Generated Artifacts 顶层 Phase。保持这些编号，不新增顶层小数 Phase，不改变现有产物校验要求。

## 数据与工具

`tasks.md` 是唯一持久化选择数据源。产品名写文件头 `<!-- product: 产品名 -->`；仅成功安装的任务追加 `Skill`、`Skill路径`、`Skill场景`、`Skill来源` 四个字段。首次生成、未匹配、拒绝使用、接口失败、下载/覆盖失败均**整组不写**，禁止空值或 `<待匹配>`。候选、理由、API结果只留在本次上下文，不创建索引或版本缓存。不创建 product.json；已有 `.codeagent/product.json` 仅作为产品解析输入。

脚本：`{skill_dir}/scripts/task_skill_matching.py`，路径相对于 core-design 安装目录。通过 subprocess 的 `input=json.dumps(payload)` 向 stdin 传 JSON，不将仓名、Skill 名或下载 URL 拼成 shell 命令。脚本输出 JSON；退出码不代表匹配成功，必须检查 `status` 和 `data.warnings`。`status: warning` 表示本次增强操作失败，不阻断 design。

| action | JSON 字段 | 用途 |
|---|---|---|
| tasks | repo（仓绝对路径）、tasks（tasks.md 绝对路径） | 只读取 1.x 描述与原始元数据（含语言） |
| product | repo | 读取 origin、根目录名、已有 product.json，并用 origin 查询产品列表 |
| scenes | offering_id | 查询产品场景 |
| skills | firstScene、secondScene、product_name | 查询场景 Skill 列表及版本 |
| finalize | repo、tasks、product（已解析产品名时传）、selections | 去重下载、安装、回写；空 selections 清除本轮 1.x 的旧 Skill 字段 |

## 产品 → 场景 → Skill 接口

实际接口是 POST，不使用设计示意图中的 GET，也不虚构 download(skill_name) 接口：

| 操作 | 地址 | 请求体 | 消费字段 |
|---|---|---|---|
| 产品 | `http://coreharness.spec.rnd.huawei.com/core-harness/api/v1/offering/list` | `{"page":1,"pageSize":20,"http_url":"https://codehub-y.huawei.com/CSP/CSPCertSDK_C"}` | `data[].offering_id` → dimCode；`offering_cn_name` → dimName |
| 场景 | `{SKILL_SCENE_BASE_URL}/experience/harness/scenes` | `{"dimCode":"22633567"}` | `data[].firstScene`、`secondScene` |
| Skill | `{SKILL_SCENE_BASE_URL}/experience/harness/scene/skills` | `{"firstScene":"需求开发","secondScene":"MML开发","dimType":"产品级","dimName":"UNC USMF  "}` | `skillName`、`skillDescription`、`versions` |
| 下载 | 被选 Skill 最新版本的 `downloadUrl` | GET，无需拼装路径 | ZIP 包 |

`SKILL_OFFERING_URL` 可覆盖产品完整地址。`SKILL_SCENE_BASE_URL` 默认是 `https://coreinsight.rnd.huawei.com`，表示服务基础地址，不包含 `/experience/harness/scenes`。脚本自动拼接上述场景和 Skill 列表路径，无需额外配置；其他部署可通过该环境变量覆盖。显式设置为空时 WARNING 后跳过，不阻塞。API 字段值（尤其产品名尾部空格）原样传回；展示时可 trim。产品分页读取至末页，不以第一页第一个结果作为默认产品。

选择最新版本按 `uploadDate` 的日期时间降序，不依赖返回顺序，也不按版本字符串字典序排序。版本信息不完整时告警，不猜下载地址、不静默回退旧版本。HTTP 请求有 30 秒超时、响应大小限制，使用系统 TLS 信任，不关闭证书校验、不臆造认证信息。

## 执行顺序

1. 读取本仓 tasks.md 的 1.x 任务、描述、编程语言。没有代码生成任务则结束。首次 8.4 完全不写四个 Skill 字段；重跑 8.6 时先用 `finalize` + `selections: []` 去掉本仓所有 1.x 旧选择，保留非 Skill 内容与本地目录，避免失败后旧选择继续生效。清除失败只报告 WARNING，不宣称本轮匹配成功，不重写其他产物。
2. 优先用 git origin 的 HTTP URL 查产品；SSH/SCP remote 规范化为 HTTPS，并去除凭据、查询串和 `.git`。唯一有效产品采用返回值；多个产品结合 tasks.md 已有产品注释、仓根目录名、已有 product.json 进行精确消歧，不能把仓名当产品 ID。既有配置可包含 `offering_id` / `offering_cn_name`，只作为明确的候选依据。产品名或 ID 无法确定时一次询问用户，可跳过；只给名称仍无法确定 ID 时跳过并告警，禁止猜 dimCode。用户跳过则 finalize 空选择，继续后续 Phase。
3. 产品确定后把名字写入文件头（`finalize` 空选择并传 product），再调 scenes。根据**每个任务描述 + 编程语言**语义匹配零到多个 `(firstScene, secondScene)`；不要仅靠字符串包含或所有任务共用一个场景。无相关场景的任务标记“未匹配到领域 Skill”。
4. 仅对命中场景调用 skills；同场景本轮只请求一次。接口①场景或②Skill 列表不可达/业务失败时，跳过本仓本轮匹配并记录 WARNING，不使用不完整候选偷偷决定。产品查询失败可用已明确的本地产品 ID/名称，否则询问或跳过。所有响应只保留本次内存。
5. 对每个 1.x 任务按领域相关性、语言兼容性、任务实际需要排序，列出 **Top 3（不足则按实际数量）**、各自场景和一句话理由；首选标 `✓ 推荐`。只有弱相关或不兼容 Skill 时允许无候选，不能为“匹配成功”强选。相同 skillName 跨场景去重，保留各任务实际命中场景。
6. **批量确认，不逐任务弹窗**：先展示 `仓 / 任务 / 语言 / Top3及理由 / 推荐` 表，再按任务组聚合到一次 AskUserQuestion。选择可用“组内全部推荐”或“自定义任务→Skill（可指定不使用）”表达，固定附加 `全部由 Agent 决定` / `本次不使用外部 Skill`。组很大或工具问题数/选项数有限时，将整张表作为问题上下文，以一次批量映射输入收集覆盖项，不退化成 N 次询问。确认规则：
   - 用户指定某 Skill → `用户选择`；明确接受展示的推荐映射同样记 `用户选择`。
   - `全部由 Agent 决定`、工具返回跳过/空答复、或未覆盖某任务 → 用该任务首选，记 `Agent自选`。未响应的判断以交互工具返回为准，不无限等待、反复追问或虚构用户回答。
   - 指定某任务“不使用”则不写字段；`本次不使用外部 Skill` 覆盖本批全部任务，**优先于推荐回退**。
   - 用户选择候选外名称时先在已返回目录验证可用性；未验证的名称不得下载或当作确认成功。无法验证则该任务无 Skill 并告警。
7. 锁定选择后构造 finalize 的 selections，仅包含选择了 Skill 的任务。每个对象形如：

   ```json
   {
     "task": "1.1",
     "skill": {
       "skillName": "k8s-deploy-helper",
       "versions": [{"version":"1.2.2","uploadDate":"2026-08-24 19:11:56","downloadUrl":"https://registry.example/skill.zip"}]
     },
     "scene": "需求开发 / 容器部署",
     "source": "Agent自选"
   }
   ```

   `skill` 对象及 URL 必须来自真实接口结果，例子不可直接用于下载。同名 Skill 多场景返回时先合并 versions，再按 uploadDate 选最新，给该名称的每个选择传一致的版本列表。脚本按 skillName 去重，每轮每个名称只下载一次，影响所有引用它的任务。
8. 安装成功后才成组回写字段：

   ```markdown
   # tasks.md
   <!-- product: paas-om -->

   ## 代码生成任务

   - [ ] 1.1 实现 namespace 粒度部署接口
     - **编程语言**: python
     - **关联需求**: REQ-001
     - **验收标准**: 支持按 namespace 提交部署请求
     - **设计锚点**: #3.1 #2.2
     - **Skill**: k8s-deploy-helper
     - **Skill路径**: .codeagent/skills/k8s-deploy-helper
     - **Skill场景**: 需求开发 / 容器部署
     - **Skill来源**: Agent自选
   ```

9. 输出按仓/任务的安装结果、来源、无匹配项及 WARNING，明确列出哪些为 Agent 自选。不以 Skill 失败改变原任务复选框、验收标准、需求或锚点。继续原产物校验与追溯审查，不修改其必需字段/占位符规则。

## 安装与降级保证

- `.codeagent/` 加入该仓 `.gitignore`；已有忽略规则保留。`.codeagent/skills/` 是共享目录，开始或结束时均不清空。Phase 11 清理也不得删除它，core-apply 仍需读取。
- 已有同名 Skill 仍下载最新包。只操作锁定名称；同名安装使用短期目录锁，冲突时本次降级，不删除其他安装者的锁。临时目录、锁是安装过程资源，不是持久化索引。
- ZIP 在目标同文件系统的临时目录解压；拒绝路径穿越、符号链接、特殊文件、重复路径与过大包；确认非空 UTF-8 SKILL.md 后再替换。支持包根或单层包装目录下的 SKILL.md，不执行包中脚本。
- 首次安装用 rename；覆盖用系统原子目录交换（Linux renameat2 RENAME_EXCHANGE），不采用“删旧再解压”或“两次 rename 假装原子”。系统不支持原子交换时保留旧目录并 WARNING，无新字段，继续原流程。
- 单个 Skill 下载/解压/覆盖失败，保留其原目录，不写所有关联任务的四字段；其他 Skill 照常。不能以旧目录存在当作本轮安装成功。
- tasks.md 整文件原子回写，仅改产品注释及 1.x 的四字段；2.x 及以后、其他字段保持不变。回写前检查文件未被并发修改；冲突时告警并重新读取，不能覆盖用户编辑。

## 多仓 M-2

主会话在 M-2 Step 4 子代理输入表显式传入本文件的**绝对路径与消费用途**。各仓先完成 8.4/8.5，再在子代理内查本仓产品、匹配场景和生成候选。子代理不能直接弹窗时返回 `SKILL_CANDIDATES`（包含仓路径、任务组、候选及理由）给主会话；主会话收齐本批候选后只做一次上述批量确认，再把按仓选择发回对应代理完成安装回写。此中间状态不是设计失败，不触发“失败重试”；不在候选阶段提前下载或宣布生成完成。跳过/空回答由主会话统一传回 Agent 自选结果，拒绝范围在问题中明确为本批。所有仓完成 8.6 或明确降级后再进入 M-3a。

各仓 tasks.md、产品、安装目录天然隔离；同名 Skill 不跨仓共享下载/目录，也不在工作区根目录安装。

## 审查兼容契约（调用方必须显式传入）

单仓 Phase 9/10 和多仓 M-3a/M-3b 每次初审、重审、降级调用都传入本节规则：

- L3 必需字段保持编程语言、关联需求、验收标准、设计锚点；四个 Skill 字段是允许出现的可选字段，缺失不算占位符、出现不算多余字段，产品注释不是任务。Skill 元数据不参与 delta_design 模块→tasks 映射。
- `.codeagent/skills/` 下的外部辅助 Skill 名称/路径不属于设计模块，不能**仅因这些元数据**判“引用 spec 外模块”；实际生成代码超出设计范围仍正常报告。
- 已提供批量确认机会且用户可拒绝时，按本规则产生的 `Skill来源: Agent自选` 不构成越权；来源字段就是选择留痕，不需要伪造 Q&A 或写“用户已确认”。这不豁免真正的越权设计或未提供确认机会的操作。
- 审查修复不得补写缺失 Skill 占位符，也不能为 Skill 名扩充 spec 模块。若旧 checker 不支持调用方契约，仍只因四字段报告误判，则对受影响任务撤销整组可选字段并重审，记录兼容性 WARNING，保留本地目录；不得伪造 PASS 或跳过原检查。仅撤销字段不能解决的真实设计问题仍按原流程处理。

本仓目前不包含 cross-doc-checker / design-doc-reviewer 源码，因此只能落地调用方传参契约，无法据此断言其内部白名单已经兼容。取得其源文件后还需将以上规则加入实际 checker/reviewer 并验证。
