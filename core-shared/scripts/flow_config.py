"""
Flow orchestration config for core-* skills.

Reads user-level global config (~/.corespec/flow-config.json, JSONC format),
resolves per-skill namespace (--skill <name>), computes config fingerprint,
determines confirmation scenario (A~E), builds the execution plan —
steps (full ordered view: fixed steps + configurable built-in steps,
each carrying its enabled state and execution info) + orchestration_points
(sub-step slots: pre-codegen / post-codegen / post-l4 / post-review / post-ut)
+ disabled (closed facts & reasons) — asserts the consistency contract,
generates skipped-<skill>.json same-source marker, and persists per-skill
execution-plan-<skill>.json. Config source stays in ~/.corespec/flow-config.json;
the plan presents only final execution state.

Per-skill registration: BUILT_IN_STEPS_BY_SKILL declares each skill's
configurable built-in steps; FIXED_STEPS_BY_SKILL declares each skill's
full ordered fixed-step flow (core-apply 15 steps, core-init 7 steps).

Sub-commands:
  --json              Output the execution plan as JSON (build-plan primary call)
  --describe          Output all configurable keys / schema / defaults / examples
  --init              Generate a commented JSONC template at ~/.corespec/flow-config.json
  --guide             Output the config guide text
  --apply             Apply confirmed adjustments to the plan and re-sync skipped marker
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_DIR_NAME = ".corespec"
CONFIG_FILE_NAME = "flow-config.json"
GUIDE_FILE_NAME = "flow-config-guide.md"
# Source of truth for the guide: GLOBAL shared guide lives in core-shared
# (framework-level, describes all core-* skills), NOT per-skill. It is
# mirrored to ~/.corespec/flow-config-guide.md on --init. Any skill's
# flow-config --init/--guide reads the same global source -> no per-skill
# copies to collide with each other at the user-level path.
GUIDE_SOURCE_RELPATH = "references/flow-config-guide.md"

# Built-in configurable steps metadata, registered PER SKILL namespace.
# Each core-* skill declares its own built-in steps (P3 generalization);
# currently core-apply and core-init are registered. Unregistered skills
# have NO built-in steps (their namespaces carry only custom steps) — a
# skill's built-in set is never imposed on another skill's namespace.
BUILT_IN_STEPS_BY_SKILL: Dict[str, List[Dict[str, Any]]] = {
    "core-apply": [
        {
            "key": "version_check",
            "at": "step-1",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 1",
            "description": "版本检查",
            "ref_file": {
                "single": "references/version-check.md",
                "multi": "references/version-check.md",
            },
        },
        {
            "key": "show_progress",
            "at": "step-8",
            "default": False,
            "depends_on": [],
            "skill_md_step": "Step 8",
            "description": "展示当前进度",
            "ref_file": {
                "single": "references/show-progress.md",
                "multi": "references/show-progress.md",
            },
        },
        {
            "key": "l4_review",
            "at": "step-10",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 10",
            "description": "L4 实现追溯验证",
            "ref_file": {
                "single": "references/l4-review.md",
                "multi": "references/l4-review-multi.md",
            },
        },
        {
            "key": "code_review",
            "at": "step-11",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 11",
            "description": "Code Review",
            "ref_file": {
                "single": "references/code-review.md",
                "multi": "references/code-review-multi.md",
            },
        },
        {
            "key": "unit_test",
            "at": "step-12",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 12",
            "description": "单元测试",
            "ref_file": {
                "single": "references/unit-test.md",
                "multi": "references/unit-test-multi.md",
            },
        },
        {
            "key": "l5_coverage",
            "at": "step-13",
            "default": True,
            "depends_on": ["unit_test"],
            "skill_md_step": "Step 13",
            "description": "L5 UT 覆盖度验证",
            "ref_file": {
                "single": "references/l5-coverage.md",
                "multi": "references/l5-coverage-multi.md",
            },
        },
        {
            "key": "completion_report",
            "at": "step-14",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 14",
            "description": "完成或暂停时展示状态",
            "ref_file": {
                "single": "references/completion-report.md",
                "multi": "references/completion-report.md",
            },
        },
    ],
    # core-init: 5 built-in steps (Step 0 version-check / Step 4 okf-knowledge-fetch /
    # Step 5 multi-analysis / Step 6a check-sync / Step 6b execute-sync).
    # SKILL.md step numbering is continuous (Step 0~6b), Step 6 splits into 6a/6b,
    # so `at` uses the 0-based EXECUTION position (steps.md sequence number - 1),
    # NOT the SKILL.md Step number — the convention documented in
    # skeleton-core-init.md §5.
    "core-init": [
        {
            "key": "version_check",
            "at": "step-0",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 0",
            "description": "版本检查",
            "ref_file": {
                "single": "references/version-check.md",
                "multi": "references/version-check.md",
            },
        },
        {
            "key": "okf_knowledge_fetch",
            "at": "step-4",
            "default": False,
            "depends_on": [],
            "skill_md_step": "Step 4",
            "description": "拉取产品知识中心代码仓（asset/ 扁平到 docs/knowledge/产品名/）",
            "ref_file": {
                "single": "references/okf-knowledge-fetch.md",
                "multi": "references/okf-knowledge-fetch.md",
            },
        },
        {
            "key": "multi_analysis",
            "at": "step-5",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 5",
            "description": "多仓依赖分析（subagent）",
            "ref_file": {
                "single": "references/multi-analysis.md",
                "multi": "references/multi-analysis.md",
            },
        },
        {
            "key": "check_sync",
            "at": "step-6",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 6a",
            "description": "同步必要性检查",
            "ref_file": {
                "single": "references/check-sync.md",
                "multi": "references/check-sync.md",
            },
        },
        {
            "key": "execute_sync",
            "at": "step-7",
            "default": True,
            # 依赖规则（flow_config.py apply_dependency_rules）：execute_sync
            # depends_on check_sync——check_sync 关闭时 execute_sync 依赖降级跳过
            # （dependency_downgraded，与 l5_coverage↔unit_test 同款机制）。
            "depends_on": ["check_sync"],
            "skill_md_step": "Step 6b",
            "description": "代码仓逆向文档获取",
            "ref_file": {
                "single": "references/execute-sync.md",
                "multi": "references/execute-sync-multi.md",
            },
        },
    ],
    # core-explore: 8 built-in steps（A 档 6 键 + B 档 3 键；其中 req_refine 默认 false）。
    # SKILL.md 采用"Step 0 + 阶段1~11"混合编号，steps.md 序号 1~16——
    # `at` 使用 0-based EXECUTION 位置（steps.md 序号 − 1 = 阶段编号 − 1），
    # 编号约定见 skeleton-core-explore.md §5.1：step-N = 阶段编号 − 1。
    # 5.5 已并入 5.1（集中路由，参照 core-apply Step 3），at 位序：
    # step-5=阶段5.1（检测与路由）、step-6=阶段5.1.5 需求文档细化（req_refine，
    #   默认关闭；启用后 step-4 解析设计文档自动降级——apply_dependency_rules 硬编码）、
    # step-7=阶段5.2、step-8=阶段5.3、step-9=阶段5.4。
    # 有 M 映射的 3 键（l1_review/explore_review/cleanup_temp）ref_file 双字段
    # {single, multi} 指向独立 *-multi.md（多仓承载 M-7/M-8/cleanup-temp 节）；
    # 无 M 映射的 3 键（version_check/find_similar/req_refine）中 req_refine 为通道型
    # （single≠multi，多仓只产出一份全局细化文档，不按仓拆分）；version_check/find_similar
    # 单多仓共用单文件。
    # B 档双层语义（knowledge_precheck/brainstorming/req_refine）：
    #   - knowledge_precheck/brainstorming 两键指令文件挂 ref_file 条件加载
    #     （knowledge-precheck.md / requirement-clarification.md，单多仓共用同一文件
    #     ——多仓 M-3 指令在 m3-multi.md，由 multi-repo.md 骨架 GATE 加载），
    #     关闭时文件不加载、内容不进上下文，检查点豁免、后处理降级（multi-repo.md M-3 同步豁免）。
    #   - req_refine 关闭时指令文件不加载、内容不进上下文；启用时产出 requirement.md
    #     + story.md 到 docs/.explore_context/req-refine/{需求ID}/，下游 knowledge_precheck
    #     （三条件豁免→四条件）与 brainstorming（七条件豁免→八条件）检测到产出自动豁免
    #     （豁免条件：docs/.explore_context/req-refine/{需求ID}/requirement.md 存在）。
    "core-explore": [
        {
            "key": "version_check",
            "at": "step-0",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 0",
            "description": "版本检查",
            "ref_file": {
                "single": "references/version-check.md",
                "multi": "references/version-check.md",
            },
        },
        {
            "key": "req_refine",
            "at": "step-6",
            "default": False,
            "depends_on": [],
            "skill_md_step": "阶段5.1.5",
            "description": "需求文档细化补全（产出 requirement.md + story.md 到 docs/.explore_context/req-refine/{需求ID}/；启用后 step-4 自动降级、step-7 上下文补全读取源切到 refined 文档）",
            # B 档双层语义：指令文件挂 ref_file 条件加载（req-refine.md / req-refine-multi.md，
            # 通道型——多仓只产出一份全局细化文档，不按仓拆分），关闭时文件不加载、内容不进上下文
            "ref_file": {
                "single": "references/req-refine.md",
                "multi": "references/req-refine-multi.md",
            },
        },
        {
            "key": "knowledge_precheck",
            "at": "step-8",
            "default": True,
            "depends_on": [],
            "skill_md_step": "阶段5.3",
            "description": "领域知识预澄清（检查点三条件；req_refine 产出时自动豁免→四条件）",
            # 双层语义：指令文件挂 ref_file 条件加载，关闭时文件不加载、三条件豁免
            # （req_refine 启用并产出 requirement.md 时自动追加第四条件豁免）
            "ref_file": {
                "single": "references/knowledge-precheck.md",
                "multi": "references/knowledge-precheck.md",
            },
        },
        {
            "key": "brainstorming",
            "at": "step-9",
            "default": True,
            "depends_on": [],
            "skill_md_step": "阶段5.4",
            "description": "需求澄清 brainstorming（检查点七条件；req_refine 产出时自动豁免→八条件）",
            # 双层语义：指令文件挂 ref_file 条件加载，关闭时文件不加载、七条件豁免、后处理降级
            # （req_refine 启用并产出 requirement.md 时自动追加第八条件豁免）
            "ref_file": {
                "single": "references/requirement-clarification.md",
                "multi": "references/requirement-clarification.md",
            },
        },
        {
            "key": "find_similar",
            "at": "step-11",
            "default": True,
            "depends_on": [],
            "skill_md_step": "阶段7",
            "description": "查找相似需求",
            "ref_file": {
                "single": "references/find-similar.md",
                "multi": "references/find-similar.md",
            },
        },
        {
            "key": "l1_review",
            "at": "step-13",
            "default": True,
            "depends_on": [],
            "skill_md_step": "阶段9",
            "description": "L1 需求完整性验证",
            "ref_file": {
                "single": "references/l1-review.md",
                "multi": "references/l1-review-multi.md",
            },
        },
        {
            "key": "explore_review",
            "at": "step-14",
            "default": True,
            "depends_on": [],
            "skill_md_step": "阶段10",
            "description": "explore-doc-reviewer 文档审查",
            "ref_file": {
                "single": "references/explore-review.md",
                "multi": "references/explore-review-multi.md",
            },
        },
        {
            "key": "cleanup_temp",
            "at": "step-15",
            "default": True,
            "depends_on": [],
            "skill_md_step": "阶段11",
            "description": "清理临时文件",
            "ref_file": {
                "single": "references/cleanup-temp.md",
                "multi": "references/cleanup-temp-multi.md",
            },
        },
    ],
    # core-design: 7 built-in steps（A 档 6 键 + B 档 1 键）。
    # SKILL.md 采用 "Phase 1~11" 连续编号，与 steps.md 序号一一对应——
    # `at` 使用 0-based EXECUTION 位置（steps.md 序号 − 1 = Phase 编号 − 1），
    # 编号约定见 skeleton-core-design.md §5：step-N = Phase 编号 − 1。
    # 内容型 3 键（version_check / read_similar / expert_experience）单多仓共用
    # 单文件；通道型 3 键（design_traceability / design_review / cleanup）按
    # 模式分文件 {single, multi} 指向独立 *-multi.md（多仓承载 M-3a/M-3b/cleanup 节）。
    # B 档 1 键（fetch_rules）只控 code-rule 拉取（Step 1~3），不控
    # design-principles / design-views GATE（GATE 无条件加载，与开关正交）。
    # M-2（各仓按仓生成）不可关，无 built-in 键映射——M-2 强制位永远生效。
    "core-design": [
        {
            "key": "version_check",
            "at": "step-0",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 1",
            "description": "版本检查",
            "ref_file": {
                "single": "references/version-check.md",
                "multi": "references/version-check.md",
            },
        },
        {
            "key": "fetch_rules",
            "at": "step-1",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 2",
            "description": "多语言规范获取（code-rule-tree → 筛选 → code-rule-content）；GATE 文件不受此开关控制",
            # B 档：只控 Step 1~3 的 code-rule 拉取，不控 design-principles/design-views GATE
            "ref_file": {
                "single": "references/rule-selection.md",
                "multi": "references/rule-selection.md",
            },
        },
        {
            "key": "read_similar",
            "at": "step-4",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 5",
            "description": "读取相似需求参考归档",
            "ref_file": {
                "single": "references/read-similar.md",
                "multi": "references/read-similar.md",
            },
        },
        {
            "key": "expert_experience",
            "at": "step-6",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 7",
            "description": "准备已有项目经验及任务能力查找上下文（不独立拉取经验）",
            "ref_file": {
                "single": "references/expert-experience.md",
                "multi": "references/expert-experience.md",
            },
        },
        {
            "key": "design_traceability",
            "at": "step-8",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 9",
            "description": "设计追溯验证（cross-doc-checker L2/L3，subagent 强制）",
            "ref_file": {
                "single": "references/design-traceability.md",
                "multi": "references/design-traceability-multi.md",
            },
        },
        {
            "key": "design_review",
            "at": "step-9",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 10",
            "description": "design-doc-reviewer 文档审查（subagent 强制）",
            "ref_file": {
                "single": "references/design-review.md",
                "multi": "references/design-review-multi.md",
            },
        },
        {
            "key": "cleanup",
            "at": "step-10",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Phase 11",
            "description": "清理临时文件（brainstorming/design.md/clarification_summary.json/drafts/downloads 等）",
            "ref_file": {
                "single": "references/cleanup.md",
                "multi": "references/cleanup-multi.md",
            },
        },
    ],
    # core-archive: 8 built-in steps（A 档 8 键）。
    # SKILL.md 采用 "Step 1~13" 编号（无 Step 0），steps.md 序号 1~12
    # （Step 13 push-and-mr 对应 steps.md 序号 12）。
    # `at` 使用 0-based EXECUTION 位置（steps.md 序号 − 1 = SKILL.md Step − 1）。
    # 编号约定见 skeleton-core-archive.md §5：step-N = SKILL.md Step N − 1 = steps.md 序号 − 1。
    # 内容型 4 键（version_check / check_artifacts / check_tasks / show_summary）
    # 单多仓共用单文件；通道型 4 键（core_verify / backfill / spec_sync / push_mr）
    # 按模式分文件 {single, multi}（backfill 例外：单文档承载标杆，single=multi=同文件）。
    # M-3（各仓归档并行）不可关，无 built-in 键映射——M-3 强制位永远生效。
    # Step 8 get-version 不可关（禁止默认版本是硬约束），无 built-in 键。
    "core-archive": [
        {
            "key": "version_check",
            "at": "step-0",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 1",
            "description": "版本检查（MANDATORY 第一个动作）",
            "ref_file": {
                "single": "references/version-check.md",
                "multi": "references/version-check.md",
            },
        },
        {
            "key": "core_verify",
            "at": "step-3",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 4",
            "description": "core-verify 归档前验证（subagent 强制，UNDER_IMPL 阻塞 / DOC_STALE 交反刷）",
            "ref_file": {
                "single": "references/verify-result-handling.md",
                "multi": "references/verify-multi.md",
            },
        },
        {
            "key": "check_artifacts",
            "at": "step-4",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 5",
            "description": "检查 artifact 完成状态（单仓 status 脚本 / 多仓 Glob）",
            "ref_file": {
                "single": "references/check-artifacts.md",
                "multi": "references/check-artifacts.md",
            },
        },
        {
            "key": "check_tasks",
            "at": "step-5",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 6",
            "description": "检查 task 完成状态 + 消费 skipped-core-apply.json",
            "ref_file": {
                "single": "references/check-tasks.md",
                "multi": "references/check-tasks.md",
            },
        },
        {
            "key": "backfill",
            "at": "step-8",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 9",
            "description": "代码反刷（GATE backfill-from-code.md，单文档承载单/多仓；多仓 M-1 子代理并行）",
            # 单文档承载标杆：single=multi=同文件（5.2 节区分多仓）
            "ref_file": {
                "single": "references/backfill-from-code.md",
                "multi": "references/backfill-from-code.md",
            },
        },
        {
            "key": "spec_sync",
            "at": "step-9",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 10",
            "description": "delta 合并到全量文档（单仓 prepare-sync-single / 多仓 M-2 子代理并行）",
            "ref_file": {
                "single": "references/spec-sync.md",
                "multi": "references/spec-sync-multi.md",
            },
        },
        {
            "key": "show_summary",
            "at": "step-11",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 12",
            "description": "展示归档摘要",
            "ref_file": {
                "single": "references/completion-report.md",
                "multi": "references/completion-report.md",
            },
        },
        {
            "key": "push_mr",
            "at": "step-12",
            "default": True,
            "depends_on": [],
            "skill_md_step": "Step 13",
            "description": "core-auto-git 推送 + 建 MR（单仓 / 多仓 M-4 逐仓）",
            # multi 内联在 multi-repo.md M-4 节（内容少不抽离独立文件）
            "ref_file": {
                "single": "references/push-mr.md",
                "multi": "references/push-mr.md",
            },
        },
    ],
}

# Orchestration point slots (SKILL.md preset positions).
# These are SUB-STEP slots (inside/around steps), NOT step-level phases:
# pre-codegen is inside the Step 9 task loop; the post-* slots sit between
# change-level steps. They live in a separate zone of the plan file.
ORCHESTRATION_POINTS: List[str] = [
    "pre-codegen",   # task level - inside Step 9 task loop, between 9.3 and 9.4
    "post-codegen",  # change level - after Step 9, before Step 10
    "post-l4",       # change level - after Step 10, before Step 11
    "post-review",   # change level - after Step 11, before Step 12
    "post-ut",       # change level - after Step 12, before Step 13
]

# Per-skill orchestration point slots (P3 generalization, parallel to
# FIXED_STEPS_BY_SKILL / BUILT_IN_STEPS_BY_SKILL). core-apply keeps the
# historical five change/task-level slots; core-init registers its own five
# slots (skeleton-core-init.md §6) — init-flow positions (post-* after the
# structure/language/analysis steps, pre/post-* around the per-repo sync loop).
ORCHESTRATION_POINTS_BY_SKILL: Dict[str, List[str]] = {
    "core-apply": ORCHESTRATION_POINTS,
    "core-init": [
        "post-init-structure",   # change level - after Step 2 (目录结构初始化)
        "post-scan-language",    # change level - after Step 4 (语言扫描)
        "post-multi-analysis",   # change level - after Step 5 (多仓依赖分析)
        "pre-execute-sync",      # repo level - Step 6b 每仓同步前
        "post-execute-sync",     # repo level - Step 6b 每仓完成后
    ],
    # core-explore: 9 插槽（skeleton-core-explore.md §6）。
    # 粒度：pre-* / post-* 均为 change 级（阶段间）；插槽分布
    # "澄清 → proposal → delta_spec → 验证 → 清理" 五段前后。
    # 新增 artifact 由 explore-doc-reviewer 统一审查（DAG 分层过滤），不再设 post-extra-review 编排点。
    "core-explore": [
        "pre-clarification",     # change level - 阶段5.4 brainstorming 前（5.2 补全上下文后）
        "post-clarification",    # change level - 阶段5.4 后处理完成后（5.1 多仓路由后由 M-3 替代，多仓下无此触发点）
        "pre-proposal",          # change level - 阶段6 proposal 生成前
        "post-proposal",         # change level - 阶段6 proposal 生成后（阶段7 前）
        "pre-delta-spec",        # change level - 阶段8 delta_spec 生成前
        "post-delta-spec",       # change level - 阶段8 delta_spec 生成后（阶段9 前）
        "post-l1",               # change level - 阶段9 L1 验证后（阶段10 前）
        "post-review",           # change level - 阶段10 explore-review 后（阶段11 前）
        "post-cleanup",          # change level - 阶段11 清理后（流程收尾）
    ],
    # core-design: 8 插槽（skeleton-core-design.md §6）。
    # 粒度：均为 change 级（Phase 间）；插槽分布
    # "规范 → 上下文 → 生成 → 验证 → 清理" 五段前后。
    # 新增 artifact 由 design-doc-reviewer 统一审查（DAG 分层过滤），不再设 post-extra-review 编排点。
    "core-design": [
        "post-rule-fetch",         # change level - Phase 2 后（规范获取完成后）
        "post-gather-context",     # change level - Phase 3 后（上下文读取完成后）
        "post-code-understanding", # change level - Phase 4 后（代码理解完成后）
        "pre-generate",            # change level - Phase 8 前（生成设计文档前）
        "post-generate",           # change level - Phase 8 后（生成设计文档后，Phase 9 前）
        "post-traceability",       # change level - Phase 9 后（追溯验证后，Phase 10 前）
        "post-design-review",      # change level - Phase 10 后（审查后，Phase 11 前）
        "post-cleanup",            # change level - Phase 11 后（清理后，流程收尾）
    ],
    # core-archive: 10 插槽（skeleton-core-archive.md §6）。
    # 粒度：均为 change 级（Step 间）；插槽分布
    # "验证 → 检查 → 反刷 → 合并 → 归档 → 推送" 六段前后。
    "core-archive": [
        "pre-verify",              # change level - Step 4 前（core-verify 验证前）
        "post-verify",             # change level - Step 4 后（验证后，Step 5 前）
        "pre-backfill",            # change level - Step 9 前（代码反刷前）
        "post-backfill",           # change level - Step 9 后（反刷后，Step 10 前）
        "pre-spec-sync",           # change level - Step 10 前（spec 合并前）
        "post-spec-sync",          # change level - Step 10 后（合并后，Step 11 前）
        "pre-archive",             # change level - Step 11 前（归档执行前）
        "post-archive",            # change level - Step 11 后（归档后，Step 12 前）
        "pre-push",                # change level - Step 13 前（推送前）
        "post-push",               # change level - Step 13 后（推送后，流程收尾）
    ],
}


def get_orchestration_points(skill: str) -> List[str]:
    """Return the orchestration point slots for the skill (fallback = core-apply's)."""
    return ORCHESTRATION_POINTS_BY_SKILL.get(skill, ORCHESTRATION_POINTS)

# Fixed steps of the SKILL.md main flow — always executed, NOT configurable.
# The execution plan presents the FULL ordered picture (steps + orchestration
# points) so users and agents see the whole flow, not only the configurable
# slices. key format: step-<n> mirrors SKILL.md Step <n>.
FIXED_STEPS: List[Dict[str, Any]] = [
    {"key": "step-0", "skill_md_step": "Step 0", "description": "构建执行计划"},
    {"key": "step-1", "skill_md_step": "Step 1", "description": "版本检查"},
    {"key": "step-2", "skill_md_step": "Step 2", "description": "选择 change"},
    {"key": "step-3", "skill_md_step": "Step 3", "description": "多仓检测与路由"},
    {"key": "step-4", "skill_md_step": "Step 4", "description": "检查 change 状态（单仓）"},
    {"key": "step-5", "skill_md_step": "Step 5", "description": "获取执行指令"},
    {"key": "step-6", "skill_md_step": "Step 6", "description": "读取上下文文件"},
    {"key": "step-7", "skill_md_step": "Step 7", "description": "加载代码生成原则（GATE）"},
    {"key": "step-8", "skill_md_step": "Step 8", "description": "展示当前进度"},
    {"key": "step-9", "skill_md_step": "Step 9", "description": "代码生成任务（含 pre-codegen 子环节）"},
    {"key": "step-10", "skill_md_step": "Step 10", "description": "Gate-1 L4 实现追溯验证"},
    {"key": "step-11", "skill_md_step": "Step 11", "description": "Code Review"},
    {"key": "step-12", "skill_md_step": "Step 12", "description": "单元测试"},
    {"key": "step-13", "skill_md_step": "Step 13", "description": "Gate-2 L5 UT 覆盖度验证"},
    {"key": "step-14", "skill_md_step": "Step 14", "description": "完成或暂停时展示状态"},
]

# Per-skill fixed step lists (P3 generalization). core-apply keeps the
# historical 15-step flow above; core-init registers its own 8-step flow.
# Convention (skeleton-core-init.md §5): step-<n> = 0-based EXECUTION position
# (steps.md sequence number - 1); the first step is ALWAYS step-0. core-init's
# SKILL.md numbering is continuous (Step 0~6b), Step 6 splits into 6a/6b,
# so the `skill_md_step` labels below keep the SKILL.md labels while `key`
# follows the execution position.
FIXED_STEPS_BY_SKILL: Dict[str, List[Dict[str, Any]]] = {
    "core-apply": FIXED_STEPS,
    "core-init": [
        {"key": "step-0", "skill_md_step": "Step 0", "description": "版本检查"},
        {"key": "step-1", "skill_md_step": "Step 1", "description": "模式检测（init/update）"},
        {"key": "step-2", "skill_md_step": "Step 2", "description": "初始化目录结构"},
        {"key": "step-3", "skill_md_step": "Step 3", "description": "语言扫描（language.json）"},
        {"key": "step-4", "skill_md_step": "Step 4", "description": "拉取产品知识中心代码仓（okf-knowledge-fetch）"},
        {"key": "step-5", "skill_md_step": "Step 5", "description": "多仓依赖分析（subagent）"},
        {"key": "step-6", "skill_md_step": "Step 6a", "description": "同步必要性检查"},
        {"key": "step-7", "skill_md_step": "Step 6b", "description": "代码仓逆向文档获取"},
    ],
    # core-explore: 16 步（SKILL.md "Step 0 + 阶段1~11" 混合编号，steps.md 序号 1~16）。
    # key 按 0-based EXECUTION 位置（steps.md 序号 − 1）；skill_md_step 保留 SKILL.md
    # 原编号标签（Step 0 / 阶段1~11），阶段 5 拆 5.1~5.4 四个子步骤 + 5.1.5 需求文档细化
    # （req_refine，5.5 已并入 5.1 集中路由，无独立步骤位）。
    # 编号约定见 skeleton-core-explore.md §5.1：step-N = 阶段编号 − 1。
    "core-explore": [
        {"key": "step-0", "skill_md_step": "Step 0", "description": "版本检查"},
        {"key": "step-1", "skill_md_step": "阶段1", "description": "检查用户输入"},
        {"key": "step-2", "skill_md_step": "阶段2", "description": "从 CoreAlm 获取需求信息"},
        {"key": "step-3", "skill_md_step": "阶段3", "description": "下载相关附件"},
        {"key": "step-4", "skill_md_step": "阶段4", "description": "解析设计文档（req_refine 启用时本步骤自动降级，由 step-6 替代）"},
        {"key": "step-5", "skill_md_step": "阶段5.1", "description": "多仓检测与路由（multi-repo-routing，5.5 已并入）"},
        {"key": "step-6", "skill_md_step": "阶段5.1.5", "description": "需求文档细化补全（req-refine，启用时产出 requirement.md + story.md 到 docs/.explore_context/req-refine/{需求ID}/）"},
        {"key": "step-7", "skill_md_step": "阶段5.2", "description": "补全上下文（context-completion，仅单仓；req_refine 启用时读取源切到 refined 文档）"},
        {"key": "step-8", "skill_md_step": "阶段5.3", "description": "领域知识预澄清（knowledge-pre-clarification）"},
        {"key": "step-9", "skill_md_step": "阶段5.4", "description": "需求澄清（requirement-clarification）"},
        {"key": "step-10", "skill_md_step": "阶段6", "description": "生成 proposal.md"},
        {"key": "step-11", "skill_md_step": "阶段7", "description": "查找相似需求（find-similar-changes）"},
        {"key": "step-12", "skill_md_step": "阶段8", "description": "生成 delta_spec.md + 剩余 artifact 循环 T5.2（详见 delta-spec-writing.md，delta_spec 生成完成后强制执行，禁止跳过：调 load_schema 获取清单→筛除内置 5 artifact→DAG 分层过滤只生成 requires ⊆ {proposal, delta_spec} 的非内置 artifact）"},
        {"key": "step-13", "skill_md_step": "阶段9", "description": "L1 需求完整性验证（verify-completeness）"},
        {"key": "step-14", "skill_md_step": "阶段10", "description": "explore-doc-reviewer 文档审查（explore-review）"},
        {"key": "step-15", "skill_md_step": "阶段11", "description": "清理临时文件（cleanup-temp）"},
    ],
    # core-design: 11 步（SKILL.md "Phase 1~11" 连续编号，steps.md 序号 1~11）。
    # key 按 0-based EXECUTION 位置（steps.md 序号 − 1）；skill_md_step 保留
    # SKILL.md 原编号标签（Phase 1~11）。Phase 8 在多仓模式下由 M-2 替代
    # （multi-repo.md M-2 各仓按仓生成），Phase 9→M-3a、Phase 10→M-3b、
    # Phase 11→多仓 cleanup，但 FIXED_STEPS 仍按 steps.md 序号统一编号。
    # 编号约定见 skeleton-core-design.md §5：step-N = Phase 编号 − 1。
    "core-design": [
        {"key": "step-0", "skill_md_step": "Phase 1", "description": "版本检查（MANDATORY 第一个动作）"},
        {"key": "step-1", "skill_md_step": "Phase 2", "description": "获取设计规范 + 设计原则/视图 GATE 加载"},
        {"key": "step-2", "skill_md_step": "Phase 3", "description": "收集上下文（delta_spec + 全局文档）"},
        {"key": "step-3", "skill_md_step": "Phase 4", "description": "代码理解（CodeBase 优先 → read/grep/glob 回退）"},
        {"key": "step-4", "skill_md_step": "Phase 5", "description": "读取相似需求参考归档"},
        {"key": "step-5", "skill_md_step": "Phase 6", "description": "读取 brainstorming design.md + impl_questions 确认"},
        {"key": "step-6", "skill_md_step": "Phase 7", "description": "获取专家经验（paradigm-exp-use）"},
        {"key": "step-7", "skill_md_step": "Phase 8", "description": "生成设计文档（delta_design/tasks/delta_test_design）+ 剩余 artifact 循环 T5.2（详见 artifact-generation.md §8.7，内置 5 artifact 生成完成后强制执行，禁止跳过：调 load_schema 获取清单→筛除内置 5 artifact→DAG 分层过滤只生成 requires 含 delta_design 或更下游的非内置 artifact）；多仓 M-2 替代"},
        {"key": "step-8", "skill_md_step": "Phase 9", "description": "设计追溯验证（cross-doc-checker L2/L3，subagent）"},
        {"key": "step-9", "skill_md_step": "Phase 10", "description": "design-doc-reviewer 审查（subagent）"},
        {"key": "step-10", "skill_md_step": "Phase 11", "description": "清理临时文件（brainstorming/design.md/clarification_summary.json/drafts/downloads 等）"},
    ],
    # core-archive: 13 步（SKILL.md "Step 1~13" 连续编号，steps.md 序号 1~13）。
    # key 按 0-based EXECUTION 位置（steps.md 序号 − 1）；skill_md_step 保留
    # SKILL.md 原编号标签（Step 1~13）。Step 7 get-repo-dirs 为多仓专属
    # （单仓模式下跳过），Step 8 get-version 不可关（禁止默认版本是硬约束）。
    # 多仓模式：Step 4→M-0、Step 9→M-1、Step 10→M-2、Step 11→M-3、Step 13→M-4，
    # 但 FIXED_STEPS 仍按 steps.md 序号统一编号。
    # 编号约定见 skeleton-core-archive.md §5：step-N = SKILL.md Step N − 1。
    "core-archive": [
        {"key": "step-0", "skill_md_step": "Step 1", "description": "版本检查（MANDATORY 第一个动作）"},
        {"key": "step-1", "skill_md_step": "Step 2", "description": "检查前置条件（change 目录存在 + proposal/delta_spec 存在）"},
        {"key": "step-2", "skill_md_step": "Step 3", "description": "多仓检测（repo_assignments.json）→ 单仓/多仓路由"},
        {"key": "step-3", "skill_md_step": "Step 4", "description": "core-verify 归档前验证（subagent 强制）；多仓 M-0 替代"},
        {"key": "step-4", "skill_md_step": "Step 5", "description": "检查 artifact 完成状态（delta_design/tasks/delta_test_design）"},
        {"key": "step-5", "skill_md_step": "Step 6", "description": "检查 task 完成状态 + 消费 skipped-core-apply.json"},
        {"key": "step-6", "skill_md_step": "Step 7", "description": "获取各仓目录路径（多仓专属，单仓跳过）"},
        {"key": "step-7", "skill_md_step": "Step 8", "description": "获取归档版本号（get-version，禁止默认版本）"},
        {"key": "step-8", "skill_md_step": "Step 9", "description": "代码反刷（backfill-from-code）；多仓 M-1 子代理并行替代"},
        {"key": "step-9", "skill_md_step": "Step 10", "description": "delta 合并到全量文档（spec-sync）；多仓 M-2 子代理并行替代"},
        {"key": "step-10", "skill_md_step": "Step 11", "description": "执行归档（archive-execution，归档索引+文件迁移）；多仓 M-3 并行替代"},
        {"key": "step-11", "skill_md_step": "Step 12", "description": "展示归档摘要（completion-report）"},
        {"key": "step-12", "skill_md_step": "Step 13", "description": "core-auto-git 推送 + 建 MR；多仓 M-4 逐仓替代"},
    ],
}


def get_fixed_steps(skill: str) -> List[Dict[str, Any]]:
    """Return the fixed steps list for the skill (fallback = core-apply's)."""
    return FIXED_STEPS_BY_SKILL.get(skill, FIXED_STEPS)


# Fixed-step keys that correspond to a configurable built-in step.
def _built_in_step_key_for(step_key: str, skill: str = "core-apply") -> Optional[str]:
    """Map a fixed step key to its built-in config key (per-skill)."""
    return {
        b["at"]: b["key"] for b in get_built_in_steps(skill)
    }.get(step_key)


def get_built_in_steps(skill: str) -> List[Dict[str, Any]]:
    """Return the built-in steps registered for the skill (empty for unregistered skills)."""
    return BUILT_IN_STEPS_BY_SKILL.get(skill, [])

# Custom step field schemas
REFERENCE_REQUIRED_FIELDS = ["type", "file", "at"]
SKILL_REQUIRED_FIELDS = ["type", "skill", "at"]


def allowed_at(skill: str) -> set:
    """Return the valid orchestration point names for a skill."""
    return set(get_orchestration_points(skill))
ALLOWED_TYPES = {"reference", "skill"}
ALLOWED_RUN_MODES = {"direct", "subagent"}

REASON_DISABLED_BY_CONFIG = "disabled_by_config"
REASON_USER_CANCELLED = "user_cancelled"
REASON_DEPENDENCY_DOWNGRADED = "dependency_downgraded"


# ---------------------------------------------------------------------------
# JSONC parsing (strip // line comments, keep strings intact)
# ---------------------------------------------------------------------------

def strip_jsonc_comments(text: str) -> str:
    """
    Strip // line comments from JSONC text, preserving strings.
    Handles: "..." strings with \" escapes, // line comments, /* */ block comments.
    """
    out: List[str] = []
    i = 0
    n = len(text)
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "/":
                # line comment: skip to newline
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if nxt == "*":
                # block comment: skip to */
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def parse_jsonc(text: str) -> Any:
    """Parse JSONC text into Python objects."""
    cleaned = strip_jsonc_comments(text)
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def get_corespec_dir() -> Path:
    """~/.corespec directory for user-level global config."""
    return Path.home() / CONFIG_DIR_NAME


def get_config_path() -> Path:
    return get_corespec_dir() / CONFIG_FILE_NAME


def get_guide_path() -> Path:
    return get_corespec_dir() / GUIDE_FILE_NAME


def update_config_value(skill: str, key: str, value: Any) -> Tuple[bool, str]:
    """Update a single key inside <skill> namespace of flow-config.json in place.

    Preserves JSONC comments and other skill namespaces by editing the raw
    text (regex within the skill block), not re-serializing the whole file.
    Used by --apply so adjustments persist into the config source; otherwise
    Step 0 rebuild (from config source) would overwrite the applied change.

    Returns (ok, error_message).
    """
    path = get_config_path()
    if not path.exists():
        return False, f"配置文件不存在：{path}"
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"配置文件读取失败：{e}"

    block = _find_skill_block(raw, skill)
    if block is None:
        return False, f"配置中不存在 '{skill}' 命名空间对象"
    head, body, tail = block

    # build the replacement line (keep indentation of the matched key)
    indent_match = re.search(r'(?m)^([ \t]*)"' + re.escape(key) + r'"\s*:', body)
    if indent_match is not None:
        indent = indent_match.group(1)
        # preserve a trailing comma AND any trailing // comment from the
        # original entry line
        comma = ""
        comment = ""
        line_match = re.search(r'(?m)^[ \t]*"' + re.escape(key) + r'"\s*:.*$', body)
        if line_match:
            raw_line = line_match.group(0)
            code_part, _, line_comment = raw_line.partition("//")
            if code_part.rstrip().endswith(","):
                comma = ","
            if line_comment:
                comment = "//" + line_comment
        replacement = f'{indent}"{key}": {json.dumps(value, ensure_ascii=False)}{comma}'
        if comment:
            replacement += " " + comment
        # Idempotency guard (2026-09-21 regression): when the entry already
        # holds the target value, the substitution below leaves the body
        # byte-identical and the old code misread that as "配置中不存在键",
        # aborting the whole --apply. Detect the no-op case up front and
        # return success without rewriting the file.
        if line_match:
            code_part = line_match.group(0).partition("//")[0].strip().rstrip(",").strip()
            colon = code_part.find(":")
            if colon != -1:
                try:
                    cur_value = json.loads(code_part[colon + 1:].strip())
                except Exception:
                    cur_value = None
                if cur_value is not None and cur_value == value:
                    return True, ""
        new_body = re.sub(
            r'(?m)^[ \t]*"' + re.escape(key) + r'"\s*:.*(?:\r?\n|$)',
            lambda m: replacement + m.group(0)[m.group(0).rfind("\n"):] if m.group(0).endswith("\n") else replacement,
            body,
            count=1,
        )
        if new_body == body:
            # The key exists (indent_match above found it); an unchanged
            # body after substitution can only mean the entry already holds
            # the target value — idempotent success, not a missing key.
            return True, ""
    else:
        # key absent -> insert before the namespace's closing brace
        last_close = body.rstrip().rfind("}")
        if last_close == -1:
            return False, f"配置中 '{skill}' 命名空间结构异常"
        # indent of the closing brace line -> child indent = that + 2 spaces
        before_close = body[:last_close]
        lines = body.splitlines()
        close_line_idx = None
        for i, ln in enumerate(lines):
            if ln.strip() == "}":
                close_line_idx = i
        if close_line_idx is None:
            return False, f"配置中 '{skill}' 命名空间结构异常"
        block_indent = lines[close_line_idx][: len(lines[close_line_idx]) - len(lines[close_line_idx].lstrip())]
        insert_indent = block_indent + "  "
        # find last non-blank, non-comment content line before the closing brace
        content_idx = None
        for i in range(close_line_idx - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
                content_idx = i
                break
        insert_lines = []
        if content_idx is not None:
            if not lines[content_idx].rstrip().endswith(","):
                lines[content_idx] = lines[content_idx].rstrip() + ","
        insert_lines.append(f'{insert_indent}"{key}": {json.dumps(value, ensure_ascii=False)}')
        new_body = "\n".join(lines[:close_line_idx]) + "\n" + "\n".join(insert_lines) + "\n" + block_indent + "}" + "\n"
        # normalize trailing newline: ensure body keeps its original ending
        if body.endswith("\n"):
            new_body = new_body.rstrip("\n") + "\n"

    new_raw = head + new_body + tail
    try:
        path.write_text(new_raw, encoding="utf-8")
    except Exception as e:
        return False, f"配置文件写入失败：{e}"
    return True, ""


def _locate_entry_range(body: str, key: str) -> Optional[Tuple[int, int]]:
    """Locate a top-level key entry inside the skill body.

    Returns (line_start, entry_end):
      line_start = index of the first char of the key's line
      entry_end   = index one past the newline that terminates the entry
                    (single line for scalars, balanced-brace object for
                    custom steps, including any trailing comma).
    Returns None when the key is absent.
    """
    m = re.search(r'(?m)^([ \t]*)"' + re.escape(key) + r'"\s*:', body)
    if m is None:
        return None
    line_start = body.rfind("\n", 0, m.start()) + 1
    after_colon = body[m.end():]
    if after_colon.lstrip().startswith("{"):
        # balanced scan from the first '{' (honors strings and comments)
        open_idx = body.find("{", m.end())
        depth = 0
        i = open_idx
        n = len(body)
        in_str = False
        while i < n:
            ch = body[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == '"':
                    in_str = False
                i += 1
                continue
            if ch == '"':
                in_str = True
                i += 1
                continue
            if ch == "/" and i + 1 < n:
                nxt = body[i + 1]
                if nxt == "/":
                    j = body.find("\n", i)
                    i = n if j == -1 else j + 1
                    continue
                if nxt == "*":
                    j = body.find("*/", i + 2)
                    i = n if j == -1 else j + 2
                    continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        else:
            return None
        # extend to include trailing comma and following newline
        j = end
        while j < n and body[j] in " \t":
            j += 1
        if j < n and body[j] == ",":
            end = j + 1
        nl = body.find("\n", end)
        if nl == -1:
            return None
        return line_start, nl + 1
    else:
        # scalar entry on one line (may carry a trailing // comment)
        nl = body.find("\n", m.start())
        if nl == -1:
            return None
        return line_start, nl + 1


def remove_config_key(skill: str, key: str) -> Tuple[bool, str]:
    """Hard-remove a key (custom step) from <skill> namespace of flow-config.json.

    Prefer comment_out_config_key for custom steps: soft removal keeps the
    declaration in the file (as a comment block) so it can be re-enabled.
    """
    path = get_config_path()
    if not path.exists():
        return False, f"配置文件不存在：{path}"
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"配置文件读取失败：{e}"

    block = _find_skill_block(raw, skill)
    if block is None:
        return False, f"配置中不存在 '{skill}' 命名空间对象"
    head, body, tail = block

    entry = _locate_entry_range(body, key)
    if entry is None:
        return False, f"配置中不存在键 '{key}'（{skill} 命名空间）"
    line_start, entry_end = entry
    new_body = body[:line_start] + body[entry_end:]

    # fix dangling comma: if the removed entry was the LAST effective key in
    # the namespace, strip the trailing comma from the previous key line
    new_body = _strip_dangling_comma_before_close(new_body)

    if new_body == body:
        return False, f"配置中不存在键 '{key}'（{skill} 命名空间）"
    new_raw = head + new_body + tail
    try:
        path.write_text(new_raw, encoding="utf-8")
    except Exception as e:
        return False, f"配置文件写入失败：{e}"
    return True, ""


def comment_out_config_key(skill: str, key: str) -> Tuple[bool, str]:
    """Soft-remove a custom step: comment the whole entry out in place.

    The entry (scalar or nested object) is preserved as a commented block
    ('// ' prefix per line, original indentation kept) so it can be
    re-enabled later via uncomment_config_key / --apply --changes <key>=true.
    Comments of other keys and other namespaces are preserved. The commented
    declaration does NOT participate in the config fingerprint, so scenario
    detection (A~E) is unaffected by soft removals.

    Returns (ok, error_message).
    """
    path = get_config_path()
    if not path.exists():
        return False, f"配置文件不存在：{path}"
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"配置文件读取失败：{e}"

    block = _find_skill_block(raw, skill)
    if block is None:
        return False, f"配置中不存在 '{skill}' 命名空间对象"
    head, body, tail = block

    entry = _locate_entry_range(body, key)
    if entry is None:
        return False, f"配置中不存在键 '{key}'（{skill} 命名空间）"
    line_start, entry_end = entry

    commented: List[str] = []
    for ln in body[line_start:entry_end].splitlines(keepends=True):
        if ln.strip():
            # preserve the ORIGINAL line indentation so nested lines stay
            # visually nested inside the commented block (uncomment and
            # declaration parsing rely on it)
            indent = ln[: len(ln) - len(ln.lstrip())]
            commented.append(indent + "// " + ln.lstrip())
        else:
            commented.append(ln)
    new_body = body[:line_start] + "".join(commented) + body[entry_end:]
    # after commenting, the previous effective key may carry a dangling
    # trailing comma (JSONC tolerates it, plain json does not)
    new_body = _strip_dangling_comma_before_close(new_body)

    if new_body == body:
        return False, f"配置中不存在键 '{key}'（{skill} 命名空间）"
    new_raw = head + new_body + tail
    try:
        path.write_text(new_raw, encoding="utf-8")
    except Exception as e:
        return False, f"配置文件写入失败：{e}"
    return True, ""


def _top_level_indent(body: str) -> Optional[str]:
    """Indent (whitespace prefix) of the first top-level key line in a skill body.

    The body starts with the skill key line itself ('"<skill>": {'); the first
    key line AFTER it is a top-level key of the namespace (e.g. a built-in
    switch or a custom step declaration). Its indent distinguishes top-level
    declarations from entries nested inside a custom step object.
    """
    for ln in body.splitlines()[1:]:
        m = re.match(r'^([ \t]*)"[^"]+"\s*:', ln)
        if m:
            return m.group(1)
    return None


def _fix_restored_entry_separators(
    lines: List[str], start_idx: int, end_idx: int
) -> List[str]:
    """Fix JSON separators around a (re)enabled entry inside the skill body.

    Called after uncommenting: the restored entry must be properly separated
    from its neighbours so the namespace stays valid after comment stripping:
      - the entry's last line ends with ',' when more effective content follows
      - the entry's last line does NOT end with ',' when it is the last
        effective key before the namespace closing brace
      - the previous effective line (not the namespace '{') gains a trailing
        ',' when it lacked one (the commented entry used to be last)
    Mutates and returns the line list.
    """
    def _strip_nl(s: str) -> str:
        return s[:-1] if s.endswith("\n") else s

    def _rewrite(idx: int, code: str, cmt: str) -> None:
        nl = "\n" if lines[idx].endswith("\n") else ""
        if cmt:
            lines[idx] = code + " //" + cmt + nl
        else:
            lines[idx] = code + nl

    # 1. previous effective line needs a trailing comma
    prev_eff = None
    for j in range(start_idx - 1, -1, -1):
        s = _strip_nl(lines[j]).strip()
        if not s or s.startswith("//"):
            continue
        prev_eff = j
        break
    if prev_eff is not None:
        code, _, cmt = _strip_nl(lines[prev_eff]).partition("//")
        code = code.rstrip()
        if code != "{" and not code.endswith(","):
            _rewrite(prev_eff, code + ",", cmt)

    # 2. entry's last line: comma depends on whether effective content follows
    nxt_eff = None
    for j in range(end_idx, len(lines)):
        s = _strip_nl(lines[j]).strip()
        if not s or s.startswith("//"):
            continue
        if s == "}":
            break
        nxt_eff = j
        break
    last_idx = end_idx - 1
    code, _, cmt = _strip_nl(lines[last_idx]).partition("//")
    code = code.rstrip()
    if nxt_eff is not None:
        if not code.endswith(","):
            _rewrite(last_idx, code + ",", cmt)
    else:
        if code.endswith(","):
            _rewrite(last_idx, code[:-1], cmt)
    return lines


def uncomment_config_key(skill: str, key: str) -> Tuple[bool, str]:
    """Re-enable a commented-out custom step: remove the '// ' prefix block.

    Scans the <skill> namespace for a commented declaration matching
    '// "key":' at top-level indentation and uncomments the whole block
    (every consecutive comment line), restoring it as a live entry. Entry
    separators (commas) are fixed so the namespace remains valid JSON after
    comment stripping.

    Returns (ok, error_message).
    """
    path = get_config_path()
    if not path.exists():
        return False, f"配置文件不存在：{path}"
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"配置文件读取失败：{e}"

    block = _find_skill_block(raw, skill)
    if block is None:
        return False, f"配置中不存在 '{skill}' 命名空间对象"
    head, body, tail = block

    lines = body.splitlines(keepends=True)
    top_indent = _top_level_indent(body)
    key_pat = re.compile(r'^([ \t]*)//[ \t]*"' + re.escape(key) + r'"\s*:')
    start_idx = None
    for i, ln in enumerate(lines):
        m = key_pat.match(ln)
        if m is None:
            continue
        if top_indent is not None and m.group(1) != top_indent:
            continue  # nested comment inside another entry, not a top-level key
        start_idx = i
        break
    if start_idx is None:
        return False, f"配置中不存在被注释的键 '{key}'（{skill} 命名空间；仅可启用已注释的自定义步骤）"

    _, end_idx = _commented_block_bounds(lines, top_indent, start_idx)

    uncommented: List[str] = []
    for ln in lines[start_idx:end_idx]:
        # remove the '//' prefix but KEEP the original code indentation:
        # '  // "type":' (nested) -> '  "type":'; the extra space between
        # '//' and the code belongs to the comment, not the code indentation
        m2 = re.match(r'^([ \t]*)// ?(.*)$', ln)
        if m2 is None:
            uncommented.append(ln)
            continue
        nl = "\n" if ln.endswith("\n") else ""
        uncommented.append(m2.group(1) + m2.group(2).rstrip("\n") + nl)

    new_lines = lines[:start_idx] + uncommented + lines[end_idx:]
    new_lines = _fix_restored_entry_separators(new_lines, start_idx, start_idx + len(uncommented))
    new_body = "".join(new_lines)

    if new_body == body:
        return False, f"配置中不存在被注释的键 '{key}'（{skill} 命名空间）"
    new_raw = head + new_body + tail
    try:
        path.write_text(new_raw, encoding="utf-8")
    except Exception as e:
        return False, f"配置文件写入失败：{e}"
    return True, ""


def _commented_block_bounds(
    lines: List[str], top_indent: Optional[str], start: int
) -> Tuple[int, int]:
    """Return (start_idx, end_idx) of the commented declaration block starting
    at lines[start] (a top-level '// "key":' comment line).

    The block runs over consecutive comment lines and closes when the object
    depth returns to 0 (the '// }' line). A following '// "otherkey":' at
    top-level indentation is a SEPARATE declaration and is not consumed —
    sibling commented declarations are never merged into one block.
    """
    depth = 0
    j = start
    n = len(lines)
    key_pat = re.compile(r'^([ \t]*)//[ \t]*"[^"]+"\s*:')
    while j < n and lines[j].strip().startswith("//"):
        s = lines[j].lstrip()[2:]  # text after '//'
        depth += s.count("{") - s.count("}")
        j += 1
        if depth <= 0:
            # object closed (or scalar declaration): the block ends here;
            # check what follows without consuming it
            if j < n:
                nxt = lines[j]
                if not nxt.strip().startswith("//"):
                    break
                nm = key_pat.match(nxt)
                if nm is not None and (top_indent is None or nm.group(1) == top_indent):
                    break  # a new top-level declaration starts on the next line
            break
    return start, j


def _parse_commented_declaration(block_lines: List[str]) -> Optional[Dict[str, Any]]:
    """Best-effort parse of a commented declaration block into a dict.

    The block text is '"<key>": { ... }' — a bare key-value pair, not a valid
    standalone document. Wrap it in braces and extract the value for the key.
    A trailing ',' on the closing line (e.g. '// },' produced when the entry
    was not the last effective key) is stripped before parsing.
    """
    uncommented: List[str] = []
    for ln in block_lines:
        s = ln.lstrip()
        if s.startswith("//"):
            s = s[2:].lstrip()
        uncommented.append(s)
    text = "".join(uncommented).strip()
    if text.endswith(","):
        text = text[:-1]
    try:
        parsed = json.loads("{" + text + "}")
    except Exception:
        return None
    if not isinstance(parsed, dict) or len(parsed) != 1:
        return None
    value = next(iter(parsed.values()))
    return value if isinstance(value, dict) else None


def list_active_custom_steps(skill: str, plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """List the currently ACTIVE (enabled) custom steps across all slots.

    Source of truth = the execution plan's orchestration_points zone (built
    from the config source). Each slot entry is returned with its slot name;
    entries carry key/type/order/file|skill/run_mode already. The list feeds
    the Adjust plan confirmation so active custom steps get a "关闭 <key>"
    option (2026-09-21: previously only enable options were offered, forcing
    the user to type a free-text answer to close e.g. compile).
    """
    plan = plan or {}
    entries: List[Dict[str, Any]] = []
    for slot in get_orchestration_points(skill):
        for e in plan.get("orchestration_points", {}).get(slot, []):
            if not isinstance(e, dict) or not e.get("key"):
                continue
            entries.append({"key": e["key"], "slot": slot, "declaration": e})
    return entries


def list_commented_custom_steps(skill: str) -> List[Dict[str, Any]]:
    """Scan the <skill> namespace for commented-out custom step declarations.

    Matches '// "key":' comment blocks at top-level indentation (the format
    produced by comment_out_config_key / the TEMPLATE_JSONC examples).
    Returns keys in file order, each with a best-effort parsed declaration
    ({key, declaration}) when the block is a valid JSON object, else
    declaration=None. The list feeds --apply --changes <key>=true re-enable
    options and the Adjust plan confirmation.
    """
    path = get_config_path()
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        return []
    block = _find_skill_block(raw, skill)
    if block is None:
        return []
    _, body, _ = block

    lines = body.splitlines(keepends=True)
    top_indent = _top_level_indent(body)
    key_pat = re.compile(r'^([ \t]*)//[ \t]*"([^"]+)"\s*:')
    result: List[Dict[str, Any]] = []
    i = 0
    n = len(lines)
    while i < n:
        m = key_pat.match(lines[i])
        if m is None or (top_indent is not None and m.group(1) != top_indent):
            i += 1
            continue
        key = m.group(2)
        start, end = _commented_block_bounds(lines, top_indent, i)
        block_lines = lines[start:end]
        result.append({"key": key, "declaration": _parse_commented_declaration(block_lines)})
        i = end
    return result


def _strip_dangling_comma_before_close(body: str) -> str:
    """Remove a trailing comma on the last effective key before the namespace's
    closing brace (JSONC tolerates it, but plain json.loads does not)."""
    lines = body.splitlines()
    close_idx = None
    for i, ln in enumerate(lines):
        if ln.strip() == "}":
            close_idx = i
            break
    if close_idx is None:
        return body
    for i in range(close_idx - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("//"):
            continue
        # last effective line: strip its trailing comma, keeping any comment
        lines[i] = lines[i].rstrip()
        if "//" in lines[i]:
            code_part, comment = lines[i].split("//", 1)
            if code_part.rstrip().endswith(","):
                lines[i] = code_part.rstrip()[:-1] + " //" + comment
        elif lines[i].endswith(","):
            lines[i] = lines[i][:-1]
        break
    return "\n".join(lines)


def _find_skill_block(raw: str, skill: str) -> Optional[Tuple[str, str, str]]:
    """Locate the <skill> namespace object in the JSONC text.

    Returns (head, body, tail): head = text before the skill key, body = the
    full skill object INCLUDING its outer braces, tail = the rest of the file.

    Uses balanced-brace scanning (JSONC comments/strings preserved verbatim).
    """
    key_pat = re.compile(r'(?m)^([ \t]*)"' + re.escape(skill) + r'"[ \t]*:[ \t]*\{')
    m = key_pat.search(raw)
    if not m:
        return None
    start = m.start()
    open_idx = raw.find("{", m.end() - 1)
    if open_idx == -1:
        return None
    # scan forward counting braces, honoring strings (\" escapes) and
    # // and /* */ comments so a "}" inside a string/comment is not counted
    depth = 0
    i = open_idx
    n = len(raw)
    in_str = False
    while i < n:
        ch = raw[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt == "/":
                j = raw.find("\n", i)
                i = n if j == -1 else j + 1
                continue
            if nxt == "*":
                j = raw.find("*/", i + 2)
                i = n if j == -1 else j + 2
                continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                return (raw[:start], raw[start:end], raw[end:])
        i += 1
    return None


def get_flow_context_dir(project_root: str) -> Path:
    return Path(project_root) / "docs" / ".flow_context"


def get_plan_path(project_root: str, skill: str) -> Path:
    return get_flow_context_dir(project_root) / f"execution-plan-{skill}.json"


def get_skipped_path(project_root: str, skill: str) -> Path:
    return get_flow_context_dir(project_root) / f"skipped-{skill}.json"


def _extract_skill_block_from_template(skill: str) -> Optional[str]:
    """
    Extract the <skill> namespace object from TEMPLATE_JSONC, uncommented one
    level. Handles BOTH forms:
      - active block:    "core-apply": { ... }  (top-level object)
      - commented block: // "core-init": { ... } (template example, uncommented here)
    Returns the block text ('  "skill": { ... }\n') or None when the template
    has no such block.

    Used by run_init --skill to append a missing namespace to an existing
    config file WITHOUT overwriting already-configured namespaces.
    """
    # active form (core-apply in the template)
    block = _find_skill_block(TEMPLATE_JSONC, skill)
    if block is not None:
        _, body, _ = block
        return body if body.endswith("\n") else body + "\n"
    # commented form: '// "skill": {'
    lines = TEMPLATE_JSONC.splitlines()
    key_pat = re.compile(r'^([ \t]*)//[ \t]*"' + re.escape(skill) + r'"[ \t]*:[ \t]*\{')
    start = None
    for i, ln in enumerate(lines):
        if key_pat.match(ln):
            start = i
            break
    if start is None:
        return None
    out: List[str] = []
    depth = 0
    for ln in lines[start:]:
        m = re.match(r'^([ \t]*)//( ?)(.*)$', ln)
        uncommented = m.group(1) + m.group(3) if m else ln
        out.append(uncommented)
        s = uncommented.lstrip()
        if s.startswith("//"):
            continue  # still a comment after one-level uncomment (inner examples)
        if s.startswith("}"):
            depth -= 1
            if depth <= 0:
                break
            continue
        if s.startswith('"') and ":" in s:
            depth += s.count("{") - s.count("}")
    return "\n".join(out) + "\n"


def _find_top_level_close(raw: str) -> Optional[int]:
    """Index of the top-level closing '}' (depth 0), honoring strings and
    comments. None when the file is not a balanced object."""
    i = 0
    n = len(raw)
    depth = 0
    in_str = False
    while i < n:
        ch = raw[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt == "/":
                j = raw.find("\n", i)
                i = n if j == -1 else j + 1
                continue
            if nxt == "*":
                j = raw.find("*/", i + 2)
                i = n if j == -1 else j + 2
                continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _ensure_comma_before_close(raw: str) -> str:
    """Ensure the last effective line before the top-level '}' ends with a
    comma (so an appended namespace block stays valid). Returns the updated
    text (unchanged when a comma is already present).

    Splices the comma in place (no line splitting) so surrounding newlines
    and indentation are preserved verbatim.
    """
    close_idx = _find_top_level_close(raw)
    if close_idx is None:
        return raw
    # walk upward from the close-brace line, skipping blank/comment-only
    # lines, to find the start of the last effective line
    ls = raw.rfind("\n", 0, close_idx) + 1  # start of the line holding '}'
    while True:
        seg = raw[ls:close_idx]
        if seg.strip() and not seg.strip().startswith("//"):
            break
        prev = raw.rfind("\n", 0, ls - 1)
        if prev < 0:
            return raw  # nothing effective before the close brace
        ls = prev + 1
    line_end = raw.find("\n", ls, close_idx)
    if line_end == -1:
        line_end = close_idx
    line = raw[ls:line_end].rstrip("\r")
    if "//" in line:
        code_len = len(line.partition("//")[0].rstrip())
        if raw[ls : ls + code_len].endswith(","):
            return raw
        return raw[: ls + code_len] + "," + raw[ls + code_len :]
    if line.endswith(","):
        return raw
    # append the comma at the end of the effective line (before its newline),
    # NOT at the close-brace position (which would glue it onto the next line)
    return raw[: ls + len(line)] + "," + raw[ls + len(line) :]



# ---------------------------------------------------------------------------
# Config loading & validation
# ---------------------------------------------------------------------------

def _repair_trailing_commas(raw: str) -> Tuple[str, bool]:
    """Repair JSONC files whose last effective key before a '}' carries a
    trailing comma (JSONC tolerates it, plain json.loads does not).

    Such files are produced by older --apply write-backs (2026-09-21: a
    second session reported 'config_missing: true' although the config file
    existed — load_config failed on the dangling comma and run_build silently
    degraded to the all-default plan). The repair strips every ',' that is
    immediately followed by optional whitespace/newlines and a '}' in the
    comment-stripped text, mapping the position back to the ORIGINAL raw text
    (which keeps JSONC comments intact). Returns (repaired_text, changed).

    Only line-level tail commas are handled: a ',' that precedes a '}' after
    optional blank lines. This is exactly the shape
    '_strip_dangling_comma_before_close' normalizes on the skill body, but
    applied globally (top level + every namespace) before any parse.
    """
    # align raw lines with their comment-stripped counterparts so a ',' found
    # in the stripped text can be mapped back to the raw line that holds it
    stripped_out: List[str] = []
    raw_line_starts: List[int] = []  # start index of each raw line in stripped_out
    for ln in raw.splitlines(keepends=True):
        raw_line_starts.append(len("".join(stripped_out)))
        stripped_out.append(strip_jsonc_comments(ln))
    stripped_text = "".join(stripped_out)

    lines = raw.splitlines(keepends=True)
    changed = False
    n = len(stripped_text)
    i = 0
    while i < n:
        if stripped_text[i] != ",":
            i += 1
            continue
        j = i + 1
        while j < n and stripped_text[j] in " \t\r\n":
            j += 1
        if j >= n or stripped_text[j] != "}":
            i += 1
            continue
        # locate the raw line holding this ',' (largest start <= i)
        line_idx = 0
        for k, start in enumerate(raw_line_starts):
            if start <= i:
                line_idx = k
            else:
                break
        raw_line = lines[line_idx]
        code_part, sep, comment = raw_line.partition("//")
        if code_part.rstrip().endswith(","):
            fixed_code = code_part.rstrip()[:-1]
            if sep:
                lines[line_idx] = fixed_code + " " + sep + comment
            else:
                lines[line_idx] = fixed_code + raw_line[len(code_part):]
            changed = True
        i = j + 1
    return "".join(lines), changed


def load_config(config_path: Optional[Path] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Load the global flow config.

    Returns:
        (config_dict, error_message). config_dict is None when file missing
        or unreadable (error_message describes the problem).

    Self-healing: a JSONC parse failure caused by a dangling trailing comma
    (produced by older --apply write-backs) is repaired in place and reloaded,
    so an existing config is never silently degraded to 'config_missing'.
    """
    path = config_path or get_config_path()
    if not path.exists():
        return None, None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return None, f"flow-config.json 读取失败：{e}"
    try:
        data = parse_jsonc(text)
        if not isinstance(data, dict):
            return None, f"flow-config.json 顶层必须是对象，实际为 {type(data).__name__}"
        return data, None
    except json.JSONDecodeError:
        # self-heal dangling trailing commas (JSONC-legal, JSON-illegal)
        repaired, changed = _repair_trailing_commas(text)
        if changed:
            try:
                path.write_text(repaired, encoding="utf-8")
            except Exception as e:
                return None, f"flow-config.json 修复尾逗号后写入失败：{e}"
            try:
                data = parse_jsonc(repaired)
                if isinstance(data, dict):
                    return data, None
            except json.JSONDecodeError:
                pass
        # still invalid after repair (or nothing to repair): report the error
        try:
            parse_jsonc(text)
        except json.JSONDecodeError as e:
            return None, f"flow-config.json 解析失败（JSONC 剥离注释后仍非法）：{e}"
        except Exception as e:
            return None, f"flow-config.json 解析失败：{e}"
        return None, "flow-config.json 解析失败（修复尾逗号后仍非法）"


def get_skill_namespace(config: Dict[str, Any], skill: str) -> Optional[Dict[str, Any]]:
    """Extract the per-skill namespace object. None when the skill object is absent."""
    ns = config.get(skill)
    if ns is None:
        return None
    if not isinstance(ns, dict):
        raise ValueError(f"配置中 '{skill}' 顶层对象必须是对象，实际为 {type(ns).__name__}")
    return ns


def validate_builtin_keys(ns: Dict[str, Any], skill: str) -> List[str]:
    """Validate built-in step switches are boolean. Returns error messages."""
    errors: List[str] = []
    known = {b["key"] for b in get_built_in_steps(skill)}
    for key, value in ns.items():
        if key in known and not isinstance(value, bool):
            errors.append(f"内置步骤 '{key}' 的值必须是 true/false，实际为 {value!r}")
    return errors


def validate_custom_step(name: str, value: Any, skill: str) -> List[str]:
    """Validate a custom step declaration. Returns error messages."""
    errors: List[str] = []
    if not isinstance(value, dict):
        return [f"自定义步骤 '{name}' 必须是对象 {{...}}，实际为 {type(value).__name__}（值类型仅支持 true/false 或对象）"]
    stype = value.get("type")
    if stype not in ALLOWED_TYPES:
        return [f"自定义步骤 '{name}' 的 type 必须是 {sorted(ALLOWED_TYPES)} 之一，实际为 {stype!r}"]
    if stype == "reference":
        for f in REFERENCE_REQUIRED_FIELDS:
            if f not in value:
                errors.append(f"reference 型步骤 '{name}' 缺少必填字段 '{f}'")
    else:
        for f in SKILL_REQUIRED_FIELDS:
            if f not in value:
                errors.append(f"skill 型步骤 '{name}' 缺少必填字段 '{f}'")
    at = value.get("at")
    if at is not None and at not in allowed_at(skill):
        errors.append(f"步骤 '{name}' 的 at='{at}' 无效，必须是 {sorted(get_orchestration_points(skill))} 之一")
    if "args" in value:
        errors.append(
            f"步骤 '{name}' 的 'args' 字段已移除：业务输入请在 skill 内自包含配置承载（如 remote_info.txt），"
            f"框架只传基础上下文（cwd / change_name / change_path）"
        )
    if "run_mode" in value and stype != "skill":
        errors.append(f"步骤 '{name}' 是 reference 型（无独立执行主体概念），不支持 run_mode 字段")
    rm = value.get("run_mode")
    if rm is not None and rm not in ALLOWED_RUN_MODES:
        errors.append(f"步骤 '{name}' 的 run_mode='{rm}' 无效，必须是 {sorted(ALLOWED_RUN_MODES)} 之一")
    order = value.get("order")
    if order is not None and not isinstance(order, int):
        errors.append(f"步骤 '{name}' 的 order 必须是整数，实际为 {order!r}")
    depends_on = value.get("depends_on")
    if depends_on is not None and not isinstance(depends_on, list):
        errors.append(f"步骤 '{name}' 的 depends_on 必须是数组，实际为 {type(depends_on).__name__}")
    return errors


def validate_namespace(ns: Dict[str, Any], skill: str) -> List[str]:
    """
    Validate the whole skill namespace. Returns error messages.

    A skill's namespace may carry boolean switches for its OWN built-in steps
    (registered via BUILT_IN_STEPS_BY_SKILL). For skills with NO registered
    built-in steps, boolean keys are NOT validated as errors — the skill
    interprets its own switches (P3 generalization: each core-* registers its
    built-ins). Only registered built-in steps must be boolean.
    """
    errors = validate_builtin_keys(ns, skill)
    builtin_keys = {b["key"] for b in get_built_in_steps(skill)}
    for key, value in ns.items():
        if key in builtin_keys:
            continue
        if isinstance(value, bool):
            if not builtin_keys:
                # unregistered skill: boolean keys are its own switches
                continue
            # stray boolean for an unknown key -> warning-level; treat as error
            errors.append(f"配置键 '{key}' 不是内置步骤名（内置：{sorted(builtin_keys)}），布尔值仅允许用于内置步骤开关")
        else:
            errors.extend(validate_custom_step(key, value, skill))
