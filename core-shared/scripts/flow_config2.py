def _step_label(entry: Dict[str, Any]) -> str:
    """Human label for a steps entry."""
    md = entry.get("skill_md_step", entry.get("key", ""))
    desc = entry.get("description", "")
    return f"{md} {desc}".strip()


def _slot_label(slot: str, skill: str = "core-apply") -> str:
    """Human label for a slot, resolved per-skill (slots may collide across skills)."""
    return SLOT_LABELS.get(f"{skill}:{slot}", SLOT_LABELS.get(slot, slot))


def build_summary(plan: Dict[str, Any]) -> str:
    """
    Build a clean, sectioned confirmation summary for the plan.

    Sections:
      A. 主流程步骤 (steps in SKILL.md execution order, with enable/disable state)
      B. 编排点子环节 (non-empty slots only; empty slots are omitted for clarity)
      C. 已关闭 (disabled reasons; omitted when none)
    """
    lines: List[str] = []

    # A. main flow steps
    steps = plan.get("steps", [])
    lines.append("【主流程步骤】")
    for e in steps:
        if e.get("type") == "fixed":
            lines.append(f"  - {_step_label(e)}")
        elif e.get("enabled"):
            lines.append(f"  - {_step_label(e)} [已启用]")
        # closed built-in steps are reported in section C only
    if not steps:
        lines.append("  （无）")

    # B. orchestration sub-step slots (only non-empty ones)
    slots = plan.get("orchestration_points", {})
    active_slots = {s: entries for s, entries in slots.items() if entries}
    if active_slots:
        lines.append("【编排点子环节】")
        for slot in get_orchestration_points(plan.get("skill", "")):
            entries = active_slots.get(slot)
            if not entries:
                continue
            descs = []
            for e in entries:
                extra = f"（{e.get('run_mode', '')}）" if e.get("run_mode") else ""
                descs.append(f"{e.get('key')}{extra}")
            lines.append(f"  - {_slot_label(slot, plan.get('skill', 'core-apply'))}: {', '.join(descs)}")
    else:
        lines.append("【编排点子环节】")
        lines.append("  （无）")

    # C. closed steps (出厂默认关闭态不展示——用户未主动关闭，无需提示)
    user_closed = {
        key: info
        for key, info in plan.get("disabled", {}).items()
        if not info.get("default_disabled")
    }
    if user_closed:
        lines.append("【已关闭】")
        for key, info in user_closed.items():
            reason = info.get("reason", "")
            extra = f"（依赖 {info.get('dependency_of')}）" if info.get("dependency_of") else ""
            lines.append(f"  - {key}: {reason}{extra}")

    return "\n".join(lines)


def sync_skipped(project_root: str, skill: str, plan: Dict[str, Any]) -> Path:
    """Write skipped-<skill>.json same-source with the FINAL persisted plan."""
    skipped = build_skipped(plan)
    ctx_dir = get_flow_context_dir(project_root)
    ctx_dir.mkdir(parents=True, exist_ok=True)
    path = get_skipped_path(project_root, skill)
    path.write_text(
        json.dumps(skipped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def persist_plan(project_root: str, skill: str, plan: Dict[str, Any]) -> Path:
    ctx_dir = get_flow_context_dir(project_root)
    ctx_dir.mkdir(parents=True, exist_ok=True)
    path = get_plan_path(project_root, skill)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_plan(project_root: str, skill: str) -> Optional[Dict[str, Any]]:
    path = get_plan_path(project_root, skill)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# --init / --describe / --guide
# ---------------------------------------------------------------------------

TEMPLATE_JSONC = """// ============================================================
// CoreSpec 通用流程编排框架 - 全局配置（JSONC：支持 // 行注释）
// 位置：~/.corespec/flow-config.json
// 说明：顶层按 skill 名分组。每个 core-* skill 只解析自己的命名空间。
//       某 skill 对象不存在 = 该 skill 全默认（内置步骤全开，无自定义步骤）。
//       首次运行已自动生成本文件，无需修改 = 全默认；
//       修改后下次运行 core-* 自动生效（无需任何命令或确认）。
// 完整指南：~/.corespec/flow-config-guide.md（或 main.py flow-config --guide）
// ============================================================

{
  "core-apply": {
    // ---- 内置步骤开关（true/false）----
    "version_check": true,  // Step 1 版本检查
    "show_progress": false,  // Step 8 展示当前进度（默认关闭）
    "l4_review": true,      // Step 10 L4 实现追溯验证
    "code_review": true,    // Step 11 Code Review
    "unit_test": true,      // Step 12 单元测试（l5_coverage 依赖它，关闭则 L5 自动降级）
    "l5_coverage": true,     // Step 13 L5 UT 覆盖度验证
    "completion_report": true, // Step 14 完成或暂停时展示状态
    // ---- 自定义步骤示例（取消注释即启用；注意：最后一个有效键不可带尾逗号）----
    "judgment_ladder": {
      "type": "reference",
      "file": "references/judgment-ladder.md",
      "at": "pre-codegen"        // 编排点：pre-codegen / post-codegen / post-l4 / post-review / post-ut
    }
    // "compile": {
    //   "type": "skill",
    //   "skill": "my-compile-skill",
    //   "at": "post-codegen",
    //   "order": 1,
    //   "description": "编译项目代码"
    // },
    // "codebase_scan": {
    //   "type": "skill",
    //   "skill": "my-scan-skill",
    //   "at": "post-review",
    //   "run_mode": "subagent"     // direct（默认，当前会话）/ subagent（独立子代理）
    // }
  },
  // ---- 其他 core-* skill 的配置各自独立分组（未配置 = 全默认，互不影响）----
  // 启用时在上方 core-apply 对象闭合 '}' 后补逗号，例如：
  // "core-design": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,       // Phase 1 版本检查
  //   "fetch_rules": true,         // Phase 2 多语言规范获取（B 档：只控 code-rule 拉取，不控 design-principles/design-views GATE）
  //   "read_similar": true,        // Phase 5 读取相似需求参考归档
  //   "expert_experience": true,   // Phase 7 获取专家经验（paradigm-exp-use，纯增益）
  //   "design_traceability": true, // Phase 9 设计追溯验证（cross-doc-checker L2/L3，subagent 强制）
  //   "design_review": true,       // Phase 10 design-doc-reviewer 审查（subagent 强制）
  //   "cleanup": true              // Phase 11 清理临时文件
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-design 编排点）----
  //   // "team_design_rules": {
  //   //   "type": "reference",
  //   //   "file": "references/team-design-rules.md",
  //   //   "at": "pre-generate"    // 编排点：post-rule-fetch / post-gather-context / post-code-understanding / pre-generate / post-generate / post-traceability / post-design-review / post-cleanup
  //   // }
  // }
  // "core-init": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,        // Step 0 版本检查
  //   "okf_knowledge_fetch": false,  // Step 4 拉取产品知识中心代码仓（asset/ 扁平到 docs/knowledge/产品名/）
  //   "multi_analysis": true,       // Step 5 多仓依赖分析（subagent）
  //   "check_sync": true,           // Step 6a 同步必要性检查
  //   "execute_sync": true          // Step 6b 代码仓逆向文档获取（依赖 check_sync，关闭 check_sync 时同步跳过）
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-init 编排点）----
  //   // "spec_source": {
  //   //   "type": "reference",
  //   //   "file": "references/spec-source.md",
  //   //   "at": "pre-execute-sync"   // 编排点：post-init-structure / post-scan-language / post-multi-analysis / pre-execute-sync / post-execute-sync
  //   // }
  // }
  // "core-explore": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,      // Step 0 版本检查
  //   "req_refine": false,        // 阶段5.1.5 需求文档细化补全（默认关闭；启用后 step-4 解析设计文档自动降级、step-7 上下文补全读取源切到 refined 文档；产出 requirement.md + story.md 到 docs/.explore_context/req-refine/{需求ID}/；产出后下游 knowledge_precheck/brainstorming 自动豁免）
  //   "knowledge_precheck": true, // 阶段5.3 领域知识预澄清（双层语义：指令文件挂 ref_file 条件加载（references/knowledge-precheck.md），关闭时文件不加载、三条件检查点豁免；req_refine 产出时追加第四条件豁免）
  //   "brainstorming": true,      // 阶段5.4 需求澄清（双层语义：指令文件挂 ref_file 条件加载（references/requirement-clarification.md），关闭时文件不加载、七条件豁免、后处理降级；req_refine 产出时追加第八条件豁免）
  //   "find_similar": true,       // 阶段7 查找相似需求
  //   "l1_review": true,          // 阶段9 L1 需求完整性验证
  //   "explore_review": true,     // 阶段10 explore-doc-reviewer 审查
  //   "cleanup_temp": true        // 阶段11 清理临时文件
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-explore 编排点）----
  //   // "team_rules": {
  //   //   "type": "reference",
  //   //   "file": "references/team-rules.md",
  //   //   "at": "pre-proposal"    // 编排点：pre-clarification / post-clarification / pre-proposal / post-proposal / pre-delta-spec / post-delta-spec / post-l1 / post-review / post-cleanup
  //   // }
  // }
  // "core-archive": {
  //   // ---- 内置步骤开关（true/false）----
  //   "version_check": true,    // Step 1 版本检查
  //   "core_verify": true,      // Step 4 core-verify 归档前验证（subagent 强制，UNDER_IMPL 阻塞 / DOC_STALE 交反刷）；多仓 M-0 替代
  //   "check_artifacts": true,  // Step 5 检查 artifact 完成状态
  //   "check_tasks": true,      // Step 6 检查 task 完成状态 + 消费 skipped-core-apply.json
  //   "backfill": true,         // Step 9 代码反刷（backfill-from-code）；多仓 M-1 子代理并行替代
  //   "spec_sync": true,        // Step 10 delta 合并到全量文档；多仓 M-2 子代理并行替代
  //   "show_summary": true,     // Step 12 展示归档摘要
  //   "push_mr": true           // Step 13 core-auto-git 推送 + 建 MR；多仓 M-4 逐仓替代
  //   // ---- 自定义步骤示例（取消注释即启用；at 取 core-archive 编排点）----
  //   // "archive_hook": {
  //   //   "type": "reference",
  //   //   "file": "references/archive-hook.md",
  //   //   "at": "pre-archive"    // 编排点：pre-verify / post-verify / pre-backfill / post-backfill / pre-spec-sync / post-spec-sync / pre-archive / post-archive / pre-push / post-push
  //   // }
  // }

  // ---- 全局默认测试策略（顶层键，不属任何 skill 命名空间）----
  // core-init 生成项目 docs/config.yaml 时参考此值；用户后续改项目级
  // config.yaml 则以项目级为准（core-design 生成 tasks.md 时项目级优先）。
  "test_strategy": "test-after"   // tdd / test-after，缺省 test-after
}
"""

def _resolve_guide_source() -> Optional[Path]:
    """
    Resolve the GLOBAL shared guide source file (core-shared, framework-level).

    Resolution order:
      1. core-shared scripts dir (via core_paths) -> ../references/flow-config-guide.md
      2. this file's repo layout fallback (core-apply/../core-shared/references/...)
      3. this file's installed skill dir fallback (references/flow-config-guide.md,
         legacy per-skill copy — kept so older installs still work)
    """
    candidates: List[Path] = []
    try:
        from core_paths import get_core_shared_scripts_dir
        shared_scripts = get_core_shared_scripts_dir()
        if shared_scripts is not None:
            candidates.append(shared_scripts.parent / GUIDE_SOURCE_RELPATH)
    except Exception:
        pass
    # core-shared 自身 references（repo/install layout: <base>/skills/core-shared）
    here = Path(__file__).resolve().parent.parent  # <base>/skills/core-shared
    candidates.append(here.parent / "core-shared" / GUIDE_SOURCE_RELPATH)
    # legacy per-skill copy (this skill's own references/)
    candidates.append(here / GUIDE_SOURCE_RELPATH)
    for c in candidates:
        if c.exists():
            return c
    return None


def load_guide_text() -> Tuple[str, Optional[str]]:
    """
    Load the config guide text from the GLOBAL shared source file.

    Returns:
        (guide_text, error_message). error_message is None on success.
        The core-shared bundled file is the single source of truth; the
        user-level ~/.corespec/flow-config-guide.md is only a mirrored copy
        (synced on --init). All core-* skills read the same global source,
        so multiple skills syncing to the user path never collide.
    """
    source = _resolve_guide_source()
    if source is None:
        return "", "指南源文件缺失：core-shared references/flow-config-guide.md 未找到（请确认 core-shared 已安装）"
    try:
        text = source.read_text(encoding="utf-8")
        return text, None
    except Exception as e:
        return "", f"指南源文件不可读：{source}（{e}）"


def describe_schema(skill: str) -> Dict[str, Any]:
    """Build the --describe output for a skill namespace."""
    return {
        "skill": skill,
        "built_in_steps": [
            {
                "key": b["key"],
                "default": b["default"],
                "depends_on": b["depends_on"],
                "skill_md_step": b["skill_md_step"],
                "description": b["description"],
            }
            for b in get_built_in_steps(skill)
        ],
        "orchestration_points": get_orchestration_points(skill),
        "custom_step_schema": {
            "reference": {
                "required": REFERENCE_REQUIRED_FIELDS,
                "optional": ["order", "description", "depends_on", "dependency_type"],
            },
            "skill": {
                "required": SKILL_REQUIRED_FIELDS,
                "optional": ["order", "description", "depends_on", "dependency_type", "run_mode"],
            },
        },
        "run_modes": sorted(ALLOWED_RUN_MODES),
        "example": {
            "judgment_ladder": {
                "type": "reference",
                "file": "references/judgment-ladder.md",
                "at": "pre-codegen",
            },
            "compile": {
                "type": "skill",
                "skill": "my-compile-skill",
                "at": "post-codegen",
                "order": 1,
            },
        },
    }


# ---------------------------------------------------------------------------
# Main flow-config command
# ---------------------------------------------------------------------------

def cmd_flow_config(argv: Optional[List[str]] = None) -> int:
    """flow-config command entry. Always exits 0 for JSON content-based judgment."""
    parser = argparse.ArgumentParser(prog="flow-config", description="CoreSpec 通用流程编排配置")
    parser.add_argument("--skill", default="core-apply", help="skill 命名空间（默认 core-apply）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--describe", action="store_true", help="输出可用配置键/schema/默认值/示例")
    parser.add_argument("--init", action="store_true", help="生成带注释的 JSONC 模板")
    parser.add_argument("--guide", action="store_true", help="输出配置指南全文")
    parser.add_argument("--fragment", action="store_true", help="输出多仓执行计划片段（子代理输入文件）")
    parser.add_argument("--repo", default=None, help="多仓片段：仓名（--fragment 用）")
    parser.add_argument("--repo-cwd", default=None, help="多仓片段：仓目录绝对路径（--fragment 用）")
    parser.add_argument("--project-root", default=os.getcwd(), help="项目根目录")
    args = parser.parse_args(argv)

    if args.init:
        return run_init(args.skill)

    if args.guide:
        text, guide_err = load_guide_text()
        if guide_err:
            print(json.dumps({"ok": False, "error": guide_err}, ensure_ascii=False, indent=2))
        else:
            print(text)
        return 0

    if args.describe:
        out = describe_schema(args.skill)
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            for b in out["built_in_steps"]:
                print(f"  {b['key']}: default={b['default']}, {b['description']} ({b['skill_md_step']})")
            print("  orchestration_points:", ", ".join(out["orchestration_points"]))
        return 0

    if args.fragment:
        return run_fragment(args.skill, args.repo, args.repo_cwd, args.project_root, args.json)

    return run_build(args.skill, args.project_root, args.json)


def run_init(skill: str = "core-apply") -> int:
    """Generate the config template, or APPEND a missing <skill> namespace.

    File absent  -> write the full TEMPLATE_JSONC (never touches an existing
                    file's configured content).
    File exists + --skill namespace ABSENT -> extract the namespace block from
                    TEMPLATE_JSONC (comments stripped) and append it before the
                    top-level closing brace. Existing namespaces/keys are left
                    untouched (no-overwrite protection preserved).
    File exists + namespace present -> no-op (idempotent), message only.

    This closes the ns_missing first-contact gap: a user whose config file was
    created by ANOTHER skill's --init (e.g. core-apply) previously got a
    "generate template" offer that could not actually add this skill's
    namespace (file existed -> '未覆盖' no-op), forcing manual edits.
    """
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raw = path.read_text(encoding="utf-8")
        if _find_skill_block(raw, skill) is not None:
            print(f"配置文件已存在：{path}（{skill} 命名空间已存在，未覆盖）")
        else:
            block = _extract_skill_block_from_template(skill)
            if block is None:
                print(f"模板中无 {skill} 命名空间示例块（已存在文件未改动）")
            else:
                close_idx = _find_top_level_close(raw)
                if close_idx is None:
                    print(f"配置文件格式异常（未找到顶层闭合 '}}'）：{path}（已存在文件未改动）")
                else:
                    raw = _ensure_comma_before_close(raw)
                    close_idx = _find_top_level_close(raw)
                    # insert the extracted block before the top-level closing
                    # brace, keeping its template indentation
                    new_block = block if block.endswith("\n") else block + "\n"
                    new_text = raw[:close_idx] + new_block + raw[close_idx:]
                    path.write_text(new_text, encoding="utf-8")
                    print(f"已追加 {skill} 命名空间到：{path}")
    else:
        path.write_text(TEMPLATE_JSONC, encoding="utf-8")
        print(f"已生成配置模板：{path}")
    # mirror the bundled guide to the user-level directory (idempotent overwrite)
    text, guide_err = load_guide_text()
    if guide_err:
        print(guide_err)
    else:
        guide_path = get_guide_path()
        guide_path.parent.mkdir(parents=True, exist_ok=True)
        guide_path.write_text(text, encoding="utf-8")
        print(f"已同步配置指南：{guide_path}")
    return 0


def run_build(skill: str, project_root: str, json_output: bool) -> int:
    """Build-plan primary call: the config file is the single source of truth.

    Mirrors the template customization model (~/.corespec/flow-config.json is
    to flow-config what the L2 templates dir is to core_templates):
      - file absent / skill namespace absent -> silently initialize the config
        (idempotent run_init, stdout suppressed) and set `config_initialized`
        in the JSON result so the skill can notify the user ONCE in its final
        summary; plan is built from the freshly generated (all-default) config
        and takes effect immediately — NO interactive confirmation.
      - user edited the config -> plan is rebuilt from the new config and
        takes effect immediately (config edit IS the intent).
      - broken/invalid config -> the ONLY interception: fail loudly (ok=false)
        and keep the existing plan untouched so the user can repair the file.
    """
    config, config_err = load_config()
    if config_err:
        # A broken config file must NOT be silently degraded to the all-default
        # plan (2026-09-21-2nd-session: a dangling trailing comma from an older
        # write-back made load_config fail; run_build then treated the file as
        # absent and OVERWROTE the persisted plan with an all-default one).
        # Fail loudly and keep the existing plan untouched so the user can
        # repair the config source.
        if json_output:
            print(json.dumps({"ok": False, "error": config_err}, ensure_ascii=False, indent=2))
        else:
            print(f"Error: {config_err}")
        return 0

    # Silent auto-initialization: file absent OR this skill's namespace absent.
    # Both are "first contact for this skill" — instead of an interactive
    # AskUserQuestion, generate/append the JSONC template (idempotent) so the
    # user can later customize by editing the file. Best-effort: on failure we
    # still proceed with the all-default plan (no config = full defaults).
    config_initialized = False
    if config is None or skill not in config:
        try:
            import contextlib
            import io

            with contextlib.redirect_stdout(io.StringIO()):
                run_init(skill=skill)
            config_initialized = True
            # reload so the plan below is built from the newly generated config
            config, config_err = load_config()
            if config_err is None and isinstance(config, dict) and skill in config:
                try:
                    ns = get_skill_namespace(config, skill)
                except ValueError:
                    ns = None
            else:
                ns = None
        except Exception:
            # auto-init is best-effort — must never block the plan build
            ns = None

    ns = None
    if config is not None:
        try:
            ns = get_skill_namespace(config, skill)
        except ValueError as e:
            if json_output:
                print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
            else:
                print(f"Error: {e}")
            return 0

    if config is not None and ns is not None:
        ns_errors = validate_namespace(ns, skill)
        if ns_errors:
            if json_output:
                print(json.dumps({"ok": False, "errors": ns_errors}, ensure_ascii=False, indent=2))
            else:
                print("配置校验失败：")
                for e in ns_errors:
                    print(f"  - {e}")
            return 0

    plan = build_execution_plan(skill, ns)
    consistency_errors = consistency_check(plan)
    if consistency_errors:
        if json_output:
            print(json.dumps({"ok": False, "errors": consistency_errors}, ensure_ascii=False, indent=2))
        else:
            print("一致性契约校验失败：")
            for e in consistency_errors:
                print(f"  - {e}")
        return 0

    plan_path = get_plan_path(project_root, skill)
    all_default = is_all_default_plan(plan)

    # persist (fingerprint is a persist-skip optimization only, no behavioral
    # semantics: any config edit rebuilds and re-persists the plan silently)
    fingerprint = canonical_fingerprint(ns) if ns is not None else None
    plan["_fingerprint"] = fingerprint if fingerprint is not None else canonical_fingerprint({})
    persist_plan(project_root, skill, plan)
    skipped_path = sync_skipped(project_root, skill, plan)

    # Auto-initialize user-level templates (L2) if absent — non-interactive,
    # no user confirmation needed. Any core-* skill running flow-config gets
    # the default builtin templates copied to ~/.corespec/core-schemas/spec-driven/
    # templates/ + the template-guide.md mirrored. If the directory already
    # exists (user has customized or a prior skill already initialized), skip.
    # stdout is suppressed so init's informational prints (e.g. guide sync
    # path) do not pollute the JSON output that callers parse from stdout.
    # When auto-init actually copies templates (first run), a
    # `template_initialized` flag is set in the JSON result so the skill can
    # proactively notify the user about the guide location. This ensures
    # discoverability even when the step that owns the template-maintenance
    # reference (e.g. execute-sync.md) is disabled and never loaded.
    template_initialized = False
    try:
        import contextlib
        import io
        from core_templates import TemplateCLI, DEFAULT_SCHEMA  # lazy import

        user_templates_dir = (
            Path.home() / ".corespec" / "core-schemas" / DEFAULT_SCHEMA / "templates"
        )
        if not user_templates_dir.exists():
            with contextlib.redirect_stdout(io.StringIO()):
                TemplateCLI.init()
            template_initialized = True
    except Exception:
        # Template init is best-effort — must never block the plan build.
        # Failures (e.g. builtin templates not found in dev env) are silently
        # ignored; the L1 builtin layer still serves templates at runtime.
        pass

    result = {
        "ok": True,
        "skill": skill,
        "all_default": all_default,
        "config_initialized": config_initialized,
        "plan_path": str(plan_path),
        "skipped_path": str(skipped_path),
        "summary": build_summary(plan),
        "plan": plan,
        "active_orchestration_entries": list_active_custom_steps(skill, plan),
        "commented_custom_steps": list_commented_custom_steps(skill),
        "template_initialized": template_initialized,
    }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"skill={skill} plan={plan_path} skipped={skipped_path}")
    return 0


def run_fragment(
    skill: str,
    repo: Optional[str],
    repo_cwd: Optional[str],
    project_root: str,
    json_output: bool,
) -> int:
    """
    Build the per-repo execution plan fragment (multi-repo subagent input file).

    Loads the persisted execution plan (execution-plan-<skill>.json at project
    root — ALL repos share this SAME plan) and copies its orchestration_points
    zone (custom steps already routed to their slots at build time).

    Fragment shape (common-plan-arch.md §9.3):
      {repo, repo_cwd, plan_path, orchestration_points: {<slot>: [entries]}}
    Five slots: pre-codegen / post-codegen / post-l4 / post-review / post-ut.

    The fragment is ALWAYS written to
    docs/.flow_context/execution-plan-fragment-<skill>-<repo>.json
    (--fragment's primary behavior is generating the subagent input file).
    --json additionally prints the same JSON to stdout (for JSON
    content-based judgment); the written file is authoritative.
    """
    plan_path = get_plan_path(project_root, skill)
    plan = load_plan(project_root, skill)
    if plan is None:
        err = {"ok": False, "error": f"执行计划不存在：{plan_path}（先运行 flow-config --json --skill {skill}）"}
        if json_output:
            print(json.dumps(err, ensure_ascii=False, indent=2))
        else:
            print(err["error"])
        return 0

    if not repo or not repo_cwd:
        err = {"ok": False, "error": "--fragment 需要 --repo（仓名）与 --repo-cwd（仓目录绝对路径）"}
        if json_output:
            print(json.dumps(err, ensure_ascii=False, indent=2))
        else:
            print(err["error"])
        return 0

    # orchestration_points zone already holds the slot-routed custom entries
    slots = {
        p: list(plan.get("orchestration_points", {}).get(p, []))
        for p in get_orchestration_points(skill)
    }

    fragment = {
        "repo": repo,
        "repo_cwd": repo_cwd,
        "plan_path": str(plan_path),
        "orchestration_points": slots,
    }

    # ALWAYS write the fragment file (--fragment's primary behavior is
    # generating the subagent input file). --json only additionally mirrors
    # the same JSON to stdout for content-based judgment.
    ctx_dir = get_flow_context_dir(project_root)
    ctx_dir.mkdir(parents=True, exist_ok=True)
    out_path = ctx_dir / f"execution-plan-fragment-{skill}-{repo}.json"
    out_path.write_text(json.dumps(fragment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if json_output:
        print(json.dumps(fragment, ensure_ascii=False, indent=2))
    else:
        print(f"片段已写入：{out_path}")
    return 0


def main() -> int:
    return cmd_flow_config()


if __name__ == "__main__":
    sys.exit(main())
